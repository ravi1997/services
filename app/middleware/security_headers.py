"""Security headers middleware for Flask application.

Adds comprehensive security headers to all HTTP responses to protect against
common web vulnerabilities.
"""

from flask import Flask


def add_security_headers(app: Flask):
    """Add security headers to all responses.
    
    Headers added:
    - Strict-Transport-Security (HSTS): Force HTTPS
    - X-Content-Type-Options: Prevent MIME sniffing
    - X-Frame-Options: Prevent clickjacking
    - X-XSS-Protection: Enable XSS filter (legacy browsers)
    - Referrer-Policy: Control referrer information
    - Content-Security-Policy: Prevent XSS and injection attacks
    - Permissions-Policy: Control browser features
    """
    
    @app.after_request
    def set_security_headers(response):
        """Set security headers on all responses."""
        
        # HSTS - Force HTTPS for 1 year (31536000 seconds)
        # Only set in production or when HTTPS is available
        if app.config.get('ENV') == 'production' or app.config.get('PREFERRED_URL_SCHEME') == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking - deny embedding in frames
        response.headers['X-Frame-Options'] = 'DENY'
        
        # XSS Protection (legacy, but still useful for older browsers)
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer Policy - don't send referrer to external sites
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy
        # For API endpoints, we use a restrictive policy
        # Adjust based on your needs (e.g., if serving HTML pages)
        csp_policy = app.config.get('CONTENT_SECURITY_POLICY', 
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers['Content-Security-Policy'] = csp_policy
        
        # Permissions Policy (formerly Feature-Policy)
        # Disable potentially dangerous browser features
        response.headers['Permissions-Policy'] = (
            'geolocation=(), '
            'microphone=(), '
            'camera=(), '
            'payment=(), '
            'usb=(), '
            'magnetometer=(), '
            'gyroscope=(), '
            'accelerometer=()'
        )
        
        return response
    
    return app
