# mARB 2.0 - API Documentation

## Overview

The mARB 2.0 API provides a comprehensive REST API for real-time claim risk analysis, EDI file processing, episode linking, and pattern learning. All endpoints are prefixed with `/api/v1`.

**Base URL**: `http://localhost:8000` (development) or `https://api.yourdomain.com` (production)

**API Version**: 2.0.0

## Authentication

Authentication is **optional** by default but can be enforced in production by setting `REQUIRE_AUTH=true` in your `.env` file.

### JWT Authentication (when enabled)

1. Obtain a JWT token by authenticating with your credentials
2. Include the token in the `Authorization` header:
   ```
   Authorization: Bearer <your-jwt-token>
   ```

### Rate Limiting

- **Per minute**: 60 requests (configurable via `RATE_LIMIT_PER_MINUTE`)
- **Per hour**: 1000 requests (configurable via `RATE_LIMIT_PER_HOUR`)

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Time when the rate limit resets

## Response Format

All API responses are JSON. Successful responses use standard HTTP status codes (200, 201, etc.). Errors follow this format:

```json
{
  "message": "Error description",
  "code": "ERROR_CODE",
  "status_code": 400,
  "details": {}
}
```

## Endpoints

### Health & Status

#### GET `/api/v1/health`

Check API health status.

**Response**:
```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```

#### GET `/api/v1/health/detailed`

Comprehensive health check including all system dependencies (database, Redis, Celery).

**Response**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2024-12-20T10:30:00",
  "components": {
    "database": {
      "status": "healthy",
      "response_time_ms": 2.45
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 1.23
    },
    "celery": {
      "status": "healthy",
      "active_workers": 2,
      "worker_names": ["celery@worker1", "celery@worker2"]
    }
  }
}
```

**Status Values**:
- `healthy`: All components are operational
- `degraded`: One or more components are unhealthy, but API is still functional

**Component Status**:
- Each component reports its own status and response time
- If a component is unavailable, it will show `"status": "unhealthy"` with an error message
- Database and Redis include response time in milliseconds
- Celery includes the number of active workers and their names

#### GET `/api/v1/cache/stats`

Get cache statistics.

**Query Parameters**:
- `key` (optional): Specific cache key to query

**Response**:
```json
{
  "overall": {
    "hits": 150,
    "misses": 50,
    "total": 200,
    "hit_rate": 0.75
  },
  "by_key": {
    "claim:123": {
      "hits": 10,
      "misses": 2
    }
  }
}
```

#### POST `/api/v1/cache/stats/reset`

Reset cache statistics.

**Response**:
```json
{
  "message": "Cache statistics reset"
}
```

---

### Claims (837 Files)

#### POST `/api/v1/claims/upload`

Upload and process a 837 claim file (EDI X12 format).

**Request**:
- **Content-Type**: `multipart/form-data`
- **Body**: File upload with field name `file`

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/claims/upload" \
  -H "accept: application/json" \
  -F "file=@claim_file.txt"
```

**Response**:
```json
{
  "message": "File queued for processing",
  "task_id": "abc123-def456-ghi789",
  "filename": "claim_file.txt"
}
```

**Notes**:
- File is processed asynchronously via Celery
- Use the `task_id` to track processing status (via Celery Flower or task monitoring)
- Processing typically completes within seconds for standard files

#### GET `/api/v1/claims`

Get a paginated list of claims.

**Query Parameters**:
- `skip` (default: 0): Number of records to skip
- `limit` (default: 100, max: 1000): Number of records to return

**Example**:
```bash
curl "http://localhost:8000/api/v1/claims?skip=0&limit=50"
```

**Response**:
```json
{
  "claims": [
    {
      "id": 1,
      "claim_control_number": "CLAIM001",
      "patient_control_number": "PATIENT001",
      "total_charge_amount": 1500.00,
      "status": "processed",
      "is_incomplete": false,
      "created_at": "2024-12-20T10:30:00"
    }
  ],
  "total": 150,
  "skip": 0,
  "limit": 50
}
```

#### GET `/api/v1/claims/{claim_id}`

Get detailed information about a specific claim.

**Path Parameters**:
- `claim_id` (integer): The ID of the claim

