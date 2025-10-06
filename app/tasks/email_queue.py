import logging
from celery import shared_task
from flask import current_app
import time
from app.extensions import db, email_sent_counter, email_failed_counter
from app.utils.email_util import send_single_email_util
from queue import Queue, Empty
import threading
import uuid
from typing import Dict, List, Any
from sqlalchemy import select
from app.models.email_message import EmailMessage


# Queue for handling email requests with rate limiting
class EmailQueue:
    def __init__(self):
        self.high_priority_queue = Queue()  # For health check tasks
        self.normal_queue = Queue()         # For regular email tasks
        self.processed_count = 0
        self.last_reset_time = time.time()
        self.rate_limit = 100  # 100 requests per minute
        self.window_size = 60  # 60 seconds
        self.lock = threading.Lock()  # Thread lock for rate limiting
        
    def add_to_queue(self, task_func, is_high_priority=False, *args, **kwargs):
        """Add a task to the appropriate queue"""
        task_id = str(uuid.uuid4())
        task_data = {
            'task_id': task_id,
            'task_func': task_func,
            'args': args,
            'kwargs': kwargs
        }
        
        if is_high_priority:
            self.high_priority_queue.put(task_data)
        else:
            self.normal_queue.put(task_data)
        
        return task_id
    
    def can_process_request(self):
        """Check if we can process another request based on rate limit"""
        with self.lock:
            now = time.time()
            # Reset counter if window has passed
            if now - self.last_reset_time >= self.window_size:
                self.processed_count = 0
                self.last_reset_time = now
            
            # Check if we're under the rate limit
            return self.processed_count < self.rate_limit
    
    def get_next_task(self):
        """Get next task from queues (high priority first)"""
        try:
            # Check high priority queue first
            if not self.high_priority_queue.empty():
                return self.high_priority_queue.get_nowait()
            # Then normal queue
            elif not self.normal_queue.empty():
                return self.normal_queue.get_nowait()
            else:
                return None
        except Empty:
            return None
    
    def process_queue(self):
        """Process queued items within rate limits"""
        if not self.can_process_request():
            return False  # Rate limit exceeded
        
        # Get next task
        task_data = self.get_next_task()
        if task_data:
            with self.lock:
                # Increment processed count only if we're under rate limit
                now = time.time()
                if now - self.last_reset_time >= self.window_size:
                    self.processed_count = 0
                    self.last_reset_time = now
                
                if self.processed_count < self.rate_limit:
                    task_func, args, kwargs = task_data['task_func'], task_data['args'], task_data['kwargs']
                    result = task_func(*args, **kwargs)
                    self.processed_count += 1
                    return result
                else:
                    # Put the task back if rate limit is exceeded
                    if task_data.get('is_high_priority', False):
                        self.high_priority_queue.put(task_data)
                    else:
                        self.normal_queue.put(task_data)
                    return False
        
        return None

# Global email queue instance
email_queue = EmailQueue()


