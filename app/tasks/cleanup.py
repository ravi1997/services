from app.extensions import celery, db
from app.models.sms_message import SMSMessage
from app.models.email_message import EmailMessage
from datetime import datetime, timedelta, timezone
import logging
import os

# We need to access app context inside the task
from flask import current_app

@celery.task(name='cleanup_old_data')
def cleanup_old_data():
    """
    Hard delete records older than DATA_RETENTION_DAYS.
    This ensures PHI/PII is not retained indefinitely.
    """
    # Default to 30 days if not configured
    days = 30
    if current_app:
        days = current_app.config.get('DATA_RETENTION_DAYS', 30)
    else:
        # Fallback if no app context (unlikely in Celery with Flask)
        days = int(os.getenv('DATA_RETENTION_DAYS', 30))

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    logger = logging.getLogger('app')
    
    logger.info(f"Starting data retention cleanup. Threshold: {days} days (older than {cutoff.isoformat()})")
    
    try:
        # Bulk delete is more efficient
        # Note: cascaded deletions might need attention if there are related tables, 
        # but currently these are standalone content tables.
        
        sms_count = SMSMessage.query.filter(SMSMessage.created_at < cutoff).delete()
        email_count = EmailMessage.query.filter(EmailMessage.created_at < cutoff).delete()
        
        db.session.commit()
        
        logger.info(f"Data retention cleanup complete. Deleted: {sms_count} SMS, {email_count} Email records.")
        return {'sms_deleted': sms_count, 'email_deleted': email_count}
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during data retention cleanup: {str(e)}")
        # Re-raise to let Celery know it failed
        raise e
