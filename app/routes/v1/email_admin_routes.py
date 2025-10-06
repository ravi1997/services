from flask import Blueprint, request, current_app
from app.extensions import db
from app.models.email_message import EmailMessage
from app.utils.response import success, error
from app.utils.decorators import require_admin_bearer_and_log
from sqlalchemy import desc, asc
import datetime

email_admin_bp = Blueprint('email_admin', __name__)

@email_admin_bp.route('/messages', methods=['GET'])
@require_admin_bearer_and_log
def list_email_messages():
    q = EmailMessage.query
    status = request.args.get('status')
    to = request.args.get('to')
    since = request.args.get('since')
    until = request.args.get('until')
    order = request.args.get('order', 'desc')
    if status:
        q = q.filter(EmailMessage.status == status)
    if to:
        q = q.filter(EmailMessage.to == to)  # Note: this will be encrypted, need to handle appropriately
    if since:
        try:
            dt = datetime.datetime.fromisoformat(since.replace('Z','+00:00'))
            q = q.filter(EmailMessage.created_at >= dt)
        except ValueError:
            return error('Invalid since', 'BAD_PARAM', 400)
    if until:
        try:
            dt = datetime.datetime.fromisoformat(until.replace('Z','+00:00'))
            q = q.filter(EmailMessage.created_at <= dt)
        except ValueError:
            return error('Invalid until', 'BAD_PARAM', 400)
    q = q.order_by(desc(EmailMessage.created_at) if order != 'asc' else asc(EmailMessage.created_at))
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 20)), 100)
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    data = {
        'items': [m.as_dict() for m in pagination.items],
        'page': page,
        'per_page': per_page,
        'total': pagination.total,
        'pages': pagination.pages
    }
    return success('Email messages listed', data)

@email_admin_bp.route('/status/<int:record_id>', methods=['GET'])
@require_admin_bearer_and_log
def email_message_status(record_id):
    msg = EmailMessage.query.get(record_id)
    if not msg:
        return error('Not found', 'NOT_FOUND', 404)
    return success('Email message status', msg.as_dict())

@email_admin_bp.route('/tasks/<task_id>', methods=['GET'])
@require_admin_bearer_and_log
def email_task_status(task_id):
    celery = getattr(current_app, 'celery', None)
    if not celery:
        return error('Celery not configured', 'NO_CELERY', 400)
    async_res = celery.AsyncResult(task_id)
    return success('Task status', {'id': task_id, 'state': async_res.state, 'result': async_res.result if async_res.ready() else None})

@email_admin_bp.route('/tasks/<task_id>/cancel', methods=['POST'])
@require_admin_bearer_and_log
def cancel_email_task(task_id):
    celery = getattr(current_app, 'celery', None)
    if not celery:
        return error('Celery not configured', 'NO_CELERY', 400)
    async_res = celery.control.revoke(task_id, terminate=True)
    return success('Cancel requested', {'task_id': task_id, 'revoked': True})