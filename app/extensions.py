import logging
from logging.handlers import RotatingFileHandler
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from prometheus_client import Counter
import os

# Initialize extensions
db = SQLAlchemy()
limiter = Limiter(key_func=get_remote_address)

# Metrics
sms_sent_counter = Counter('sms_sent_total', 'Total SMS successfully sent')
sms_failed_counter = Counter('sms_failed_total', 'Total SMS failed to send')
sms_queued_counter = Counter('sms_queued_total', 'Total SMS queued for async send')

# Email metrics
email_sent_counter = Counter('email_sent_total', 'Total emails successfully sent')
email_failed_counter = Counter('email_failed_total', 'Total emails failed to send')
email_queued_counter = Counter('email_queued_total', 'Total emails queued for async send')

def init_logging(json_logs: bool = False):
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Set up different loggers
    loggers = {
        'app': 'logs/app.log',
        'access': 'logs/access.log',
        'sms': 'logs/sms.log',
        'email': 'logs/email.log',  # Add email logger
        'error': 'logs/error.log'
    }
    
    level = logging.INFO
    fmt = '%(asctime)s %(levelname)s %(name)s %(message)s'
    formatter = logging.Formatter(fmt)
    
    for logger_name, log_file in loggers.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        
        # Create rotating file handler
        handler = RotatingFileHandler(log_file, maxBytes=10485760, backupCount=5)  # 10MB files, keep 5 backups
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    # Also keep console handler for general logging
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Prevent duplicate logs by setting propagate to False for specific loggers
    logging.getLogger('error').propagate = False
    logging.getLogger('access').propagate = False
    logging.getLogger('app').propagate = False
    logging.getLogger('sms').propagate = False
    logging.getLogger('email').propagate = False  # Add email logger to prevent duplicate logs
