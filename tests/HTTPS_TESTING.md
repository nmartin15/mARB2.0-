# HTTPS Testing Procedures for mARB 2.0

This document outlines the HTTPS testing procedures and test suite for mARB 2.0.

## Overview

The HTTPS testing suite verifies:
- SSL/TLS certificate configuration
- Security headers (HSTS, X-Frame-Options, etc.)
- HTTP to HTTPS redirects
- CORS configuration with HTTPS origins
- Production readiness for HTTPS deployment

## Test Structure

### Test Files

- `tests/test_https.py` - Main HTTPS test suite
- `tests/utils/https_test_utils.py` - Utilities for HTTPS testing

### Test Categories

1. **HTTPS Configuration Tests** (`TestHTTPSConfiguration`)
   - Security headers presence and validation
   - HSTS header validation
   - Security headers extraction

2. **SSL Certificate Tests** (`TestSSLCertificateGeneration`)
   - Self-signed certificate generation for testing
   - Certificate validation
   - Custom hostname support

3. **HTTPS Integration Tests** (`TestHTTPSIntegration`)
   - HTTPS endpoint accessibility
   - HTTP to HTTPS redirect simulation
   - CORS with HTTPS origins

4. **Security Best Practices Tests** (`TestSecurityBestPractices`)
   - No sensitive data in URLs
   - Secure cookie settings

5. **Production Readiness Tests** (`TestHTTPSProductionReadiness`)
   - Health endpoint HTTPS readiness
   - API endpoints HTTPS readiness

## Running HTTPS Tests

### Run All HTTPS Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all HTTPS tests
pytest tests/test_https.py -v

# Run with coverage
pytest tests/test_https.py --cov=app --cov-report=html -v
```

### Run Specific Test Categories

```bash
# Run only security header tests
pytest tests/test_https.py::TestHTTPSConfiguration -v

# Run only certificate generation tests
pytest tests/test_https.py::TestSSLCertificateGeneration -v

# Run only integration tests
pytest tests/test_https.py::TestHTTPSIntegration -v

# Run only production readiness tests
pytest tests/test_https.py::TestHTTPSProductionReadiness -v
```

### Run Tests by Markers

```bash
# Run all security-related tests
pytest -m security -v

# Run all integration tests
pytest -m integration -v

# Run all API tests
pytest -m api -v
```

## Test Utilities

### Certificate Generation

The test utilities include functions for generating self-signed certificates for testing:

```python
from tests.utils.https_test_utils import generate_self_signed_certificate

# Generate a self-signed certificate
cert_path, key_path = generate_self_signed_certificate(
    hostname="test.example.com",
    output_dir=Path("/tmp/certs"),
)
```

### Security Headers Validation

```python
from tests.utils.https_test_utils import get_security_headers, validate_hsts_header

# Extract security headers from response
headers = dict(response.headers)
security_headers = get_security_headers(headers)

# Validate HSTS header
hsts_value = security_headers["Strict-Transport-Security"]
validation = validate_hsts_header(hsts_value)
```

### SSL Certificate Checking

```python
from tests.utils.https_test_utils import check_ssl_certificate

# Check certificate details
cert_info = check_ssl_certificate(cert_path)
assert cert_info["valid"] is True
```

## Manual Testing Procedures

### 1. Test HTTPS Connection

After deploying with HTTPS, verify the connection:

```bash
# Test HTTPS endpoint
curl -I https://api.yourdomain.com/api/v1/health

# Should return HTTP 200 with security headers
```

### 2. Test HTTP to HTTPS Redirect

```bash
# Test HTTP redirect
curl -I http://api.yourdomain.com/api/v1/health

# Should return HTTP 301 redirect to HTTPS
```

### 3. Verify Security Headers

```bash
# Check security headers
curl -I https://api.yourdomain.com/api/v1/health | grep -i "strict-transport\|x-frame\|x-content"

# Should see:
# - Strict-Transport-Security
# - X-Frame-Options
# - X-Content-Type-Options
# - X-XSS-Protection
```

### 4. Test SSL Certificate

```bash
# Check SSL certificate
openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com < /dev/null

# Verify certificate details
openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com -showcerts
```

### 5. Test SSL Rating

Visit [SSL Labs SSL Test](https://www.ssllabs.com/ssltest/) and enter your domain. Should achieve **A+ rating** with proper configuration.

## Continuous Integration

### GitHub Actions Example

Add to `.github/workflows/test.yml`:

```yaml
- name: Run HTTPS Tests
  run: |
    source venv/bin/activate
    pytest tests/test_https.py -v --cov=app --cov-report=xml
```

### Pre-commit Hook

Add HTTPS tests to pre-commit checks:

```bash
# In .pre-commit-config.yaml or Makefile
test-https:
	pytest tests/test_https.py -v
```

## Production Deployment Checklist

Before deploying to production with HTTPS:

- [ ] All HTTPS tests pass (`pytest tests/test_https.py -v`)
- [ ] SSL certificate obtained and configured
- [ ] nginx configured with security headers
- [ ] HTTP to HTTPS redirect working
- [ ] Security headers present in responses
- [ ] SSL Labs rating is A or A+
- [ ] Certificate auto-renewal configured
- [ ] CORS origins updated to HTTPS URLs
- [ ] Database connections use SSL
- [ ] Redis connections use SSL (if applicable)

## Troubleshooting

### Tests Fail with "openssl not found"

Install OpenSSL:

```bash
# macOS
brew install openssl

# Ubuntu/Debian
sudo apt-get install openssl

# Verify installation
openssl version
```

### Certificate Generation Fails

Ensure `cryptography` is installed:

```bash
pip install cryptography
```

The `cryptography` package is included via `python-jose[cryptography]` in `requirements.txt`.

### Security Headers Not Present in Tests

**Note**: Security headers are typically set by nginx in production, not by the FastAPI application. The tests verify:
1. The application structure supports HTTPS
2. Security header validation logic works correctly
3. The application is ready for HTTPS deployment

To test actual security headers in production, use manual testing procedures or integration tests against a deployed environment.

## Test Coverage

The HTTPS test suite covers:

- ✅ Security headers validation
- ✅ HSTS header parsing and validation
- ✅ SSL certificate generation utilities
- ✅ Certificate validation
- ✅ HTTPS endpoint accessibility
- ✅ CORS with HTTPS origins
- ✅ Production readiness checks

## Additional Resources

- [HTTPS Setup Guide](../deployment/SETUP_HTTPS.md)
- [Security Guide](../SECURITY.md)
- [nginx Configuration](../deployment/nginx.conf.example)
- [SSL Labs SSL Test](https://www.ssllabs.com/ssltest/)

