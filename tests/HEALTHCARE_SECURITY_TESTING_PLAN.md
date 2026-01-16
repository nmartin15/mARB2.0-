# Healthcare Security Testing Plan for mARB 2.0

## Overview

This document outlines comprehensive security and compliance testing requirements for mARB 2.0, a healthcare application handling Protected Health Information (PHI). All tests must be implemented to meet HIPAA compliance standards and healthcare industry security requirements.

## Critical Test Categories

### 1. Authentication & Authorization Tests ⚠️ **HIGH PRIORITY - MISSING**

#### 1.1 JWT Authentication Tests
**File to Create:** `tests/test_auth_jwt.py`

- [ ] **Token Creation & Validation**
  - Test JWT token creation with valid credentials
  - Test JWT token validation with valid token
  - Test JWT token validation with expired token
  - Test JWT token validation with invalid signature
  - Test JWT token validation with missing token
  - Test JWT token validation with malformed token
  - Test JWT token refresh mechanism
  - Test token expiration handling

- [ ] **Token Security**
  - Test that tokens cannot be tampered with
  - Test that tokens include proper claims (user_id, exp, iat)
  - Test that tokens use secure algorithm (HS256/RS256)
  - Test that tokens are not logged in plaintext
  - Test that tokens are not exposed in error messages

- [ ] **Authentication Middleware**
  - Test `OptionalAuthMiddleware` when `REQUIRE_AUTH=true`
  - Test `OptionalAuthMiddleware` when `REQUIRE_AUTH=false`
  - Test authentication exemption for health endpoints
  - Test authentication exemption for docs endpoints
  - Test 401 response for unauthenticated requests to protected endpoints
  - Test proper WWW-Authenticate header in 401 responses

#### 1.2 Role-Based Access Control (RBAC) Tests
**File to Create:** `tests/test_rbac.py`

- [ ] **Role Definitions**
  - Test role hierarchy (Admin > Provider > Billing > Analyst)
  - Test role permissions matrix
  - Test role assignment and revocation

- [ ] **Provider Access Control**
  - Test providers can only access their own patients' data
  - Test providers cannot access other providers' patients
  - Test providers cannot modify other providers' claims
  - Test provider access to remittances for their claims only

- [ ] **Billing Staff Access Control**
  - Test billing staff can access claims/remittances
  - Test billing staff cannot access patient PHI directly
  - Test billing staff cannot modify clinical data
  - Test billing staff can only view financial information

- [ ] **Analyst Access Control**
  - Test analysts can only access de-identified data
  - Test analysts cannot access PHI fields
  - Test analysts can access aggregated statistics
  - Test analysts cannot export PHI

- [ ] **Administrator Access Control**
  - Test administrators have full access
  - Test administrator actions are logged
  - Test administrator cannot bypass audit logging

#### 1.3 API Endpoint Authorization Tests
**File to Create:** `tests/test_endpoint_authorization.py`

- [ ] **Claims API Authorization**
  - Test GET `/api/v1/claims` requires authentication when `REQUIRE_AUTH=true`
  - Test GET `/api/v1/claims/{id}` requires authentication
  - Test POST `/api/v1/claims/upload` requires authentication
  - Test users can only access claims they're authorized for
  - Test unauthorized access returns 403 Forbidden

- [ ] **Remittances API Authorization**
  - Test GET `/api/v1/remits` requires authentication
  - Test GET `/api/v1/remits/{id}` requires authentication
  - Test POST `/api/v1/remits/upload` requires authentication
  - Test users can only access remittances for their claims

- [ ] **Episodes API Authorization**
  - Test GET `/api/v1/episodes` requires authentication
  - Test GET `/api/v1/episodes/{id}` requires authentication
  - Test users can only access episodes for their claims

- [ ] **Risk API Authorization**
  - Test GET `/api/v1/risk/{id}` requires authentication
  - Test POST `/api/v1/risk/{id}/calculate` requires authentication
  - Test users can only calculate risk for their claims

