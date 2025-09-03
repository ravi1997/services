from datetime import datetime, timezone
from app.extensions import db


class SMSMessage(db.Model):
    __tablename__ = 'sms_messages'
    id = db.Column(db.Integer, primary_key=True)
    to = db.Column(db.String(32), index=True, nullable=False)
    message = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(32), index=True, default='queued')
    task_id = db.Column(db.String(64), unique=True)
    correlation_id = db.Column(db.String(64), index=True)
    attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}