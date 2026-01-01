import os
from dotenv import load_dotenv

load_dotenv()


class Config:
	# Core
	SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')
	DEBUG = os.getenv('DEBUG', 'True') == 'True'

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
	SMS_API_KEY = os.getenv('SMS_API_KEY', 'your-sms-api-key')

	# OTP / SOAP gateway credentials (used by sms_service)
	OTP_USERNAME = os.getenv('OTP_USERNAME')
	OTP_PASSWORD = os.getenv('OTP_PASSWORD')
	OTP_SERVER = os.getenv('OTP_SERVER')
	OTP_ID = os.getenv('OTP_ID')
	OTP_SENDERID = os.getenv('OTP_SENDERID')
	OTP_FLAG = os.getenv('OTP_FLAG', 'True') == 'True'  # enable real sending by default if configured
	LOG_RETENTION_MONTHS = int(os.getenv('LOG_RETENTION_MONTHS', 8))
	TRACE_ENABLED = os.getenv('TRACE_ENABLED', 'False') == 'True'
	ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', 'your-admin-api-key')

	# Encryption key for sensitive data
	ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '0123456789abcdef0123456789abcdef')

	# CDAC API configuration
	CDAC_SERVER = os.getenv('CDAC_SERVER', 'https://example-cdac-api.com')
	CDAC_AUTH_BEARER = os.getenv('CDAC_AUTH_BEARER', 'your-cdac-auth-bearer-token')
	# Allow access to CDAC API (can be set to False to disable)
	CAN_ACCESS_CDAC = os.getenv('CAN_ACCESS_CDAC', 'True') == 'True'
 
	# eHospital API configuration
	EHOSPITAL_INIT_URL = os.getenv('EHOSPITAL_INIT_URL', 'https://example-ehospital-api.com/init')
	EHOSPITAL_FETCH_PATIENT_URL = os.getenv('EHOSPITAL_FETCH_PATIENT_URL', 'https://example-ehospital-api.com/fetchPatientFullDetails')
	EHOSPITAL_USERNAME = os.getenv('EHOSPITAL_USERNAME', 'your-ehospital-username')
	EHOSPITAL_PASSWORD = os.getenv('EHOSPITAL_PASSWORD', 'your-ehospital-password')
	EHOSPITAL_HOSPITAL_ID = os.getenv('EHOSPITAL_HOSPITAL_ID', '1')
 
 
	# Email configuration
	SMTP_SERVER = os.getenv('SMTP_SERVER', 'localhost')
	SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
	SMTP_USERNAME = os.getenv('SMTP_USERNAME')
	SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
	SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL', 'noreply@example.com')
	SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True') == 'True'




class DevelopmentConfig(Config):
	DEBUG = True


class ProductionConfig(Config):
	DEBUG = False
