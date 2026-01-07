# AIIMS Services API

**AIIMS Services API** is a comprehensive, secure, and modular messaging microservice. It provides a unified interface for sending SMS, dispatching emails, and integrating with external healthcare systems like **CDAC** and **eHospital**.

Built with **Flask**, **Celery**, and **SQLAlchemy**, it is designed for high reliability, security (PII encryption), and scalability.

---

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:

- **[API User Guide](docs/API_USER_GUIDE.md)**: For consumers. Includes **cURL examples**, detailed **error recovery steps**, rate limit headers, and authentication generation.
- **[Developer Guide](docs/DEVELOPER_GUIDE.md)**: For contributors. Covers **OS-specific setup** (Mac/Linux/Windows), **troubleshooting** common issues (Redis/DB), and a step-by-step guide to **adding new routes**.
- **[Changelog](docs/CHANGELOG_2026_01_06.md)**: Recent changes and updates.

---

## 🚀 Key Features

*   **Multi-Channel Messaging**: Unified APIs for SMS (SOAP Gateway) and Email (SMTP).
*   **Security First**:
    *   **PII Encryption**: Mobile numbers and messages are encrypted at rest using `Fernet`.
    *   **Strict Security**: IP Allowlisting, CORS reflection, and Input Sanitization.
    *   **Audit Logging**: Comprehensive logs for all transaction attempts.
*   **Reliable Delivery**:
    *   **Async Processing**: Celery-based queuing for high throughput.
    *   **Smart Fallback**: Automatic fallback to direct sending if the queue is unavailable.
    *   **Idempotency**: Prevents duplicate messages via `Idempotency-Key` headers.
*   **Integrations**: Proxies for CDAC and eHospital patient data fetching.

## 🏗️ Architecture

The service follows a modular factory pattern:

```
app/
├── routes/          # API Blueprints (v1/sms, v1/mail, etc.)
├── models/          # Database Models (Encrypted SMSMessage)
├── utils/           # Shared Logic (Sanitization, SMS Workflow)
├── tasks/           # Celery Async Tasks
├── config.py        # Environment-based Configuration
└── __init__.py      # App Factory & Middleware
```

## ⚡ Quick Start

### Prerequisites
*   Python 3.9+
*   Redis (for Celery & Rate Limiting)
*   SQLite (default) or PostgreSQL

### Installation

#### Method 1: Standard (Python venv)

1.  **Clone & Install**
    ```bash
    git clone <repository>
    cd aiims-services
    pip install -r requirements.txt
    ```

2.  **Configure Environment**
    Copy `.env.example` to `.env` and set essential keys:
    ```bash
    export APP_ENV=development
    export SECRET_KEY=<random-string>
    export ENCRYPTION_KEY=<generated-fernet-key>
    export ALLOWED_IPS=127.0.0.1,192.168.1.100
    ```

3.  **Run Application**
    ```bash
    # Start API
    flask run --port 5000

    # Start Worker (Optional, for async)
    celery -A app.extensions.celery worker --loglevel=info
    ```

#### Method 2: Docker (Fast Track)

We use `uv` for lightning-fast builds.

```bash
chmod +x setup_uv_docker.sh
./setup_uv_docker.sh
```
This will start the API on port `9000` and a Redis-backed Celery worker.

## 🛡️ Security Configuration

### Authentication
All API endpoints (except health checks) require a **Bearer Token**:
`Authorization: Bearer <YOUR_API_KEY>`

### IP Allowlisting
Access is restricted to IPs defined in `ALLOWED_IPS` (in `.env` or `config.py`).
*   **Note**: The API supports `X-Forwarded-For` for reverse proxies.

### Rate Limiting
Default limits are configured per endpoint (e.g., `100/minute` for SMS).

## 🧪 Testing

Run the test suite using `pytest`:

```bash
# Run all tests
pytest

# Check coverage
pytest --cov=app
```

---
*Maintained by the AIIMS Services Engineering Team.*