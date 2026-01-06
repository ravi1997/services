import uuid
import logging
from sqlalchemy import select
from flask import current_app
from app.extensions import db, sms_sent_counter, sms_failed_counter, sms_queued_counter
from app.models.sms_message import SMSMessage
from app.tasks.sms_queue import add_to_queue_task
from app.utils.sms_util import send_single_sms_util

logger = logging.getLogger('sms')

class SMSWorkflowError(Exception):
    def __init__(self, message, error_code, http_code=400):
        super().__init__(message)
        self.error_code = error_code
        self.http_code = http_code

def process_single_sms(mobile: str, message: str, idempotency_key: str = None) -> dict:
    """
    Orchestrates the lifecycle of a single SMS:
    1. Validation
    2. DB Persistence (Queued)
    3. Async Queueing (Celery) or Synchronous Fallback
    4. DB Update
    5. Metric Emission
    
    Returns:
        dict: The serializable SMSMessage record.
        
    Raises:
        SMSWorkflowError: On validation or processing failure.
    """
    
    # 1. Idempotency Check
    if idempotency_key:
        existing = SMSMessage.query.filter_by(idempotency_key=idempotency_key).first()
        if existing:
            logging.getLogger('app').info(f"Idempotent request: SMS already processed: {idempotency_key}")
            return existing.as_dict()

    # 2. Create DB Record (Queued)
    try:
        record = SMSMessage(
            to=mobile, 
            message=message, 
            status='queued', 
            idempotency_key=idempotency_key, 
            uuid=str(uuid.uuid4())
        )
        db.session.add(record)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        logging.getLogger('error').error(f"SMS validation error: {str(e)}")
        raise SMSWorkflowError(f"Invalid SMS data: {str(e)}", "SMS_SERVICE_ERROR", 400)
    except Exception as e:
        db.session.rollback()
        logging.getLogger('error').error(f"Database error when creating SMS record: {str(e)}")
        raise SMSWorkflowError("Internal server error", "SMS_SERVICE_ERROR", 500)

    # 3. Processing (Queue vs Direct)
    celery = getattr(current_app, 'celery', None)
    
    if celery:
        try:
            task = add_to_queue_task.delay('process_single_sms', record.id, None)
            
            # Update record with task_id
            with db.session.begin():
                row = db.session.execute(
                    select(SMSMessage).where(SMSMessage.id == record.id).with_for_update()
                ).scalar_one()
                row.task_id = task.id if hasattr(task, 'id') else str(uuid.uuid4())[:16]
            
            sms_queued_counter.inc()
            logger.info(f"Single SMS queued for {mobile}")
            return record.as_dict()
            
        except Exception as e:
            logging.getLogger('error').error(f"Error queuing SMS task: {str(e)}")
            # Proceed to fallback
            pass

    # 4. Fallback (Direct Send)
    status_code, status_msg = send_single_sms_util(mobile, message)
    
    with db.session.begin():
        row = db.session.execute(
            select(SMSMessage).where(SMSMessage.id == record.id).with_for_update()
        ).scalar_one()
        
        if status_code == 200:
            row.status = 'sent'
            sms_sent_counter.inc()
            logger.info(f"Single SMS sent directly to {mobile}")
        else:
            row.status = 'failed'
            sms_failed_counter.inc()
            logger.error(f"Single SMS failed to {mobile}, status: {status_code}")
            
    # Refresh record state for return
    if status_code != 200:
         raise SMSWorkflowError("Failed to send SMS", "SMS_SERVICE_ERROR", 400)
         
    # We return the dict representation of the *updated* row, but we can't easily 
    # access 'row' outside the session block if it was local.
    # We can reconstruct it or query it. Since we just need the dict:
    return {
        **record.as_dict(),
        'status': 'sent' # Force status to match what we just did
    }
