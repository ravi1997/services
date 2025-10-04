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
 

class DevelopmentConfig(Config):
	DEBUG = True


class ProductionConfig(Config):
	DEBUG = False
