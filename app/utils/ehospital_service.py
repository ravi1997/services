import logging
from flask import Blueprint, jsonify, request
import requests


def send_ehospital_init(current_app):
    current_app.logger.info("Initializing eHospital session")
    url = current_app.config['EHOSPITAL_INIT_URL']
    headers = {'Content-Type': 'application/json'}
    data = {
        'username': current_app.config['EHOSPITAL_USERNAME'],
        'password': current_app.config['EHOSPITAL_PASSWORD']
    }
    current_app.logger.debug(
        f"eHospital init URL: {url}, Data: {data}, Headers: {headers}")
    try:
        response = requests.post(url, headers=headers, json=data)
        current_app.logger.info(
            f"eHospital init response code: {response.status_code}, response: {response.text}")
        if response.status_code in [200, 201]:
            response_data = response.json()
            token = response_data.get('token')
            current_app.logger.info(f"eHospital token received: {token}")
            return token
        else:
            current_app.logger.error("Failed to initialize eHospital session")
            return ""
    except Exception as e:
        current_app.logger.error(f"Error initializing eHospital session: {e}")
        return ""


def send_ehospital_uhid(current_app, uhid):
    current_app.logger.info("send_ehospital_uhid route called")
    current_app.logger.debug(f"Received UHID: {uhid}")
    if not uhid:
        current_app.logger.warning("UHID missing in request")
        return jsonify({"error": "UHID is required"}), 400

    token = send_ehospital_init(current_app)
    if token == "":
        current_app.logger.error("No token received from eHospital init")
        return None

    data = {
        'hospital_id': current_app.config['EHOSPITAL_HOSPITAL_ID'],
        'reg_no': uhid,
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    url = current_app.config['EHOSPITAL_FETCH_PATIENT_URL']
    current_app.logger.debug(
        f"eHospital fetch patient URL: {url}, Data: {data}, Headers: {headers}")
    try:
        response = requests.post(url, json=data, headers=headers)
        current_app.logger.info(
            f"eHospital fetch patient response code: {response.status_code}, response: {response.text}")
        if response.status_code in [200, 201]:
            response_data = response.json()
            patientDetails = response_data.get('patientDetails')
            current_app.logger.info(
                f"Patient details received: {patientDetails}")
            return patientDetails
        else:
            current_app.logger.error(
                "Failed to fetch patient details from eHospital")
            return None
    except Exception as e:
        current_app.logger.error(f"Error fetching patient details: {e}")
        return None
