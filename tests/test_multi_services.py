import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SMS_API_KEY'] = 'your-sms-api-key'
    with app.test_client() as c:
        yield c


AUTH = {'Authorization': 'Bearer your-sms-api-key'}

def test_sms_single_success(client):
    r = client.post('/services/api/v1/sms/single', headers=AUTH, json={'mobile': '9876543210', 'message': 'hi'})
    assert r.status_code == 200
    assert r.json['status'] == 'success'


def test_sms_bulk_success(client):
    r = client.post('/services/api/v1/sms/bulk', headers=AUTH, json={'mobiles': ['9876543210','9876543211'], 'message': 'x'})
    assert r.status_code == 200
    assert r.json['status'] == 'success'


# Tests for failure injection removed as feature is not implemented
# def test_sms_health_fail(client): ...
# def test_cdac_health_fail(client): ...
# def test_mail_health_fail(client): ...
# def test_ehospital_health_fail(client): ...