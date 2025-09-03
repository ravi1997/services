from flask import Blueprint, request
from flask_restx import Api, Resource, fields
from app.utils.decorators import require_bearer_and_log, require_admin_bearer_and_log
from app.extensions import limiter
from app.schema.sms_schema import SMSSchema
from app.tasks.sms_tasks import send_sms_task, cancel_sms_task
from sqlalchemy import select, desc, asc
from datetime import datetime, timezone

sms_bp = Blueprint('sms', __name__)
api = Api(sms_bp, doc='/docs', title='SMS API', description='API for sending SMS and checking status')

sms_model = api.model('SMS', {
    'to': fields.String(required=True, description='Recipient phone number'),
    'message': fields.String(required=True, description='Message content')
})

sms_schema = SMSSchema()

# Models for documentation of list endpoint
sms_list_item = api.model('SMSMessageListItem', {
    'id': fields.Integer(description='Database ID'),
    'to': fields.String(description='Recipient phone number'),
    'status': fields.String(description='Current status'),
    'attempts': fields.Integer(description='Retry attempts'),
    'task_id': fields.String(description='Celery task ID'),
    'correlation_id': fields.String(description='Correlation ID'),
    'created_at': fields.String(description='Creation time ISO-8601'),
})

sms_list_response = api.model('SMSMessageList', {
    'items': fields.List(fields.Nested(sms_list_item)),
    'page': fields.Integer,
    'per_page': fields.Integer,
    'total': fields.Integer,
    'pages': fields.Integer,
})



@api.route('/send')
class SendSMS(Resource):
    method_decorators = [require_bearer_and_log]

    @api.expect(sms_model)
    def post(self):
        data = request.get_json()
        errors = sms_schema.validate(data)
        if errors:
            return {'errors': errors}, 400
        to = data['to']
        message = data['message']
        try:
            # Async SMS send
            corr_id = getattr(request, 'correlation_id', None)
            # Idempotency support
            idem_key = request.headers.get('Idempotency-Key')
            from flask import current_app
            db = current_app.db
            from app.models.sms_message import SMSMessage
            if idem_key:
                existing = db.session.query(SMSMessage).filter_by(correlation_id=idem_key, to=to, message=message).first()
                if existing and existing.task_id:
                    return {'task_id': existing.task_id, 'status': existing.status, 'correlation_id': corr_id, 'record_id': existing.id, 'idempotent': True}, 202
            # Create DB record
            msg = SMSMessage(to=to, message=message, status='queued', correlation_id=idem_key or corr_id)
            db.session.add(msg)
            db.session.commit()
            # In tests, avoid hitting a broker; otherwise queue via Celery
            if getattr(current_app, 'testing', False) or current_app.config.get('TESTING'):
                import uuid as _uuid
                fake_id = str(_uuid.uuid4())
                msg.task_id = fake_id
                db.session.commit()
                return {'task_id': fake_id, 'status': 'queued', 'correlation_id': corr_id, 'record_id': msg.id}, 202
            else:
                task = send_sms_task.delay(to, message, correlation_id=corr_id, record_id=msg.id)
                msg.task_id = task.id
                db.session.commit()
                return {'task_id': task.id, 'status': 'queued', 'correlation_id': corr_id, 'record_id': msg.id}, 202
        except Exception as e:
            api.logger.error(f"Failed to queue SMS: {e}")
            return {'error': 'Failed to queue SMS'}, 500


@api.route('/status/<string:sms_id>')
class SMSStatus(Resource):
    method_decorators = [require_bearer_and_log]

    def get(self, sms_id):
        # Try to fetch persisted status from DB by ID or task_id
        from flask import current_app
        db = current_app.db
        from app.models.sms_message import SMSMessage
        msg = None
        # Lookup by numeric primary key if possible, else by task_id
        try:
            msg_id = int(sms_id)
            msg = db.session.get(SMSMessage, msg_id)
        except ValueError:
            msg = db.session.query(SMSMessage).filter_by(task_id=sms_id).first()
        if not msg:
            return {'error': 'Not found', 'sms_id': sms_id}, 404
        return {'sms_id': sms_id, 'record': msg.as_dict(), 'status': msg.status}, 200