@shared_task(bind=True, name='email.send_and_record', autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=60, retry_jitter=True, max_retries=5)
def send_and_record(self, record_id, correlation_id=None):
    """
    Send email with database record tracking and retry logic.
    
    Args:
        record_id: ID of the EmailMessage record in the database
        correlation_id: Correlation ID for tracing
    """
    # Short transaction: lock row and increment attempts to avoid lost updates
    with db.session.begin():
        row = db.session.execute(
            select(EmailMessage).where(EmailMessage.id == record_id).with_for_update()
        ).scalar_one_or_none()
        if not row:
            return {'error': 'record_not_found', 'record_id': record_id}
        attempt = self.request.retries + 1
        row.attempts = attempt

    # Input validation outside the locked transaction (keeps lock short)
    from app.utils.email_util import validate_email, validate_subject, validate_body
    from cryptography.fernet import Fernet
    import os
    
    # Decrypt sensitive data
    try:
        encryption_key = os.getenv("ENCRYPTION_KEY")
        f = Fernet(encryption_key.encode())
        to = f.decrypt(row.to.encode()).decode()
        subject = f.decrypt(row.subject.encode()).decode()
        body = f.decrypt(row.body.encode()).decode()
    except Exception as e:
        logging.getLogger('error').error(f"Failed to decrypt email data for record {record_id}: {str(e)}")
        return {'error': 'decryption_error', 'record_id': record_id}

    # Validate inputs
    if not validate_email(to):
        # persist invalid state and retry (if desired) - here we raise to trigger retry/backoff
        raise ValueError("Invalid email address")
    if not validate_subject(subject):
        raise ValueError("Invalid subject")
    if not validate_body(body):
        raise ValueError("Invalid body content")

    # Audit logging
    app_logger = logging.getLogger('app')
    app_logger.info(f"Audit: Sending email to {to}, correlation_id: {correlation_id}")

    # Get result of actual email sending
    status_code, message_id = send_single_email_util(to, subject, body)

    # Persist status with a short transaction and row-level lock to avoid races
    if status_code == 200:
        with db.session.begin():
            r = db.session.execute(
                select(EmailMessage).where(EmailMessage.id == record_id).with_for_update()
            ).scalar_one()
            r.status = 'sent'
            email_sent_counter.inc()
            if not r.uuid:
                r.uuid = str(uuid.uuid4())
        return {'record_id': r.id, 'status': r.status, 'attempts': r.attempts, 'uuid': r.uuid, 'correlation_id': correlation_id, 'message_id': message_id}
    else:
        # If we're going to retry, persist the 'retry' state before raising to ensure visibility
        attempt = self.request.retries + 1
        if attempt >= 5:
            with db.session.begin():
                r = db.session.execute(
                    select(EmailMessage).where(EmailMessage.id == record_id).with_for_update()
                ).scalar_one()
                r.status = 'failed'
                email_failed_counter.inc()
            app_logger.error(f"Failed email delivery: to={to}, status={status_code}")
            return {'record_id': r.id, 'status': r.status, 'attempts': r.attempts, 'uuid': r.uuid, 'correlation_id': correlation_id}
        else:
            with db.session.begin():
                r = db.session.execute(
                    select(EmailMessage).where(EmailMessage.id == record_id).with_for_update()
                ).scalar_one()
                r.status = 'retry'
            app_logger.error(f"Failed email delivery: to={to}, status={status_code}")
            # Ask Celery to retry using its machinery
            self.retry(exc=Exception(f"Failed email delivery: {status_code}"), countdown=10, max_retries=5)


@shared_task(bind=True, name='email.add_to_queue', autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=60, retry_jitter=True, max_retries=3)
def add_to_queue_task(self, task_name, is_high_priority=False, *args, **kwargs):
    """
    Add a task to the email queue for processing.
    
    Args:
        task_name: Name of the task function to execute
        is_high_priority: Whether this is a high priority task (e.g., health check)
        *args, **kwargs: Arguments to pass to the task function
    """
    app_logger = logging.getLogger('app')
    app_logger.info(f"Adding task {task_name} to email queue, priority: {is_high_priority}")
    
    # Get the actual function by name
    if task_name == 'process_single_email':
        task_func = process_single_email
    elif task_name == 'process_health_check':
        task_func = process_health_check
        is_high_priority = True  # Health check is always high priority
    else:
        error_msg = f"Unknown task name: {task_name}"
        app_logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Add to queue
    task_id = email_queue.add_to_queue(task_func, is_high_priority, *args, **kwargs)
    
    app_logger.info(f"Task added to queue. Task ID: {task_id}, Priority: {is_high_priority}")
    
    # Try to process immediately if within rate limits
    if email_queue.can_process_request():
        result = email_queue.process_queue()
        if result:
            app_logger.info(f"Task processed immediately. Result: {result}")
            return result
        else:
            # Task remains in queue due to rate limits
            queue_length = email_queue.high_priority_queue.qsize() + email_queue.normal_queue.qsize()
            app_logger.info(f"Task remains in queue due to rate limits. Queue length: {queue_length}")
            return {'status': 'queued', 'task_id': task_id, 'queue_length': queue_length}
    else:
        # Task remains in queue due to rate limits
        queue_length = email_queue.high_priority_queue.qsize() + email_queue.normal_queue.qsize()
        app_logger.info(f"Task remains in queue due to rate limits. Queue length: {queue_length}")
        return {'status': 'queued', 'task_id': task_id, 'queue_length': queue_length}


