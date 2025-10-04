**[Solved]** File: app/utils/cdac_service.py
	- Issue: No timeout on requests.post, risking indefinite hangs.
	- Solution: Timeout parameter added to all requests.post calls.
**[Solved]** File: app/utils/cdac_service.py
	- Issue: No retry logic for transient network errors or rate limits.
	- Solution: Retry logic implemented for requests.post calls.
**[Solved]** File: app/utils/cdac_service.py
	- Issue: Sensitive data (searchKey, API URL) logged without masking.
	- Solution: Sensitive fields are masked/redacted in logs.
**[Solved]** File: app/utils/cdac_service.py
	- Issue: Exception handling is broad; may hide root causes and leak stack traces.
	- Solution: Granular exception handling and secure logging implemented.
**[Solved]** File: app/utils/cdac_service.py
	- Issue: Returns generic error messages, which may not help users or developers.
	- Solution: Informative, user-friendly error messages returned.
**[Solved]** File: app/utils/cdac_service.py
	- Issue: No input validation for emp_id or search_key; possible injection risk if used elsewhere.
	- Solution: Input validation and sanitization added for emp_id/search_key.
**[Solved]** File: app/utils/cdac_service.py
	- Issue: No schema validation for API response; may break if response format changes.
	- Solution: Response structure validated using schema.
**[Solved]** File: app/utils/cdac_service.py
	- Issue: Uses app.config directly, tightly coupling to Flask context.
	- Solution: Dependency injection for config values implemented.
**[Solved]** File: app/utils/cdac_service.py
	- Issue: No authentication/authorization checks before calling sensitive API.
	- Solution: Explicit authentication/authorization checks added before API calls.
**[Solved]** File: app/utils/cdac_service.py
	- Issue: No audit logging for sensitive API calls.
	- Solution: Audit logging for all sensitive API interactions implemented.
# Solved Issues
#
## response.py Specific Issues
**[Solved]** File: app/utils/response.py
	- Details: Unified response schema and standardized status codes are now used for all endpoints.
	- Solution: Unified response schema and status codes implemented in response.py.
**[Solved]** File: app/utils/response.py
	- Issue: Information leakage in error responses.
	- Details: Internal info is masked in error responses; only generic error messages are returned to clients.
	- Solution: Masking of internal info and use of generic error messages implemented in response.py.

## sms_service.py Specific Issues
**[Solved]** File: app/utils/sms_service.py
	- Issue: No input validation for phone numbers or message content.
	- Solution: Input validation for phone numbers and message content implemented in sms_service.py.

**[Solved]** File: app/utils/sms_service.py
	- Issue: No rate limiting or abuse protection for SMS sending.
	- Solution: Rate limiting and abuse detection implemented for SMS sending in sms_service.py.

**[Solved]** File: app/utils/sms_service.py
	- Issue: No logging of failed SMS delivery attempts.
	- Solution: Logging of all failed SMS delivery attempts implemented in sms_service.py.
**[Solved]** File: app/models/sms_message.py
	- Issue: No input validation or sanitization for model fields.
	- Details: All input is validated and sanitized before storing in model fields. Phone number and message are checked for format, length, and forbidden content.
	- Solution: Input validation and sanitization logic added to model constructor in sms_message.py.
**[Solved]** File: app/models/sms_message.py
	- Issue: No constraints or checks for unique or required fields (e.g., phone number, message content).
	- Details: Unique and required constraints added to critical fields (uuid, to, idempotency_key, task_id) in the model and database schema.
	- Solution: Unique and required constraints enforced in sms_message.py and database schema.
**[Solved]** File: app/models/sms_message.py
	- Issue: No audit logging for creation, update, or deletion of sensitive records.
	- Details: Audit logging added for creation and soft deletion of sensitive records using audit_logger.
	- Solution: Audit logging implemented for all sensitive model operations in sms_message.py.
**[Solved]** File: app/models/sms_message.py
	- Issue: No encryption for sensitive fields (e.g., message content, phone numbers).
	- Details: Sensitive fields (phone number, message) are encrypted before storing in the database and decrypted on access using Fernet symmetric encryption.
	- Solution: Encryption and decryption logic added for sensitive fields in sms_message.py.
**[Solved]** File: app/models/sms_message.py
	- Issue: No soft delete or archival for deleted records.
	- Details: Soft delete logic implemented using deleted_at field and audit logging for archival actions.
	- Solution: Soft delete/archival logic implemented for sensitive records in sms_message.py.
	- Why: Failed SMS are not tracked for troubleshooting.
	- Cause: Missing error logging.
	- Effect: Harder to debug and resolve SMS issues.
	- Solution: Log all failed SMS delivery attempts with details.

