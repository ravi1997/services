# API User Guide

## Introduction
This guide is for developers integrating with the AIIMS Services API. The API provides capabilities for sending SMS notifications via a unified interface, abstracting away underlying provider complexities.

## 🌐 Base URL
All API requests should be made to:
`https://<service-domain>/services/api/v1`

---

## 🔐 Authentication
The API uses **Bearer Token** authentication. 
*   **Header**: `Authorization`
*   **Value**: `Bearer <YOUR_API_TOKEN>`

```bash
# Example
curl -H "Authorization: Bearer my-secure-token" ...
```

> [!IMPORTANT]
> Keep your API Token secure. Do not commit it to version control.

---

## 📡 Endpoints

### 1. Send Single SMS
Send a transactional SMS to a single recipient.

**Endpoint:** `POST /sms/single`

**Request Body:**
| Field | Type | Required | Description | Constraints |
|---|---|---|---|---|
| `mobile` | String | Yes | Recipient's mobile number. | 10 digits or E.164 (`+91...`). |
| `message` | String | Yes | Message content. | Max 500 chars. No scripts/SQL patterns. |
| `to` | String | No | Legacy alias for `mobile`. | Same as `mobile`. |

**Rate Limits:** 100 requests / minute

**Example Request (cURL):**
```bash
curl -X POST https://api.aiims.org/services/api/v1/sms/single \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-req-id-12345" \
  -d '{
    "mobile": "9876543210",
    "message": "Your appointment is confirmed for 10:00 AM."
  }'
```

**Success Response (200 OK):**
```json
{
  "status": "success",
  "message": "SMS processed",
  "data": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "status": "queued",
    "mobile": "9876543210",
    "created_at": "2026-01-07T10:00:00Z"
  },
  "code": 200
}
```

### 2. Send Bulk SMS
Send the same message to multiple recipients.

**Endpoint:** `POST /sms/bulk`

**Constraints:**
*   Max **200** recipients per request.
*   Rate Limit: 10 requests / minute.

**Example Request:**
```json
{
  "mobiles": ["9876543210", "9876543211", "9876543212"],
  "message": "System downtime scheduled for Sunday 2 AM."
}
```

---

## 🚦 Error Handling

### Standard Error Response
```json
{
  "status": "error",
  "message": "Invalid phone number format",
  "data": {
    "error_code": "SMS_SERVICE_ERROR"
  },
  "code": 400
}
```

### Common Error Codes & Recovery
| Error Code | HTTP | Description | Recovery Action |
|---|---|---|---|
| `SECURITY_VIOLATION` | 400 | Input contained forbidden characters (HTML tags, SQL keywords). | Sanitize input. Remove `<script>`, `SELECT`, etc. |
| `SMS_SERVICE_ERROR` | 400 | Validation failed (e.g., invalid phone format, too long). | Verify payload against constraints. |
| `SMS_SERVICE_UNHEALTHY`| 503 | Downstream gateway (CDAC/Provider) is unreachable. | Retry after 30 seconds (Exponential Backoff). |
| `RATE_LIMIT_EXCEEDED` | 429 | You have sent too many requests. | Slow down. Check `X-RateLimit-Reset` header. |
| `UNAUTHORIZED` | 401 | Missing or invalid Bearer token. | Check `Authorization` header. Renew token. |

---

## ⏳ Rate Limiting
The API enforces rate limits to ensure stability. Limits are applied per API Token.
When a limit is exceeded, you receive a `429 Too Many Requests`.

**Response Headers:**
*   `X-RateLimit-Limit`: The ceiling for this timeframe (e.g., "100").
*   `X-RateLimit-Remaining`: Requests left in the current window.
*   `X-RateLimit-Reset`: Time (in Unix epoch seconds) when the window resets.

---

## 🤝 Support
For integration issues, please provide:
1.  The `uuid` of the request (if success).
2.  The `X-Request-ID` header value (for debugging traces).
3.  The exact error code received.
