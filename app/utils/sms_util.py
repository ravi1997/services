import threading
import time
from flask import current_app
import requests
import re
import logging
from cryptography.fernet import Fernet
import os

# Get encryption key from environment, with fallback
encryption_key = os.getenv('ENCRYPTION_KEY', '0123456789abcdef0123456789abcdef')
# Ensure the encryption key is properly formatted for Fernet (must be 32 bytes URL-safe base64 encoded)
if isinstance(encryption_key, str) and len(encryption_key) != 32:
    # If it's not the right length, we need to encode it properly
    import base64
    import hashlib
    # Create a proper 32-byte key from the string
    key_bytes = hashlib.sha256(encryption_key.encode()).digest()
    _ENCRYPTION_KEY = base64.urlsafe_b64encode(key_bytes)
else:
    _ENCRYPTION_KEY = encryption_key.encode() if isinstance(encryption_key, str) else encryption_key
fernet = Fernet(_ENCRYPTION_KEY)

# Thread lock for SMS sending
sms_send_lock = threading.Lock()

def send_single_sms_util(mobile, message):
    """
    Utility function to send a single SMS with thread locking.
    This is the thread-safe function that actually sends the SMS.
    """
    with sms_send_lock:
        logging.getLogger('sms').info(f"Processing single SMS to {mobile}")
        
        # Input validation
        phone_pattern = re.compile(r"^\d{6,16}$")
        if not phone_pattern.match(str(mobile)):
            logging.getLogger('sms').warning(f"Invalid phone number: {mobile}")
            logging.getLogger('sms').error(f"Failed SMS delivery: mobile={mobile}, reason=invalid_phone")
            return 400
        if not isinstance(message, str) or not (1 <= len(message) <= 500):
            logging.getLogger('sms').warning(f"Invalid message length for mobile {mobile}")
            logging.getLogger('sms').error(f"Failed SMS delivery: mobile={mobile}, reason=invalid_message_length")
            return 400
        forbidden = ["<script", "SELECT ", "INSERT ", "DELETE ", "UPDATE ", "DROP "]
        if any(f in message.upper() for f in forbidden):
            logging.getLogger('sms').warning(f"Forbidden content in SMS message for mobile {mobile}")
            logging.getLogger('sms').error(f"Failed SMS delivery: mobile={mobile}, reason=forbidden_content")
            return 400

        # Rate limiting (per mobile number, 1 SMS per 10 seconds)
        if not hasattr(current_app, "sms_rate_limit"): 
            current_app.sms_rate_limit = {}
        now = time.time()
        last_sent = current_app.sms_rate_limit.get(mobile, 0)
        if now - last_sent < 10:
            logging.getLogger('sms').warning(f"Rate limit exceeded for mobile {mobile}")
            logging.getLogger('sms').error(f"Failed SMS delivery: mobile={mobile}, reason=rate_limit_exceeded")
            return 429
        current_app.sms_rate_limit[mobile] = now

        # SMS service config
        username = current_app.config.get('OTP_USERNAME')
        password = current_app.config.get('OTP_PASSWORD')
        senderid = current_app.config.get('OTP_SENDERID')
        templateid = current_app.config.get('OTP_ID')
        url = current_app.config.get('OTP_SERVER')

        # SOAP Envelope (SOAP 1.2)
        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
        <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
                         xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
                         xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
            <soap12:Body>
                <sendSingleSMS xmlns="http://tempuri.org/">
                    <username>{username}</username>
                        <password>{password}</password>
                        <senderid>{senderid}</senderid>
                        <mobileNos>{mobile}</mobileNos>
                        <message>{message}</message>
                        <templateid1>{templateid}</templateid1>
                    </sendSingleSMS>
                </soap12:Body>
            </soap12:Envelope>"""

        headers = {
            "Content-Type": "application/soap+xml; charset=utf-8",
            "Content-Length": str(len(soap_body))
        }

        # Skip real sending if:
        # - In testing mode
        # - OTP_FLAG is False
        # - Required gateway URL not configured
        if current_app.config.get('TESTING') or not current_app.config.get('OTP_FLAG') or not url:
            logging.getLogger('sms').info("SMS skipped (testing/disabled/missing URL). Returning 200 for mobile %s", mobile)
            return 200

        try:
            logging.getLogger('sms').info(
                f"Sending SOAP SMS request to {url} for mobile {mobile}")

            # Added timeout to prevent indefinite hanging
            response = requests.post(
                url, data=soap_body.encode('utf-8'), headers=headers, timeout=30)

            logging.getLogger('sms').info(f"SOAP SMS sent. Status: {response.status_code}")
            if response.status_code != 200:
                logging.getLogger('sms').warning(
                    f"Failed to send SOAP SMS. Status: {response.status_code}, Response: {response.text}"
                )
                # Log failed SMS delivery attempt
                logging.getLogger('sms').error(f"Failed SMS delivery: mobile={mobile}, status={response.status_code}, response={response.text}")
            return response.status_code

        except requests.Timeout:
            logging.getLogger('sms').error(
                f"Timeout sending SOAP SMS to {mobile}: request timed out after 30 seconds")
            # Log failed SMS delivery attempt
            logging.getLogger('sms').error(f"Failed SMS delivery: mobile={mobile}, reason=timeout")
            return 408  # Request Timeout
        except requests.ConnectionError:
            logging.getLogger('sms').error(
                f"Connection error sending SOAP SMS to {mobile}: could not connect to server")
            # Log failed SMS delivery attempt
            logging.getLogger('sms').error(f"Failed SMS delivery: mobile={mobile}, reason=connection_error")
            return 502  # Bad Gateway
        except requests.RequestException as e:
            logging.getLogger('sms').error(
                f"Error sending SOAP SMS to {mobile}: {e}")
            # Log failed SMS delivery attempt
            logging.getLogger('sms').error(f"Failed SMS delivery: mobile={mobile}, error={e}")
            return 500