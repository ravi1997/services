from celery import shared_task, states
import random
import time
import logging
from app.utils.logging_utils import json_extra
from flask import current_app

task_logger = logging.getLogger('app_logger')

MAX_RETRIES = 5

@shared_task(bind=True, name='sms.send_sms', autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=60, retry_jitter=True, max_retries=MAX_RETRIES)
def send_sms_task(self, to, message, correlation_id=None, record_id=None):
    """Simulated SMS send with random transient failure to demonstrate retry/backoff.

    correlation_id: propagated from incoming request for traceability.
    """
    attempt = self.request.retries + 1
    task_logger.info('sms_task_start', extra=json_extra(event='sms_task_start', task_id=self.request.id, attempt=attempt, to=to, correlation_id=correlation_id))
    try:
        if random.random() < 0.3:
            raise Exception("Transient provider error")
        time.sleep(0.2)  # simulate network latency
        result = {"status": "success", "to": to, "message": message, "attempt": attempt, "correlation_id": correlation_id}
        # Persist success
        try:
            if current_app:
                db = current_app.db
                from app.models.sms_message import SMSMessage
                msg = db.session.get(SMSMessage, record_id) if record_id else None
                if msg:
                    msg.status = 'sent'
                    msg.attempts = attempt
                    db.session.commit()
        except Exception as db_exc:  # pragma: no cover
            task_logger.warning('sms_task_db_update_failed', extra=json_extra(event='sms_task_db_update_failed', error=str(db_exc)))
        task_logger.info('sms_task_success', extra=json_extra(event='sms_task_success', task_id=self.request.id, result=result, correlation_id=correlation_id))
        return result
    except Exception as exc:
        # Persist retry state
        try:
            if current_app:
                db = current_app.db
                from app.models.sms_message import SMSMessage
                msg = db.session.get(SMSMessage, record_id) if record_id else None
                if msg:
                    msg.status = 'retry'
                    msg.attempts = attempt
                    db.session.commit()
        except Exception as db_exc:  # pragma: no cover
            task_logger.warning('sms_task_db_retry_update_failed', extra=json_extra(event='sms_task_db_retry_update_failed', error=str(db_exc)))
        task_logger.warning('sms_task_retry', extra=json_extra(event='sms_task_retry', task_id=self.request.id, attempt=attempt, error=str(exc), correlation_id=correlation_id))
        raise exc

@shared_task(bind=True, name='sms.cancel_sms')
def cancel_sms_task(self, task_id, correlation_id=None):
    task_logger.info('sms_task_cancel', extra=json_extra(event='sms_task_cancel', task_id=task_id, correlation_id=correlation_id))
    return {"status": "cancel_requested", "task_id": task_id, "correlation_id": correlation_id}