import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
import logging
import re
from threading import Lock
from typing import Optional, Tuple
import os
from cryptography.fernet import Fernet
import time


# Thread lock for email sending (per-process)
email_send_lock = Lock()

# Email regex: basic validation
EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

# Forbidden tokens (use uppercase for normalized checks)
FORBIDDEN_TOKENS = [t.strip().upper() for t in ["<script", "SELECT", "INSERT", "DELETE", "UPDATE", "DROP", "UNION", "EXEC"]]


def get_fernet() -> Fernet:
    """
    Lazy initializer for Fernet. Raises RuntimeError with a clear message if the key is missing/invalid.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY environment variable is not set. Generate one with Fernet.generate_key() and set it.")
    # Accept either raw base64-key (44 chars) OR raw bytes hex string (less recommended).
    if isinstance(key, str):
        key = key.strip()
    try:
        # If key is bytes already, Fernet() will accept. Otherwise convert to bytes.
        kbytes = key.encode() if isinstance(key, str) else key
        f = Fernet(kbytes)
        return f
    except Exception as e:
        # Provide helpful context
        raise RuntimeError(
            "Invalid ENCRYPTION_KEY. It must be a URL-safe base64-encoded 32-byte key (44-character string). "
            "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from e


def validate_email(email: str) -> bool:
    """
    Validates email format
    """
    if not isinstance(email, str) or not email:
        return False
    return bool(EMAIL_RE.fullmatch(email.strip()))


def validate_subject(subject: str) -> bool:
    """
    Validates email subject
    """
    if not isinstance(subject, str) or not subject.strip():
        return False
    if len(subject.strip()) > 500:  # Reasonable subject length
        return False
    # Check for forbidden content
    subject_upper = subject.upper()
    if any(token in subject_upper for token in FORBIDDEN_TOKENS):
        return False
    return True


def validate_body(body: str) -> bool:
    """
    Validates email body content
    """
    if not isinstance(body, str) or not body.strip():
        return False
    if len(body.strip()) > 10000:  # Reasonable body length (10KB)
        return False
    # Check for forbidden content
    body_upper = body.upper()
    if any(token in body_upper for token in FORBIDDEN_TOKENS):
        return False
    return True


def _is_forbidden(content: str) -> bool:
    content_upper = content.upper()
    for token in FORBIDDEN_TOKENS:
        if token in content_upper:
            return True
    return False


def send_single_email_util(to_email: str, subject: str, body: str,
                          from_email: Optional[str] = None,
                          smtp_server: Optional[str] = None,
                          smtp_port: Optional[int] = None,
                          smtp_username: Optional[str] = None,
                          smtp_password: Optional[str] = None,
                          use_tls: bool = True) -> Tuple[int, str]:
    """
    Thread-safe utility function to send a single email.

    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body content
        from_email: Sender email (if different from SMTP config)
        smtp_server: SMTP server address
        smtp_port: SMTP server port
        smtp_username: SMTP username
        smtp_password: SMTP password
        use_tls: Whether to use TLS encryption

    Returns:
        Tuple of (status_code, message_id or error_message)
    """
    with email_send_lock:
        app_logger = logging.getLogger('app')
        email_logger = logging.getLogger('email')
        
        app_logger.info(f"Processing single email to {to_email}")
        
        # Input validation
        if not validate_email(to_email):
            error_msg = f"Invalid email address: {to_email}"
            email_logger.error(error_msg)
            return 400, error_msg

        if not validate_subject(subject):
            error_msg = f"Invalid email subject for {to_email}"
            email_logger.error(error_msg)
            return 400, error_msg

        if not validate_body(body):
            error_msg = f"Invalid email body content for {to_email}"
            email_logger.error(error_msg)
            return 400, error_msg

        # Get configuration from Flask app context or environment
        try:
            from flask import current_app
            smtp_server = smtp_server or current_app.config.get('SMTP_SERVER', 'localhost')
            smtp_port = smtp_port or int(current_app.config.get('SMTP_PORT', 587))
            smtp_username = smtp_username or current_app.config.get('SMTP_USERNAME')
            smtp_password = smtp_password or current_app.config.get('SMTP_PASSWORD')
            from_email = from_email or current_app.config.get('SMTP_FROM_EMAIL', smtp_username)
            use_tls = current_app.config.get('SMTP_USE_TLS', True)
            use_ssl = current_app.config.get('SMTP_USE_SSL', False)
        except RuntimeError:
            # Not in Flask app context (e.g., in Celery worker)
            smtp_server = smtp_server or os.getenv('SMTP_SERVER', 'localhost')
            smtp_port = smtp_port or int(os.getenv('SMTP_PORT', 587))
            smtp_username = smtp_username or os.getenv('SMTP_USERNAME')
            smtp_password = smtp_password or os.getenv('SMTP_PASSWORD')
            from_email = from_email or os.getenv('SMTP_FROM_EMAIL', smtp_username or 'noreply@example.com')
            use_tls = os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'
            use_ssl = os.getenv('SMTP_USE_SSL', 'False').lower() == 'true'

        # Check required configuration
        if not all([smtp_server, smtp_username, smtp_password, from_email]):
            error_msg = "Missing SMTP configuration"
            email_logger.error(error_msg)
            logging.getLogger('error').error(error_msg)
            return 500, error_msg

        # Rate limiting - per process fallback. Replace with Redis for multi-process deployments.
        now = time.time()
        try:
            # Process-global rate limiting
            global _PROCESS_EMAIL_RATE_LIMIT
            if '_PROCESS_EMAIL_RATE_LIMIT' not in globals():
                _PROCESS_EMAIL_RATE_LIMIT = {}
            rate_store = _PROCESS_EMAIL_RATE_LIMIT
        except NameError:
            _PROCESS_EMAIL_RATE_LIMIT = {}
            rate_store = _PROCESS_EMAIL_RATE_LIMIT

        last_sent = rate_store.get(to_email, 0)
        if now - last_sent < 1:  # 1 second minimum between emails to same address
            error_msg = f"Rate limit exceeded for {to_email}"
            email_logger.warning(error_msg)
            return 429, error_msg
        rate_store[to_email] = now

        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = to_email
            msg['Subject'] = subject

            # Add body to email
            msg.attach(MIMEText(body, 'plain'))

            # Extract headers for logging
            headers = dict(msg.items())

            # Send the email using SMTP
            smtp_port = int(smtp_port)
            use_ssl_for_port = smtp_port == 465 or use_ssl
            smtp_class = smtplib.SMTP_SSL if use_ssl_for_port else smtplib.SMTP

            with smtp_class(smtp_server, smtp_port) as server:
                if not use_ssl_for_port and use_tls:
                    server.starttls()  # Enable encryption
                server.login(smtp_username, smtp_password)
                server.send_message(msg)

            # Log successful email and increment metrics
            from app.extensions import email_sent_counter
            email_sent_counter.inc()

            msg_id = f"email_{int(time.time())}_{hash(to_email) % 10000}"
            success_msg = f"Email sent successfully to {to_email}, headers: {headers}"
            email_logger.info(success_msg)
            return 200, msg_id

        except smtplib.SMTPAuthenticationError:
            error_msg = f"SMTP authentication failed for {to_email}"
            email_logger.error(error_msg)
            return 401, error_msg
        except smtplib.SMTPRecipientsRefused:
            error_msg = f"Recipient email address refused: {to_email}"
            email_logger.error(error_msg)
            return 400, error_msg
        except smtplib.SMTPServerDisconnected:
            error_msg = f"SMTP server disconnected when sending to {to_email}"
            email_logger.error(error_msg)
            return 503, error_msg
        except Exception as e:
            # Increment failure counter
            from app.extensions import email_failed_counter
            email_failed_counter.inc()

            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            email_logger.error(error_msg)
            logging.getLogger('error').exception(error_msg)
            return 500, error_msg