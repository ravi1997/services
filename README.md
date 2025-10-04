# AIIMS Services API

AIIMS Services API is a comprehensive messaging and integration microservice that provides various communication channels including SMS, email, CDAC, and eHospital integrations. The service is built using Flask and is designed for scalability, security, and reliability.

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [API Endpoints](#api-endpoints)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Security](#security)
- [Monitoring & Logging](#monitoring--logging)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Multi-channel Communication**: Send SMS, email, and integrate with CDAC/eHospital systems
- **Rate Limiting**: Per-IP rate limiting with configurable limits
- **Authentication**: Bearer token authentication for all protected endpoints
- **Asynchronous Processing**: Celery-based task queue for async operations
- **Structured Logging**: Comprehensive logging across multiple levels (access, SMS, error, app)
- **IP Whitelisting**: Restrict access to specific IP ranges (192.168.14.*)
- **Input Validation**: Comprehensive validation for all inputs
- **Bulk Operations**: Support for sending bulk messages with partial success reporting
- **Health Monitoring**: Health check endpoints for all services and system metrics
- **API Documentation**: Built-in Swagger/OpenAPI documentation

## Architecture

The service follows a modular architecture with clear separation of concerns:

```
├── app/
│   ├── routes/          # API route handlers
│   ├── models/          # Database models
│   ├── utils/           # Utility functions
│   ├── tasks/           # Celery tasks
│   ├── schema/          # Validation schemas
│   └── extensions.py    # Flask extensions
├── docs/               # Documentation
├── logs/               # Log files
├── tests/              # Test suite
└── run.py              # Application entry point
```

### Tech Stack
- **Framework**: Flask 2.x
- **Database**: SQLAlchemy with support for multiple databases
- **Task Queue**: Celery with Redis/RabbitMQ
- **Rate Limiting**: Flask-Limiter
- **API Documentation**: Flask-RESTX
- **Validation**: Marshmallow
- **Logging**: Python logging module with file rotation
- **Security**: Cryptography for data encryption

## API Endpoints

### SMS Service
- `POST /services/api/v1/sms/single` - Send a single SMS
- `POST /services/api/v1/sms/bulk` - Send bulk SMS (max 200 at a time)
- `GET /services/api/v1/sms/health` - SMS service health check
- `GET /services/api/v1/sms/docs` - API documentation

### Email Service
- `POST /services/api/v1/mail/send` - Send a single email
- `POST /services/api/v1/mail/bulk_send` - Send bulk emails
- `GET /services/api/v1/mail/health` - Email service health check

### CDAC Service
- `POST /services/api/v1/cdac/single` - Fetch single CDAC data
- `POST /services/api/v1/cdac/bulk` - Fetch bulk CDAC data
- `GET /services/api/v1/cdac/health` - CDAC service health check

### eHospital Service
- `POST /services/api/v1/ehospital/patient` - Get patient details
- `POST /services/api/v1/ehospital/bulk_patient` - Get bulk patient details
- `GET /services/api/v1/ehospital/health` - eHospital service health check

### Admin & Maintenance
- `GET /services/api/v1/sms/messages` - List SMS messages (admin)
- `GET /services/api/v1/sms/status/<id>` - Get message status (admin)
- `POST /services/api/v1/logs/cleanup` - Cleanup old logs (admin)

### System
- `GET /health` - Global health check
- `GET /metrics` - Prometheus metrics

## Quick Start

### Prerequisites
- Python 3.8+
- Redis server (for Celery)
- SOAP SMS gateway (for SMS functionality)

### Installation

1. Clone the repository
```bash
git clone <repository-url>
cd aiims-services
```

2. Create and activate virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
```bash
cp .env.example .env
# Edit .env with appropriate values
```

5. Start Redis server
```bash
redis-server &
```

6. Start the application
```bash
python run.py
```

7. (Optional) Start Celery worker
```bash
celery -A app.celery worker --loglevel=info
```

### Docker (Optional)
```bash
# Build and run with Docker
docker-compose up --build
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Application environment (development/production) | development |
| `DEBUG` | Enable debug mode | False |
| `SECRET_KEY` | Flask secret key | change-me |
| `DATABASE_URL` | Database connection string | sqlite:///:memory: |
| `CELERY_BROKER_URL` | Celery broker URL | None |
| `CELERY_RESULT_BACKEND` | Celery result backend | None |
| `SMS_API_KEY` | API key for SMS endpoints | your-sms-api-key |
| `ADMIN_API_KEY` | API key for admin endpoints | your-admin-api-key |
| `OTP_USERNAME` | SMS gateway username | None |
| `OTP_PASSWORD` | SMS gateway password | None |
| `OTP_SERVER` | SMS gateway server URL | None |
| `OTP_ID` | SMS template ID | None |
| `OTP_SENDERID` | SMS sender ID | None |
| `OTP_FLAG` | Enable SMS sending | True |
| `CDAC_SERVER` | CDAC API server | https://example-cdac-api.com |
| `CDAC_AUTH_BEARER` | CDAC API authentication token | your-cdac-auth-bearer-token |
| `DEFAULT_RATE_LIMIT` | Default rate limit | 30 per minute |
| `LOG_RETENTION_MONTHS` | Log retention in months | 8 |
| `ENCRYPTION_KEY` | Encryption key for sensitive data | 0123456789abcdef0123456789abcdef |

### Rate Limits
- Single SMS: 200 per minute
- Bulk SMS: 10 per minute (max 200 messages)
- Health check: 5 per minute
- Admin endpoints: 5 per minute

## Usage Examples

### Send Single SMS
```bash
curl -X POST http://localhost:5000/services/api/v1/sms/single \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer your-sms-api-key' \
  -d '{
    "mobile": "+919876543210",
    "message": "Hello from AIIMS Services"
  }'
```

### Send Bulk SMS
```bash
curl -X POST http://localhost:5000/services/api/v1/sms/bulk \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer your-sms-api-key' \
  -d '{
    "mobiles": ["+919876543210", "+919876543211"],
    "message": "Bulk message from AIIMS Services"
  }'
