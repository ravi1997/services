from flask import Blueprint, request, current_app, g
from flask_restx import Api, Resource, fields
from app.schema.sms_schema import SMSSchema
from app.utils.response import success, error
from app.extensions import db, sms_sent_counter, sms_failed_counter, sms_queued_counter
from app.utils.decorators import require_bearer_and_log
from app.tasks.sms_queue import add_to_queue_task, process_health_check_task
from app.models.sms_message import SMSMessage
import uuid
from typing import List
import re
from sqlalchemy import select
import time
import logging

from app.utils.sms_service import send_sms

sms_bp = Blueprint('sms', __name__)
api = Api(sms_bp, doc='/docs', title='SMS API', description='API for sending SMS and checking status')

single_sms_model = api.model('SingleSMSRequest', {
    'mobile': fields.String(required=False, description='Recipient phone (preferred)'),
    'to': fields.String(required=False, description='Recipient phone (legacy key)'),
    'message': fields.String(required=True, description='Message content')
})

bulk_sms_model = api.model('BulkSMSRequest', {
    'mobiles': fields.List(fields.String, required=False, description='List of recipient phones (preferred)'),
    'to': fields.List(fields.String, required=False, description='Legacy key for list of phones'),
    'message': fields.String(required=True, description='Message content')
})

sms_schema = SMSSchema()

"""SMS endpoints with specific rate limits and functionality."""

def _normalize_number(n: str) -> str:
    return n.strip()

_PHONE_RE = re.compile(r'^\+?[1-9]\d{5,14}$')

def _validate_number(num: str) -> bool:
    if not isinstance(num, str):
        return False
    n = num.strip()
    return bool(_PHONE_RE.fullmatch(n))

def _get_ip_range():
    """Get client IP, checking for reverse proxy headers"""
    # Check for common reverse proxy headers
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip = forwarded_for.split(',')[0].strip()
        return ip
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    return request.remote_addr


@api.route('/single')
class SingleSMS(Resource):
    method_decorators = [require_bearer_and_log]
    
    @api.expect(single_sms_model)
    def post(self):
        
        data = request.get_json(silent=True) or {}
        mobile = (data.get('mobile') or data.get('to') or '').strip()
        message = (data.get('message') or '').strip()
        
        if not mobile or not message:
            return error("Missing required fields: mobile and message are required", "SMS_SERVICE_ERROR", 400)
            
        # Sanitization and Validation
        from app.utils.sanitization import sanitize_text, validate_safe_input
        is_safe, reason = validate_safe_input(message, context="sms_message")
        if not is_safe:
            return error(f"Invalid message content: {reason}", "SECURITY_VIOLATION", 400)
            
        message = sanitize_text(message)
            
        if len(message) > 500:
            return error("Message exceeds maximum length of 500 characters", "SMS_SERVICE_ERROR", 400)
        if not _validate_number(mobile):
            return error("Invalid phone number format", "SMS_SERVICE_ERROR", 400)
        
        idempotency_key = request.headers.get('Idempotency-Key')
        
        from app.utils.sms_workflow import process_single_sms, SMSWorkflowError
        
        try:
            result = process_single_sms(mobile, message, idempotency_key)
            # Check if this was an existing idempotent return or a new success
            msg = "SMS already processed" if idempotency_key and result.get('status') == 'sent' and 'created_at' in result else "SMS processed"
            return success(msg, result)
        except SMSWorkflowError as e:
            return error(str(e), e.error_code, e.http_code)
        except Exception as e:
            logging.getLogger('error').error(f"Unexpected error in SingleSMS: {str(e)}")
            return error("Internal server error", "SMS_SERVICE_ERROR", 500)


