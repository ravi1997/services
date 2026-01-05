from flask import Blueprint, request, current_app, g
from flask_restx import Api, Resource, fields
from app.utils.response import success, error
from app.extensions import db, email_sent_counter, email_failed_counter, email_queued_counter
from app.utils.decorators import require_bearer_and_log
from app.tasks.email_queue import add_to_queue_task, send_and_record, process_health_check_task
from app.models.email_message import EmailMessage
import uuid
from typing import List
import re
from sqlalchemy import select
import time
import logging

mail_bp = Blueprint('mail', __name__)
api = Api(mail_bp, doc='/docs', title='Email API', description='API for sending emails and checking status')

single_email_model = api.model('SingleEmailRequest', {
    'to': fields.String(required=True, description='Recipient email'),
    'subject': fields.String(required=True, description='Email subject'),
    'body': fields.String(required=True, description='Email body content'),
    'correlation_id': fields.String(required=False, description='Correlation ID for tracing')
})

bulk_email_model = api.model('BulkEmailRequest', {
    'to': fields.List(fields.String, required=True, description='List of recipient emails'),
    'subject': fields.String(required=True, description='Email subject'),
    'body': fields.String(required=True, description='Email body content'),
    'correlation_id': fields.String(required=False, description='Correlation ID for tracing')
})

"""Email endpoints with database persistence and advanced functionality."""

def _normalize_email(e: str) -> str:
    return e.strip().lower()

_EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

def _validate_email(email: str) -> bool:
    if not isinstance(email, str):
        return False
    e = email.strip()
    return bool(_EMAIL_RE.fullmatch(e))

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


def _check_ip_allowed():
    """Check if the client IP is in the allowed range"""
    client_ip = _get_ip_range()
    if client_ip.startswith('192.168.14.'):
        return True
    if client_ip.startswith('192.168.156.10'):
        return True
    return False


@api.route('/single')
class SingleEmail(Resource):
    method_decorators = [require_bearer_and_log]
    
    @api.expect(single_email_model)
    def post(self):
        # Check IP range
        if not _check_ip_allowed():
            logging.getLogger('access').error(f"Access denied from IP: {_get_ip_range()}")
            return error("Access denied from this IP", "ACCESS_DENIED", 403)
        
        data = request.get_json(silent=True) or {}
        to = (data.get('to') or '').strip()
        subject = (data.get('subject') or '').strip()
        body = (data.get('body') or '').strip()
        correlation_id = data.get('correlation_id', str(uuid.uuid4()))
        
        if not to or not subject or not body:
            return error("Missing required fields: to, subject, and body are required", "EMAIL_SERVICE_ERROR", 400)
            
        # Sanitization and Validation
        from app.utils.sanitization import sanitize_text, validate_safe_input
        
        is_safe_subj, reason_subj = validate_safe_input(subject, context="email_subject")
        if not is_safe_subj:
            return error(f"Invalid subject content: {reason_subj}", "SECURITY_VIOLATION", 400)
            
        is_safe_body, reason_body = validate_safe_input(body, context="email_body")
        if not is_safe_body:
            return error(f"Invalid body content: {reason_body}", "SECURITY_VIOLATION", 400)
            
        subject = sanitize_text(subject)
        body = sanitize_text(body)
            
        if len(subject) > 500:
            return error("Subject exceeds maximum length of 500 characters", "EMAIL_SERVICE_ERROR", 400)
        if len(body) > 10000:
            return error("Body exceeds maximum length of 10000 characters", "EMAIL_SERVICE_ERROR", 400)
        if not _validate_email(to):
            return error("Invalid email address format", "EMAIL_SERVICE_ERROR", 400)
        
        idempotency_key = request.headers.get('Idempotency-Key')
        if idempotency_key:
            # Note: This will only work if email addresses are stored unencrypted in the DB
            # For encrypted emails, we'd need a different approach for idempotency
            existing = EmailMessage.query.filter_by(idempotency_key=idempotency_key).first()
            if existing:
                logging.getLogger('app').info(f"Idempotent request: Email already processed: {idempotency_key}")
                return success("Email already processed", existing.as_dict())
        
        try:
            # Create record within a transaction to ensure a consistent id is available
            record = EmailMessage(to=to, subject=subject, body=body, status='queued', idempotency_key=idempotency_key, correlation_id=correlation_id, uuid=str(uuid.uuid4()))
            db.session.add(record)
            db.session.commit()  # create the row so we have an id
        except ValueError as e:
            # Handle validation errors from EmailMessage constructor
            db.session.rollback()
            logging.getLogger('error').error(f"Email validation error: {str(e)}")
            return error(f"Invalid email data: {str(e)}", "EMAIL_SERVICE_ERROR", 400)
        except Exception as e:
            # Handle any other database error
            db.session.rollback()
            logging.getLogger('error').error(f"Database error when creating email record: {str(e)}")
            return error("Internal server error", "EMAIL_SERVICE_ERROR", 500)

        # Add to queue for processing
        celery = getattr(current_app, 'celery', None)
        if celery:
            try:
                # Add to queue with the send_and_record task (which handles database tracking)
                task = send_and_record.delay(record.id, correlation_id)
                
                # Update the record to store the task ID
                with db.session.begin():
                    row = db.session.execute(
                        select(EmailMessage).where(EmailMessage.id == record.id).with_for_update()
                    ).scalar_one()
                    # We don't have a direct task ID from send_and_record, but it's tracked internally
                    row.task_id = task.id if hasattr(task, 'id') else str(uuid.uuid4())[:16]
                
                email_queued_counter.inc()
                logging.getLogger('email').info(f"Single email queued for {to}")
                return success("Email queued for processing", record.as_dict())
            except Exception as e:
                logging.getLogger('error').error(f"Error queuing email task: {str(e)}")
                # Fallback to direct sending if queueing fails
                from app.utils.email_util import send_single_email_util
                status, message_id = send_single_email_util(to, subject, body)
                
                # Update status in DB
                with db.session.begin():
                    row = db.session.execute(
                        select(EmailMessage).where(EmailMessage.id == record.id).with_for_update()
                    ).scalar_one()
                    if status == 200:
                        row.status = 'sent'
                        email_sent_counter.inc()
                        logging.getLogger('email').info(f"Single email sent directly to {to}")
                        return success("Email sent successfully", row.as_dict())
                    else:
                        row.status = 'failed'
                        email_failed_counter.inc()
                        logging.getLogger('email').error(f"Single email failed to {to}, status: {status}")
                        return error("Failed to send email", "EMAIL_SERVICE_ERROR", 400)
        else:
            # Direct send if no Celery
            from app.utils.email_util import send_single_email_util
            status, message_id = send_single_email_util(to, subject, body)
            
            with db.session.begin():
                row = db.session.execute(
                    select(EmailMessage).where(EmailMessage.id == record.id).with_for_update()
                ).scalar_one()
                if status == 200:
                    row.status = 'sent'
                    email_sent_counter.inc()
                    logging.getLogger('email').info(f"Single email sent directly to {to}")
                    return success("Email sent successfully", row.as_dict())
                else:
                    row.status = 'failed'
                    email_failed_counter.inc()
                    logging.getLogger('email').error(f"Single email failed to {to}, status: {status}")
                    return error("Failed to send email", "EMAIL_SERVICE_ERROR", 400)

