# Developer Guide

## Introduction
This document is the definitive guide for engineers working on the **AIIMS Services** microservice (`app`). It covers everything from setting up your local environment to deploying in production, with a focus on common workflows and troubleshooting.

---

## 🏗️ Project Architecture

The application uses a **Factory Pattern** (`create_app`) to decouple configuration from the application instance.

### Directory Breakdown
| Directory | Purpose | Key Files |
|---|---|---|
| `app/` | Core Application Logic | `__init__.py` (Factory) |
| `app/config.py` | Configuration | `DevelopmentConfig`, `ProductionConfig` |
| `app/extensions.py` | extension Init | `db`, `limiter`, `celery` |
| `app/models/` | SQLAlchemy Models | `sms_message.py` (PII Encrypted) |
| `app/routes/v1/` | API Blueprints | `sms_routes.py`, `mail_routes.py` |
| `app/middleware/` | Request Processing | `security_headers.py`, CORS logic |
| `app/tasks/` | Async Tasks | `sms_queue.py` (Celery Tasks) |
| `app/utils/` | Shared Logic | `sms_workflow.py` (Orchestration), `sanitization.py` |

### Key Design Decisions
1.  **PII Encryption**: We use `Fernet` (symmetric encryption) for `mobile` and `message` columns in `SMSMessage`. Keys are cached to avoid performance hits.
2.  **Workflow Separation**: Routes (`sms_routes.py`) only handle HTTP/Validation. Logic is delegated to `sms_workflow.py`.
3.  **Configurable Security**: IP Allowlisting is managed via `ALLOWED_IPS` environment variables, not hardcoded.

---

## 🛠️ Setup & Installation

### Prerequisites
*   **OS**: Linux, macOS, or Windows (WSL recommended)
*   **Python**: 3.9+
*   **Redis**: Required for Celery/Rate Limiting
*   **Database**: SQLite (default dev), PostgreSQL (prod)

### Step-by-Step Setup

#### 1. Clone & venv
```bash
git clone <repository-url>
cd aiims-services
python3 -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
# .\venv\Scripts\activate
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 3. Environment Config
Create a `.env` file from the example:
```bash
cp .env.example .env
```

**Minimal `.env` for Development:**
```ini
APP_ENV=development
SECRET_KEY=dev-secret-key-123
# Generate a key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=YOUR_GENERATED_KEY_HERE
ALLOWED_IPS=127.0.0.1
DEBUG=True
```

#### 4. Database Initialization
Initialize the local SQLite database:
```bash
# This creates instance/db.sqlite (or similar depending on config)
flask db upgrade

# OR manual creation shell:
# python -c "from app import create_app, db; app=create_app(); app.app_context().push(); db.create_all()"
```

#### 5. Start Redis (Required)
```bash
# Linux/Mac
redis-server &
```

---

## 🏃 Running the Application

### 1. API Server
```bash
flask run --port 5000 --reload
```
Access at: `http://localhost:5000/health`

### 2. Celery Worker (Background Tasks)
Open a new terminal, activate venv, and run:
```bash
celery -A app.extensions.celery worker --loglevel=info
```

---

## 💻 Common Workflows

### How to: Add a New API Route
1.  **Create File**: `app/routes/v1/new_feature_routes.py`
    ```python
    from flask import Blueprint
    from flask_restx import Api, Resource
    from app.utils.decorators import require_bearer_and_log

    new_bp = Blueprint('new_feature', __name__)
    api = Api(new_bp)

    @api.route('/hello')
    class HelloResource(Resource):
        method_decorators = [require_bearer_and_log]
        def get(self):
            return {'message': 'Hello World'}
    ```
2.  **Register Endpoint**: Add to `app/__init__.py`:
    ```python
    from app.routes.v1.new_feature_routes import new_bp
    app.register_blueprint(new_bp, url_prefix='/services/api/v1/new')
    ```

### How to: Add a Database Migration
(Assuming Flask-Migrate is setup)
```bash
flask db migrate -m "Added status column"
flask db upgrade
```

---

## ❓ Troubleshooting

### 1. `RuntimeError: ENCRYPTION_KEY not set`
**Cause**: The `.env` file is missing the `ENCRYPTION_KEY` or it is not loaded.
**Fix**: Generate a key and add it to `.env`. Ensure `load_dotenv()` is called or variables are exported.

### 2. SMS Status stuck at 'queued'
**Cause**: Celery worker is not running.
**Fix**: Start the worker with `celery -A app.extensions.celery worker`.

### 3. `403 Forbidden` / `Access Denied`
**Cause**: Your IP is not in `ALLOWED_IPS` or `ALLOWED_IP_PREFIXES`.
**Fix**: Add `127.0.0.1` or your specific IP to `.env`.

### 4. `Redis Connection Error`
**Cause**: Redis is not running or `RATELIMIT_STORAGE_URI` is wrong.
**Fix**: Start `redis-server`. Check `REDIS_URL` in config.

---

## 🧪 Testing

### Running Tests
```bash
# Run all tests
pytest

# Run specific file
pytest tests/test_sms_routes.py -v

# Run with coverage report
pytest --cov=app tests/
```

### Writing Tests
Use `conftest.py` fixtures (`client`, `auth_headers`).
```python
def test_new_route(client, auth_headers):
    resp = client.get('/services/api/v1/new/hello', headers=auth_headers)
    assert resp.status_code == 200
```
