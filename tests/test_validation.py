import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


AUTH = {'Authorization': 'Bearer your-sms-api-key'}

def test_sms_single_invalid_phone(client):
    resp = client.post('/api/v1/sms/single', headers=AUTH, json={"mobile": "12345", "message": "test"})
    assert resp.status_code == 400


def test_sms_single_message_too_long(client):
    long_msg = "x" * 600
    resp = client.post('/api/v1/sms/single', headers=AUTH, json={"mobile": "+911234567890", "message": long_msg})
    assert resp.status_code == 400