@api.route('/bulk')
class BulkEmail(Resource):
    method_decorators = [require_bearer_and_log]
    
    @api.expect(bulk_email_model)
    def post(self):
        # Check IP range
        if not _check_ip_allowed():
            logging.getLogger('access').error(f"Access denied from IP: {_get_ip_range()}")
            return error("Access denied from this IP", "ACCESS_DENIED", 403)
        
        data = request.get_json(silent=True) or {}
        recipients: List[str] = data.get('to') or []
        subject = (data.get('subject') or '').strip()
        body = (data.get('body') or '').strip()
        correlation_id = data.get('correlation_id', str(uuid.uuid4()))
        
        if not isinstance(recipients, list) or not recipients or not subject or not body:
            return error("Missing required fields: to, subject, and body are required", "EMAIL_SERVICE_ERROR", 400)
            
        # Sanitization and Validation
        from app.utils.sanitization import sanitize_text, validate_safe_input
        
        is_safe_subj, reason_subj = validate_safe_input(subject, context="bulk_email_subject")
        if not is_safe_subj:
            return error(f"Invalid subject content: {reason_subj}", "SECURITY_VIOLATION", 400)
            
        is_safe_body, reason_body = validate_safe_input(body, context="bulk_email_body")
        if not is_safe_body:
            return error(f"Invalid body content: {reason_body}", "SECURITY_VIOLATION", 400)
            
        subject = sanitize_text(subject)
        body = sanitize_text(body)
            
        if len(subject) > 500:
            return error("Subject exceeds maximum length of 500 characters", "EMAIL_SERVICE_ERROR", 400)
        if len(body) > 10000:
            return error("Body exceeds maximum length of 10000 characters", "EMAIL_SERVICE_ERROR", 400)
        if len(recipients) > 200:  # Max 200 in bulk request
            return error("Bulk email request exceeds maximum of 200 messages", "EMAIL_SERVICE_ERROR", 400)
        
        cleaned = []
        for e in recipients:
            if not isinstance(e, str):
                return error("Invalid email address format in bulk request", "EMAIL_SERVICE_ERROR", 400)
            norm = _normalize_email(e)
            if not _validate_email(norm):
                return error(f"Invalid email address format: {norm}", "EMAIL_SERVICE_ERROR", 400)
            cleaned.append(norm)
        
        successes = []
        failures = []
        
        for e in cleaned:
            try:
                record = EmailMessage(to=e, subject=subject, body=body, status='queued', correlation_id=correlation_id, uuid=str(uuid.uuid4()))
                db.session.add(record)
                db.session.flush()  # Use flush to get ID without committing
            except ValueError as ve:
                # Handle validation error from EmailMessage constructor
                db.session.rollback()
                failures.append({'email': e, 'error': str(ve)})
                continue
            except Exception as e:
                # Handle any other database error
                db.session.rollback()
                failures.append({'email': e, 'error': 'Database error'})
                continue
            
            # Add to queue for processing
            celery = getattr(current_app, 'celery', None)
            if celery:
                try:
                    # Add to queue with the send_and_record task for each record
                    task = send_and_record.delay(record.id, correlation_id)
                    
                    # Update the record to store the task ID
                    record.task_id = task.id if hasattr(task, 'id') else str(uuid.uuid4())[:16]
                    email_queued_counter.inc()
                    successes.append({'email': e, 'record_id': record.id, 'task_queued': True})
                    logging.getLogger('email').info(f"Bulk email queued for {e}")
                except Exception as e:
                    logging.getLogger('error').error(f"Error queuing email task for {e}: {str(e)}")
                    # Fallback to direct sending if queueing fails
                    from app.utils.email_util import send_single_email_util
                    code, message_id = send_single_email_util(e, subject, body)
                    if code == 200:
                        record.status = 'sent'
                        email_sent_counter.inc()
                        successes.append({'email': e, 'record_id': record.id, 'direct_send': True})
                        logging.getLogger('email').info(f"Bulk email sent directly to {e}")
                    else:
                        record.status = 'failed'
                        email_failed_counter.inc()
                        failures.append({'email': e, 'record_id': record.id, 'status_code': code})
                        logging.getLogger('email').error(f"Bulk email failed to {e}, status: {code}")
            else:
                # Direct send if no Celery
                from app.utils.email_util import send_single_email_util
                code, message_id = send_single_email_util(e, subject, body)
                if code == 200:
                    record.status = 'sent'
                    email_sent_counter.inc()
                    successes.append({'email': e, 'record_id': record.id, 'direct_send': True})
                    logging.getLogger('email').info(f"Bulk email sent directly to {e}")
                else:
                    record.status = 'failed'
                    email_failed_counter.inc()
                    failures.append({'email': e, 'record_id': record.id, 'status_code': code})
                    logging.getLogger('email').error(f"Bulk email failed to {e}, status: {code}")
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.getLogger('error').error(f"Database error when committing bulk email records: {str(e)}")
            return error("Internal server error during bulk email processing", "EMAIL_SERVICE_ERROR", 500)
        
        overall = 200 if successes and not failures else (207 if successes and failures else 400)
        payload = {"successes": successes, "failures": failures, "requested": len(cleaned)}
        
        if overall == 200:
            logging.getLogger('email').info(f"Bulk email: {len(successes)} sent successfully")
            return success("Bulk email processed successfully", payload, 200)
        if overall == 207:
            logging.getLogger('email').info(f"Bulk email: {len(successes)} succeeded, {len(failures)} failed")
            body, _ = success("Bulk email partially successful", payload, 207)
            body["status"] = "partial"
            return body, 207
        
        logging.getLogger('email').error(f"Bulk email: all {len(failures)} failed")
        return error("Failed to send Bulk email", "EMAIL_SERVICE_ERROR", 400)

