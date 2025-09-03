from flask import Blueprint, request
from app.utils.response import success, error
import uuid

mail_bp = Blueprint('mail', __name__)


@mail_bp.route('/health', methods=['GET'])
def mail_health():
    return success("Email service is healthy", {"health": "healthy"})


@mail_bp.route('/send', methods=['POST'])
def mail_send():
    payload = request.get_json(silent=True) or {}
    to = payload.get('to')
    subject = payload.get('subject')
    body = payload.get('body')
    if not to or not subject or not body:
        return error("Failed to send email", "EMAIL_SERVICE_ERROR", 400)
    msg_id = str(uuid.uuid4())
    return success("Email sent successfully", {"message_id": msg_id})


@mail_bp.route('/bulk_send', methods=['POST'])
def mail_bulk_send():
    payload = request.get_json(silent=True) or {}
    recipients = payload.get('to')
    subject = payload.get('subject')
    body = payload.get('body')
    if not isinstance(recipients, list) or not recipients or not subject or not body:
        return error("Failed to send bulk email", "EMAIL_SERVICE_ERROR", 400)
    ids = [str(uuid.uuid4()) for _ in recipients]
    return success("Bulk email sent successfully", {"message_ids": ids})

