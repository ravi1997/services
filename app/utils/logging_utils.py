import json
from logging import Formatter, getLogger, handlers
import re

SENSITIVE_FIELDS = ['password', 'token', 'api_key', 'secret', 'email', 'phone']

def mask_sensitive(data):
    if isinstance(data, dict):
        for k in data:
            if k.lower() in SENSITIVE_FIELDS:
                data[k] = '***MASKED***'
    return data

class JsonFormatter(Formatter):
    def format(self, record):
        payload = {
            'ts': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        extra = getattr(record, 'extra', None)
        if isinstance(extra, dict):
            payload.update(mask_sensitive(extra))
        # Mask sensitive info in message
        payload['message'] = re.sub(r'(password|token|api_key|secret|email|phone)[^\s:]*', '***MASKED***', payload['message'], flags=re.IGNORECASE)
        return json.dumps(payload, ensure_ascii=False)

def json_extra(**kwargs):
    return {'extra': mask_sensitive(kwargs)}

def setup_rotating_logger(name, log_file, max_bytes=10485760, backup_count=5):
    logger = getLogger(name)
    handler = handlers.RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel('INFO')
    return logger