@api.route('/messages')
class SMSMessages(Resource):
    method_decorators = [require_admin_bearer_and_log]

    @api.doc(params={
        'page': 'Page number (default 1)',
        'per_page': 'Items per page (default 20, max 100)',
        'status': 'Filter by status (e.g., queued, sent)',
        'to': 'Filter by recipient phone number',
        'since': 'Filter by created_at >= ISO-8601 (e.g., 2025-01-01T00:00:00Z)',
        'until': 'Filter by created_at <= ISO-8601',
        'order': 'Sort by created_at: desc or asc (default desc)'
    })
    @api.marshal_with(sms_list_response, code=200, description='Paginated SMS messages')
    @limiter.limit(lambda: "1000 per minute" if __import__('flask').current_app.config.get('TESTING') else "5 per minute")
    def get(self):
        # Query with pagination and optional filters
        from flask import current_app
        db = current_app.db
        from app.models.sms_message import SMSMessage

        # Params
        args = request.args
        page = int(args.get('page', 1))
        per_page = int(args.get('per_page', 20))
        per_page = max(1, min(per_page, 100))
        status = args.get('status')
        to_value = args.get('to')
        order = args.get('order', 'desc').lower()
        since_s = args.get('since')
        until_s = args.get('until')

        stmt = select(SMSMessage)
        if status:
            stmt = stmt.where(SMSMessage.status == status)
        if to_value:
            # partial match if contains wildcard '*' else exact
            tv = to_value
            if '*' in tv:
                like = tv.replace('*', '%')
                stmt = stmt.where(SMSMessage.to.like(like))
            else:
                stmt = stmt.where(SMSMessage.to == tv)

        def parse_dt(value):
            if not value:
                return None
            raw = value.strip()
            # Normalize common variants (URL '+' decoded as space, 'Z' suffix)
            candidates = [raw]
            if raw.endswith('Z'):
                candidates.append(raw[:-1] + '+00:00')
            if ' ' in raw:
                try:
                    base, offset = raw.rsplit(' ', 1)
                    candidates.append(base + '+' + offset)
                except ValueError:
                    pass
            for cand in candidates:
                try:
                    dt = datetime.fromisoformat(cand)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except Exception:
                    continue
            return None

        since_dt = parse_dt(since_s)
        until_dt = parse_dt(until_s)
        if since_dt:
            stmt = stmt.where(SMSMessage.created_at >= since_dt)
        if until_dt:
            stmt = stmt.where(SMSMessage.created_at <= until_dt)

        stmt = stmt.order_by(desc(SMSMessage.created_at) if order == 'desc' else asc(SMSMessage.created_at))

        page_obj = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
        items = []
        for m in page_obj.items:
            items.append({
                'id': m.id,
                'to': m.to,
                'status': m.status,
                'attempts': m.attempts,
                'task_id': m.task_id,
                'correlation_id': m.correlation_id,
                'created_at': m.created_at.isoformat() if m.created_at else None,
            })

        return {
            'items': items,
            'page': page_obj.page,
            'per_page': page_obj.per_page,
            'total': page_obj.total,
            'pages': page_obj.pages
        }, 200

@api.route('/tasks/<string:task_id>')
class SMSTaskStatus(Resource):
    method_decorators = [require_bearer_and_log]
    def get(self, task_id):
        from flask import current_app
        from celery.result import AsyncResult
        result = AsyncResult(task_id)
        resp = {'task_id': task_id, 'state': result.state}
        if result.successful():
            resp['result'] = result.result
        elif result.failed():
            resp['error'] = str(result.result)
        return resp, 200

@api.route('/tasks/<string:task_id>/cancel')
class SMSTaskCancel(Resource):
    method_decorators = [require_bearer_and_log]
    def post(self, task_id):
        from flask import current_app
        from celery.result import AsyncResult
        async_res = AsyncResult(task_id)
        if async_res.state in ('PENDING', 'RETRY'):
            corr_id = getattr(request, 'correlation_id', None)
            async_res.revoke(terminate=False)
            cancel_sms_task.delay(task_id, correlation_id=corr_id)
            return {'task_id': task_id, 'status': 'revoked', 'correlation_id': corr_id}, 202
        return {'task_id': task_id, 'status': 'not_revoked', 'state': async_res.state}, 200
