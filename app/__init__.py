
"""Application factory for the SMS service (trimmed and focused)."""

# --- Imports ---
import os
from flask import Flask
from flask_cors import CORS
from app.routes.v1 import sms_bp
from app.extensions import db, limiter

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
    # Relax/disable certain integrations during testing
    if app.config.get('TESTING'):
        app.config['RATELIMIT_ENABLED'] = False

    # CORS
    CORS(app)

    # Rate limiter using shared instance
    # Defaults picked from config: RATELIMIT_STORAGE_URI, RATELIMIT_DEFAULT
    limiter.init_app(app)

    # Database
    db.init_app(app)
    app.db = db

    # Celery scaffolding removed for a leaner core; tasks can still be queued
    # via Celery's default app in production if configured globally.

    # Minimal setup only; removed custom file loggers and log-cleanup endpoints

    # --- Health Check Endpoint ---
    @app.route('/health', methods=['GET'])
    def health():
        return {"status": "ok"}, 200

    # Metrics endpoint removed for minimal footprint; re-add if needed.

    # Removed duplicate task-status route; it's available under the blueprint

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
