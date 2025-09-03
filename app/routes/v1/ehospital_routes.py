from flask import Blueprint, request
from app.utils.response import success, error

ehospital_bp = Blueprint('ehospital', __name__)


@ehospital_bp.route('/health', methods=['GET'])
def ehospital_health():
    return success("eHospital service is healthy", {"health": "healthy"})


@ehospital_bp.route('/patient', methods=['POST'])
def patient_details():
    payload = request.get_json(silent=True) or {}
    uhid = payload.get('uhid')
    if not uhid:
        return error("Failed to register patient", "EHOSPITAL_SERVICE_ERROR", 400)
    # Mocked patient details
    details = {"uhid": uhid, "name": "John Doe", "age": 30, "gender": "male"}
    return success("Patient details fetched successfully", details)


@ehospital_bp.route('/bulk_patient', methods=['POST'])
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