### 2. Audit Logging Tests ⚠️ **HIGH PRIORITY - MISSING**

#### 2.1 PHI Access Logging Tests
**File to Create:** `tests/test_audit_logging.py`

- [ ] **Audit Middleware Tests**
  - Test all API requests are logged
  - Test user_id is captured in audit logs
  - Test IP address is captured in audit logs
  - Test timestamp is captured in audit logs
  - Test request method and path are logged
  - Test response status code is logged
  - Test request duration is logged

- [ ] **PHI Access Logging**
  - Test claim access is logged with hashed identifiers
  - Test remittance access is logged with hashed identifiers
  - Test patient data access is logged
  - Test PHI is NOT logged in plaintext
  - Test hashed identifiers are deterministic (same PHI = same hash)
  - Test hashed identifiers cannot be reversed to PHI

- [ ] **Audit Log Storage**
  - Test audit logs are stored in database (when implemented)
  - Test audit logs are immutable (cannot be modified)
  - Test audit logs include all required fields
  - Test audit log retention policy
  - Test audit log archival process

- [ ] **Audit Log Query & Reporting**
  - Test audit logs can be queried by user_id
  - Test audit logs can be queried by date range
  - Test audit logs can be queried by resource type
  - Test audit logs can be exported for compliance reporting
  - Test audit log export requires admin privileges

#### 2.2 PHI Sanitization Tests
**File to Create:** `tests/test_phi_sanitization.py`

- [ ] **PHI Field Detection**
  - Test PHI fields are correctly identified
  - Test patient names are detected and hashed
  - Test SSNs are detected and hashed
  - Test medical record numbers are detected and hashed
  - Test dates of birth are detected and hashed
  - Test email addresses are detected and hashed
  - Test phone numbers are detected and hashed

- [ ] **PHI Hashing**
  - Test `hash_phi_value()` creates deterministic hashes
  - Test `hash_phi_value()` uses salt correctly
  - Test `hash_phi_value()` cannot be reversed
  - Test `extract_and_hash_identifiers()` extracts all PHI
  - Test `create_audit_identifier()` creates unique identifiers

- [ ] **Log Sanitization**
  - Test PHI is not logged in error messages
  - Test PHI is not logged in debug logs
  - Test PHI is not logged in exception traces
  - Test PHI is redacted in Sentry events
  - Test PHI is redacted in all log outputs

### 3. Data Encryption Tests ⚠️ **HIGH PRIORITY - MISSING**

#### 3.1 Encryption at Rest Tests
**File to Create:** `tests/test_encryption_at_rest.py`

- [ ] **Database Encryption**
  - Test sensitive database columns are encrypted
  - Test encryption keys are stored securely (not in code)
  - Test encrypted data can be decrypted correctly
  - Test encryption keys are rotated properly
  - Test database backups are encrypted

- [ ] **PHI Field Encryption**
  - Test `patient_control_number` is encrypted (if implemented)
  - Test `patient_name` is encrypted (if stored)
  - Test `medical_record_number` is encrypted (if stored)
  - Test any SSN fields are encrypted (if stored)
  - Test encryption is transparent to application code

- [ ] **Key Management**
  - Test encryption keys are not logged
  - Test encryption keys are not exposed in error messages
  - Test encryption keys can be rotated without downtime
  - Test encryption key access is logged and audited

#### 3.2 Encryption in Transit Tests
**File to Create:** `tests/test_encryption_in_transit.py`

- [ ] **HTTPS/TLS Tests**
  - Test all API endpoints require HTTPS in production
  - Test TLS 1.2+ is enforced
  - Test weak cipher suites are rejected
  - Test certificate validation is enforced
  - Test HSTS headers are set correctly

- [ ] **Database Connection Encryption**
  - Test database connections use SSL/TLS
  - Test database connection strings are encrypted
  - Test database credentials are not logged

