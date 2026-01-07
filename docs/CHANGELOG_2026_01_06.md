# Changelog - 2026-01-06

## Fixed
- **Hardcoded Configuration**: Moved `ALLOWED_IPS` and `ALLOWED_IP_PREFIXES` from `app/__init__.py` to `app/config.py` to allow environment-based configuration and easier deployment updates.
- **Performance**: Added caching for the `Fernet` encryption key in `app/models/sms_message.py` to prevent redundant environment variable lookups and object instantiation on every database row access.
- **Code Duplication**: Refactored `app/routes/v1/sms_routes.py` to remove duplicate logic between `SingleSMS` and `BulkSMS`. Created `app/utils/sms_workflow.py` to centralize the SMS processing lifecycle (Validation -> Persistence -> Queue/Send -> Status Update).

## Security
- **CORS Hardening**: Updated `app/__init__.py` to reflect the specific `Origin` header for allowed IPs instead of returning a wildcard `*`, improving security posture for browser-based clients.
- **CSRF Documentation**: Clarified CSRF exemption logic for API blueprints to prevent future misconfiguration.
- Maintained existing PII logging behavior as per user request (WONTFIX on PII leakage).

## Documentation Updates
- **New Architecture**: Split monolithic documentation into `API_USER_GUIDE.md` (for consumers) and `DEVELOPER_GUIDE.md` (for contributors).
- **Enhanced Depth**: Added specific OS setup guides, Redis/Celery troubleshooting, and step-by-step route creation workflows.
- **User Guide Improvements**: Added cURL examples, Authentication headers, and Rate Limit explanations.
- **Project Structure**: Created `docs/` directory and updated `README.md` to serve as a clean entry point.

## Components Changed
- `app/config.py`
- `app/__init__.py`
- `app/models/sms_message.py`
- `app/routes/v1/sms_routes.py`
- `app/utils/sms_workflow.py` (New)
- `docs/` (Directory Created)
- `README.md` (Revised)
