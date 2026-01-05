# Security Hardening Guide

## Overview

This document describes the security hardening measures implemented for the Flask services application handling PHI/PII data (SMS, Email, CDAC, eHospital services).

**Last Updated:** 2026-01-05  
**Version:** 1.0  
**Environment:** Development/Staging/Production

---

## Security Controls Implemented

### 1. Security Headers

**Location:** `app/middleware/security_headers.py`

All HTTP responses include comprehensive security headers:

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS (production only) |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Enable XSS filter (legacy browsers) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer information |
| `Content-Security-Policy` | Restrictive policy | Prevent XSS and injection attacks |
| `Permissions-Policy` | Disabled features | Disable dangerous browser features |

**Verification:**
```bash
curl -I https://your-domain.com/health
# Check for all security headers
```

---

### 2. Configuration Security

**Location:** `app/config.py`

**Improvements:**
- ✅ Strong `SECRET_KEY` generation (64-char hex)
- ✅ No weak defaults for sensitive values
- ✅ Production fail-fast for missing secrets
- ✅ Session security configuration
- ✅ Request body size limits (10MB default)

**Required Environment Variables (Production):**
```bash
SECRET_KEY=<64-char-hex-string>
ENCRYPTION_KEY=<64-char-hex-string>
SMS_API_KEY=<strong-api-key>
ADMIN_API_KEY=<strong-admin-key>
```

**Generate Secrets:**
```bash
python -c 'import secrets; print(secrets.token_hex(32))'
```

**Session Security:**
- `SESSION_COOKIE_SECURE=True` (production)
- `SESSION_COOKIE_HTTPONLY=True`
- `SESSION_COOKIE_SAMESITE=Lax`
- `PERMANENT_SESSION_LIFETIME=3600` (1 hour)

---

### 3. Secure Logging

**Location:** `app/utils/decorators.py`

**Changes:**
- ❌ Removed token logging from audit logs
- ✅ Log authentication success/failure without exposing tokens
- ✅ PHI/PII-safe logging patterns

**Before:**
```python
audit_logger.warning(f"Malformed token: ip={ip}, token={token}")  # ❌ Exposes token
```

**After:**
```python
audit_logger.warning(f"Authentication failed: ip={ip}, reason=invalid_token")  # ✅ Safe
```

---

### 4. Authentication & Authorization

**Existing Controls:**
- ✅ Bearer token authentication
- ✅ Rate limiting (Redis-backed)
- ✅ IP-based access control
- ✅ Nonce-based replay protection
- ✅ Role-based access control (RBAC)
- ✅ Idempotency key support

**Rate Limits:**
- Single SMS: 200/minute
- Bulk SMS: 10/minute
- Health checks: 5/minute
- Admin endpoints: 5/minute

---

### 5. Input Validation

**Existing Controls:**
- ✅ Phone number validation (regex)
- ✅ Email validation (regex)
- ✅ Message length limits (500 chars for SMS, 10000 for email)
- ✅ Bulk request size limits (200 max)
- ✅ Request body size limits (10MB)

**Validation Patterns:**
```python
# Phone: ^\\+?[1-9]\\d{5,14}$
# Email: ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$
```

---

### 6. Data Protection

**PHI/PII Encryption:**
- ✅ Encryption key configured (`ENCRYPTION_KEY`)
- ✅ Sensitive data encrypted at rest
- ✅ No sensitive data in logs

**Logging Policy:**
- ❌ Never log: tokens, passwords, API keys, PHI/PII fields
- ✅ Log: request ID, IP, method, path, status, latency
- ✅ Redact: Authorization headers, sensitive query params

---

## Security Testing

**Location:** `tests/test_security.py`

**Test Coverage:**
- ✅ Security headers presence
- ✅ Authentication/Authorization
- ✅ Rate limiting
- ✅ Input validation
- ✅ Replay protection
- ✅ RBAC
- ✅ Session security
- ✅ Request size limits

**Run Tests:**
```bash
source .venv/bin/activate
pytest tests/test_security.py -v
```

---

## Security Checklist

### Deployment Checklist

- [ ] All environment variables set in production
- [ ] Secrets are strong (64+ chars, random)
- [ ] HTTPS enabled (HSTS will activate)
- [ ] Rate limiting Redis instance configured
- [ ] Database encryption at rest enabled
- [ ] Firewall rules configured for IP allowlist
- [ ] Monitoring and alerting configured
- [ ] Security headers verified in production

### Ongoing Maintenance

- [ ] Weekly: Review security logs for anomalies
- [ ] Monthly: Rotate API keys and secrets
- [ ] Quarterly: Run dependency vulnerability scans
- [ ] Annually: Full security audit

---

## Incident Response

### Security Event Types

1. **Authentication Failures** - Multiple failed login attempts
2. **Rate Limit Violations** - Excessive requests from single IP
3. **Replay Attacks** - Duplicate nonce detected
4. **RBAC Violations** - Unauthorized role access attempts
5. **Input Validation Failures** - Malicious input patterns

### Response Procedure

1. **Detect** - Monitor logs for security events
2. **Contain** - Block malicious IP if needed
3. **Investigate** - Review audit logs
4. **Remediate** - Fix vulnerability
5. **Document** - Create incident report

**Emergency Contacts:**
- Security Team: [contact-info]
- DevOps Team: [contact-info]

---

## Configuration Examples

### Development (.env)
```bash
APP_ENV=development
DEBUG=True
SECRET_KEY=dev-secret-key-not-for-production
SMS_API_KEY=dev-api-key
ADMIN_API_KEY=dev-admin-key
ENCRYPTION_KEY=dev-encryption-key
SESSION_COOKIE_SECURE=False
```

### Production (.env)
```bash
APP_ENV=production
DEBUG=False
SECRET_KEY=<generate-with-secrets.token_hex(32)>
SMS_API_KEY=<strong-random-key>
ADMIN_API_KEY=<strong-random-key>
ENCRYPTION_KEY=<generate-with-secrets.token_hex(32)>
SESSION_COOKIE_SECURE=True
PREFERRED_URL_SCHEME=https
MAX_CONTENT_LENGTH=10485760
RATELIMIT_STORAGE_URI=redis://localhost:6379/2
```

---

## Known Limitations

1. **Nonce Storage** - Currently in-memory, not suitable for multi-process deployments
   - **Mitigation:** Use Redis-backed nonce storage (Phase 2)

2. **CSRF Protection** - Not implemented for API endpoints
   - **Mitigation:** Bearer token authentication provides protection

3. **IP Allowlist** - Can be bypassed with X-Forwarded-For spoofing
   - **Mitigation:** Ensure nginx/load balancer properly sets headers

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/latest/security/)
- [PHI/PII Safe Logging Policy](file:///home/programmer/Desktop/projects/aiims/services/ai/policy/PHI_SAFE_LOGGING.md)
- [Security Baseline](file:///home/programmer/Desktop/projects/aiims/services/ai/security/BASELINE.md)

---

## Support

For security questions or to report vulnerabilities:
- Email: security@your-domain.com
- Slack: #security-team