- [ ] **External Service Encryption**
  - Test Redis connections use TLS (if configured)
  - Test Celery broker connections use TLS
  - Test all external API calls use HTTPS

### 4. Input Validation & Injection Prevention Tests ⚠️ **MEDIUM PRIORITY - PARTIAL**

#### 4.1 SQL Injection Tests
**File to Create:** `tests/test_sql_injection.py`

- [ ] **SQL Injection Prevention**
  - Test SQLAlchemy ORM prevents SQL injection
  - Test parameterized queries are used everywhere
  - Test raw SQL queries (if any) are properly sanitized
  - Test user input is never concatenated into SQL queries
  - Test SQL injection attempts are logged and blocked

- [ ] **SQL Injection Attack Vectors**
  - Test injection via claim_id parameter
  - Test injection via patient_control_number
  - Test injection via search/filter parameters
  - Test injection via pagination parameters
  - Test injection via sort parameters

#### 4.2 XSS (Cross-Site Scripting) Tests
**File to Create:** `tests/test_xss_prevention.py`

- [ ] **XSS Prevention**
  - Test user input is sanitized before rendering
  - Test HTML/JavaScript is escaped in responses
  - Test JSON responses are properly encoded
  - Test error messages don't contain user input
  - Test XSS attempts are logged and blocked

- [ ] **XSS Attack Vectors**
  - Test XSS via claim data fields
  - Test XSS via patient names
  - Test XSS via error messages
  - Test XSS via API response fields

#### 4.3 Input Validation Tests
**File to Create:** `tests/test_input_validation.py`

- [ ] **Pydantic Validation**
  - Test all API endpoints use Pydantic models
  - Test invalid data types are rejected
  - Test missing required fields are rejected
  - Test out-of-range values are rejected
  - Test malformed JSON is rejected

- [ ] **PHI Field Validation**
  - Test patient names are validated (format, length)
  - Test SSNs are validated (format, checksum)
  - Test dates are validated (format, range)
  - Test medical record numbers are validated
  - Test diagnosis codes are validated (ICD-10 format)
  - Test procedure codes are validated (CPT format)

- [ ] **File Upload Validation**
  - Test file size limits are enforced
  - Test file type validation (EDI files only)
  - Test malicious file uploads are rejected
  - Test file content is validated before processing

### 5. Session & Token Management Tests ⚠️ **MEDIUM PRIORITY - MISSING**

#### 5.1 Session Management Tests
**File to Create:** `tests/test_session_management.py`

- [ ] **Session Security**
  - Test sessions expire after inactivity
  - Test sessions expire after maximum lifetime
  - Test concurrent sessions are handled correctly
  - Test session tokens are unique
  - Test session tokens cannot be guessed

- [ ] **Token Management**
  - Test access tokens expire correctly
  - Test refresh tokens expire correctly
  - Test tokens are invalidated on logout
  - Test tokens are invalidated on password change
  - Test token revocation works correctly

#### 5.2 Password Security Tests
**File to Create:** `tests/test_password_security.py`

- [ ] **Password Hashing**
  - Test passwords are hashed with bcrypt
  - Test bcrypt rounds are >= 10
  - Test passwords are never stored in plaintext
  - Test passwords are never logged
  - Test password hashes cannot be reversed

- [ ] **Password Policy**
  - Test password minimum length is enforced
  - Test password complexity requirements (if any)
  - Test password history is maintained (if implemented)
  - Test password reset tokens expire
  - Test password reset requires secure channel

### 6. CORS & Security Headers Tests ⚠️ **LOW PRIORITY - PARTIAL**

#### 6.1 CORS Security Tests
**File to Create:** `tests/test_cors_security.py`

- [ ] **CORS Configuration**
  - Test CORS origins are restricted in production
  - Test wildcard CORS is rejected in production
  - Test localhost CORS is only allowed in development
  - Test CORS preflight requests are handled correctly
  - Test CORS headers are set correctly

- [ ] **CORS Attack Prevention**
  - Test unauthorized origins are blocked
  - Test CORS credentials are handled securely
  - Test CORS headers don't expose sensitive information

