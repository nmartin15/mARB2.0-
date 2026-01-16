# HTTPS End-to-End Testing Guide

This guide explains how to test your HTTPS setup end-to-end once you have a production URL.

## Prerequisites

- Production URL with HTTPS configured
- SSL certificate installed (Let's Encrypt or custom)
- nginx configured with SSL
- Python 3.9+ with required packages

## Quick Start

### 1. Install Required Packages

```bash
source venv/bin/activate
pip install httpx requests
```

### 2. Run HTTPS Test

```bash
# Test with production URL
python scripts/test_https_end_to_end.py https://api.yourdomain.com

# Or set environment variable
export API_URL=https://api.yourdomain.com
python scripts/test_https_end_to_end.py
```

## What the Test Checks

The `test_https_end_to_end.py` script performs comprehensive HTTPS testing:

### 1. SSL Certificate Validation
- Verifies certificate is valid and not expired
- Checks certificate subject and issuer
- Validates TLS protocol version (should be 1.2 or 1.3)
- Checks cipher suite
- Warns if certificate expires within 30 days

### 2. HTTPS Connection Test
- Tests HTTPS connection to health endpoint
- Measures response time
- Verifies SSL handshake succeeds
- Checks for SSL errors

### 3. HTTP to HTTPS Redirect
- Verifies HTTP requests redirect to HTTPS
- Checks redirect status code (301, 302, 307, or 308)
- Validates redirect URL uses HTTPS

### 4. Security Headers Check
- Verifies presence of required security headers:
  - `Strict-Transport-Security` (HSTS)
  - `X-Frame-Options`
  - `X-Content-Type-Options`
- Warns if any headers are missing

### 5. OpenSSL Connection Test (Optional)
- Uses OpenSSL command-line tool if available
- Performs deep SSL connection analysis
- Validates certificate chain

## Expected Output

### Successful Test

```
======================================================================
mARB 2.0 - End-to-End HTTPS Testing
======================================================================
Timestamp: 2025-01-15T10:30:00Z

Testing URL: https://api.yourdomain.com

1. Testing SSL Certificate...
   ✓ SSL Certificate is valid
     Subject: api.yourdomain.com
     Issuer: Let's Encrypt
     Protocol: TLSv1.3
     Cipher: TLS_AES_256_GCM_SHA384
     ✓ Certificate expires in 45 days

2. Testing HTTPS Connection...
   ✓ HTTPS connection successful
     Status Code: 200
     Response Time: 125.50 ms

3. Testing HTTP to HTTPS Redirect...
   ✓ HTTP redirects to HTTPS
     Redirect URL: https://api.yourdomain.com/api/v1/health

4. Checking Security Headers...
   ✓ Required security headers present
     Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
     X-Frame-Options: DENY
     X-Content-Type-Options: nosniff

5. Testing with OpenSSL (if available)...
   ✓ OpenSSL connection successful
     Certificate verification: OK

======================================================================
HTTPS TEST SUMMARY
======================================================================

✓ All HTTPS tests passed!

Your HTTPS setup appears to be correctly configured.

Next steps:
  - Verify SSL Labs rating (https://www.ssllabs.com/ssltest/)
  - Test certificate auto-renewal
  - Monitor certificate expiration
```

### Test with Issues

```
======================================================================
HTTPS TEST SUMMARY
======================================================================

⚠ Issues found:
  • Certificate expires in 15 days
  • Missing security headers: X-Content-Type-Options

⚠ Warnings found, but no critical failures.
```

## Manual Testing

### Test SSL Certificate

```bash
# Check certificate details
openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com < /dev/null

# Check certificate expiration
echo | openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com 2>/dev/null | \
  openssl x509 -noout -dates
```

### Test HTTPS Connection

```bash
# Test health endpoint
curl -I https://api.yourdomain.com/api/v1/health

# Test with verbose SSL info
curl -v https://api.yourdomain.com/api/v1/health
```

### Test HTTP Redirect

```bash
# Should return 301 redirect
curl -I http://api.yourdomain.com/api/v1/health

# Follow redirect
curl -L http://api.yourdomain.com/api/v1/health
```

### Check Security Headers

```bash
curl -I https://api.yourdomain.com/api/v1/health | grep -i "strict-transport-security\|x-frame-options\|x-content-type-options"
```

## SSL Labs Test

After running the automated test, verify your SSL configuration with SSL Labs:

1. Visit: https://www.ssllabs.com/ssltest/
2. Enter your domain: `api.yourdomain.com`
3. Wait for the test to complete (may take a few minutes)
4. Review the rating (should be A or A+)
5. Address any warnings or issues

### Common Issues and Fixes

#### Rating Below A
- **Weak cipher suites**: Update nginx configuration to use modern ciphers
- **Missing HSTS**: Add `Strict-Transport-Security` header
- **Weak DH parameters**: Generate 2048-bit DH parameters
- **Missing OCSP stapling**: Enable OCSP stapling in nginx

#### Certificate Expiring Soon
- **Auto-renewal not working**: Check certbot timer status
- **Manual renewal**: Run `sudo certbot renew`

#### Missing Security Headers
- **Add to nginx config**: See `deployment/nginx.conf.example`
- **Verify headers are set**: Check nginx configuration

## Automated Testing

### Cron Job for Regular Testing

Create a cron job to test HTTPS regularly:

```bash
# Add to crontab (test daily at 2 AM)
0 2 * * * /opt/marb2.0/venv/bin/python /opt/marb2.0/scripts/test_https_end_to_end.py https://api.yourdomain.com >> /opt/marb2.0/logs/https_test.log 2>&1
```

### Alert on Failures

Modify the script to send alerts on failures:

```bash
#!/bin/bash
# /opt/marb2.0/scripts/test_https_with_alert.sh

API_URL="https://api.yourdomain.com"
ALERT_EMAIL="admin@yourdomain.com"

python /opt/marb2.0/scripts/test_https_end_to_end.py "$API_URL"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "HTTPS test failed for $API_URL" | mail -s "HTTPS Test Failure" "$ALERT_EMAIL"
fi
```

## Integration with Monitoring

### Health Check Integration

Add HTTPS test to your health monitoring:

```python
# In your monitoring script
import subprocess

def test_https():
    result = subprocess.run(
        ["python", "scripts/test_https_end_to_end.py", "https://api.yourdomain.com"],
        capture_output=True,
        text=True
    )
    return result.returncode == 0
```

### Sentry Integration

Log HTTPS test failures to Sentry:

```python
from sentry_sdk import capture_message

if not test_https():
    capture_message("HTTPS test failed", level="error")
```

## Troubleshooting

### Certificate Not Found
- **Issue**: Certificate path incorrect in nginx config
- **Fix**: Verify certificate paths in `/etc/nginx/sites-available/marb2.0`

### Connection Refused
- **Issue**: Firewall blocking port 443
- **Fix**: Open port 443: `sudo ufw allow 443/tcp`

### SSL Handshake Failed
- **Issue**: Certificate doesn't match domain
- **Fix**: Ensure certificate is for the correct domain

### Redirect Not Working
- **Issue**: HTTP server block not configured
- **Fix**: Add HTTP to HTTPS redirect in nginx config

## Best Practices

1. **Test Regularly**: Run HTTPS tests weekly or after configuration changes
2. **Monitor Expiration**: Set up alerts for certificates expiring within 30 days
3. **SSL Labs Rating**: Aim for A+ rating on SSL Labs
4. **Security Headers**: Always include required security headers
5. **Auto-Renewal**: Verify certbot auto-renewal is working
6. **Documentation**: Keep HTTPS configuration documented

## Related Documentation

- `deployment/SETUP_HTTPS.md` - HTTPS setup guide
- `deployment/nginx.conf.example` - nginx configuration template
- `SECURITY.md` - Security best practices
- `scripts/test_https_end_to_end.py` - Test script source code

## Support

If you encounter issues:

1. Check nginx error logs: `sudo tail -f /var/log/nginx/error.log`
2. Verify certificate: `sudo certbot certificates`
3. Test nginx config: `sudo nginx -t`
4. Review SSL Labs report for specific issues

