from flask import Blueprint, request
from flask_restx import Api, Resource, fields
from app.utils.decorators import require_bearer_and_log
from app.schema.sms_schema import SMSSchema
from app.tasks.sms_tasks import send_sms_task, cancel_sms_task

sms_bp = Blueprint('sms', __name__)
api = Api(sms_bp, doc='/docs', title='SMS API', description='API for sending SMS and checking status')

sms_model = api.model('SMS', {
    'to': fields.String(required=True, description='Recipient phone number'),
    'message': fields.String(required=True, description='Message content')
})

sms_schema = SMSSchema()



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
            # Create DB record
            from flask import current_app
            db = current_app.db
            from app.models.sms_message import SMSMessage
            msg = SMSMessage(to=to, message=message, status='queued', correlation_id=corr_id)
            db.session.add(msg)
            db.session.commit()
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
        # In production, fetch status from SMS provider or DB
        return {'sms_id': sms_id, 'status': 'delivered'}, 200

@api.route('/tasks/<string:task_id>')
class SMSTaskStatus(Resource):
    method_decorators = [require_bearer_and_log]
    def get(self, task_id):
        from flask import current_app
        from celery.result import AsyncResult
        result = AsyncResult(task_id, app=current_app.celery)
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
        async_res = AsyncResult(task_id, app=current_app.celery)
        if async_res.state in ('PENDING', 'RETRY'):
            corr_id = getattr(request, 'correlation_id', None)
            async_res.revoke(terminate=False)
            cancel_sms_task.delay(task_id, correlation_id=corr_id)
            return {'task_id': task_id, 'status': 'revoked', 'correlation_id': corr_id}, 202
        return {'task_id': task_id, 'status': 'not_revoked', 'state': async_res.state}, 200
