from flask import request, current_app
from functools import wraps
import logging
from app.utils.response import error

def require_bearer_and_log(route_func):
    @wraps(route_func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger('access_logger')
        audit_logger = logging.getLogger('audit_logger')
        
        # Determine if this is an SMS endpoint to apply specific rate limits
        is_single_sms = request.path.endswith('/single') and 'sms' in request.path
        is_bulk_sms = request.path.endswith('/bulk') and 'sms' in request.path
        is_health_sms = request.path.endswith('/health') and 'sms' in request.path
        
        # SMS-specific rate limiting
        if is_single_sms:
            # Single SMS: 200 per minute
            limit = 200
        elif is_bulk_sms:
            # Bulk SMS: 10 per minute
            limit = 10
        elif is_health_sms:
            # Health check: 5 per minute
            limit = 5
        else:
            # Default rate limit for other endpoints
            limit = 10
        
        # Rate limiting (simple in-memory, per IP)
        ip = request.remote_addr
        if not hasattr(current_app, 'rate_limit'): current_app.rate_limit = {}
        from time import time
        now = time()
        window = 60  # 1 minute window
        rl = current_app.rate_limit.setdefault(ip, [])
        rl[:] = [t for t in rl if now-t < window]
        if len(rl) >= limit:
            logger.warning(f"Rate limit exceeded for {ip} on {request.path} (limit: {limit})")
            audit_logger.warning(f"Rate limit exceeded: ip={ip}, path={request.path}, user_agent={request.headers.get('User-Agent')}")
            return error("Rate limit exceeded", "RATE_LIMIT", 429)
        rl.append(now)

        # Token validation
        auth_header = request.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
        # Require config value, no fallback
        expected_token = current_app.config.get('SMS_API_KEY')
        if not expected_token:
            logger.error("Missing SMS_API_KEY in config")
            return error("Server misconfiguration", "SERVER_ERROR", 500)
        # Token format validation (simple: length, chars, not default)
        import re
        if not token or not re.match(r'^[A-Za-z0-9\-_.]{16,}$', token):
            logger.warning(f"Malformed token for {ip} on {request.path}")
            audit_logger.warning(f"Malformed token: ip={ip}, path={request.path}, token={token}")
            return error("Malformed token", "UNAUTHORIZED", 401)
        # Replay protection (simple: nonce in token, not reused)
        nonce = request.headers.get('X-Nonce')
        if nonce:
            if not hasattr(current_app, 'used_nonces'): current_app.used_nonces = set()
            if nonce in current_app.used_nonces:
                logger.warning(f"Replay attack detected for {ip} nonce={nonce}")
                audit_logger.warning(f"Replay attack: ip={ip}, nonce={nonce}, path={request.path}")
                return error("Replay detected", "REPLAY_ATTACK", 403)
            current_app.used_nonces.add(nonce)
        # RBAC (simple: X-Role header)
        role = request.headers.get('X-Role', 'user')
        allowed_roles = current_app.config.get('ALLOWED_ROLES', ['user', 'admin'])
        if role not in allowed_roles:
            logger.warning(f"RBAC denied for {ip} role={role} on {request.path}")
            audit_logger.warning(f"RBAC denied: ip={ip}, role={role}, path={request.path}")
            return error("Forbidden", "FORBIDDEN", 403)
        # API key check
        if token != expected_token:
            logger.warning(f"Unauthorized access attempt to {request.path} from {ip}")
            audit_logger.warning(f"Unauthorized: ip={ip}, path={request.path}, token={token}")
            return error("Unauthorized", "UNAUTHORIZED", 401)
        # Log request metadata
        logger.info(f"Authorized access to {request.path} from {ip} user_agent={request.headers.get('User-Agent')} role={role}")
        audit_logger.info(f"Access granted: ip={ip}, path={request.path}, user_agent={request.headers.get('User-Agent')}, role={role}, nonce={nonce}")
        return route_func(*args, **kwargs)
    return wrapper

def require_admin_bearer_and_log(route_func):
    @wraps(route_func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger('access_logger')
        audit_logger = logging.getLogger('audit_logger')
        ip = request.remote_addr
        # Admin rate limiting (per IP, 5 requests/minute)
        if not hasattr(current_app, 'admin_rate_limit'): current_app.admin_rate_limit = {}
        from time import time
        now = time()
        window = 60
        limit = 5
        rl = current_app.admin_rate_limit.setdefault(ip, [])
        rl[:] = [t for t in rl if now-t < window]
        if len(rl) >= limit:
            logger.warning(f"Admin rate limit exceeded for {ip} on {request.path}")
            audit_logger.warning(f"Admin rate limit exceeded: ip={ip}, path={request.path}, user_agent={request.headers.get('User-Agent')}")
            return error("Rate limit exceeded", "RATE_LIMIT", 429)
        rl.append(now)

        # Token validation
        auth_header = request.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
        expected_token = current_app.config.get('ADMIN_API_KEY')
        if not expected_token:
            logger.error("Missing ADMIN_API_KEY in config")
            return error("Server misconfiguration", "SERVER_ERROR", 500)
        import re
        if not token or not re.match(r'^[A-Za-z0-9\-_.]{16,}$', token):
            logger.warning(f"Malformed admin token for {ip} on {request.path}")
            audit_logger.warning(f"Malformed admin token: ip={ip}, path={request.path}, token={token}")
            return error("Malformed token", "UNAUTHORIZED", 401)
        # Replay protection
        nonce = request.headers.get('X-Nonce')
        if nonce:
            if not hasattr(current_app, 'used_admin_nonces'): current_app.used_admin_nonces = set()
            if nonce in current_app.used_admin_nonces:
                logger.warning(f"Admin replay attack detected for {ip} nonce={nonce}")
                audit_logger.warning(f"Admin replay attack: ip={ip}, nonce={nonce}, path={request.path}")
                return error("Replay detected", "REPLAY_ATTACK", 403)
            current_app.used_admin_nonces.add(nonce)
        # RBAC (require admin role)
        role = request.headers.get('X-Role', 'user')
        if role != 'admin':
            logger.warning(f"RBAC denied for {ip} role={role} on {request.path}")
            audit_logger.warning(f"RBAC denied: ip={ip}, role={role}, path={request.path}")
            return error("Forbidden", "FORBIDDEN", 403)
        if token != expected_token:
            logger.warning(f"Unauthorized admin access attempt to {request.path} from {ip}")
            audit_logger.warning(f"Unauthorized admin: ip={ip}, path={request.path}, token={token}")
            return error("Unauthorized", "UNAUTHORIZED", 401)
        # Log request metadata and audit
        logger.info(f"Admin access to {request.path} from {ip} user_agent={request.headers.get('User-Agent')} role={role}")
        audit_logger.info(f"Admin access granted: ip={ip}, path={request.path}, user_agent={request.headers.get('User-Agent')}, role={role}, nonce={nonce}")
        return route_func(*args, **kwargs)
    return wrapper