**Response**:
```json
{
  "id": 1,
  "claim_control_number": "CLAIM001",
  "patient_control_number": "PATIENT001",
  "provider_id": 1,
  "payer_id": 1,
  "total_charge_amount": 1500.00,
  "facility_type_code": "11",
  "claim_frequency_type": "1",
  "assignment_code": "Y",
  "statement_date": "2024-12-15",
  "admission_date": null,
  "discharge_date": null,
  "service_date": "2024-12-15",
  "diagnosis_codes": ["E11.9"],
  "principal_diagnosis": "E11.9",
  "status": "processed",
  "is_incomplete": false,
  "parsing_warnings": [],
  "practice_id": 1,
  "claim_lines": [
    {
      "id": 1,
      "line_number": 1,
      "procedure_code": "99213",
      "charge_amount": 1500.00,
      "service_date": "2024-12-15"
    }
  ],
  "created_at": "2024-12-20T10:30:00",
  "updated_at": "2024-12-20T10:30:00"
}
```

**Caching**: Responses are cached for 30 minutes (configurable).

---

### Remittances (835 Files)

#### POST `/api/v1/remits/upload`

Upload and process a 835 remittance file (EDI X12 format).

**Request**:
- **Content-Type**: `multipart/form-data`
- **Body**: File upload with field name `file`

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/remits/upload" \
  -H "accept: application/json" \
  -F "file=@remittance_file.txt"