## tasks Folder Specific Issues
**[Solved]** File: app/tasks/sms_async.py, app/tasks/sms_tasks.py
	- Issue: No retry logic or dead-letter queue for failed async jobs.
	- Details: Retry logic and error handling are implemented for transient failures; failed jobs are logged for review.
	- Solution: Retry logic and failed job logging added to Celery tasks in sms_async.py and sms_tasks.py.
**[Solved]** File: app/tasks/sms_async.py, app/tasks/sms_tasks.py
	- Issue: No input validation for task parameters (e.g., phone numbers, message content).
	- Details: All task parameters are validated and sanitized before processing.
	- Solution: Input validation and sanitization logic added to Celery tasks in sms_async.py and sms_tasks.py.
**[Solved]** File: app/tasks/sms_async.py, app/tasks/sms_tasks.py
	- Issue: No logging of failed or completed async jobs with sufficient detail.
	- Details: All task executions, failures, and completions are logged with relevant metadata.
	- Solution: Logging of failed and completed jobs added to Celery tasks in sms_async.py and sms_tasks.py.
**[Solved]** File: app/tasks/sms_async.py, app/tasks/sms_tasks.py
	- Issue: No rate limiting or abuse protection for async SMS/email jobs.
	- Details: Simple rate limiting is enforced for SMS sending tasks.
	- Solution: Rate limiting logic added to Celery tasks in sms_async.py and sms_tasks.py.
**[Solved]** File: app/tasks/sms_async.py, app/tasks/sms_tasks.py
	- Issue: No audit logging for sensitive async operations (e.g., sending SMS).
	- Details: Audit logging is implemented for all sensitive async operations, including user identity and reason for action.
	- Solution: Audit logging added to Celery tasks in sms_async.py and sms_tasks.py.

## routes Folder Specific Issues
**[Solved]** File: app/utils/decorators.py
	- Issue: No support for role-based access control (RBAC).
	- Solution: RBAC checks using user roles/claims implemented in decorators.py.

**[Solved]** File: app/utils/decorators.py
	- Issue: No protection against replay attacks.
	- Solution: Replay attack protection implemented in decorators.py.

**[Solved]** File: app/routes/v1/cdac_routes.py
	- Issue: No authentication, authorization, or role-based access control for sensitive endpoints.
	- Why: Endpoints may be accessed by unauthorized users if not protected.
	- Cause: Missing or weak access control logic in route handlers.
	- Effect: Security risk, data leakage, or unauthorized actions.
	- Solution: Authentication, authorization, and RBAC checks are now implemented for all sensitive endpoints in cdac_routes.py. Endpoints require valid tokens and enforce role-based access using the X-Role header. Unauthorized or insufficient role access is denied with proper logging and error response.

- **[Solved]** File: app/routes/v1/cdac_routes.py, app/routes/v1/ehospital_routes.py, app/routes/v1/mail_routes.py, app/routes/v1/maintenance_routes.py, app/routes/v1/sms_admin_routes.py, app/routes/v1/sms_routes.py
	- Issue: No input validation or sanitization for request data.
	- Why: Malformed or malicious input can cause errors or security risks.
	- Cause: Missing validation logic in route handlers.
	- Effect: Application errors, injection attacks, or data corruption.
	- Solution: Input validation and sanitization logic has been added to all route handlers. All incoming request data is now validated using strict schemas and sanitized before processing, preventing malformed or malicious input from causing errors or security risks.

**[Solved]** File: app/routes/v1/cdac_routes.py
	- Issue: No error handling or reporting for failed operations.
	- Why: Failures may not be logged or reported clearly to users or developers.
	- Cause: Missing error handling/reporting logic in route handlers.
	- Effect: Harder to debug issues, poor user experience.
	- Solution: All exceptions and service errors are now caught, logged via audit logger, and returned with clear error messages and status codes in cdac_routes.py.

**[Solved]** File: app/routes/v1/cdac_routes.py
	- Issue: No rate limiting or abuse protection for public endpoints.
	- Why: Unrestricted access can be abused for spam or denial-of-service.
	- Cause: No rate limiting or monitoring of endpoint usage.
	- Effect: Service abuse, resource exhaustion, or blacklisting.
	- Solution: All endpoints now enforce a simple in-memory rate limit per IP address, with audit logging for abuse attempts in cdac_routes.py.

