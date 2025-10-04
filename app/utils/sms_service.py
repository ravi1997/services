from flask import current_app as app
import requests

def send_sms(mobile, message):
    """
    Sends an SMS using the configured SOAP-based SMS service.

    Args:
        mobile (str): The recipient's mobile number.
        message (str): The message to send.

    Returns:
        int: HTTP status code from the SMS service response.
    """

    import re
    from time import time
    app.logger.info("Preparing to send SMS via SOAP...")

    # Input validation
    phone_pattern = re.compile(r"^\d{6,16}$")
    if not phone_pattern.match(str(mobile)):
        app.logger.warning(f"Invalid phone number: {mobile}")
        app.logger.error(f"Failed SMS delivery: mobile={mobile}, reason=invalid_phone")
        return 400
    if not isinstance(message, str) or not (1 <= len(message) <= 500):
        app.logger.warning(f"Invalid message length for mobile {mobile}")
        app.logger.error(f"Failed SMS delivery: mobile={mobile}, reason=invalid_message_length")
        return 400
    forbidden = ["<script", "SELECT ", "INSERT ", "DELETE ", "UPDATE ", "DROP "]
    if any(f in message.upper() for f in forbidden):
        app.logger.warning(f"Forbidden content in SMS message for mobile {mobile}")
        app.logger.error(f"Failed SMS delivery: mobile={mobile}, reason=forbidden_content")
        return 400

    # Improved rate limiting (per mobile number, 1 SMS per 10 seconds)
    if not hasattr(app, "sms_rate_limit"): app.sms_rate_limit = {}
    now = time()
    last_sent = app.sms_rate_limit.get(mobile, 0)
    if now - last_sent < 10:
        app.logger.warning(f"Rate limit exceeded for mobile {mobile}")
        app.logger.error(f"Failed SMS delivery: mobile={mobile}, reason=rate_limit_exceeded")
        return 429
    app.sms_rate_limit[mobile] = now

    # SMS service config
    username = app.config.get('OTP_USERNAME')
    password = app.config.get('OTP_PASSWORD')
    senderid = app.config.get('OTP_SENDERID')
    templateid = app.config.get('OTP_ID')
    url = app.config.get('OTP_SERVER')

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
    if app.config.get('TESTING') or not app.config.get('OTP_FLAG') or not url:
        app.logger.info("SMS skipped (testing/disabled/missing URL). Returning 200 for mobile %s", mobile)
        return 200

    try:
        app.logger.info(
            f"Sending SOAP SMS request to {url} for mobile {mobile}")

        # Added timeout to prevent indefinite hanging
        response = requests.post(
            url, data=soap_body.encode('utf-8'), headers=headers, timeout=30)

        app.logger.info(f"SOAP SMS sent. Status: {response.status_code}")
        if response.status_code != 200:
            app.logger.warning(
                f"Failed to send SOAP SMS. Status: {response.status_code}, Response: {response.text}"
            )
            # Log failed SMS delivery attempt
            app.logger.error(f"Failed SMS delivery: mobile={mobile}, status={response.status_code}, response={response.text}")
        return response.status_code

    except requests.Timeout:
        app.logger.error(
            f"Timeout sending SOAP SMS to {mobile}: request timed out after 30 seconds")
        # Log failed SMS delivery attempt
        app.logger.error(f"Failed SMS delivery: mobile={mobile}, reason=timeout")
        return 408  # Request Timeout
    except requests.ConnectionError:
        app.logger.error(
            f"Connection error sending SOAP SMS to {mobile}: could not connect to server")
        # Log failed SMS delivery attempt
        app.logger.error(f"Failed SMS delivery: mobile={mobile}, reason=connection_error")
        return 502  # Bad Gateway
    except requests.RequestException as e:
        app.logger.error(
            f"Error sending SOAP SMS to {mobile}: {e}")
        # Log failed SMS delivery attempt
        app.logger.error(f"Failed SMS delivery: mobile={mobile}, error={e}")
        return 500