def process_single_email(record_id: int, correlation_id: str = None):
    """
    Process a single email by calling the thread-safe utility function.
    """
    app_logger = logging.getLogger('app')
    
    # Get the email record from the database
    email_record = EmailMessage.query.get(record_id)
    if not email_record:
        error_msg = f"Email record not found: {record_id}"
        app_logger.error(error_msg)
        return {
            'status': 'failed',
            'error': 'record_not_found',
            'record_id': record_id,
            'correlation_id': correlation_id
        }
    
    app_logger.info(f"Audit: Processing email to {email_record.to}, correlation_id: {correlation_id}")
    
    # Decrypt the sensitive data
    try:
        from cryptography.fernet import Fernet
        import os
        encryption_key = os.getenv("ENCRYPTION_KEY")
        f = Fernet(encryption_key.encode())
        to_email = f.decrypt(email_record.to.encode()).decode()
        subject = f.decrypt(email_record.subject.encode()).decode()
        body = f.decrypt(email_record.body.encode()).decode()
    except Exception as e:
        error_msg = f"Failed to decrypt email data for record {record_id}: {str(e)}"
        app_logger.error(error_msg)
        return {
            'status': 'failed',
            'error': 'decryption_error',
            'record_id': record_id,
            'correlation_id': correlation_id
        }
    
    # Call the thread-safe utility function
    status_code, message_id_or_error = send_single_email_util(to_email, subject, body)
    
    if status_code == 200:
        success_msg = f"Email sent successfully to {to_email}, message_id: {message_id_or_error}"
        logging.getLogger('email').info(success_msg)
        app_logger.info(success_msg)
        return {
            'status': 'sent', 
            'to_email': to_email, 
            'message_id': message_id_or_error, 
            'record_id': record_id,
            'correlation_id': correlation_id,
            'status_code': status_code
        }
    else:
        error_msg = f"Failed to send email to {to_email}: {message_id_or_error}"
        logging.getLogger('email').error(error_msg)
        logging.getLogger('error').error(error_msg)
        return {
            'status': 'failed', 
            'to_email': to_email, 
            'error': message_id_or_error, 
            'record_id': record_id,
            'correlation_id': correlation_id,
            'status_code': status_code
        }


