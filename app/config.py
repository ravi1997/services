import os
import secrets
from dotenv import load_dotenv

load_dotenv()


class Config:
	# Core - Generate strong secret if not provided
	_secret_key = os.getenv('SECRET_KEY')
	if not _secret_key or _secret_key == 'change-me':
		# Generate a strong random secret key
		_secret_key = secrets.token_hex(32)
		# In production, this should fail-fast instead
		if os.getenv('APP_ENV', 'development').lower() == 'production':
			raise ValueError(
				"SECRET_KEY must be set in production environment. "
				"Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
			)
	SECRET_KEY = _secret_key
	DEBUG = os.getenv('DEBUG', 'True') == 'True'

	ADMIN_API_KEY = os.getenv('ADMIN_API_KEY')

	# Security: Session configuration
	SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True') == 'True'  # HTTPS only
	SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
	SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
	PERMANENT_SESSION_LIFETIME = 3600  # 1 hour session timeout
	
	# Security: Request size limits (10MB default, prevents DoS)
	MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))
	
	# Security: Content Security Policy (can be customized)
	CONTENT_SECURITY_POLICY = os.getenv('CONTENT_SECURITY_POLICY', 
		"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
		"img-src 'self' data:; font-src 'self'; connect-src 'self'; "
		"frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
	)

	# Database (default to in-memory SQLite if none provided)
	SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///:memory:')
	SQLALCHEMY_TRACK_MODIFICATIONS = False

	# Rate limiting
	DEFAULT_RATE_LIMIT = os.getenv('DEFAULT_RATE_LIMIT', '30 per minute')
	# Rate limit storage (used by Flask-Limiter). Default to Redis on localhost (db 2)
	RATELIMIT_STORAGE_URI = os.getenv('RATELIMIT_STORAGE_URI', 'redis://localhost:6379/2')

	# Celery / Redis (optional async queue)
	CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')
	CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND')

	# SMS API key (for potential auth decorator) and provider config
	SMS_API_KEY = os.getenv('SMS_API_KEY')
	if not SMS_API_KEY and os.getenv('APP_ENV', 'development').lower() == 'production':
		raise ValueError("SMS_API_KEY must be set in production environment")

	# OTP / SOAP gateway credentials (used by sms_service)
	OTP_USERNAME = os.getenv('OTP_USERNAME')
	OTP_PASSWORD = os.getenv('OTP_PASSWORD')
	OTP_SERVER = os.getenv('OTP_SERVER')
	OTP_ID = os.getenv('OTP_ID')
	OTP_SENDERID = os.getenv('OTP_SENDERID')
	OTP_FLAG = os.getenv('OTP_FLAG', 'True') == 'True'  # enable real sending by default if configured
	LOG_RETENTION_MONTHS = int(os.getenv('LOG_RETENTION_MONTHS', 8))
	TRACE_ENABLED = os.getenv('TRACE_ENABLED', 'False') == 'True'
	
	# Admin API key - must be set in production
	ADMIN_API_KEY = os.getenv('ADMIN_API_KEY')
	if not ADMIN_API_KEY and os.getenv('APP_ENV', 'development').lower() == 'production':
		raise ValueError("ADMIN_API_KEY must be set in production environment")

	# Encryption key for sensitive data - MUST be set, no default
	ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
	if not ENCRYPTION_KEY:
		if os.getenv('APP_ENV', 'development').lower() == 'production':
			raise ValueError(
				"ENCRYPTION_KEY must be set in production environment. "
				"Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
			)
		else:
			# Development only - generate temporary key
			ENCRYPTION_KEY = secrets.token_hex(32)

	# CDAC API configuration
	CDAC_SERVER = os.getenv('CDAC_SERVER', 'https://example-cdac-api.com')
	CDAC_AUTH_BEARER = os.getenv('CDAC_AUTH_BEARER')
	# Allow access to CDAC API (can be set to False to disable)
	CAN_ACCESS_CDAC = os.getenv('CAN_ACCESS_CDAC', 'True') == 'True'
 
	# eHospital API configuration
	EHOSPITAL_INIT_URL = os.getenv('EHOSPITAL_INIT_URL', 'https://example-ehospital-api.com/init')
	EHOSPITAL_FETCH_PATIENT_URL = os.getenv('EHOSPITAL_FETCH_PATIENT_URL', 'https://example-ehospital-api.com/fetchPatientFullDetails')
	EHOSPITAL_USERNAME = os.getenv('EHOSPITAL_USERNAME')
	EHOSPITAL_PASSWORD = os.getenv('EHOSPITAL_PASSWORD')
	EHOSPITAL_HOSPITAL_ID = os.getenv('EHOSPITAL_HOSPITAL_ID', '1')
 
 
	# Email configuration
	SMTP_SERVER = os.getenv('SMTP_SERVER', 'localhost')
	SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
	SMTP_USERNAME = os.getenv('SMTP_USERNAME')
	SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
	SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL', 'noreply@example.com')
	SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True') == 'True'

	HEALTH_CHECK_TEST_NUMBER = os.getenv('HEALTH_CHECK_TEST_NUMBER', '9876543210')

	# IP Allowlisting
	# Parse comma-separated lists from env, or use defaults
	ALLOWED_IP_PREFIXES = tuple(
		p.strip() for p in os.getenv('ALLOWED_IP_PREFIXES', '192.168.8.').split(',') if p.strip()
	)
	
	ALLOWED_IPS = set(
		ip.strip() for ip in os.getenv('ALLOWED_IPS', 
			'123.252.211.122,45.64.84.98,35.207.200.220,35.207.210.89'
		).split(',') if ip.strip()
	)




class DevelopmentConfig(Config):
	DEBUG = True
	# Development can have relaxed session security for localhost
	SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
	DEBUG = False
	# Production must have secure sessions
	SESSION_COOKIE_SECURE = True
	# Enforce HTTPS
	PREFERRED_URL_SCHEME = 'https'
