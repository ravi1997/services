from flask import request, jsonify, current_app
from functools import wraps
import logging

def require_bearer_and_log(route_func):
    @wraps(route_func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger('access_logger')
        auth_header = request.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
        expected_token = current_app.config.get('SMS_API_KEY', 'your-sms-api-key')
        if not token or token != expected_token:
            logger.warning(f"Unauthorized access attempt to {request.path} from {request.remote_addr}")
            # Return plain dict so Flask-RESTX handles JSON serialization cleanly
            return {'error': 'Unauthorized'}, 401
        logger.info(f"Authorized access to {request.path} from {request.remote_addr}")
        return route_func(*args, **kwargs)
    return wrapper

def require_admin_bearer_and_log(route_func):
    @wraps(route_func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger('access_logger')
        auth_header = request.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
        expected_token = current_app.config.get('ADMIN_API_KEY', 'your-admin-api-key')
        if not token or token != expected_token:
            logger.warning(f"Unauthorized admin access attempt to {request.path} from {request.remote_addr}")
            return {'error': 'Unauthorized'}, 401
        logger.info(f"Admin access to {request.path} from {request.remote_addr}")
        return route_func(*args, **kwargs)
    return wrapper
