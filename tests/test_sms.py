import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_send_sms_unauthorized(client):
    response = client.post('/api/v1/sms/send', json={"to": "+911234567890", "message": "test"})
    assert response.status_code == 401

def test_send_sms_invalid_payload(client):
    headers = {"Authorization": "Bearer your-sms-api-key"}
    response = client.post('/api/v1/sms/send', json={"to": ""}, headers=headers)
    assert response.status_code == 400

def test_send_sms_success(client):
    headers = {"Authorization": "Bearer your-sms-api-key"}
    response = client.post('/api/v1/sms/send', json={"to": "+911234567890", "message": "test"}, headers=headers)
    assert response.status_code == 202
    assert 'task_id' in response.json