**[Solved]** File: app/routes/v1/cdac_routes.py
	- Issue: No audit logging for sensitive operations (e.g., sending SMS, updating records).
	- Why: Sensitive actions should be tracked for compliance and security.
	- Cause: No audit trail for route operations.
	- Effect: Harder to detect misuse or investigate incidents.
	- Solution: All sensitive operations, errors, and access attempts are now logged using an audit logger with user and action details in cdac_routes.py.

**[Solved]** File: app/routes/v1/cdac_routes.py
	- Issue: No unified response schema or status code usage across endpoints.
	- Why: Different endpoints may return different formats or codes.
	- Cause: Lack of standardized response logic.
	- Effect: Client confusion, harder integration, or information leakage.
	- Solution: All endpoints now use the unified response schema and standardized status codes from app.utils.response in cdac_routes.py.

## schema Folder Specific Issues
**[Solved]** File: app/schema/sms_schema.py
	- Issue: Incomplete schema coverage for all possible input variations.
	- Details: Schema now validates phone number and message fields for type, format, length, and forbidden content. Edge cases and input variations are covered.
	- Solution: Schema validation expanded to cover all expected and edge case inputs in sms_schema.py.
**[Solved]** File: app/schema/sms_schema.py
	- Issue: No type or format validation for fields (e.g., phone numbers, message content).
	- Details: Type and format validation enforced for phone number and message fields using Marshmallow and regex.
	- Solution: Type and format validation enforced for all fields in sms_schema.py.
**[Solved]** File: app/schema/sms_schema.py
	- Issue: No length or boundary checks for fields (e.g., message length, phone number length).
	- Details: Length and boundary checks added for phone number (6-16 digits) and message (1-500 characters).
	- Solution: Length and boundary checks added for all relevant fields in sms_schema.py.
**[Solved]** File: app/schema/sms_schema.py
	- Issue: No sanitization of input fields to prevent injection attacks.
	- Details: All input fields are sanitized and checked for forbidden content (e.g., script tags, SQL keywords) before processing.
	- Solution: Input fields sanitized before processing or storing in sms_schema.py.
**[Solved]** File: app/schema/sms_schema.py
	- Issue: No error handling or reporting for schema validation failures.
	- Details: All schema validation errors are now reported with clear messages using Marshmallow's ValidationError.
	- Solution: All schema validation errors are logged and reported with clear messages in sms_schema.py.

## models Folder Specific Issues
**[Solved]** File: app/models/sms_message.py
	- Issue: No input validation or sanitization for model fields.
	- Details: All input is validated and sanitized before storing in model fields. Phone number and message are checked for format, length, and forbidden content.
	- Solution: Input validation and sanitization logic added to model constructor in sms_message.py.
**[Solved]** File: app/models/sms_message.py
	- Issue: No constraints or checks for unique or required fields (e.g., phone number, message content).
	- Details: Unique and required constraints added to critical fields (uuid, to, idempotency_key, task_id) in the model and database schema.
	- Solution: Unique and required constraints enforced in sms_message.py and database schema.
**[Solved]** File: app/models/sms_message.py
	- Issue: No audit logging for creation, update, or deletion of sensitive records.
	- Details: Audit logging added for creation and soft deletion of sensitive records using audit_logger.
	- Solution: Audit logging implemented for all sensitive model operations in sms_message.py.
**[Solved]** File: app/models/sms_message.py
	- Issue: No encryption for sensitive fields (e.g., message content, phone numbers).
	- Details: Sensitive fields (phone number, message) are encrypted before storing in the database and decrypted on access using Fernet symmetric encryption.
	- Solution: Encryption and decryption logic added for sensitive fields in sms_message.py.
**[Solved]** File: app/models/sms_message.py
	- Issue: No soft delete or archival for deleted records.
	- Details: Soft delete logic implemented using deleted_at field and audit logging for archival actions.
	- Solution: Soft delete/archival logic implemented for sensitive records in sms_message.py.

## ehospital_service.py Specific Issues
**[Solved]** File: app/utils/ehospital_service.py
	- Issue: No input validation for parameters passed to external APIs.
	- Details: All input parameters are validated and sanitized before use in API calls.
	- Solution: Input validation and sanitization logic added to ehospital_service.py.
**[Solved]** File: app/utils/ehospital_service.py
	- Issue: No timeout or retry logic for requests to external services.
	- Details: All external requests use a timeout and retry logic (tenacity) to prevent hangs and transient failures.
	- Solution: Timeout and retry logic added to all external requests in ehospital_service.py.
**[Solved]** File: app/utils/ehospital_service.py
	- Issue: No schema validation for API responses.
	- Details: All API responses are validated using Marshmallow schema to ensure correct structure.
	- Solution: Response schema validation added to ehospital_service.py.

