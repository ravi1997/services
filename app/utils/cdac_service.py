from flask import current_app as app
import requests
import logging
import re
from time import sleep
from app.utils.response import error

def mask_sensitive(data):
	if isinstance(data, str):
		# Mask sensitive data like phone numbers, employee IDs, etc.
		# Mask middle digits of numbers
		masked = re.sub(r'(\d{2})\d{2,}(\d{2})', r'\1**\2', data)
		# Mask URLs but keep the domain structure
		masked = re.sub(r'(https?://)([^/]+)', r'\1***', masked)
		return masked
	return data

def validate_emp_id(emp_id):
	# Validate employee ID format - alphanumeric, 5-12 characters
	if not isinstance(emp_id, (str, int)):
		return False
	emp_id_str = str(emp_id)
	return bool(re.match(r'^[A-Za-z0-9]{5,12}$', emp_id_str))

def call_third_party_api(search_key, access_token, api_url, key_type="emp_id", timeout=10, max_retries=3):
	headers = {"Authorization": f"Bearer {access_token}"}
	params = {"keyType": key_type, "searchKey": search_key}
	
	for attempt in range(max_retries):
		try:
			app.logger.info(f"Calling third-party API at {mask_sensitive(api_url)} with searchKey: {mask_sensitive(str(search_key))}")
			response = requests.post(api_url, headers=headers, params=params, timeout=timeout)
			app.logger.info(f"Third-party API response status: {response.status_code}")
			return response
		except requests.Timeout:
			app.logger.warning(f"Timeout calling third-party API (attempt {attempt+1})")
			if attempt == max_retries - 1:  # Last attempt
				app.logger.error(f"Failed to call third-party API after {max_retries} attempts due to timeout")
			sleep(1)
		except requests.ConnectionError:
			app.logger.warning(f"Connection error calling third-party API (attempt {attempt+1})")
			if attempt == max_retries - 1:  # Last attempt
				app.logger.error(f"Failed to call third-party API after {max_retries} attempts due to connection error")
			sleep(1)
		except requests.RequestException as e:
			app.logger.warning(f"Request error calling third-party API (attempt {attempt+1}): {type(e).__name__}")
			if attempt == max_retries - 1:  # Last attempt
				app.logger.error(f"Failed to call third-party API after {max_retries} attempts due to request error: {e}")
			sleep(1)
	return None

def validate_response_schema(data):
	# Example: expect dict with 'status' and 'result' keys
	return isinstance(data, dict) and 'status' in data and 'result' in data

def cdac_service(emp_id: str, config=None, audit_logger=None) -> dict | str:
	"""
	Fetches employee details using the CDAC API.
	Args:
		emp_id (str): Employee ID to search.
		config (dict): Optional config for dependency injection.
		audit_logger: Optional audit logger for compliance.
	Returns:
		dict | str: JSON data if the call is successful, otherwise an error message.
	"""
	if config is None:
		config = app.config
	if audit_logger is None:
		audit_logger = logging.getLogger('audit_logger')
	# Input validation
	if not validate_emp_id(emp_id):
		app.logger.warning(f"Invalid emp_id: {mask_sensitive(emp_id)}")
		audit_logger.warning(f"Invalid emp_id: {mask_sensitive(emp_id)}")
		return error("Invalid employee ID format", "INVALID_INPUT", 400)
	# Auth check
	access_token = config.get("CDAC_AUTH_BEARER")
	if not access_token:
		app.logger.error("Access token not found in configuration.")
		audit_logger.error("Access token missing for CDAC API call.")
		return error("Access token missing", "SERVER_ERROR", 500)
	# Authorization check (example: require 'can_access_cdac' in config)
	if not config.get("CAN_ACCESS_CDAC", True):
		app.logger.warning("Unauthorized attempt to access CDAC API.")
		audit_logger.warning("Unauthorized CDAC API access attempt.")
		return error("Unauthorized", "FORBIDDEN", 403)
	api_url = config.get("CDAC_SERVER")
	if not api_url:
		app.logger.error("CDAC_SERVER not configured.")
		audit_logger.error("CDAC_SERVER missing in config.")
		return error("API server not configured", "SERVER_ERROR", 500)
	response_api = call_third_party_api(emp_id, access_token, api_url)
	if response_api and response_api.status_code == 200:
		try:
			data = response_api.json()
			if not validate_response_schema(data):
				app.logger.error("API response schema invalid.")
				audit_logger.error("API response schema invalid.")
				return error("Invalid response format", "INVALID_RESPONSE", 502)
			app.logger.info("Successfully fetched data from the third-party API.")
			audit_logger.info(f"CDAC API call success for emp_id={mask_sensitive(emp_id)}")
			return data
		except Exception as e:
			app.logger.error(f"Error parsing API response: {e}")
			audit_logger.error(f"Error parsing API response: {e}")
			return error("Error parsing response", "RESPONSE_ERROR", 502)
	else:
		error_msg = f"API call failed. Status: {response_api.status_code if response_api else 'No response'}"
		app.logger.error(error_msg)
		audit_logger.error(error_msg)
		return error("API call failed", "API_ERROR", response_api.status_code if response_api else 502)