@api.route('/health')
class EmailHealth(Resource):
    def get(self):
        # Check IP range
        if not _check_ip_allowed():
            logging.getLogger('access').error(f"Health check access denied from IP: {_get_ip_range()}")
            return error("Access denied from this IP", "ACCESS_DENIED", 403)
        
        # Process as high priority health check
        celery = getattr(current_app, 'celery', None)
        if celery:
            # Run health check as a high priority task
            try:
                task = process_health_check_task.delay()
                result = task.get(timeout=10)  # Wait up to 10 seconds
                logging.getLogger('app').info(f"Health check completed: {result}")
                return success("Email service health check", result)
            except Exception as e:
                logging.getLogger('error').error(f"Health check failed: {str(e)}")
                return error("Health check failed", "HEALTH_CHECK_ERROR", 500)
        else:
            # Direct health check if no Celery
            try:
                from flask import current_app
                if current_app.config.get('SMTP_SERVER') and current_app.config.get('SMTP_USERNAME'):
                    logging.getLogger('app').info("Direct health check: configuration OK")
                    return success("Email service is configured and ready", {"health": "healthy", "configured": True})
                else:
                    logging.getLogger('app').error("Direct health check: missing configuration")
                    return error("Email service configuration missing", "EMAIL_SERVICE_ERROR", 503)
            except RuntimeError:
                # Not in app context, use environment variables
                import os
                smtp_server = os.getenv('SMTP_SERVER')
                smtp_username = os.getenv('SMTP_USERNAME')
                if smtp_server and smtp_username:
                    logging.getLogger('app').info("Direct health check: configuration OK")
                    return success("Email service is configured and ready", {"health": "healthy", "configured": True})
                else:
                    logging.getLogger('app').error("Direct health check: missing configuration")
                    return error("Email service configuration missing", "EMAIL_SERVICE_ERROR", 503)