import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


AUTH = {'Authorization': 'Bearer your-sms-api-key'}

def test_sms_single_success(client):
    r = client.post('/api/v1/sms/single', headers=AUTH, json={'mobile': '9876543210', 'message': 'hi'})
    assert r.status_code == 200
    assert r.json['status'] == 'success'


def test_sms_bulk_success(client):
    r = client.post('/api/v1/sms/bulk', headers=AUTH, json={'mobiles': ['1234567','2345678'], 'message': 'x'})
    assert r.status_code == 200
    assert r.json['status'] == 'success'


def test_sms_health_fail(client):
    r = client.get('/api/v1/sms/health?fail=1')
    assert r.status_code == 503
    assert r.json['data']['error_code'] == 'SMS_SERVICE_UNHEALTHY'


def test_cdac_health_fail(client):
    r = client.get('/api/v1/cdac/health?fail=1')
    assert r.status_code == 503
    assert r.json['data']['error_code'] == 'CDAC_SERVICE_UNHEALTHY'


def test_mail_health_fail(client):
    r = client.get('/api/v1/mail/health?fail=1')
    assert r.status_code == 503
    assert r.json['data']['error_code'] == 'EMAIL_SERVICE_UNHEALTHY'


def test_ehospital_health_fail(client):
    r = client.get('/api/v1/ehospital/health?fail=1')
    assert r.status_code == 503
    assert r.json['data']['error_code'] == 'EHOSPITAL_SERVICE_UNHEALTHY'