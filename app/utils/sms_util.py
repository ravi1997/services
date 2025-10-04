import threading
import time
import logging
import re
import os
from typing import Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, has_app_context
from xml.sax.saxutils import escape as xml_escape
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Thread lock for SMS sending (per-process)
sms_send_lock = threading.Lock()

# Phone regex: allow 6-16 digits (you used this; adjust as needed)
PHONE_RE = re.compile(r"^\d{6,16}$")

# Forbidden tokens (use uppercase for normalized checks). Consider tightening or removing.
FORBIDDEN_TOKENS = [t.strip().upper() for t in ["<script",
                                                "SELECT", "INSERT", "DELETE", "UPDATE", "DROP"]]


def _get_fernet() -> Fernet:
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


def _get_config_value(name: str, default=None):
    """
    Safely get config from current_app if in an app context, otherwise fallback to environment.
    """
    if has_app_context():
        return current_app.config.get(name, default)
    return os.getenv(name, default)


def _create_requests_session(retries: int = 2, backoff_factor: float = 0.3, status_forcelist=(500, 502, 503, 504)):
    s = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(["GET", "POST"])
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def _xml_escape_params(**kwargs) -> dict:
    """
    XML-escape all string params to avoid breaking SOAP body or allowing XML injection.
    Non-strings are converted to str() then escaped.
    """
    escaped = {}
    for k, v in kwargs.items():
        if v is None:
            escaped[k] = ""
        else:
            escaped[k] = xml_escape(str(v))
    return escaped


def _is_forbidden(message: str) -> bool:
    mu = message.upper()
    for token in FORBIDDEN_TOKENS:
        if token in mu:
            return True
    return False


def send_single_sms_util(mobile: str, message: str) -> Tuple[int, str]:
    """
    Send a single SMS; returns (status_code, message).
    Keeps previous behavior but:
      - safer Fernet lazy init if you need encryption
      - XML-escapes payload
      - uses a retrying requests session
      - checks app context and falls back to env-based config
    """
    with sms_send_lock:
        logger = logging.getLogger('sms')
        logger.info("Processing single SMS to %s", mobile)

        # Basic validations
        if not PHONE_RE.match(str(mobile)):
            logger.warning("Invalid phone number: %s", mobile)
            return 400, "invalid_phone"

        if not isinstance(message, str) or not (1 <= len(message) <= 500):
            logger.warning("Invalid message length for mobile %s", mobile)
            return 400, "invalid_message_length"

        if _is_forbidden(message):
            logger.warning(
                "Forbidden content in SMS message for mobile %s", mobile)
            return 400, "forbidden_content"

        # Rate limiting - per process fallback. Replace with Redis for multi-process deployments.
        now = time.time()
        if has_app_context():
            rate_store = getattr(current_app, "sms_rate_limit", None)
            if rate_store is None:
                current_app.sms_rate_limit = {}
                rate_store = current_app.sms_rate_limit
        else:
            # process-global fallback
            global _PROCESS_SMS_RATE_LIMIT
            try:
                _PROCESS_SMS_RATE_LIMIT
            except NameError:
                _PROCESS_SMS_RATE_LIMIT = {}
            rate_store = _PROCESS_SMS_RATE_LIMIT

        last_sent = rate_store.get(mobile, 0)
        if now - last_sent < 10:
            logger.warning("Rate limit exceeded for mobile %s", mobile)
            return 429, "rate_limit_exceeded"
        rate_store[mobile] = now

        # Config - prefer Flask config if available
        username = _get_config_value('OTP_USERNAME')
        password = _get_config_value('OTP_PASSWORD')
        senderid = _get_config_value('OTP_SENDERID')
        templateid = _get_config_value('OTP_ID')
        url = _get_config_value('OTP_SERVER')
        otp_flag = _get_config_value('OTP_FLAG', False)
        testing = _get_config_value('TESTING', False)

        # Escape params for XML safety
        params = _xml_escape_params(username=username, password=password, senderid=senderid,
                                    mobile=mobile, message=message, templateid=templateid)

        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                 xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <sendSingleSMS xmlns="http://tempuri.org/">
      <username>{params['username']}</username>
      <password>{params['password']}</password>
      <senderid>{params['senderid']}</senderid>
      <mobileNos>{params['mobile']}</mobileNos>
      <message>{params['message']}</message>
      <templateid1>{params['templateid']}</templateid1>
    </sendSingleSMS>
  </soap12:Body>
</soap12:Envelope>"""

        headers = {
            "Content-Type": "application/soap+xml; charset=utf-8",
            "Content-Length": str(len(soap_body))
        }

        # Skip sending if configured to skip
        if testing or not bool(otp_flag) or not url:
            logger.info(
                "SMS skipped (testing/disabled/missing URL) for mobile %s", mobile)
            return 200, "skipped"

        session = _create_requests_session()

        try:
            logger.info(
                "Sending SOAP SMS request to %s for mobile %s", url, mobile)
            resp = session.post(url, data=soap_body.encode(
                'utf-8'), headers=headers, timeout=30)
            logger.info("SOAP SMS sent. Status: %s", resp.status_code)
            if resp.status_code != 200:
                logger.warning(
                    "Failed to send SOAP SMS. Status: %s, Response: %s", resp.status_code, resp.text)
                return resp.status_code, "gateway_error"
            return 200, "ok"
        except requests.Timeout:
            logger.exception("Timeout sending SOAP SMS to %s", mobile)
            return 408, "timeout"
        except requests.ConnectionError:
            logger.exception("Connection error sending SOAP SMS to %s", mobile)
            return 502, "connection_error"
        except requests.RequestException:
            logger.exception(
                "Unexpected requests error when sending SMS to %s", mobile)
            return 500, "request_exception"
        except Exception:
            logger.exception(
                "Unexpected error in send_single_sms_util for %s", mobile)
            return 500, "internal_error"
