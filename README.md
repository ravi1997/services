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

## Admin Access
- Admin-only endpoints (e.g., listing messages) require an `ADMIN_API_KEY`.
- Set `ADMIN_API_KEY` in your environment or `.env` file.
- Use header: `Authorization: Bearer <ADMIN_API_KEY>`.

## Getting Started
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# run tests to verify setup
pytest -q
```

## Quick Start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SMS_API_KEY=your-sms-api-key
export ADMIN_API_KEY=your-admin-api-key
redis-server &  # ensure Redis is running
python run.py
```

Start Celery worker in another terminal:
```bash
source .venv/bin/activate
celery -A app.celery worker --loglevel=info
```

### Database Migrations (Alembic)
```bash
# create a new migration from model changes
make db-revision
# apply migrations
make db-upgrade
# see current revision
make db-current
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
ADMIN_API_KEY=your-admin-api-key

## Metrics
- Prometheus endpoint: `GET /metrics` (exposes default process metrics).
  - Add to your Prometheus scrape configs.

## API
Docs: http://localhost:5000/api/v1/sms/docs

### Send SMS
POST /api/v1/sms/send
Authorization: Bearer <SMS_API_KEY>
Body: {"to": "+911234567890", "message": "Hello"}
Response (202): {"task_id": "<uuid>", "status": "queued"}
Notes:
- Optional `Idempotency-Key` header can be provided to avoid duplicate sends with the same payload.

### Admin: List SMS Messages
GET /api/v1/sms/messages
Authorization: Bearer <ADMIN_API_KEY>
Query params:
- page: page number (default 1)
- per_page: items per page (default 20, max 100)
- status: filter by status (e.g., queued, sent)
- to: filter by recipient
- since: ISO-8601 timestamp, created_at >= since (e.g., 2025-01-01T00:00:00Z)
- until: ISO-8601 timestamp, created_at <= until
- order: desc|asc (default desc)
Response (200): {"items": [...], "page": 1, "per_page": 20, "total": 35, "pages": 2}
Rate limit: 5 requests/min per client.

Example:
```bash
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
  "http://localhost:5000/api/v1/sms/messages?status=sent&per_page=10"
```

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

## Security
- Keep `SMS_API_KEY` and `ADMIN_API_KEY` out of logs and code. Use environment variables or a secret manager.
- Rotate keys regularly and immediately after suspected exposure.
- Prefer least-privilege: use a separate admin key for admin endpoints.
- Avoid sending secrets in URLs; use headers. Our request/response logger masks fields containing key/token/password.

## Further Improvements
- Persist SMS tasks/results to DB
- Real provider integration
- JWT auth / multi-user tokens
- Distributed tracing (OpenTelemetry)
- Structured JSON logs for ELK
- Correlation ID propagation into downstream services

## License
Internal / Private
