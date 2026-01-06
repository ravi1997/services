from flask import Blueprint, request, current_app
from app.extensions import db
from app.models.sms_message import SMSMessage
from app.utils.response import success, error
from app.utils.decorators import require_admin_bearer_and_log
from sqlalchemy import desc, asc
import datetime

sms_admin_bp = Blueprint('sms_admin', __name__)

@sms_admin_bp.route('/messages', methods=['GET'])
@require_admin_bearer_and_log
def list_messages():
    # Only show records that aren't soft-deleted
    q = SMSMessage.query.filter(SMSMessage.deleted_at == None)
    
    status = request.args.get('status')
    to = request.args.get('to')
    since = request.args.get('since')
    until = request.args.get('until')
    order = request.args.get('order', 'desc')
    
    if status:
        q = q.filter(SMSMessage.status == status)
    
    if to:
        # WARNING: SMSMessage.to is encrypted. 
        # Standard equality filtering will not work without a deterministic hash (blind index).
        # We'll log a warning and return an error for now to avoid silent failures.
        current_app.logger.warning(f"Filter by 'to' attempted on encrypted field. Query results may be inaccurate.")
        return error("Searching by phone number is currently unsupported due to encryption", "NOT_SUPPORTED", 400)

    if since:
        try:
            dt = datetime.datetime.fromisoformat(since.replace('Z','+00:00'))
            q = q.filter(SMSMessage.created_at >= dt)
        except ValueError:
            return error('Invalid since', 'BAD_PARAM', 400)
    if until:
        try:
            dt = datetime.datetime.fromisoformat(until.replace('Z','+00:00'))
            q = q.filter(SMSMessage.created_at <= dt)
        except ValueError:
            return error('Invalid until', 'BAD_PARAM', 400)
            
    q = q.order_by(desc(SMSMessage.created_at) if order != 'asc' else asc(SMSMessage.created_at))
    
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        if page < 1 or per_page < 1:
            raise ValueError()
    except ValueError:
        return error('Invalid pagination parameters', 'BAD_PARAM', 400)

    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    data = {
        'items': [m.as_dict() for m in pagination.items],
        'page': page,
        'per_page': per_page,
        'total': pagination.total,
        'pages': pagination.pages
    }
    return success('Messages listed', data)

@sms_admin_bp.route('/status/<int:record_id>', methods=['GET'])
@require_admin_bearer_and_log
def message_status(record_id):
    msg = SMSMessage.query.get(record_id)
    if not msg:
        return error('Not found', 'NOT_FOUND', 404)
    return success('Message status', msg.as_dict())

@sms_admin_bp.route('/tasks/<task_id>', methods=['GET'])
@require_admin_bearer_and_log
def task_status(task_id):
    celery = getattr(current_app, 'celery', None)
    if not celery:
        return error('Celery not configured', 'NO_CELERY', 400)
    async_res = celery.AsyncResult(task_id)
    return success('Task status', {'id': task_id, 'state': async_res.state, 'result': async_res.result if async_res.ready() else None})

@sms_admin_bp.route('/tasks/<task_id>/cancel', methods=['POST'])
@require_admin_bearer_and_log
def cancel_task(task_id):
    celery = getattr(current_app, 'celery', None)
    if not celery:
        return error('Celery not configured', 'NO_CELERY', 400)
    async_res = celery.control.revoke(task_id, terminate=True)
    return success('Cancel requested', {'task_id': task_id, 'revoked': True})
