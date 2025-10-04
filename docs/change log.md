# Change Log
### [logging_utils.py]
### [email_service.py]
### [ehospital_service.py]
### [tasks]
### [solved_issue.md]

2025-10-03:
	- Created solved_issue.md and migrated all solved issues from issue.md for better tracking and organization.
2024-10-03:
	- Retry logic and failed job logging added to Celery tasks in sms_async.py and sms_tasks.py
	- Input validation and sanitization logic added to Celery tasks in sms_async.py and sms_tasks.py
	- Logging of failed and completed jobs added to Celery tasks in sms_async.py and sms_tasks.py
	- Rate limiting logic added to Celery tasks in sms_async.py and sms_tasks.py
	- Audit logging added to Celery tasks in sms_async.py and sms_tasks.py
2024-06-09:
	- Input validation and sanitization logic added for parameters passed to external APIs
	- Timeout and retry logic added for all external requests
	- Response schema validation added for all API responses
2024-06-09:
	- Input validation and sanitization logic added for email addresses and message content
	- Rate limiting and abuse protection logic added for email sending
	- Logging of failed email delivery attempts added using email_logger
...existing log entries...

## [2025-10-03] decorators.py security and logging improvements
- Fixed hardcoded fallback API keys
- Added token format validation
- Implemented rate limiting and lockout for repeated failed authentication attempts
- Logged additional request metadata
- Added audit logging for all admin access attempts
- Implemented RBAC checks using user roles/claims
- Added protection against replay attacks

## [2025-10-03] Issue migration
- Migrated all solved issues from issue.md to solved_issue.md for better tracking
	- Log rotation and size limits implemented using RotatingFileHandler
	- Masking of sensitive fields (password, token, api_key, secret, email, phone) in logs
This file records all major changes, updates, and improvements made to the backend services project.

## 2025-10-04
### [cdac_service.py]

2025-10-04:
	- Added timeout to requests.post calls to prevent indefinite hangs
	- Improved retry logic with specific exception handling (Timeout, ConnectionError, RequestException)
	- Enhanced sensitive data masking in logs
	- Fixed input validation for employee IDs
	- Added proper schema validation for API responses
	- Improved error handling and logging

### [sms_service.py]

2025-10-04:
	- Added timeout parameter (30 seconds) to prevent hanging requests
	- Added specific exception handling for different error types (408 for timeout, 502 for connection errors)
	- Improved error response codes

### [SMSMessage model]

2025-10-04:
	- Fixed initialization order to ensure proper logging
	- Updated encryption key handling to use environment variables

### [Configuration]

2025-10-04:
	- Added proper encryption key configuration
	- Added CDAC access control configuration

### [Extensions]

2025-10-04:
	- Fixed duplicate initialization issue

### [SMS routes]

2025-10-04:
	- Improved error handling and validation in both single and bulk SMS endpoints
	- Added proper database rollback on errors
	- Enhanced health check endpoint to avoid sending actual test messages
	- Improved error messages for better debugging

### [Tasks]

2025-10-04:
	- Improved error handling and retry logic in Celery tasks
	- Added proper validation in tasks

### [Response utility]

2025-10-04:
	- Enhanced security by masking internal details in error responses

### [Application factory]

2025-10-04:
	- Added proper initialization logging

### [Documentation]

2025-10-04:
	- Updated issue.md to mark solved issues
	- Updated solved_issue.md with comprehensive list of resolved issues
	- Updated changelog with all changes made

## 2025-10-03
### [response.py]

2024-06-09:
	- Unified response schema and status codes for all endpoints
	- Masked internal info in error responses; only generic error messages returned

## [2025-10-03] Business logic: race-condition fix
- Files changed: `app/tasks/sms_tasks.py`, `app/routes/v1/sms_routes.py`
- Description: Added short transactions and row-level locking (SELECT ... FOR UPDATE) when updating `SMSMessage` rows. This prevents lost updates when concurrent requests or Celery workers modify the same record. Also persisted retry/sent/failed states inside short transactions to improve reliability and observability.
