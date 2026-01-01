from flask import Blueprint, request,current_app
from app.utils.ehospital_service import send_ehospital_uhid
from app.utils.response import success, error
from app.utils.decorators import require_bearer_and_log

ehospital_bp = Blueprint('ehospital', __name__)


@ehospital_bp.route('/health', methods=['GET'])
def ehospital_health():
    from flask import request
    if request.args.get('fail') == '1':
        return error("eHospital service is unhealthy", "EHOSPITAL_SERVICE_UNHEALTHY", 503)
    return success("eHospital service is healthy", {"health": "healthy"})


@ehospital_bp.route('/patient', methods=['POST'])
@require_bearer_and_log
def patient_details():
    payload = request.get_json(silent=True) or {}
    uhid = payload.get('uhid')
    if not uhid:
        return error("Failed to register patient", "EHOSPITAL_SERVICE_ERROR", 400)
    # Mocked patient details
    details = send_ehospital_uhid(current_app, uhid)
    if details is None:
        return error("Failed to fetch patient details", "EHOSPITAL_SERVICE_ERROR", 500)
    return success("Patient details fetched successfully", details)


@ehospital_bp.route('/bulk_patient', methods=['POST'])
@require_bearer_and_log
def bulk_patient_details():
    payload = request.get_json(silent=True) or {}
    uhids = payload.get('uhids')
    if not isinstance(uhids, list) or not uhids:
        return error("Failed to fetch bulk patient details", "EHOSPITAL_SERVICE_ERROR", 400)
    patients = []
    # Mocked list
    for i, u in enumerate(uhids):
        patients.append({
            "uhid": u,
            "name": "John Doe" if i % 2 == 0 else "Jane Smith",
            "age": 30 if i % 2 == 0 else 25,
            "gender": "male" if i % 2 == 0 else "female",
        })
    return success("Bulk patient details fetched successfully", {"patients": patients})