@api.route('/bulk')
class BulkSMS(Resource):
    method_decorators = [require_bearer_and_log]
    
    @api.expect(bulk_sms_model)
    def post(self):
        
        data = request.get_json(silent=True) or {}
        mobiles: List[str] = data.get('mobiles') or data.get('to') or []
        message = (data.get('message') or '').strip()
        
        if not isinstance(mobiles, list) or not mobiles or not message:
            return error("Missing required fields: mobiles and message are required", "SMS_SERVICE_ERROR", 400)
            
        # Sanitization and Validation
        from app.utils.sanitization import sanitize_text, validate_safe_input
        is_safe, reason = validate_safe_input(message, context="bulk_sms_message")
        if not is_safe:
            return error(f"Invalid message content: {reason}", "SECURITY_VIOLATION", 400)
            
        message = sanitize_text(message)
            
        if len(message) > 500:
            return error("Message exceeds maximum length of 500 characters", "SMS_SERVICE_ERROR", 400)
        if len(mobiles) > 200:  # Max 200 in bulk request
            return error("Bulk SMS request exceeds maximum of 200 messages", "SMS_SERVICE_ERROR", 400)
        
        cleaned = []
        for m in mobiles:
            if not isinstance(m, str):
                return error("Invalid mobile number format in bulk request", "SMS_SERVICE_ERROR", 400)
            n = _normalize_number(m)
            if not _validate_number(n):
                return error(f"Invalid phone number format: {n}", "SMS_SERVICE_ERROR", 400)
            cleaned.append(n)
        
        successes = []
        failures = []
        
        from app.utils.sms_workflow import process_single_sms, SMSWorkflowError
        
        for n in cleaned:
            try:
                # We process each one individually using the workflow
                # This explicitly trades batch performance for code reuse and safety
                record = process_single_sms(n, message, idempotency_key=None)
                successes.append({'mobile': n, 'record_id': record.get('id'), 'status': 'queued'})
            except SMSWorkflowError as e:
                failures.append({'mobile': n, 'error': str(e)})
            except Exception as e:
                failures.append({'mobile': n, 'error': "Internal processing error"})
        
        overall = 200 if successes and not failures else (207 if successes and failures else 400)
        payload = {"successes": successes, "failures": failures, "requested": len(cleaned)}
        
        if overall == 200:
            logging.getLogger('sms').info(f"Bulk SMS: {len(successes)} sent successfully")
            return success("Bulk SMS processed successfully", payload, 200)
        if overall == 207:
            logging.getLogger('sms').info(f"Bulk SMS: {len(successes)} succeeded, {len(failures)} failed")
            body, _ = success("Bulk SMS partially successful", payload, 207)
            body["status"] = "partial"
            return body, 207
        
        logging.getLogger('sms').error(f"Bulk SMS: all {len(failures)} failed")
        return error("Failed to send Bulk SMS", "SMS_SERVICE_ERROR", 400)

@api.route('/health')
class SMSHealth(Resource):
    def get(self):
        # Process as high priority health check
        celery = getattr(current_app, 'celery', None)
        if celery:
            # Run health check as a high priority task
            try:
                task = process_health_check_task.delay()
                result = task.get(timeout=10)  # Wait up to 10 seconds
                logging.getLogger('app').info(f"Health check completed: {result}")
                return success("SMS service health check", result)
            except Exception as e:
                logging.getLogger('error').error(f"Health check failed: {str(e)}")
                return error("Health check failed", "HEALTH_CHECK_ERROR", 500)
        else:
            # Direct health check if no Celery
            if current_app.config.get('OTP_FLAG', True):
                if current_app.config.get('OTP_SERVER') and current_app.config.get('OTP_USERNAME'):
                    logging.getLogger('app').info("Direct health check: configuration OK")
                    # Use configured test number or skip actual sending
                    test_number = current_app.config.get('HEALTH_CHECK_TEST_NUMBER')
                    if test_number:
                        status = send_sms(test_number, "Health Check Test")
                        if status == 200:
                            logging.getLogger('app').info("Direct health check: SMS sent successfully")
                            return success("SMS service is configured and ready", {"health": "healthy", "configured": True})
                        else:
                            logging.getLogger('app').error(f"Direct health check: SMS send failed with status {status}")
                            return error("SMS service health check failed", "SMS_SERVICE_UNHEALTHY", 503)
                    else:
                        # Configuration check only, no actual SMS sending
                        logging.getLogger('app').info("Direct health check: configuration verified (no test send)")
                        return success("SMS service is configured", {"health": "healthy", "configured": True, "test_send": False})
                else:
                    logging.getLogger('app').error("Direct health check: missing configuration")
                    return error("SMS service configuration missing", "SMS_SERVICE_UNHEALTHY", 503)
            else:
                logging.getLogger('app').info("Direct health check: test mode")
                return success("SMS service is configured (test mode)", {"health": "healthy", "configured": True, "test_mode": True})