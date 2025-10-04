# Secure, robust email_service.py implementation
import re
import logging
import time

RATE_LIMIT = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 20    # max emails per window per IP

def validate_email(email):
	# Basic email validation
	if not isinstance(email, str) or not email:
		return False
	return re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email)

def validate_message(msg):
	if not isinstance(msg, str) or not msg.strip():
		return False
	if len(msg) > 1000:
		return False
	if re.search(r'<script|SELECT|INSERT|UPDATE|DELETE|DROP|--', msg, re.IGNORECASE):
		return False
	return True

def check_rate_limit(ip):
	now = int(time.time())
	window = now // RATE_LIMIT_WINDOW
	key = f"{ip}:{window}"
	count = RATE_LIMIT.get(key, 0)
	if count >= RATE_LIMIT_MAX:
		return False
	RATE_LIMIT[key] = count + 1
	return True

def send_email(to_email, message, ip='127.0.0.1'):
	logger = logging.getLogger('email_logger')
	if not validate_email(to_email):
		logger.error(f"Invalid email address: {to_email}")
		return False
	if not validate_message(message):
		logger.error(f"Invalid email message content")
		return False
	if not check_rate_limit(ip):
		logger.warning(f"Rate limit exceeded for IP: {ip}")
		return False
	try:
		# Simulate email sending (replace with actual email logic)
		logger.info(f"Email sent to {to_email} from IP {ip}")
		return True
	except Exception as ex:
		logger.error(f"Failed to send email to {to_email}: {ex}")
		return False
