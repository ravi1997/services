from datetime import datetime, timezone
from app.extensions import db
import re
import os
import logging
from cryptography.fernet import Fernet


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


class EmailMessage(db.Model):  # type: ignore
    __tablename__ = 'email_messages'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), index=True, nullable=False, unique=True)
    to = db.Column(db.String(255), index=True, nullable=False)  # Encrypted
    subject = db.Column(db.String(500), nullable=False)  # Encrypted
    body = db.Column(db.Text, nullable=False)  # Encrypted
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
        subject = kwargs.get('subject', '').strip()
        body = kwargs.get('body', '').strip()

        # Email format validation
        email_pattern = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
        if not email_pattern.fullmatch(to):
            raise ValueError('Invalid email address format')
        if len(to) > 255:
            raise ValueError('Email address too long')
        if not subject or len(subject) > 500:
            raise ValueError('Subject length must be 1–500 characters')
        if not body or len(body) > 10000:  # 10KB max
            raise ValueError('Body length must be 1–10000 characters')
        # Check for forbidden content
        forbidden = ["<script", "SELECT", "INSERT", "DELETE", "UPDATE", "DROP"]
        content_to_check = (subject + " " + body).upper()
        if any(f in content_to_check for f in forbidden):
            raise ValueError('Message contains forbidden content')

        # Set non-encrypted fields
        for k, v in kwargs.items():
            if k not in ['to', 'subject', 'body']:
                setattr(self, k, v)

        # Encrypt sensitive fields
        fernet = get_fernet()
        self.to = fernet.encrypt(to.encode()).decode()
        self.subject = fernet.encrypt(subject.encode()).decode()
        self.body = fernet.encrypt(body.encode()).decode()

        # Audit log
        # PII Protection: Do not log the actual email in plain text
        logging.getLogger('audit_logger').info(
            f"Created EmailMessage: uuid={self.uuid}")

    def as_dict(self):
        fernet = None
        try:
            fernet = get_fernet()
        except Exception:
            pass  # If key invalid, we'll just return masked data

        to = None
        subject = None
        body = None
        if fernet:
            try:
                to = fernet.decrypt(self.to.encode()).decode()
            except Exception:
                pass
            try:
                subject = fernet.decrypt(self.subject.encode()).decode()
            except Exception:
                pass
            try:
                body = fernet.decrypt(self.body.encode()).decode()
            except Exception:
                pass

        return {
            'id': self.id,
            'uuid': self.uuid,
            'to': to,
            'subject': subject,
            'body': body,
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
            f"Soft deleted EmailMessage: uuid={self.uuid}")