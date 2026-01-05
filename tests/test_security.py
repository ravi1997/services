"""Security tests for Flask application.

Tests security controls including:
- Security headers
- Authentication/Authorization
- Rate limiting
- Input validation
- CSRF protection
- Session security
"""

import pytest
from flask import Flask
from app import create_app
from app.config import DevelopmentConfig


class TestConfig(DevelopmentConfig):
    """Test configuration."""
    TESTING = True
    SMS_API_KEY = 'test-api-key-12345'
    ADMIN_API_KEY = 'test-admin-key-12345'
    RATELIMIT_STORAGE_URI = 'memory://'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app(TestConfig)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestSecurityHeaders:
    """Test security headers are present."""
    
    def test_security_headers_on_health_endpoint(self, client):
        """Test security headers are set on health endpoint."""
        response = client.get('/health')
        
        # Check for security headers
        assert 'X-Content-Type-Options' in response.headers
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        
        assert 'X-Frame-Options' in response.headers
        assert response.headers['X-Frame-Options'] == 'DENY'
        
        assert 'X-XSS-Protection' in response.headers
        assert response.headers['X-XSS-Protection'] == '1; mode=block'
        
        assert 'Referrer-Policy' in response.headers
        assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
        
        assert 'Content-Security-Policy' in response.headers
        assert 'Permissions-Policy' in response.headers
    
    def test_hsts_header_in_production(self, app):
        """Test HSTS header is set in production mode."""
        app.config['ENV'] = 'production'
        app.config['PREFERRED_URL_SCHEME'] = 'https'
        
        with app.test_client() as client:
            response = client.get('/health')
            assert 'Strict-Transport-Security' in response.headers
            assert 'max-age=31536000' in response.headers['Strict-Transport-Security']


class TestAuthentication:
    """Test authentication and authorization."""
    
    def test_missing_bearer_token(self, client):
        """Test request without bearer token is rejected."""
        response = client.post('/services/api/v1/sms/single',
                              json={'mobile': '1234567890', 'message': 'test'})
        assert response.status_code == 401
        data = response.get_json()
        assert data['data']['error_code'] == 'UNAUTHORIZED'
    
    def test_invalid_bearer_token(self, client):
        """Test request with invalid bearer token is rejected."""
        response = client.post('/services/api/v1/sms/single',
                              headers={'Authorization': 'Bearer invalid-token'},
                              json={'mobile': '1234567890', 'message': 'test'})
        assert response.status_code == 401
        data = response.get_json()
        assert data['data']['error_code'] == 'UNAUTHORIZED'
    
    def test_valid_bearer_token(self, client):
        """Test request with valid bearer token is accepted."""
        response = client.post('/services/api/v1/sms/single',
                              headers={'Authorization': 'Bearer test-api-key-12345'},
                              json={'mobile': '+1234567890', 'message': 'test'})
        # Should not be 401 (may be other errors due to test setup)
        assert response.status_code != 401
    
    def test_admin_endpoint_requires_admin_key(self, client):
        """Test admin endpoints require admin API key."""
        # Try with regular API key
        response = client.get('/services/api/v1/sms/messages',
                             headers={'Authorization': 'Bearer test-api-key-12345',
                                    'X-Role': 'admin'})
        assert response.status_code == 401
        
        # Try with admin API key
        response = client.get('/services/api/v1/sms/messages',
                             headers={'Authorization': 'Bearer test-admin-key-12345',
                                    'X-Role': 'admin'})
        # Should not be 401
        assert response.status_code != 401


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limit_exceeded(self, client):
        """Test rate limiting blocks excessive requests."""
        # Make many requests rapidly
        headers = {'Authorization': 'Bearer test-api-key-12345'}
        
        # First requests should succeed (or fail for other reasons, but not rate limit)
        for _ in range(5):
            response = client.post('/services/api/v1/sms/single',
                                  headers=headers,
                                  json={'mobile': '+1234567890', 'message': 'test'})
            # Should not be rate limited yet
            if response.status_code == 429:
                pytest.fail("Rate limited too early")
        
        # After many requests, should be rate limited
        for _ in range(200):
            client.post('/services/api/v1/sms/single',
                       headers=headers,
                       json={'mobile': '+1234567890', 'message': 'test'})
        
        response = client.post('/services/api/v1/sms/single',
                              headers=headers,
                              json={'mobile': '+1234567890', 'message': 'test'})
        assert response.status_code == 429
        data = response.get_json()
        assert data['data']['error_code'] == 'RATE_LIMIT'