#### 6.2 Security Headers Tests
**File to Create:** `tests/test_security_headers.py`

- [ ] **Security Headers**
  - Test HSTS header is set correctly
  - Test X-Frame-Options header is set
  - Test X-Content-Type-Options header is set
  - Test X-XSS-Protection header is set
  - Test Content-Security-Policy header is set (if applicable)
  - Test Referrer-Policy header is set

### 7. Rate Limiting & DoS Prevention Tests ✅ **EXISTS**

#### 7.1 Rate Limiting Tests
**File:** `tests/test_rate_limit.py` (Already exists)

- [x] Rate limit enforcement per minute
- [x] Rate limit enforcement per hour
- [x] Health endpoint exclusion
- [x] Rate limit headers
- [ ] **Additional Tests Needed:**
  - Test rate limiting prevents DoS attacks
  - Test rate limiting is enforced per IP address
  - Test rate limiting handles X-Forwarded-For correctly
  - Test rate limiting logs blocked requests
  - Test rate limiting returns proper error messages

### 8. Data Retention & Deletion Tests ⚠️ **HIGH PRIORITY - MISSING**

#### 8.1 Data Retention Tests
**File to Create:** `tests/test_data_retention.py`

- [ ] **Retention Policies**
  - Test data retention policies are enforced
  - Test old PHI is automatically deleted after retention period
  - Test audit logs are retained for required period (6+ years for HIPAA)
  - Test data deletion is logged and audited
  - Test data deletion requires proper authorization

- [ ] **Data Deletion**
  - Test PHI deletion is permanent and secure
  - Test deleted PHI cannot be recovered
  - Test data deletion follows HIPAA requirements
  - Test data deletion requires audit logging
  - Test bulk deletion requires admin privileges

#### 8.2 Right to Access & Deletion Tests
**File to Create:** `tests/test_patient_rights.py`

- [ ] **Right to Access**
  - Test patients can request their PHI
  - Test PHI export is secure and encrypted
  - Test PHI export is logged and audited
  - Test PHI export requires authentication

- [ ] **Right to Deletion**
  - Test patients can request PHI deletion (where legally allowed)
  - Test deletion requests are logged
  - Test deletion requests require verification
  - Test deletion follows legal requirements

### 9. Error Handling & Information Disclosure Tests ⚠️ **MEDIUM PRIORITY - PARTIAL**

#### 9.1 Error Handling Tests
**File to Create:** `tests/test_error_handling_security.py`

- [ ] **Error Message Security**
  - Test error messages don't expose PHI
  - Test error messages don't expose system internals
  - Test error messages don't expose database structure
  - Test error messages don't expose file paths
  - Test error messages are logged securely

- [ ] **Exception Handling**
  - Test exceptions don't leak PHI
  - Test exceptions are logged with sanitized data
  - Test exceptions are sent to Sentry with PHI filtered
  - Test stack traces don't expose sensitive information

#### 9.2 Information Disclosure Tests
**File to Create:** `tests/test_information_disclosure.py`

- [ ] **API Information Disclosure**
  - Test API responses don't expose internal IDs
  - Test API responses don't expose database structure
  - Test API responses don't expose system paths
  - Test API responses don't expose version information (in production)

- [ ] **Log Information Disclosure**
  - Test logs don't contain PHI
  - Test logs don't contain passwords
  - Test logs don't contain tokens
  - Test logs don't contain encryption keys

### 10. Integration Security Tests ⚠️ **MEDIUM PRIORITY - MISSING**

#### 10.1 External Service Security Tests
**File to Create:** `tests/test_external_service_security.py`

- [ ] **Redis Security**
  - Test Redis connections require authentication (if configured)
  - Test Redis data is not logged
  - Test Redis keys don't contain PHI in plaintext

- [ ] **Celery Security**
  - Test Celery tasks don't log PHI
  - Test Celery task results don't contain PHI
  - Test Celery broker connections are secure