```

**Response**:
```json
{
  "message": "File queued for processing",
  "task_id": "xyz789-abc123-def456",
  "filename": "remittance_file.txt"
}
```

#### GET `/api/v1/remits`

Get a paginated list of remittances.

**Query Parameters**:
- `skip` (default: 0): Number of records to skip
- `limit` (default: 100, max: 1000): Number of records to return

**Response**:
```json
{
  "remits": [
    {
      "id": 1,
      "remittance_control_number": "REM001",
      "claim_control_number": "CLAIM001",
      "payer_name": "Blue Cross Blue Shield",
      "payment_amount": 1200.00,
      "status": "processed",
      "created_at": "2024-12-20T10:30:00"
    }
  ],
  "total": 75,
  "skip": 0,
  "limit": 50
}
```

#### GET `/api/v1/remits/{remit_id}`

Get detailed information about a specific remittance.

**Path Parameters**:
- `remit_id` (integer): The ID of the remittance

**Response**:
```json
{
  "id": 1,
  "remittance_control_number": "REM001",
  "payer_id": 1,
  "payer_name": "Blue Cross Blue Shield",
  "payment_amount": 1200.00,
  "payment_date": "2024-12-20",
  "check_number": "CHK123456",
  "claim_control_number": "CLAIM001",
  "denial_reasons": ["CO45", "PR1"],
  "adjustment_reasons": ["CO45: Charge exceeds fee schedule", "PR1: Patient responsibility"],
  "status": "processed",
  "parsing_warnings": [],
  "created_at": "2024-12-20T10:30:00",
  "updated_at": "2024-12-20T10:30:00"
}
```

**Caching**: Responses are cached for 30 minutes (configurable).

#### POST `/api/v1/remits/{remittance_id}/link`

Manually trigger episode linking for a remittance. This attempts to match the remittance with existing claims.

**Path Parameters**:
- `remittance_id` (integer): The ID of the remittance

**Response**:
```json
{
  "message": "Episode linking completed",
  "remittance_id": 1,
  "episodes_linked": 1,
  "episodes": [
    {
      "id": 1,
      "claim_id": 1,
      "status": "linked"
    }
  ]
}
```

---

### Episodes

Episodes link claims with their remittance outcomes, creating a complete picture of the claim lifecycle.

#### GET `/api/v1/episodes`

Get a paginated list of claim episodes.

**Query Parameters**:
- `skip` (default: 0): Number of records to skip
- `limit` (default: 100, max: 1000): Number of records to return
- `claim_id` (optional): Filter episodes by claim ID

**Example**:
```bash
curl "http://localhost:8000/api/v1/episodes?claim_id=1&skip=0&limit=10"
```

**Response**:
```json
{
  "episodes": [
    {
      "id": 1,
      "claim_id": 1,
      "remittance_id": 1,
      "status": "linked",
      "payment_amount": 1200.00,
      "denial_count": 0,
      "adjustment_count": 2,
      "linked_at": "2024-12-20T10:30:00",
      "created_at": "2024-12-20T10:30:00"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 10
}
```

#### GET `/api/v1/episodes/{episode_id}`

Get detailed information about a specific episode.

**Path Parameters**:
- `episode_id` (integer): The ID of the episode

**Response**:
```json
{
  "id": 1,
  "claim_id": 1,
  "remittance_id": 1,
  "status": "linked",
  "payment_amount": 1200.00,
  "denial_count": 0,
  "adjustment_count": 2,
  "linked_at": "2024-12-20T10:30:00",
  "created_at": "2024-12-20T10:30:00",
  "updated_at": "2024-12-20T10:30:00"
}
```

**Caching**: Responses are cached for 30 minutes (configurable).

#### POST `/api/v1/episodes/{episode_id}/link`

Manually link a claim to a remittance to create an episode.

**Path Parameters**:
- `episode_id` (integer): The ID of the episode (if updating existing)

**Query Parameters**:
- `claim_id` (required): The ID of the claim
- `remittance_id` (required): The ID of the remittance

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/episodes/1/link?claim_id=1&remittance_id=1"
```

**Response**:
```json
{
  "message": "Episode linked successfully",
  "episode": {
    "id": 1,
    "claim_id": 1,
    "remittance_id": 1,
    "status": "linked"
  }
}
```

#### PATCH `/api/v1/episodes/{episode_id}/status`

Update the status of an episode.

**Path Parameters**:
- `episode_id` (integer): The ID of the episode

**Request Body**:
```json
{
  "status": "complete"
}
```

**Valid Status Values**:
- `pending`
- `linked`
- `complete`
- `denied`

**Response**:
```json
{
  "message": "Episode status updated",
  "episode": {
    "id": 1,
    "status": "complete"
  }
}
```

#### POST `/api/v1/episodes/{episode_id}/complete`

Mark an episode as complete.

**Path Parameters**:
- `episode_id` (integer): The ID of the episode

**Response**:
```json
{
  "message": "Episode marked as complete",
  "episode": {
    "id": 1,
    "status": "complete"
  }
}
```

#### GET `/api/v1/claims/unlinked`

Get claims that haven't been linked to remittances yet.

**Query Parameters**:
- `skip` (default: 0): Number of records to skip
- `limit` (default: 100, max: 1000): Number of records to return

**Response**:
```json
{
  "claims": [
    {
      "id": 1,
      "claim_control_number": "CLAIM001",
      "total_charge_amount": 1500.00,
      "date_of_service": "2024-12-15",
      "payer_name": "Blue Cross Blue Shield"
    }
  ],
  "total": 5,
  "skip": 0,
  "limit": 100
}
```

---

### Risk Scoring

#### GET `/api/v1/risk/{claim_id}`

Get the current risk score for a claim (cached).

**Path Parameters**:
- `claim_id` (integer): The ID of the claim

**Response**:
```json
{
  "claim_id": 1,
  "overall_score": 75.5,
  "risk_level": "medium",
  "component_scores": {
    "coding_risk": 80.0,
    "documentation_risk": 70.0,
    "payer_risk": 75.0,
    "historical_risk": 77.0
  },
  "risk_factors": [
    "High charge amount relative to typical",
    "Multiple diagnosis codes",
    "Prior denials for similar claims"
  ],
  "recommendations": [
    "Review documentation for completeness",
    "Verify prior authorization requirements",
    "Check payer-specific rules"
  ],
  "calculated_at": "2024-12-20T10:30:00"
}
```

**Caching**: Responses are cached for 60 minutes (configurable).

**Note**: If no risk score has been calculated yet, returns:
```json
{
  "claim_id": 1,
  "message": "Risk score not yet calculated"
}
```

#### POST `/api/v1/risk/{claim_id}/calculate`

Calculate or recalculate the risk score for a claim.

**Path Parameters**:
- `claim_id` (integer): The ID of the claim

**Response**:
```json
{
  "claim_id": 1,
  "overall_score": 75.5,
  "risk_level": "medium",
  "status": "calculated"
}
```

**Notes**:
- This endpoint invalidates any cached risk score
- Calculation may take a few seconds for complex claims
- The new score is automatically cached

---

### Audit Logs (HIPAA Compliance)

The audit log endpoints provide access to HIPAA-compliant audit trails of all API requests. All API access is automatically logged by the AuditMiddleware.

**Security Note**: These endpoints require authentication. In production, they should be restricted to admin/audit roles.

#### GET `/api/v1/audit-logs`

Get audit logs for HIPAA compliance reporting.

**Query Parameters**:
- `skip` (default: 0, min: 0): Number of records to skip
- `limit` (default: 100, min: 1, max: 1000): Maximum number of records to return
- `method` (optional): Filter by HTTP method (GET, POST, PUT, DELETE, etc.)
- `path` (optional): Filter by path (supports partial match)
- `status_code` (optional, min: 100, max: 599): Filter by HTTP status code
- `user_id` (optional): Filter by user ID
- `client_ip` (optional): Filter by client IP address
- `start_date` (optional): Filter by start date (ISO 8601 format)
- `end_date` (optional): Filter by end date (ISO 8601 format)

**Example**:
```bash
curl -X GET "http://localhost:8000/api/v1/audit-logs?method=POST&status_code=200&limit=50" \
  -H "Authorization: Bearer <token>"
```

**Response**:
```json
{
  "logs": [
    {
      "id": 1,
      "method": "POST",
      "path": "/api/v1/claims/upload",
      "status_code": 200,
      "duration": 0.234,
      "user_id": "user123",
      "client_ip": "192.168.1.100",
      "request_identifier": "hash_abc123",
      "response_identifier": "hash_def456",
      "created_at": "2024-12-20T10:30:00"
    }
  ],
  "total": 150,
  "skip": 0,
  "limit": 50
}
```

**Notes**:
- All PHI (Protected Health Information) is hashed before storage
- Only hashed identifiers are returned (no plaintext PHI)
- Logs are ordered by creation date (newest first)
- Path filtering supports partial matches (e.g., `/claims` matches `/api/v1/claims/upload`)

#### GET `/api/v1/audit-logs/stats`

Get audit log statistics for compliance reporting.

**Query Parameters**:
- `days` (default: 7, min: 1, max: 365): Number of days to analyze

**Example**:
```bash
curl -X GET "http://localhost:8000/api/v1/audit-logs/stats?days=30" \
  -H "Authorization: Bearer <token>"
```

**Response**:
```json
{
  "period_days": 30,
  "start_date": "2024-11-20T00:00:00",
  "end_date": "2024-12-20T10:30:00",
  "total_requests": 15234,
  "requests_by_method": {
    "GET": 8500,
    "POST": 4500,
    "PUT": 1500,
    "DELETE": 734
  },
  "requests_by_status": {
    "200": 12000,
    "201": 2000,
    "400": 500,
    "404": 234,
    "500": 500
  },
  "unique_users": 45,
  "unique_ip_addresses": 12,
  "average_duration_seconds": 0.1234,
  "requests_per_day": 507.8
}
```

**Notes**:
- Provides aggregated statistics for compliance reporting
- Useful for monitoring API usage patterns
- All statistics are calculated from database queries (efficient aggregations)

---

### Pattern Learning

#### POST `/api/v1/patterns/detect/{payer_id}`

Detect denial patterns for a specific payer based on historical data.

**Path Parameters**:
- `payer_id` (integer): The ID of the payer

**Query Parameters**:
- `days_back` (default: 90, min: 1, max: 365): Number of days to look back

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/patterns/detect/1?days_back=180"
```

**Response**:
```json
{
  "payer_id": 1,
  "payer_name": "Blue Cross Blue Shield",
  "patterns_detected": 3,
  "patterns": [
    {
      "id": 1,
      "pattern_type": "denial_reason",
      "pattern_description": "Frequent CO45 denials for CPT 99213",
      "denial_reason_code": "CO45",
      "occurrence_count": 25,
      "frequency": 0.15,
      "confidence_score": 0.85,
      "conditions": {
        "cpt_codes": ["99213"],
        "charge_threshold": 1500.00
      },
      "first_seen": "2024-09-01T00:00:00",
      "last_seen": "2024-12-20T00:00:00"
    }
  ]
}
```

#### POST `/api/v1/patterns/detect-all`

Detect denial patterns for all payers in the system.

**Query Parameters**:
- `days_back` (default: 90, min: 1, max: 365): Number of days to look back

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/patterns/detect-all?days_back=180"
```

**Response**:
```json
{
  "payers_processed": 5,
  "total_patterns": 12,
  "patterns_by_payer": {
    "1": 3,
    "2": 2,
    "3": 4,
    "4": 2,
    "5": 1
  }
}
```

**Notes**:
- Processes all payers in the database
- Returns aggregate statistics across all payers
- Useful for bulk pattern detection across the entire system

#### GET `/api/v1/patterns/payer/{payer_id}`

Get all learned denial patterns for a specific payer.

**Path Parameters**:
- `payer_id` (integer): The ID of the payer

**Example**:
```bash
curl "http://localhost:8000/api/v1/patterns/payer/1"
```

**Response**:
```json
{
  "payer_id": 1,
  "payer_name": "Blue Cross Blue Shield",
  "patterns": [
    {
      "id": 1,
      "pattern_type": "denial_reason",
      "pattern_description": "Frequent CO45 denials for CPT 99213",
      "denial_reason_code": "CO45",
      "occurrence_count": 25,
      "frequency": 0.15,
      "confidence_score": 0.85,
      "conditions": {
        "cpt_codes": ["99213"],
        "charge_threshold": 1500.00
      },
      "first_seen": "2024-09-01T00:00:00",
      "last_seen": "2024-12-20T00:00:00"
    }
  ]
}
```

#### POST `/api/v1/patterns/analyze-claim/{claim_id}`

Analyze a claim against known denial patterns to predict potential issues before submission.

**Path Parameters**:
- `claim_id` (integer): The ID of the claim to analyze

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/patterns/analyze-claim/1"
```

**Response**:
```json
{
  "claim_id": 1,
  "payer_id": 1,
  "matching_patterns_count": 2,
  "matching_patterns": [
    {
      "pattern_id": 1,
      "pattern_description": "Frequent CO45 denials for CPT 99213",
      "match_confidence": 0.85,
      "risk_factors": ["CPT code matches", "Charge amount exceeds threshold"]
    }
  ]
}
```

---

### WebSocket Notifications

#### WebSocket `/ws/notifications`

Real-time WebSocket endpoint for receiving notifications about claim processing, risk scores, and episode linking.

**Connection**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/notifications');

ws.onmessage = (event) => {
  const notification = JSON.parse(event.data);
  console.log('Notification:', notification);
};
```

**Notification Types**:
- `risk_score_calculated`: Risk score has been calculated for a claim
- `claim_processed`: A claim has been processed
- `remittance_processed`: A remittance has been processed
- `episode_linked`: An episode has been linked
- `episode_completed`: An episode has been marked complete
- `file_processed`: An EDI file has been processed
- `error`: An error occurred
- `info`: General information message

**Notification Format**:
```json
{
  "type": "risk_score_calculated",
  "timestamp": "2024-12-20T10:30:00",
  "data": {
    "claim_id": 1,
    "risk_score": 75.5,
    "risk_level": "medium"
  },
  "message": "Risk score calculated for claim 1"
}
```

**Connection Message**:
Upon connection, you'll receive:
```json
{
  "type": "connection",
  "message": "Connected to mARB 2.0 notifications",
  "timestamp": "2024-12-20T10:30:00"
}
```

**Client Messages**:
You can send JSON messages to the server (they will be acknowledged):
```json
{
  "action": "subscribe",
  "filters": ["risk_score_calculated", "episode_linked"]
}
```

---

## Error Handling

### HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Error Response Format

```json
{
  "message": "Claim not found",
  "code": "NOT_FOUND",
  "status_code": 404,
  "details": {
    "resource": "Claim",
    "id": "123"
  }
}
```

### Common Error Codes

- `NOT_FOUND`: Resource not found
- `VALIDATION_ERROR`: Request validation failed
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `UNAUTHORIZED`: Authentication required
- `INTERNAL_ERROR`: Server error

---

## Pagination

List endpoints support pagination using `skip` and `limit` query parameters:

- `skip`: Number of records to skip (default: 0)
- `limit`: Number of records to return (default: 100, max: 1000)

**Example**:
```bash
# Get first page (records 0-49)
GET /api/v1/claims?skip=0&limit=50

# Get second page (records 50-99)
GET /api/v1/claims?skip=50&limit=50
```

**Response includes pagination metadata**:
```json
{
  "claims": [...],
  "total": 150,
  "skip": 0,
  "limit": 50
}
```

---

## Caching

Several endpoints use Redis caching to improve performance:

- **Claims**: 30 minutes TTL
- **Remittances**: 30 minutes TTL
- **Episodes**: 30 minutes TTL
- **Risk Scores**: 60 minutes TTL

Cache is automatically invalidated when:
- A claim is updated
- A risk score is recalculated
- An episode status is updated

---

## Rate Limiting

Rate limiting is enforced per IP address:

- **Per minute**: 60 requests (configurable)
- **Per hour**: 1000 requests (configurable)

When rate limit is exceeded, you'll receive:
```json
{
  "message": "Rate limit exceeded",
  "code": "RATE_LIMIT_EXCEEDED",
  "status_code": 429,
  "details": {
    "retry_after": 30
  }
}
```

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Interactive API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

These interfaces allow you to:
- Browse all available endpoints
- View request/response schemas
- Test endpoints directly from the browser
- See example requests and responses

---

## Examples

### Complete Workflow: Upload Claim and Calculate Risk

```bash
# 1. Upload claim file
curl -X POST "http://localhost:8000/api/v1/claims/upload" \
  -F "file=@claim.txt"

# Response: {"task_id": "abc123", ...}

# 2. Wait for processing (check Celery or poll claims endpoint)
sleep 5

# 3. Get list of claims to find the new claim ID
curl "http://localhost:8000/api/v1/claims?limit=1"

# 4. Calculate risk score
curl -X POST "http://localhost:8000/api/v1/risk/1/calculate"

# 5. Get risk score
curl "http://localhost:8000/api/v1/risk/1"
```

### Upload Remittance and Link Episode

```bash
# 1. Upload remittance file
curl -X POST "http://localhost:8000/api/v1/remits/upload" \
  -F "file=@remittance.txt"

# 2. Wait for processing
sleep 5

# 3. Get remittance ID
curl "http://localhost:8000/api/v1/remits?limit=1"

# 4. Link remittance to claims
curl -X POST "http://localhost:8000/api/v1/remits/1/link"

# 5. View linked episodes
curl "http://localhost:8000/api/v1/episodes?claim_id=1"
```

### WebSocket Connection (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/notifications');

ws.onopen = () => {
  console.log('Connected to mARB 2.0 notifications');
};

ws.onmessage = (event) => {
  const notification = JSON.parse(event.data);
  
  switch(notification.type) {
    case 'risk_score_calculated':
      console.log(`Risk score calculated: ${notification.data.risk_score}`);
      break;
    case 'episode_linked':
      console.log(`Episode linked: ${notification.data.episode_id}`);
      break;
    default:
      console.log('Notification:', notification);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket connection closed');
};
```

---

## Support

For API issues or questions:
- Check the interactive documentation at `/docs`
- Review error messages and status codes
- Check application logs
- See `TROUBLESHOOTING.md` for common issues

---

---

## Additional Endpoints

### Root Endpoint

#### GET `/`

Root endpoint providing basic API information.

**Response**:
```json
{
  "name": "mARB 2.0 - Real-Time Claim Risk Engine",
  "version": "2.0.0",
  "status": "running"
}
```

### Sentry Debug Endpoint

#### GET `/sentry-debug`

Debug endpoint to verify Sentry error tracking is working. **Note**: This endpoint intentionally triggers an error for testing purposes.

**Response**: Will return a 500 error (this is expected behavior for testing).

---

**Last Updated**: 2024-12-26  
**API Version**: 2.0.0

