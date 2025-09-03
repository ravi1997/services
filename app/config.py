import os
from dotenv import load_dotenv

load_dotenv()



class Config:
	SECRET_KEY = os.getenv('SECRET_KEY', 'your-default-secret-key')
	DEBUG = os.getenv('DEBUG', 'True') == 'True'
	# Admin API key for privileged endpoints
	ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', 'your-admin-api-key')
	# Add SMS service config if needed, e.g. API keys, endpoints
	SMS_API_URL = os.getenv('SMS_API_URL', 'https://api.example.com/sms')
	SMS_API_KEY = os.getenv('SMS_API_KEY', 'your-sms-api-key')
	# Log retention in months
	LOG_RETENTION_MONTHS = int(os.getenv('LOG_RETENTION_MONTHS', 8))
	# Celery config
	CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
	CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
	# Rate limit default
	DEFAULT_RATE_LIMIT = os.getenv('DEFAULT_RATE_LIMIT', '1000 per minute')
	# Limiter storage URI (Redis recommended)
	RATELIMIT_STORAGE_URI = os.getenv('RATELIMIT_STORAGE_URI', os.getenv('LIMITER_STORAGE_URI', 'redis://localhost:6379/1'))
	# Flask-Limiter default limits (read by extension)
	RATELIMIT_DEFAULT = DEFAULT_RATE_LIMIT
	# Structured JSON logging toggle
	JSON_LOGS = os.getenv('JSON_LOGS', 'True') == 'True'
	TRACE_ENABLED = os.getenv('TRACE_ENABLED', 'True') == 'True'
	# Database (SQLite default)
	SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///sms.db')
	SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
	DEBUG = True

class ProductionConfig(Config):
	DEBUG = False
