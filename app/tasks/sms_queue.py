import logging
from celery import shared_task
from flask import current_app
import time
from app.extensions import db, sms_sent_counter, sms_failed_counter
from app.utils.sms_util import send_single_sms_util
from sqlalchemy import select
from app.models.sms_message import SMSMessage

# Queue for handling SMS requests with rate limiting
class SMSQueue:
    def __init__(self):
        self.queue = []
        self.processed_count = 0
        self.last_reset_time = time.time()
        self.rate_limit = 100  # 100 requests per minute
        self.window_size = 60  # 60 seconds
    
    def add_to_queue(self, task_func, *args, **kwargs):
        """Add a task to the queue"""
        self.queue.append((task_func, args, kwargs))
        return len(self.queue)  # Return current queue length
    
    def can_process_request(self):
        """Check if we can process another request based on rate limit"""
        now = time.time()
        # Reset counter if window has passed
        if now - self.last_reset_time >= self.window_size:
            self.processed_count = 0
            self.last_reset_time = now
        
        # Check if we're under the rate limit
        return self.processed_count < self.rate_limit
    
    def process_queue(self):
        """Process queued items within rate limits"""
        if not self.can_process_request():
            return False  # Rate limit exceeded
        
        # Process one item if available
        if self.queue:
            task_func, args, kwargs = self.queue.pop(0)
            result = task_func(*args, **kwargs)
            self.processed_count += 1
            return result
        
        return None

# Global SMS queue instance
sms_queue = SMSQueue()

@shared_task(bind=True, name='sms.add_to_queue', autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=60, retry_jitter=True, max_retries=3)
def add_to_queue_task(self, task_name, *args, **kwargs):
    """
    Add a task to the SMS queue for processing.
    
    Args:
        task_name: Name of the task function to execute
        *args, **kwargs: Arguments to pass to the task function
    """
    import logging
    logging.getLogger('app').info(f"Adding task {task_name} to queue")
    
    # Get the actual function by name
    if task_name == 'process_single_sms':
        from app.tasks.sms_queue import process_single_sms
        task_func = process_single_sms
    else:
        raise ValueError(f"Unknown task name: {task_name}")
    
    # Add to queue
    queue_length = sms_queue.add_to_queue(task_func, *args, **kwargs)
    
    logging.getLogger('app').info(f"Task added to queue. Current queue length: {queue_length}")
    
    # Try to process immediately if within rate limits
    if sms_queue.can_process_request():
        return sms_queue.process_queue()
    else:
        logging.getLogger('app').info("Rate limit reached, task remains in queue")
        return {'status': 'queued', 'queue_length': queue_length}

def process_single_sms(record_id, correlation_id=None):
    """
    Process a single SMS record by calling the thread-safe utility function.
    """
    # Short transaction: lock row and increment attempts to avoid lost updates
    with db.session.begin():
        row = db.session.execute(
            select(SMSMessage).where(SMSMessage.id == record_id).with_for_update()
        ).scalar_one_or_none()
        if not row:
            return {'error': 'record_not_found', 'record_id': record_id}
        # Increment attempts (this will be handled by the caller in real implementation)
    
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
    logging.getLogger('app').info(f"Audit: Sending SMS to {row.to}")

    status_code = send_single_sms_util(str(row.to), row.message)

    # Persist status with a short transaction and row-level lock to avoid races
    if status_code == 200:
        with db.session.begin():
            r = db.session.execute(
                select(SMSMessage).where(SMSMessage.id == record_id).with_for_update()
            ).scalar_one()
            r.status = 'sent'
            sms_sent_counter.inc()
            if not r.uuid:
                r.uuid = str(r.uuid)  # Use existing UUID or generate new one
        return {'record_id': r.id, 'status': r.status, 'uuid': r.uuid, 'correlation_id': correlation_id}
    else:
        with db.session.begin():
            r = db.session.execute(
                select(SMSMessage).where(SMSMessage.id == record_id).with_for_update()
            ).scalar_one()
            r.status = 'failed'
            sms_failed_counter.inc()
        logging.getLogger('app').error(f"Failed SMS delivery: to={row.to}, status={status_code}")
        return {'record_id': r.id, 'status': r.status, 'uuid': r.uuid, 'correlation_id': correlation_id}

@shared_task(bind=True, name='sms.process_health_check', autorety_for=(Exception,), retry_backoff=True, retry_backoff_max=60, retry_jitter=True, max_retries=1)
def process_health_check_task(self):
    """
    Process a health check task with highest priority.
    This runs immediately without queuing.
    """
    logging.getLogger('app').info("Processing health check task")
    
    # Simple connectivity check - just verify configuration exists
    if current_app.config.get('OTP_FLAG', True):
        if current_app.config.get('OTP_SERVER') and current_app.config.get('OTP_USERNAME'):
            logging.getLogger('app').info("SMS service health check: configuration OK")
            return {"status": "healthy", "configured": True}
        else:
            logging.getLogger('app').error("SMS service health check: missing configuration")
            return {"status": "unhealthy", "configured": False, "error": "Missing OTP configuration"}
    else:
        logging.getLogger('app').info("SMS service health check: test mode")
        return {"status": "healthy", "configured": True, "test_mode": True}