@shared_task(bind=True, name='email.send_email', autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=60, retry_jitter=True, max_retries=5)
def send_email_task(self, to, subject, body, correlation_id=None, record_id=None):
    """
    Send email with proper error handling and retry logic.

    correlation_id: propagated from incoming request for traceability.
    """
    from app.utils.email_util import send_single_email_util
    from app.extensions import db, email_sent_counter, email_failed_counter
    from app.models.email_message import EmailMessage
    from sqlalchemy import select
    from cryptography.fernet import Fernet
    import os
    
    attempt = self.request.retries + 1
    current_app.logger.info(f'email_task_start: task_id={self.request.id}, attempt={attempt}, to={to}, correlation_id={correlation_id}')
    
    # Validation
    from app.utils.email_util import validate_email, validate_subject, validate_body
    if not validate_email(to):
        raise ValueError("Invalid email address")
    if not validate_subject(subject):
        raise ValueError("Invalid subject")
    if not validate_body(body):
        raise ValueError("Invalid body content")
    
    try:
        # Try to send the email
        status_code, message_id = send_single_email_util(to, subject, body)
        
        # Update database based on result
        if status_code == 200:
            # Persist success
            if record_id:
                with db.session.begin():
                    msg = db.session.execute(
                        select(EmailMessage).where(EmailMessage.id == record_id).with_for_update()
                    ).scalar_one_or_none()
                    if msg:
                        msg.status = 'sent'
                        msg.attempts = attempt
            email_sent_counter.inc()
            result = {"status": "success", "to": to, "subject": subject, "attempt": attempt, "correlation_id": correlation_id, "message_id": message_id}
            current_app.logger.info(f'email_task_success: task_id={self.request.id}, result={result}, correlation_id={correlation_id}')
            return result
        else:
            # Log failure
            current_app.logger.error(f"Failed email delivery: to={to}, status={status_code}")
            # Update message status for tracking
            if record_id:
                with db.session.begin():
                    msg = db.session.execute(
                        select(EmailMessage).where(EmailMessage.id == record_id).with_for_update()
                    ).scalar_one_or_none()
                    if msg:
                        msg.status = 'retry' if attempt < 5 else 'failed'
                        msg.attempts = attempt
            if attempt >= 5:
                email_failed_counter.inc()
            # Retry if not at max attempts
            if attempt < 5:
                self.retry(exc=Exception(f"Failed email delivery: {status_code}"), countdown=10)
            else:
                # Final failure
                return {"status": "failed", "to": to, "attempt": attempt, "correlation_id": correlation_id}
                
    except Exception as exc:
        # Log the exception
        current_app.logger.error(f'email_task_error: task_id={self.request.id}, attempt={attempt}, error={str(exc)}, correlation_id={correlation_id}')
        # Update message status for tracking
        if record_id:
            with db.session.begin():
                msg = db.session.execute(
                    select(EmailMessage).where(EmailMessage.id == record_id).with_for_update()
                ).scalar_one_or_none()
                if msg:
                    msg.status = 'retry' if attempt < 5 else 'failed'
                    msg.attempts = attempt
        if attempt >= 5:
            email_failed_counter.inc()
        # Retry if not at max attempts
        if attempt < 5:
            self.retry(exc=exc, countdown=10)
        else:
            # Final failure
            raise exc


@shared_task(bind=True, name='email.process_health_check', autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=60, retry_jitter=True, max_retries=1)
def process_health_check_task(self):
    """
    Process a health check task with highest priority.
    This runs immediately without queuing.
    """
    app_logger = logging.getLogger('app')
    
    app_logger.info("Processing email service health check task")
    
    # Check if email service is properly configured
    try:
        # Attempt to get app context, fallback to environment variables
        smtp_server = None
        smtp_username = None
        
        try:
            from flask import current_app
            smtp_server = current_app.config.get('SMTP_SERVER')
            smtp_username = current_app.config.get('SMTP_USERNAME')
        except RuntimeError:
            # Not in Flask app context, try environment variables
            import os
            smtp_server = os.getenv('SMTP_SERVER')
            smtp_username = os.getenv('SMTP_USERNAME')
        
        if smtp_server and smtp_username:
            app_logger.info("Email service health check: configuration OK")
            return {"status": "healthy", "configured": True}
        else:
            error_msg = "Email service health check: missing SMTP configuration"
            app_logger.error(error_msg)
            return {"status": "unhealthy", "configured": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Email service health check failed: {str(e)}"
        logging.getLogger('error').error(error_msg)
        app_logger.error(error_msg)
        return {"status": "unhealthy", "configured": False, "error": error_msg}


def get_queue_status():
    """Return current queue status for monitoring"""
    return {
        'high_priority_queue_size': email_queue.high_priority_queue.qsize(),
        'normal_queue_size': email_queue.normal_queue.qsize(),
        'total_queue_size': email_queue.high_priority_queue.qsize() + email_queue.normal_queue.qsize(),
        'processed_count': email_queue.processed_count,
        'rate_limit': email_queue.rate_limit,
        'can_process_request': email_queue.can_process_request(),
        'last_reset_time': email_queue.last_reset_time
    }