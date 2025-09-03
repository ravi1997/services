import pytest
from datetime import datetime, timedelta, timezone

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        from app.extensions import db
        from app.models.sms_message import SMSMessage
        # clean slate
        db.session.query(SMSMessage).delete()
        now = datetime.now(timezone.utc)
        # seed data
        for i in range(35):
            status = 'sent' if i % 2 == 0 else 'queued'
            created = now - timedelta(minutes=i)
            msg = SMSMessage(to=f"+910000000{i:02d}", message=f"hello {i}", status=status, attempts=i % 3, created_at=created)
            db.session.add(msg)
        db.session.commit()
    with app.test_client() as client:
        yield client


def test_messages_unauthorized(client):
    resp = client.get('/api/v1/sms/messages')
    assert resp.status_code == 401


def test_messages_list_pagination(client):
    headers = {"Authorization": "Bearer your-admin-api-key"}
    resp = client.get('/api/v1/sms/messages', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'items' in data
    assert data['page'] == 1
    assert data['per_page'] == 20
    assert data['total'] >= 35
    assert len(data['items']) == 20
    # next page
    resp2 = client.get('/api/v1/sms/messages?page=2', headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2['page'] == 2
    assert len(data2['items']) > 0


def test_messages_filters(client):
    headers = {"Authorization": "Bearer your-admin-api-key"}
    # filter by status
    resp = client.get('/api/v1/sms/messages?status=sent', headers=headers)
    assert resp.status_code == 200
    items = resp.get_json()['items']
    assert all(it['status'] == 'sent' for it in items)
    # since filter
    now_iso = datetime.now(timezone.utc).isoformat()
    resp2 = client.get(f'/api/v1/sms/messages?since={now_iso}', headers=headers)
    assert resp2.status_code == 200
    # likely none newer than now
    assert resp2.get_json()['total'] == 0
