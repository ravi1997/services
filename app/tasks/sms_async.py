from celery import shared_task
from app.utils.sms_service import send_sms
import uuid

@shared_task(bind=True, name='sms.send_single')
def send_single_sms_task(self, mobile, message):
    import re
    from time import time
    # Input validation
    phone_pattern = re.compile(r"^\d{6,16}$")
    if not phone_pattern.match(str(mobile)):
        self.retry(exc=ValueError("Invalid phone number"), countdown=10, max_retries=3)
    if not isinstance(message, str) or not (1 <= len(message) <= 500):
        self.retry(exc=ValueError("Invalid message length"), countdown=10, max_retries=3)
    forbidden = ["<script", "SELECT ", "INSERT ", "DELETE ", "UPDATE ", "DROP "]
    if any(f in message.upper() for f in forbidden):
        self.retry(exc=ValueError("Forbidden content in SMS message"), countdown=10, max_retries=3)
    # Simple rate limiting (per mobile number, 1 SMS per 10 seconds)
    if not hasattr(self, "sms_rate_limit"): self.sms_rate_limit = {}
    now = time()
    last_sent = self.sms_rate_limit.get(mobile, 0)
    if now - last_sent < 10:
        self.retry(exc=ValueError("Rate limit exceeded for mobile"), countdown=10, max_retries=3)
    self.sms_rate_limit[mobile] = now
    # Audit logging
    self.request.logger.info(f"Audit: Sending SMS to {mobile}")
    status = send_sms(mobile, message)
    if status != 200:
        self.request.logger.error(f"Failed SMS delivery: mobile={mobile}, status={status}")
        self.retry(exc=Exception("Failed SMS delivery"), countdown=10, max_retries=3)
    return {"mobile": mobile, "status_code": status, "message_id": str(uuid.uuid4()) if status == 200 else None}