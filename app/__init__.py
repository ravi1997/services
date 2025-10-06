
"""Application factory with full feature set (DB, logging, metrics, tracing, admin)."""

import os
from flask import Flask, request, g
from flask_cors import CORS
from app.routes.v1 import sms_bp, cdac_bp, mail_bp, ehospital_bp
from app.routes.v1.sms_admin_routes import sms_admin_bp
from app.routes.v1.email_admin_routes import email_admin_bp
from app.routes.v1.maintenance_routes import maintenance_bp
from app.extensions import db, limiter, init_logging
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import logging
import uuid
from celery import Celery


def create_app(config_class=None):
    app = Flask(__name__)

    # Basic config selection (kept simple)
    if not config_class:
        from app.config import DevelopmentConfig, ProductionConfig
        env = os.getenv('APP_ENV', 'development').lower()
        config_class = ProductionConfig if env == 'production' else DevelopmentConfig
    app.config.from_object(config_class)

    # Custom CORS handling for IP range
    @app.after_request
    def after_request(response):
        # Check if the request is from an allowed IP range
        client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
        if client_ip.startswith('192.168.14.'):
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Request-ID,Idempotency-Key,X-Nonce,X-Role')
            response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response

    # Logging
    init_logging(json_logs=False)

    # Correlation / request ID
    @app.before_request
    def assign_request_id():
        rid = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        g.request_id = rid

    @app.after_request
    def add_request_id(resp):
        rid = getattr(g, 'request_id', None)
        if rid:
            resp.headers['X-Request-ID'] = rid
        return resp

    # Rate Limiter
    limiter.init_app(app)
    app.limiter = limiter

    # Database
    db.init_app(app)
    with app.app_context():
        db.create_all()

    # Celery (full) if broker configured
    broker_url = app.config.get('CELERY_BROKER_URL') or os.getenv('CELERY_BROKER_URL')
    backend_url = app.config.get('CELERY_RESULT_BACKEND') or os.getenv('CELERY_RESULT_BACKEND')
    if broker_url:
        celery = Celery(app.import_name, broker=broker_url, backend=backend_url)
        celery.conf.update(task_always_eager=app.config.get('TESTING', False))
        app.celery = celery
    from app.tasks.sms_tasks import send_and_record  # noqa: F401

    # Core health endpoint (global)
    @app.get('/health')
    def health():
        return {"status": "ok"}, 200

    # Metrics endpoint
    @app.get('/metrics')
    def metrics():
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

    # Register blueprints/endpoints
    app.register_blueprint(sms_bp, url_prefix='/services/api/v1/sms')
    app.register_blueprint(cdac_bp, url_prefix='/services/api/v1/cdac')
    app.register_blueprint(mail_bp, url_prefix='/services/api/v1/mail')
    app.register_blueprint(ehospital_bp, url_prefix='/services/api/v1/ehospital')
    app.register_blueprint(sms_admin_bp, url_prefix='/services/api/v1/sms')
    app.register_blueprint(email_admin_bp, url_prefix='/services/api/v1/mail')
    app.register_blueprint(maintenance_bp, url_prefix='/services/api/v1')

    # Log app initialization
    app.logger.info("Application factory completed initialization")
    
    return app