## email_service.py Specific Issues
**[Solved]** File: app/utils/email_service.py
	- Issue: No input validation for email addresses or message content.
	- Details: All email addresses and message content are validated and sanitized before sending.
	- Solution: Input validation and sanitization logic added to email_service.py.
**[Solved]** File: app/utils/email_service.py
	- Issue: No rate limiting or abuse protection for email sending.
	- Details: Rate limiting and abuse detection implemented for email sending per IP address.
	- Solution: Rate limiting and abuse protection logic added to email_service.py.
**[Solved]** File: app/utils/email_service.py
	- Issue: No logging of failed email delivery attempts.
	- Details: All failed email delivery attempts are logged with details using email_logger.
	- Solution: Logging of failed email delivery attempts added to email_service.py.

## logging_utils.py Specific Issues
**[Solved]** File: app/utils/logging_utils.py
	- Issue: No log rotation or size management.
	- Details: Log rotation and size limits are implemented using RotatingFileHandler.
	- Solution: Log rotation and size limits implemented in logging_utils.py.
**[Solved]** File: app/utils/logging_utils.py
	- Issue: Logging sensitive data (PII, credentials) without masking.
	- Details: Sensitive fields (password, token, api_key, secret, email, phone) are masked in logs to prevent information leakage.
	- Solution: Masking of sensitive fields implemented in logging_utils.py.

## response.py Specific Issues
**[Solved]** File: app/utils/response.py
	- Issue: Inconsistent response structure or status codes across endpoints.
	- Details: Unified response schema and standardized status codes are now used for all endpoints.
	- Solution: Unified response schema and status codes implemented in response.py.
**[Solved]** File: app/utils/response.py
	- Issue: Information leakage in error responses.
	- Details: Internal info is masked in error responses; only generic error messages are returned to clients.
	- Solution: Masking of internal info and use of generic error messages implemented in response.py.

## sms_service.py Specific Issues
**[Solved]** File: app/utils/sms_service.py
	- Issue: No input validation for phone numbers or message content.
	- Details: Phone numbers are validated for format and length; message content is validated for length and forbidden content.
	- Solution: Input validation and sanitization logic added to send_sms in sms_service.py.
**[Solved]** File: app/utils/sms_service.py
	- Issue: No rate limiting or abuse protection for SMS sending.
	- Details: Simple rate limiting (1 SMS per 10 seconds per mobile) is enforced.
	- Solution: Rate limiting logic added to send_sms in sms_service.py.
**[Solved]** File: app/utils/sms_service.py
	- Issue: No logging of failed SMS delivery attempts.
	- Details: All failed SMS delivery attempts are logged with details using app.logger.
	- Solution: Logging of failed SMS delivery attempts added to send_sms in sms_service.py.

## tasks Folder Specific Issues
**[Solved]** File: app/tasks/sms_async.py, app/tasks/sms_tasks.py
	- Issue: No retry logic or dead-letter queue for failed async jobs.
	- Details: Retry logic and error handling are implemented for transient failures; failed jobs are logged for review.
	- Solution: Retry logic and failed job logging added to Celery tasks in sms_async.py and sms_tasks.py.
**[Solved]** File: app/tasks/sms_async.py, app/tasks/sms_tasks.py
	- Issue: No input validation for task parameters (e.g., phone numbers, message content).
	- Details: All task parameters are validated and sanitized before processing.
	- Solution: Input validation and sanitization logic added to Celery tasks in sms_async.py and sms_tasks.py.
**[Solved]** File: app/tasks/sms_async.py, app/tasks/sms_tasks.py
	- Issue: No logging of failed or completed async jobs with sufficient detail.
	- Details: All task executions, failures, and completions are logged with relevant metadata.
	- Solution: Logging of failed and completed jobs added to Celery tasks in sms_async.py and sms_tasks.py.
**[Solved]** File: app/tasks/sms_async.py, app/tasks/sms_tasks.py
	- Issue: No rate limiting or abuse protection for async SMS/email jobs.
	- Details: Simple rate limiting is enforced for SMS sending tasks.
	- Solution: Rate limiting logic added to Celery tasks in sms_async.py and sms_tasks.py.
**[Solved]** File: app/tasks/sms_async.py, app/tasks/sms_tasks.py
	- Issue: No audit logging for sensitive async operations (e.g., sending SMS).
	- Details: Audit logging is implemented for all sensitive async operations, including user identity and reason for action.
	- Solution: Audit logging added to Celery tasks in sms_async.py and sms_tasks.py.

