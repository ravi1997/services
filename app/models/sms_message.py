from datetime import datetime, timezone
from app.extensions import db
import re
import os
import logging
from cryptography.fernet import Fernet

# ---------- Safe Fernet helper ----------


def get_fernet() -> Fernet:
    """
    Lazily create a Fernet instance from ENCRYPTION_KEY.
    Raises RuntimeError with a clear message if missing or invalid.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Generate one with:\n"
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "and set it in your environment."
        )
    if isinstance(key, str):
        key = key.strip().encode()
    try:
        return Fernet(key)
    except Exception as e:
        raise RuntimeError(
            "Invalid ENCRYPTION_KEY: must be a URL-safe base64-encoded 32-byte key "
            "(44 characters long)."
        ) from e


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
    created_at = db.Column(
        db.DateTime(timezone=True),
        index=True,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    deleted_at = db.Column(db.DateTime(timezone=True),
                           nullable=True, index=True)

    def __init__(self, **kwargs):
        # Input validation and sanitization
        to = kwargs.get('to', '').strip()
        message = kwargs.get('message', '').strip()

        if not re.fullmatch(r'\+[1-9]\d{5,14}', to) and not re.fullmatch(r'[1-9]\d{5,14}', to):
            raise ValueError('Invalid phone number format')
        if len(to) < 6 or len(to) > 16:
            raise ValueError('Phone number length must be 6–16 digits')
        if not message or len(message) < 1 or len(message) > 500:
            raise ValueError('Message length must be 1–500 characters')
        if re.search(r'<script|SELECT|INSERT|UPDATE|DELETE|DROP|--', message, re.IGNORECASE):
            raise ValueError('Message contains forbidden content')

        # Set non-encrypted fields
        for k, v in kwargs.items():
            if k not in ['to', 'message']:
                setattr(self, k, v)

        # Encrypt sensitive fields only now
        fernet = get_fernet()
        self.to = fernet.encrypt(to.encode()).decode()
        self.message = fernet.encrypt(message.encode()).decode()

        # Audit log
        # PII Protection: Do not log the actual phone number in plain text
        logging.getLogger('audit_logger').info(
            f"Created SMSMessage: uuid={self.uuid}")

    def as_dict(self):
        fernet = None
        try:
            fernet = get_fernet()
        except Exception:
            pass  # If key invalid, we'll just return masked data

        to = None
        message = None
        if fernet:
            try:
                to = fernet.decrypt(self.to.encode()).decode()
            except Exception:
                pass
            try:
                message = fernet.decrypt(self.message.encode()).decode()
            except Exception:
                pass

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
        logging.getLogger('audit_logger').info(
            f"Soft deleted SMSMessage: uuid={self.uuid}")
