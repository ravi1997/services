from datetime import datetime, timezone
from app.extensions import db
import re
import os
import logging
from cryptography.fernet import Fernet

# Get encryption key from environment, with fallback
encryption_key = os.getenv('ENCRYPTION_KEY', '0123456789abcdef0123456789abcdef')
# Ensure the encryption key is properly formatted for Fernet (must be 32 bytes URL-safe base64 encoded)
if isinstance(encryption_key, str) and len(encryption_key) != 32:
    # If it's not the right length, we need to encode it properly
    import base64
    import hashlib
    # Create a proper 32-byte key from the string
    key_bytes = hashlib.sha256(encryption_key.encode()).digest()
    _ENCRYPTION_KEY = base64.urlsafe_b64encode(key_bytes)
else:
    _ENCRYPTION_KEY = encryption_key.encode() if isinstance(encryption_key, str) else encryption_key
fernet = Fernet(_ENCRYPTION_KEY)

class SMSMessage(db.Model):  # type: ignore
    __tablename__ = 'sms_messages'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), index=True, nullable=False, unique=True)
    to = db.Column(db.String(32), index=True, nullable=False)
    message = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(32), index=True, default='queued')
    task_id = db.Column(db.String(64), unique=True)
    correlation_id = db.Column(db.String(64), index=True)
    attempts = db.Column(db.Integer, default=0)
    idempotency_key = db.Column(db.String(64), unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), index=True, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    def __init__(self, **kwargs):
        # Input validation and sanitization
        to = kwargs.get('to', '').strip()
        message = kwargs.get('message', '').strip()
        if not re.fullmatch(r'\+[1-9]\d{5,14}', to) and not re.fullmatch(r'[1-9]\d{5,14}', to):
            raise ValueError('Invalid phone number format')
        if len(to) < 6 or len(to) > 16:
            raise ValueError('Phone number length must be 6-16 digits')
        if not message or len(message) < 1 or len(message) > 500:
            raise ValueError('Message length must be 1-500 characters')
        if re.search(r'<script|SELECT|INSERT|UPDATE|DELETE|DROP|--', message, re.IGNORECASE):
            raise ValueError('Message contains forbidden content')
        # Set other fields before encryption to allow setting of uuid, etc.
        for k, v in kwargs.items():
            if k not in ['to', 'message']:
                setattr(self, k, v)
        # Encrypt sensitive fields
        self.to = fernet.encrypt(to.encode()).decode()
        self.message = fernet.encrypt(message.encode()).decode()
        # Create logger after setting other fields
        logger = logging.getLogger('audit_logger')
        logger.info(f"Created SMSMessage: uuid={self.uuid}, to={to}")

    def as_dict(self):
        # Decrypt sensitive fields
        try:
            to = fernet.decrypt(self.to.encode()).decode()
        except Exception:
            to = None
        try:
            message = fernet.decrypt(self.message.encode()).decode()
        except Exception:
            message = None
        return {
            'id': self.id,
            'uuid': self.uuid,
            'to': to,
            'message': message,
            'status': self.status,
            'task_id': self.task_id,
            'correlation_id': self.correlation_id,
            'attempts': self.attempts,
            'idempotency_key': self.idempotency_key,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def soft_delete(self):
        self.deleted_at = datetime.now(timezone.utc)
        logger = logging.getLogger('audit_logger')
        logger.info(f"Soft deleted SMSMessage: uuid={self.uuid}")
