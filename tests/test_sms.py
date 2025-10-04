import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app(); app.config['TESTING']=True
    with app.test_client() as c:
        yield c

AUTH = {'Authorization': 'Bearer your-sms-api-key'}

def test_sms_single_success(client):
    r = client.post('/api/v1/sms/single', headers=AUTH, json={'mobile':'1234567890','message':'hi'})
    assert r.status_code == 200
    assert r.json['status'] == 'success'

def test_sms_bulk_success(client):
    r = client.post('/api/v1/sms/bulk', headers=AUTH, json={'mobiles':['1234567','2345678'],'message':'hi'})
    assert r.status_code == 200
    assert r.json['status'] == 'success'

def test_sms_health(client):
    r = client.get('/api/v1/sms/health')
    assert r.status_code == 200
    assert r.json['data']['health'] == 'healthy'
