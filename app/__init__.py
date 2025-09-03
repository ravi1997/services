
"""Application factory and infrastructure wiring."""

# --- Imports ---
import os
import glob
import time
import logging
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from flask import Flask, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery import Celery
from app.routes.v1 import sms_bp
from app.config import Config
from app.utils.logging_utils import JsonFormatter, json_extra
from flask_sqlalchemy import SQLAlchemy
from app.extensions import db
import uuid
import warnings
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
except ImportError:  # pragma: no cover
    trace = None
    TracerProvider = None
    FlaskInstrumentor = None

# --- App Factory ---
def create_app(config_class=None):
    """Flask application factory."""
    app = Flask(__name__)

    # Select config
    if not config_class:
        from app.config import DevelopmentConfig, ProductionConfig
        env = os.getenv('APP_ENV', 'development').lower()
        config_class = ProductionConfig if env == 'production' else DevelopmentConfig
    app.config.from_object(config_class)

    # CORS
    CORS(app)

    # Tracing
    tracing_enabled = app.config.get('TRACE_ENABLED', True) and not app.config.get('TESTING')
    tracer = None
    if tracing_enabled and TracerProvider and trace and FlaskInstrumentor:
        try:
            provider = TracerProvider()
            # Use SimpleSpanProcessor to reduce shutdown race issues seen with Batch + Console in tests
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
            trace.set_tracer_provider(provider)
            FlaskInstrumentor().instrument_app(app)
            tracer = trace.get_tracer(__name__)
        except Exception as _te:  # pragma: no cover
            app.logger.warning(f"Tracing init failed: {_te}")

    # Suppress known third-party deprecation warning (jsonschema RefResolver)
    warnings.filterwarnings('ignore', category=DeprecationWarning, message='jsonschema.RefResolver is deprecated')
    warnings.filterwarnings('ignore', category=DeprecationWarning, message='.*RefResolver.*')

    # Rate limiter with storage
    limiter = Limiter(key_func=get_remote_address,
                      default_limits=[app.config.get('DEFAULT_RATE_LIMIT', '10 per minute')],
                      storage_uri=app.config.get('RATELIMIT_STORAGE_URI'))
    limiter.init_app(app)
    app.limiter = limiter

    # Database
    db.init_app(app)
    app.db = db

    # Celery wiring
    def make_celery(flask_app):
        celery = Celery(flask_app.import_name, broker=flask_app.config.get('CELERY_BROKER_URL'))
        celery.conf.update(flask_app.config)

        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with flask_app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask
        return celery

    app.celery = make_celery(app)

    # Logging setup (JSON optional)
    json_logs = app.config.get('JSON_LOGS', True)

    def build_handler(path):
        handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3)
        if json_logs:
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(name)s %(module)s: %(message)s'))
        return handler

    app_logger = logging.getLogger('app_logger'); app_logger.setLevel(logging.INFO); app_logger.addHandler(build_handler('logs/app.log')); app_logger.propagate = False
    error_logger = logging.getLogger('error_logger'); error_logger.setLevel(logging.ERROR); error_logger.addHandler(build_handler('logs/error.log')); error_logger.propagate = False
    access_logger = logging.getLogger('access_logger'); access_logger.setLevel(logging.INFO); access_logger.addHandler(build_handler('logs/access.log')); access_logger.propagate = False

    # --- Log Cleanup Utility ---
    def delete_old_logs():
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
        retention_months = app.config.get('LOG_RETENTION_MONTHS', 8)
        cutoff_date = datetime.now() - timedelta(days=retention_months * 30)
        deleted = []
        for log_file in glob.glob(os.path.join(log_dir, '*.log')):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
                if mtime < cutoff_date:
                    os.remove(log_file)
                    deleted.append(os.path.basename(log_file))
            except Exception as e:
                app.logger.error(f"Failed to delete log {log_file}: {e}")
        return deleted

    # Call log cleanup at startup
    delete_old_logs()


    # --- Request/Response Logging with Masking ---
    def mask_sensitive(data):
        if isinstance(data, dict):
            masked = {}
            for k, v in data.items():
                if 'key' in k.lower() or 'token' in k.lower() or 'password' in k.lower():
                    masked[k] = '***MASKED***'
                else:
                    masked[k] = v
            return masked
        return data

    @app.before_request
    def log_request():
        request._start_time = time.time()
        # Correlation / Request ID
        corr_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        request.correlation_id = corr_id
        body = mask_sensitive(request.get_json(silent=True) or {})
        access_logger.info('request', extra=json_extra(event='request', correlation_id=corr_id, ip=request.remote_addr, method=request.method, path=request.path, body=body))

    @app.after_request
    def log_response(response):
        try:
            resp_data = response.get_json() if response.is_json else response.data.decode()[:500]
        except Exception:
            resp_data = '<non-json>'
        duration = None
        if hasattr(request, '_start_time'):
            duration = round((time.time() - request._start_time) * 1000, 2)
        corr_id = getattr(request, 'correlation_id', None)
        if corr_id:
            response.headers['X-Request-ID'] = corr_id
        access_logger.info('response', extra=json_extra(event='response', correlation_id=corr_id, ip=request.remote_addr, method=request.method, path=request.path, status=response.status_code, duration_ms=duration, body=mask_sensitive(resp_data)))
        return response

    @app.errorhandler(Exception)
    def handle_exception(e):
        corr_id = getattr(request, 'correlation_id', None)
        error_logger.error(f"Exception: {e}", exc_info=True, extra=json_extra(correlation_id=corr_id, event='error'))
        return {"error": str(e), "correlation_id": corr_id}, 500


    # --- Log Cleanup Endpoint ---
    @app.route('/api/v1/logs/cleanup', methods=['POST'])
    @limiter.limit("2 per minute")
    def cleanup_logs():
        deleted = delete_old_logs()
        return {"deleted_logs": deleted, "message": f"Deleted {len(deleted)} log(s) older than {app.config.get('LOG_RETENTION_MONTHS', 8)} months."}, 200

    # --- Health Check Endpoint ---
    @app.route('/health', methods=['GET'])
    def health():
        return {"status": "ok"}, 200

    # Celery task status core endpoint
    from celery.result import AsyncResult

    @app.route('/api/v1/sms/tasks/<task_id>', methods=['GET'])
    def task_status(task_id):
        result = AsyncResult(task_id, app=app.celery)
        response = {'task_id': task_id, 'state': result.state}
        if result.successful():
            response['result'] = result.result
        elif result.failed():
            response['error'] = str(result.result)
        return response, 200

    # --- Register Blueprints (API Versioning) ---
    app.register_blueprint(sms_bp, url_prefix='/api/v1/sms')
    try:
        from app.tasks import sms_tasks  # noqa: F401
    except Exception as e:  # pragma: no cover
        app.logger.error(f"Failed to load tasks: {e}")
    # Create tables if not exist
    with app.app_context():
        from app.models.sms_message import SMSMessage  # noqa: F401
        db.create_all()
    return app