```

### Get SMS Service Health
```bash
curl -X GET http://localhost:5000/services/api/v1/sms/health
```

### Send Email
```bash
curl -X POST http://localhost:5000/services/api/v1/mail/send \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer your-sms-api-key' \
  -d '{
    "to": "user@example.com",
    "subject": "Test Email",
    "body": "This is a test email"
  }'
```

## Security

### Authentication
All non-health endpoints require Bearer token authentication:
```http
Authorization: Bearer <api-key>
```

### IP Whitelisting
The service only accepts requests from the `192.168.14.*` IP range.

### Rate Limiting
- Per-IP rate limiting with configurable limits
- Custom limits for different SMS endpoints
- Protection against abuse and DDoS attacks

### Input Validation
- Comprehensive validation for all inputs
- Protection against injection attacks
- Length and format validation
- Forbidden content detection

### Data Encryption
- Sensitive data (phone numbers, messages) are encrypted at rest
- Fernet symmetric encryption used for data protection

## Monitoring & Logging

### Log Files
- `logs/app.log` - Application logs
- `logs/access.log` - Access logs
- `logs/sms.log` - SMS-specific logs
- `logs/error.log` - Error logs

### Metrics
- Prometheus metrics endpoint at `/metrics`
- SMS counters: sent, failed, queued
- Request timing and rate limiting metrics

### Health Checks
- Service-specific health endpoints
- Global health check at `/health`
- Metrics for monitoring service status

## Testing

### Unit Tests
```bash
pytest tests/
```

### Coverage
```bash
pytest --cov=app tests/
```

### API Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test module
python -m pytest tests/test_sms.py
```

## Deployment

### Production Deployment
1. Set `APP_ENV=production`
2. Configure a proper database (PostgreSQL recommended)
3. Set up Redis for Celery
4. Use a WSGI server like Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

### Environment-Specific Config
- Use dedicated configuration classes in `app/config.py`
- Implement environment-based settings for development, staging, production
- Use secrets management for production environments

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guide
- Write tests for new features
- Document API endpoints with docstrings
- Update documentation when changing interfaces
- Use type hints where possible

## License

This project is proprietary and intended for internal use only. All rights reserved.

## Support

For support, please contact the development team.

---
*AIIMS Services API v1.0.0*