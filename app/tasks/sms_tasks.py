from celery import shared_task
from flask import current_app
import uuid
from app.extensions import db, sms_sent_counter, sms_failed_counter
from app.utils.sms_service import send_sms
from sqlalchemy import select


@shared_task(bind=True, name='sms.send_and_record', autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=60, retry_jitter=True, max_retries=5)
def send_and_record(self, record_id, correlation_id=None):
    from app.models.sms_message import SMSMessage  # lazy import

    # Short transaction: lock row and increment attempts to avoid lost updates
    with db.session.begin():
        row = db.session.execute(
            select(SMSMessage).where(SMSMessage.id == record_id).with_for_update()
        ).scalar_one_or_none()
        if not row:
            return {'error': 'record_not_found', 'record_id': record_id}
        attempt = self.request.retries + 1
        row.attempts = attempt

    # Input validation outside the locked transaction (keeps lock short)
    import re
    phone_pattern = re.compile(r"^\d{6,16}$")
    if not phone_pattern.match(str(row.to)):
        # persist invalid state and retry (if desired) - here we raise to trigger retry/backoff
        raise ValueError("Invalid phone number")
    if not isinstance(row.message, str) or not (1 <= len(row.message) <= 500):
        raise ValueError("Invalid message length")
    forbidden = ["<script", "SELECT ", "INSERT ", "DELETE ", "UPDATE ", "DROP "]
    if any(f in row.message.upper() for f in forbidden):
        raise ValueError("Forbidden content in SMS message")

    # Audit logging
    current_app.logger.info(f"Audit: Sending SMS to {row.to}")

    status_code = send_sms(row.to, row.message)

    # Persist status with a short transaction and row-level lock to avoid races
    if status_code == 200:
        with db.session.begin():
            r = db.session.execute(
                select(SMSMessage).where(SMSMessage.id == record_id).with_for_update()
            ).scalar_one()
            r.status = 'sent'
            sms_sent_counter.inc()
            if not r.uuid:
                r.uuid = str(uuid.uuid4())
        return {'record_id': r.id, 'status': r.status, 'attempts': r.attempts, 'uuid': r.uuid, 'correlation_id': correlation_id}
    else:
        # If we're going to retry, persist the 'retry' state before raising to ensure visibility
        attempt = self.request.retries + 1
        if attempt >= 5:
            with db.session.begin():
                r = db.session.execute(
                    select(SMSMessage).where(SMSMessage.id == record_id).with_for_update()
                ).scalar_one()
                r.status = 'failed'
                sms_failed_counter.inc()
            current_app.logger.error(f"Failed SMS delivery: to={row.to}, status={status_code}")
            return {'record_id': r.id, 'status': r.status, 'attempts': r.attempts, 'uuid': r.uuid, 'correlation_id': correlation_id}
        else:
            with db.session.begin():
                r = db.session.execute(
                    select(SMSMessage).where(SMSMessage.id == record_id).with_for_update()
                ).scalar_one()
                r.status = 'retry'
            current_app.logger.error(f"Failed SMS delivery: to={row.to}, status={status_code}")
            # Ask Celery to retry using its machinery
            self.retry(exc=Exception("Failed SMS delivery"), countdown=10, max_retries=5)

@shared_task(bind=True, name='sms.send_sms', autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=60, retry_jitter=True, max_retries=5)
def send_sms_task(self, to, message, correlation_id=None, record_id=None):
    """Send SMS with proper error handling and retry logic.

    correlation_id: propagated from incoming request for traceability.
    """
    import re
    from app.utils.sms_service import send_sms
    from app.extensions import db, sms_sent_counter, sms_failed_counter
    from app.models.sms_message import SMSMessage
    from sqlalchemy import select
    
    attempt = self.request.retries + 1
    current_app.logger.info(f'sms_task_start: task_id={self.request.id}, attempt={attempt}, to={to}, correlation_id={correlation_id}')
    
    # Validation
    phone_pattern = re.compile(r"^\d{6,16}$")
    if not phone_pattern.match(str(to)):
        raise ValueError("Invalid phone number")
    if not isinstance(message, str) or not (1 <= len(message) <= 500):
        raise ValueError("Invalid message length")
    forbidden = ["<script", "SELECT ", "INSERT ", "DELETE ", "UPDATE ", "DROP "]
    if any(f in message.upper() for f in forbidden):
        raise ValueError("Forbidden content in SMS message")
    
    try:
        # Try to send the SMS
        status_code = send_sms(to, message)
        
        # Update database based on result
        if status_code == 200:
            # Persist success
            if record_id:
                with db.session.begin():
                    msg = db.session.execute(
                        select(SMSMessage).where(SMSMessage.id == record_id).with_for_update()
                    ).scalar_one_or_none()
                    if msg:
                        msg.status = 'sent'
                        msg.attempts = attempt
            sms_sent_counter.inc()
            result = {"status": "success", "to": to, "message": message, "attempt": attempt, "correlation_id": correlation_id}
            current_app.logger.info(f'sms_task_success: task_id={self.request.id}, result={result}, correlation_id={correlation_id}')
            return result
        else:
            # Log failure
            current_app.logger.error(f"Failed SMS delivery: to={to}, status={status_code}")
            # Update message status for tracking
            if record_id:
                with db.session.begin():
                    msg = db.session.execute(
                        select(SMSMessage).where(SMSMessage.id == record_id).with_for_update()
                    ).scalar_one_or_none()
                    if msg:
                        msg.status = 'retry' if attempt < 5 else 'failed'
                        msg.attempts = attempt
            if attempt >= 5:
                sms_failed_counter.inc()
            # Retry if not at max attempts
            if attempt < 5:
                self.retry(exc=Exception("Failed SMS delivery"), countdown=10)
            else:
                # Final failure
                return {"status": "failed", "to": to, "attempt": attempt, "correlation_id": correlation_id}
                
    except Exception as exc:
        # Log the exception
        current_app.logger.error(f'sms_task_error: task_id={self.request.id}, attempt={attempt}, error={str(exc)}, correlation_id={correlation_id}')
        # Update message status for tracking
        if record_id:
            with db.session.begin():
                msg = db.session.execute(
                    select(SMSMessage).where(SMSMessage.id == record_id).with_for_update()
                ).scalar_one_or_none()
                if msg:
                    msg.status = 'retry' if attempt < 5 else 'failed'
                    msg.attempts = attempt
        if attempt >= 5:
            from app.extensions import sms_failed_counter
            sms_failed_counter.inc()
        # Retry if not at max attempts
        if attempt < 5:
            self.retry(exc=exc, countdown=10)
        else:
            # Final failure
            raise exc

@shared_task(bind=True, name='sms.cancel_sms')
def cancel_sms_task(self, task_id, correlation_id=None):
    current_app.logger.info(f'sms_task_cancel: task_id={task_id}, correlation_id={correlation_id}')
    # In a real implementation, this would communicate with the SMS provider to cancel a pending message
    return {"status": "cancel_requested", "task_id": task_id, "correlation_id": correlation_id}