from app.utils.cdac_service import cdac_service
from flask import Blueprint, request, g, current_app
from app.utils.response import success, error
from app.utils.decorators import require_bearer_and_log
import re
import time
import logging

def validate_emp_id(emp_id):
    # Only allow alphanumeric, length 5-12
    return bool(re.match(r'^[A-Za-z0-9]{5,12}$', str(emp_id)))

def validate_bulk_ids(ids):
    return isinstance(ids, list) and all(validate_emp_id(i) for i in ids)

cdac_bp = Blueprint('cdac', __name__)

# Simple in-memory rate limit store (per IP)
RATE_LIMIT = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 30    # max requests per window

def check_rate_limit(ip):
    now = int(time.time())
    window = now // RATE_LIMIT_WINDOW
    key = f"{ip}:{window}"
    count = RATE_LIMIT.get(key, 0)
    if count >= RATE_LIMIT_MAX:
        return False
    RATE_LIMIT[key] = count + 1
    return True

def audit_log(action, user=None, details=None):
    logger = logging.getLogger('audit_logger')
    logger.info(f"action={action} user={user} details={details}")


@cdac_bp.route('/health', methods=['GET'])
def cdac_health():
    ip = request.remote_addr
    if not check_rate_limit(ip):
        audit_log("rate_limit_exceeded", user=ip, details="health endpoint")
        return error("Rate limit exceeded", "RATE_LIMIT", 429)
    if isinstance(cdac_service('E1902460'), str):
        audit_log("service_unhealthy", user=ip)
        return error("CDAC service is unhealthy", "CDAC_SERVICE_UNHEALTHY", 503)
    audit_log("health_check", user=ip)
    return success("CDAC service is healthy", {"health": "healthy"})


@cdac_bp.route('/single', methods=['POST'])
@require_bearer_and_log
def cdac_fetch():
    ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    if not check_rate_limit(ip):
        audit_log("rate_limit_exceeded", user=ip, details="single endpoint")
        return error("Rate limit exceeded", "RATE_LIMIT", 429)
    payload = request.get_json(silent=True) or {}
    req_id = payload.get('request_id')
    if not req_id or not validate_emp_id(req_id):
        audit_log("invalid_input", user=ip, details={"request_id": req_id})
        return error("Invalid or missing request_id", "INVALID_INPUT", 400)
    # RBAC: Example, only allow users with role 'user' or 'admin' (expand as needed)
    role = request.headers.get('X-Role', 'user')
    if role not in ['user', 'admin']:
        audit_log("rbac_denied", user=ip, details={"role": role})
        return error("Forbidden: insufficient role", "FORBIDDEN", 403)
    try:
        info = cdac_service(req_id)
        if not isinstance(info, dict) or "Data" not in info or not info["Data"]:
            audit_log("service_error", user=ip, details={"request_id": req_id})
            return error("Failed to fetch CDAC data", "CDAC_SERVICE_ERROR", 400)
        audit_log("fetch_single", user=ip, details={"request_id": req_id, "role": role})
        return success("CDAC data fetched successfully", info["Data"][0])
    except Exception as ex:
        audit_log("exception", user=ip, details=str(ex))
        return error("Internal server error", "INTERNAL_ERROR", 500)


@cdac_bp.route('/bulk', methods=['POST'])
@require_bearer_and_log
def cdac_bulk_fetch():
    ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    if not check_rate_limit(ip):
        audit_log("rate_limit_exceeded", user=ip, details="bulk endpoint")
        return error("Rate limit exceeded", "RATE_LIMIT", 429)
    payload = request.get_json(silent=True) or {}
    req_ids = payload.get('request_ids')
    if not validate_bulk_ids(req_ids):
        audit_log("invalid_input", user=ip, details={"request_ids": req_ids})
        return error("Invalid or missing request_ids", "INVALID_INPUT", 400)
    role = request.headers.get('X-Role', 'user')
    if role not in ['admin']:
        audit_log("rbac_denied", user=ip, details={"role": role})
        return error("Forbidden: insufficient role", "FORBIDDEN", 403)
    infos = []
    try:
        for r in req_ids:
            info = cdac_service(r)
            if not isinstance(info, dict) or "Data" not in info or not info["Data"]:
                continue
            infos.append(info["Data"][0])
        if not infos:
            audit_log("service_error", user=ip, details={"request_ids": req_ids})
            return error("Failed to fetch any CDAC bulk data", "CDAC_SERVICE_ERROR", 400)
        audit_log("fetch_bulk", user=ip, details={"request_ids": req_ids, "role": role})
        return success("CDAC bulk data fetched successfully", {"cdac_info": infos})
    except Exception as ex:
        audit_log("exception", user=ip, details=str(ex))
        return error("Internal server error", "INTERNAL_ERROR", 500)