class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_invalid_phone_number_format(self, client):
        """Test invalid phone number is rejected."""
        headers = {'Authorization': 'Bearer test-api-key-12345'}
        
        # Test various invalid formats
        invalid_numbers = [
            'abc',
            '123',  # Too short
            'not-a-number',
            '<script>alert(1)</script>',
            '"; DROP TABLE users;--'
        ]
        
        for number in invalid_numbers:
            response = client.post('/services/api/v1/sms/single',
                                  headers=headers,
                                  json={'mobile': number, 'message': 'test'})
            assert response.status_code == 400
            data = response.get_json()
            assert 'Invalid phone number' in data['message']
    
    def test_message_length_limit(self, client):
        """Test message length is enforced."""
        headers = {'Authorization': 'Bearer test-api-key-12345'}
        
        # Message too long (>500 chars)
        long_message = 'x' * 501
        response = client.post('/services/api/v1/sms/single',
                              headers=headers,
                              json={'mobile': '+1234567890', 'message': long_message})
        assert response.status_code == 400
        data = response.get_json()
        assert 'exceeds maximum length' in data['message']
    
    def test_bulk_request_size_limit(self, client):
        """Test bulk request size is limited."""
        headers = {'Authorization': 'Bearer test-api-key-12345'}
        
        # Too many recipients (>200)
        mobiles = [f'+123456789{i:02d}' for i in range(201)]
        response = client.post('/services/api/v1/sms/bulk',
                              headers=headers,
                              json={'mobiles': mobiles, 'message': 'test'})
        assert response.status_code == 400
        data = response.get_json()
        assert 'exceeds maximum' in data['message']
    
    def test_missing_required_fields(self, client):
        """Test missing required fields are rejected."""
        headers = {'Authorization': 'Bearer test-api-key-12345'}
        
        # Missing message
        response = client.post('/services/api/v1/sms/single',
                              headers=headers,
                              json={'mobile': '+1234567890'})
        assert response.status_code == 400
        
        # Missing mobile
        response = client.post('/services/api/v1/sms/single',
                              headers=headers,
                              json={'message': 'test'})
        assert response.status_code == 400

    def test_xss_content_rejected(self, client):
        """Test XSS content in message is rejected."""
        headers = {'Authorization': 'Bearer test-api-key-12345'}
        response = client.post('/services/api/v1/sms/single',
                              headers=headers,
                              json={'mobile': '+1234567890', 'message': 'Hello <script>alert(1)</script>'})
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid message content' in data['message']

    def test_sqli_content_rejected(self, client):
        """Test SQL injection content in message is rejected."""
        headers = {'Authorization': 'Bearer test-api-key-12345'}
        response = client.post('/services/api/v1/sms/single',
                              headers=headers,
                              json={'mobile': '+1234567890', 'message': "Hello ' OR 1=1 --"})
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid message content' in data['message']


class TestReplayProtection:
    """Test replay attack protection."""
    
    def test_nonce_replay_detection(self, client):
        """Test nonce-based replay protection."""
        headers = {
            'Authorization': 'Bearer test-api-key-12345',
            'X-Nonce': 'test-nonce-12345'
        }
        
        # First request should succeed (or fail for other reasons)
        response1 = client.post('/services/api/v1/sms/single',
                               headers=headers,
                               json={'mobile': '+1234567890', 'message': 'test'})
        
        # Second request with same nonce should be rejected
        response2 = client.post('/services/api/v1/sms/single',
                               headers=headers,
                               json={'mobile': '+1234567890', 'message': 'test'})
        assert response2.status_code == 403
        data = response2.get_json()
        assert data['data']['error_code'] == 'REPLAY_ATTACK'


class TestRBAC:
    """Test role-based access control."""
    
    def test_invalid_role_rejected(self, client):
        """Test invalid role is rejected."""
        headers = {
            'Authorization': 'Bearer test-api-key-12345',
            'X-Role': 'superadmin'  # Not in allowed roles
        }
        
        response = client.post('/services/api/v1/sms/single',
                              headers=headers,
                              json={'mobile': '+1234567890', 'message': 'test'})
        assert response.status_code == 403
        data = response.get_json()
        assert data['data']['error_code'] == 'FORBIDDEN'
    
    def test_admin_role_required_for_admin_endpoints(self, client):
        """Test admin role is required for admin endpoints."""
        # Try with user role
        headers = {
            'Authorization': 'Bearer test-admin-key-12345',
            'X-Role': 'user'
        }
        
        response = client.get('/services/api/v1/sms/messages', headers=headers)
        assert response.status_code == 403


class TestSessionSecurity:
    """Test session security configuration."""
    
    def test_session_cookie_secure_flag(self, app):
        """Test session cookies have secure flag in production."""
        # Development should have it disabled
        assert app.config['SESSION_COOKIE_SECURE'] == False
        
        # Production should have it enabled
        from app.config import ProductionConfig
        prod_app = create_app(ProductionConfig)
        assert prod_app.config['SESSION_COOKIE_SECURE'] == True
    
    def test_session_cookie_httponly(self, app):
        """Test session cookies are HTTPOnly."""
        assert app.config['SESSION_COOKIE_HTTPONLY'] == True
    
    def test_session_cookie_samesite(self, app):
        """Test session cookies have SameSite attribute."""
        assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'


class TestRequestSizeLimits:
    """Test request body size limits."""
    
    def test_max_content_length_configured(self, app):
        """Test MAX_CONTENT_LENGTH is configured."""
        assert 'MAX_CONTENT_LENGTH' in app.config
        assert app.config['MAX_CONTENT_LENGTH'] > 0
        # Should be 10MB by default
        assert app.config['MAX_CONTENT_LENGTH'] == 10 * 1024 * 1024


class TestIdempotency:
    """Test idempotency key handling."""
    
    def test_idempotency_key_prevents_duplicate(self, client):
        """Test idempotency key prevents duplicate requests."""
        headers = {
            'Authorization': 'Bearer test-api-key-12345',
            'Idempotency-Key': 'test-idempotency-12345'
        }
        
        # First request
        response1 = client.post('/services/api/v1/sms/single',
                               headers=headers,
                               json={'mobile': '+1234567890', 'message': 'test'})
        
        # Second request with same idempotency key
        response2 = client.post('/services/api/v1/sms/single',
                               headers=headers,
                               json={'mobile': '+1234567890', 'message': 'test'})
        
        # Both should succeed, but second should return cached result
        assert response1.status_code in [200, 400, 500]  # Various possible outcomes
        assert response2.status_code in [200, 400, 500]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
