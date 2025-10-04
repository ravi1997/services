# AIIMS Messaging Microservice (Minimal)

Minimal Flask service exposing only the required messaging-related endpoints:

* SMS: `/api/v1/sms/single`, `/api/v1/sms/bulk`, `/api/v1/sms/health`
* Email (mock): `/api/v1/mail/send`, `/api/v1/mail/bulk_send`, `/api/v1/mail/health`
* CDAC (mock): `/api/v1/cdac/fetch`, `/api/v1/cdac/bulk_fetch`, `/api/v1/cdac/health`
* eHospital (mock): `/api/v1/ehospital/patient`, `/api/v1/ehospital/bulk_patient`, `/api/v1/ehospital/health`
* Global health: `/health`

Swagger-style docs for SMS endpoints are available at: `http://localhost:5000/api/v1/sms/docs`.

## Current Capabilities
* Input validation (Marshmallow) for SMS numbers + message length (<=500 chars)
* Bulk SMS partial success reporting (HTTP 207 when mixed results)
* Optional async dispatch via Celery + Redis (if broker URLs provided)
* Basic per-client rate limiting (default 30/min) via Flask-Limiter
* Bearer token auth (set `SMS_API_KEY`; include header `Authorization: Bearer <token>`) on non-health endpoints

Everything else (DB persistence, advanced logging, tracing, metrics, migrations, admin listing) has been removed for simplicity.

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# (optional) Redis for Celery
redis-server &

# Environment (adjust as needed)
export DEBUG=True
export SMS_API_KEY=your-sms-api-key
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/0
export OTP_USERNAME=Aiims
export OTP_PASSWORD=Aiims@123
export OTP_SERVER=http://192.168.14.30/sms_service/Service.asmx
export OTP_ID=1307161579789431013
export OTP_SENDERID=AIIMSD

python run.py
```

Start a Celery worker (only if broker vars set):
```bash
celery -A app.celery worker --loglevel=info
```

## SMS Examples
Single:
```bash
curl -X POST http://localhost:5000/api/v1/sms/single \
  -H 'Content-Type: application/json' \
  -d '{"mobile":"+911234567890","message":"Hello"}'
```

Bulk:
```bash
curl -X POST http://localhost:5000/api/v1/sms/bulk \
  -H 'Content-Type: application/json' \
  -d '{"mobiles":["+911234567890","+918765432109"],"message":"Hello All"}'
```

## Testing
```bash
pytest -q
```

## Environment Variables
| Variable | Purpose |
|----------|---------|
| DEBUG | Enable Flask debug mode |
| DEFAULT_RATE_LIMIT | Override default rate limit (e.g. `50 per minute`) |
| CELERY_BROKER_URL | Redis/AMQP broker URL for async queue |
| CELERY_RESULT_BACKEND | Backend for task results |
| SMS_API_KEY | (Reserved for future auth) |
| OTP_USERNAME / OTP_PASSWORD / OTP_SERVER / OTP_ID / OTP_SENDERID | SOAP gateway credentials |
| OTP_FLAG | Set to `False` to skip real SOAP calls (defaults True) |

## Notes
* If Celery broker vars are absent, SMS send is synchronous.
* Bulk endpoint returns HTTP 207 + both successes and failures if partial.
* No persistence layer is included; every request is stateless.

## Future (Optional) Enhancements
* Add persistence (PostgreSQL + SQLAlchemy)
* Add auth (bearer/JWT) enforcement
* Provider failover & retry strategy
* Structured logging and tracing

## License
Internal / Private