- [ ] **Database Security**
  - Test database connection pooling is secure
  - Test database credentials are not exposed
  - Test database queries are logged without PHI

#### 10.2 File Upload Security Tests
**File to Create:** `tests/test_file_upload_security.py`

- [ ] **File Upload Security**
  - Test file uploads are validated
  - Test file uploads are scanned for malware (if implemented)
  - Test uploaded files are stored securely
  - Test uploaded files are encrypted at rest
  - Test file access is logged and audited

- [ ] **EDI File Security**
  - Test EDI files are validated before processing
  - Test EDI files don't contain executable code
  - Test EDI file processing doesn't expose PHI in logs
  - Test EDI file storage is secure

### 11. Compliance & Regulatory Tests ⚠️ **HIGH PRIORITY - MISSING**

#### 11.1 HIPAA Compliance Tests
**File to Create:** `tests/test_hipaa_compliance.py`

- [ ] **Administrative Safeguards**
  - Test security policies are documented
  - Test security training is required (if applicable)
  - Test access controls are documented

- [ ] **Physical Safeguards**
  - Test data center security (if applicable)
  - Test backup security
  - Test disaster recovery procedures

- [ ] **Technical Safeguards**
  - Test access controls are implemented
  - Test audit controls are implemented
  - Test integrity controls are implemented
  - Test transmission security is implemented

#### 11.2 Breach Detection & Response Tests
**File to Create:** `tests/test_breach_detection.py`

- [ ] **Breach Detection**
  - Test unauthorized access attempts are detected
  - Test suspicious activity is logged
  - Test breach detection alerts are sent (if implemented)

- [ ] **Breach Response**
  - Test breach notification procedures (if applicable)
  - Test breach logging and documentation
  - Test breach containment procedures

### 12. Performance & Load Security Tests ⚠️ **LOW PRIORITY - PARTIAL**

#### 12.1 Load Testing Security
**File to Create:** `tests/test_load_security.py`

- [ ] **Security Under Load**
  - Test authentication works under high load
  - Test rate limiting works under high load
  - Test audit logging works under high load
  - Test encryption performance under load

#### 12.2 Stress Testing Security
**File to Create:** `tests/test_stress_security.py`

- [ ] **Security Under Stress**
  - Test security measures don't fail under stress
  - Test error handling doesn't leak information under stress
  - Test audit logging continues under stress

## Test Implementation Priority

### Phase 1: Critical Security Tests (Immediate)
1. Authentication & Authorization Tests
2. Audit Logging Tests
3. Data Encryption Tests
4. Input Validation & Injection Prevention Tests

### Phase 2: Important Security Tests (Within 2 weeks)
5. Session & Token Management Tests
6. Data Retention & Deletion Tests
7. Error Handling & Information Disclosure Tests
8. Compliance & Regulatory Tests

### Phase 3: Additional Security Tests (Within 1 month)
9. CORS & Security Headers Tests
10. Integration Security Tests
11. Performance & Load Security Tests

## Test Coverage Goals

- **Security Test Coverage**: Minimum 95% for all security-critical code
- **Authentication/Authorization**: 100% coverage
- **Audit Logging**: 100% coverage
- **PHI Handling**: 100% coverage
- **Encryption**: 100% coverage

## Test Execution

### Continuous Integration
- All security tests must pass before deployment
- Security tests run on every commit
- Security tests run in production-like environment

### Regular Security Audits
- Monthly security test review
- Quarterly penetration testing
- Annual HIPAA compliance audit

## Notes

- All tests must use test fixtures that don't contain real PHI
- All tests must clean up test data after execution
- All tests must be documented with clear test descriptions
- All security test failures must be treated as critical issues
- All security tests must be reviewed by security team before merging

## References

- HIPAA Security Rule: 45 CFR Parts 160, 162, and 164
- NIST Cybersecurity Framework
- OWASP Top 10
- Healthcare Industry Security Best Practices

