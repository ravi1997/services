from flask import Blueprint, request
from app.utils.response import success, error

cdac_bp = Blueprint('cdac', __name__)


@cdac_bp.route('/health', methods=['GET'])
def cdac_health():
    return success("CDAC service is healthy", {"health": "healthy"})


@cdac_bp.route('/fetch', methods=['POST'])
def cdac_fetch():
    payload = request.get_json(silent=True) or {}
    req_id = payload.get('request_id')
    if not req_id:
        return error("Failed to fetch CDAC data", "CDAC_SERVICE_ERROR", 400)
    # Mocked response
    info = {"name": "John Doe", "age": 30, "request_id": req_id}
    return success("CDAC data fetched successfully", {"cdac_info": info})


@cdac_bp.route('/bulk_fetch', methods=['POST'])
def cdac_bulk_fetch():
    payload = request.get_json(silent=True) or {}
    req_ids = payload.get('request_ids')
    if not isinstance(req_ids, list) or not req_ids:
        return error("Failed to fetch CDAC bulk data", "CDAC_SERVICE_ERROR", 400)
    infos = []
    for r in req_ids:
        infos.append({"name": "John Doe" if len(str(r)) % 2 == 0 else "Jane Smith", "age": 30 if len(str(r)) % 2 == 0 else 25, "request_id": r})
    return success("CDAC bulk data fetched successfully", {"cdac_info": infos})

