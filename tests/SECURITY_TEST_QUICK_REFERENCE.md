# Security Test Quick Reference

## Quick Summary

This is a quick reference guide for implementing healthcare security tests. For detailed requirements, see `HEALTHCARE_SECURITY_TESTING_PLAN.md` and `CRITICAL_MISSING_TESTS.md`.

## 🚨 Must-Have Tests (Implement First)

### 1. Authentication Tests
**File:** `tests/test_auth_jwt.py`
```python
# Test JWT token validation
- Valid token → 200 OK
- Expired token → 401 Unauthorized
- Invalid token → 401 Unauthorized
- Missing token → 401 Unauthorized (when REQUIRE_AUTH=true)
```

### 2. Authorization Tests
**File:** `tests/test_endpoint_authorization.py`
```python
# Test all PHI endpoints require auth
- GET /api/v1/claims → Requires auth
- GET /api/v1/remits → Requires auth
- GET /api/v1/episodes → Requires auth
- POST /api/v1/claims/upload → Requires auth
```

### 3. Audit Logging Tests
**File:** `tests/test_audit_logging.py`
```python
# Test all PHI access is logged
- Request logged with: user_id, IP, timestamp, path
- PHI is hashed (not plaintext)
- Audit logs are stored in database
```

### 4. PHI Sanitization Tests
**File:** `tests/test_phi_sanitization.py`
```python
# Test PHI is never logged in plaintext
- Patient names → Hashed
- SSNs → Hashed
- MRNs → Hashed
- PHI not in error messages
- PHI not in debug logs
```

### 5. Encryption Tests
**Files:** `tests/test_encryption_at_rest.py`, `tests/test_encryption_in_transit.py`
```python
# Test encryption
- Database columns encrypted (if implemented)
- HTTPS required in production
- TLS 1.2+ enforced
- Database connections use SSL
```

## 📋 Test File Checklist

### Critical (Implement This Week)
- [ ] `tests/test_auth_jwt.py` - JWT authentication
- [ ] `tests/test_endpoint_authorization.py` - API authorization
- [ ] `tests/test_audit_logging.py` - Audit logging
- [ ] `tests/test_phi_sanitization.py` - PHI sanitization
- [ ] `tests/test_encryption_at_rest.py` - Encryption at rest
- [ ] `tests/test_encryption_in_transit.py` - Encryption in transit

### High Priority (Within 2 Weeks)
- [ ] `tests/test_rbac.py` - Role-based access control
- [ ] `tests/test_sql_injection.py` - SQL injection prevention
- [ ] `tests/test_xss_prevention.py` - XSS prevention
- [ ] `tests/test_input_validation.py` - Input validation (expand)
- [ ] `tests/test_session_management.py` - Session security
- [ ] `tests/test_data_retention.py` - Data retention
- [ ] `tests/test_hipaa_compliance.py` - HIPAA compliance

### Medium Priority (Within 1 Month)
- [ ] `tests/test_cors_security.py` - CORS security (expand)
- [ ] `tests/test_security_headers.py` - Security headers
- [ ] `tests/test_external_service_security.py` - Integration security
- [ ] `tests/test_file_upload_security.py` - File upload security

## Test Template

```python
"""Tests for [security feature]."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.mark.security
@pytest.mark.hipaa
class Test[FeatureName]:
    """Test [security feature] for HIPAA compliance."""
    
    def test_[specific_test_case](self, client: TestClient):
        """Test [what this test verifies]."""
        # Arrange
        # Act
        # Assert
        pass
```

## Key Test Patterns

### Authentication Test Pattern
```python
def test_endpoint_requires_auth_when_enabled(self, client: TestClient):
    """Test endpoint requires authentication when REQUIRE_AUTH=true."""
    # Set REQUIRE_AUTH=true
    # Make request without token
    # Assert 401 Unauthorized
    pass
```

### Audit Logging Test Pattern
```python
def test_phi_access_is_logged(self, client: TestClient):
    """Test PHI access is logged with hashed identifiers."""
    # Make request to PHI endpoint
    # Check audit log
    # Assert PHI is hashed (not plaintext)
    pass
```

### PHI Sanitization Test Pattern
```python
def test_phi_not_in_logs(self, client: TestClient):
    """Test PHI is not logged in plaintext."""
    # Make request with PHI
    # Check logs
    # Assert PHI is hashed or redacted
    pass
```

## Running Security Tests

```bash
# Run all security tests
pytest tests/ -m security

# Run HIPAA compliance tests
pytest tests/ -m hipaa

# Run with coverage
pytest tests/ -m security --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth_jwt.py -v
```

## Test Markers

Use these pytest markers:
- `@pytest.mark.security` - Security-related tests
- `@pytest.mark.hipaa` - HIPAA compliance tests
- `@pytest.mark.auth` - Authentication tests
- `@pytest.mark.audit` - Audit logging tests
- `@pytest.mark.encryption` - Encryption tests

## Common Assertions

```python
# Authentication
assert response.status_code == 401  # Unauthorized
assert "Authentication required" in response.json()["detail"]

# Authorization
assert response.status_code == 403  # Forbidden
assert "Access denied" in response.json()["detail"]

# Audit Logging
assert audit_log.user_id is not None
assert audit_log.client_ip is not None
assert audit_log.timestamp is not None
assert "[REDACTED]" in log_message  # PHI redacted

# Encryption
assert response.url.scheme == "https"  # HTTPS
assert "HSTS" in response.headers  # HSTS header
```

## Test Data Guidelines

- **Never use real PHI** in tests
- Use synthetic test data (see `tests/factories.py`)
- Use test fixtures that don't contain real patient information
- Clean up test data after each test

## CI/CD Integration

Add to `.github/workflows/tests.yml` or similar:
```yaml
- name: Run Security Tests
  run: |
    pytest tests/ -m security --cov=app --cov-report=xml
    pytest tests/ -m hipaa --cov=app --cov-report=xml
```

## Resources

- **HIPAA Security Rule**: 45 CFR Parts 160, 162, and 164
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
- **NIST Cybersecurity Framework**: https://www.nist.gov/cyberframework
- **Detailed Plan**: `HEALTHCARE_SECURITY_TESTING_PLAN.md`
- **Critical Tests**: `CRITICAL_MISSING_TESTS.md`

## Questions?

- Review `HEALTHCARE_SECURITY_TESTING_PLAN.md` for detailed requirements
- Review `CRITICAL_MISSING_TESTS.md` for priority list
- Check existing tests in `tests/test_security.py` and `tests/test_config_security.py` for examples

