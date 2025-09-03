# AIIMS SMS Service

Lightweight Flask service providing SMS endpoints with authentication, logging, rate limiting, async task queue, and API docs.

## Features
- Versioned API (`/api/v1/sms`)
- Bearer token auth via decorator
- Structured logging (access, app, error) + rotation + retention cleanup
- On-demand and startup log cleanup
- Rate limiting (Flask-Limiter)
- Request/response logging with masking
- Async SMS queue via Celery + Redis
- Correlation / Request IDs (X-Request-ID)
- OpenTelemetry tracing (console exporter)
- Marshmallow validation + Swagger docs (Flask-RESTX)
- Health check `/health`
- Tests (pytest)

## Quick Start
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
redis-server &  # ensure Redis is running
python run.py
```

Start Celery worker in another terminal:
```bash
source venv/bin/activate
celery -A app.celery worker --loglevel=info
```

## Environment Variables (.env)
SECRET_KEY=change-me
SMS_API_KEY=your-sms-api-key
APP_ENV=development  # or production
LOG_RETENTION_MONTHS=8
DEFAULT_RATE_LIMIT="10 per minute"
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
RATELIMIT_STORAGE_URI=redis://localhost:6379/1
JSON_LOGS=True
TRACE_ENABLED=True  # set False to disable OpenTelemetry setup

## API
Docs: http://localhost:5000/api/v1/sms/docs

### Send SMS
POST /api/v1/sms/send
Authorization: Bearer <SMS_API_KEY>
Body: {"to": "+911234567890", "message": "Hello"}
Response (202): {"task_id": "<uuid>", "status": "queued"}

### Status (Mock)
GET /api/v1/sms/status/<sms_id>

### Task Status
GET /api/v1/sms/tasks/<task_id>

### Cancel Task
POST /api/v1/sms/tasks/<task_id>/cancel

### Log Cleanup
POST /api/v1/logs/cleanup (rate-limited)

### Health
GET /health

## Testing
```bash
pytest -q
```

## Further Improvements
- Persist SMS tasks/results to DB
- Real provider integration
- JWT auth / multi-user tokens
- Distributed tracing (OpenTelemetry)
- Structured JSON logs for ELK
- Correlation ID propagation into downstream services

## License
Internal / Private