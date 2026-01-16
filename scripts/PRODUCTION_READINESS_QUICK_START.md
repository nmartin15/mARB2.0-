# Production Readiness - Quick Start Guide

This guide provides quick commands and workflows for production readiness validation.

## 🚀 Quick Commands

### 1. Security Validation

```bash
# Enhanced validation (recommended - includes dependency checks)
python scripts/validate_production_security_enhanced.py

# Basic validation (faster, basic checks only)
python scripts/validate_production_security.py
```

**What it checks**:
- Security settings (secrets, auth, CORS)
- Dependency vulnerabilities (if `safety` installed)
- Outdated packages
- File permissions
- SSL/TLS configuration
- Logging configuration

### 2. HTTPS Testing

```bash
# Test default URL (from API_URL env var or localhost)
python scripts/test_https_end_to_end.py

# Test specific production URL
python scripts/test_https_end_to_end.py https://api.yourdomain.com
```

**What it tests**:
- SSL certificate validity and expiration
- HTTPS connection
- HTTP to HTTPS redirect
- Security headers
- OpenSSL connection (if available)

### 3. Health Monitoring

```bash
# Monitor default URL
python scripts/monitor_health.py

# Monitor specific URL
python scripts/monitor_health.py https://api.yourdomain.com

# Save results to JSON file
API_URL=https://api.yourdomain.com HEALTH_CHECK_OUTPUT=health.json python scripts/monitor_health.py
```

**What it monitors**:
- Basic health endpoint
- Detailed health (database, Redis, Celery)
- System resources (CPU, memory, disk)
- Cache statistics

## 📋 Pre-Deployment Workflow

### Step 1: Security Validation

```bash
# Run enhanced security validation
python scripts/validate_production_security_enhanced.py

# Fix any errors (warnings are optional but recommended)
# Re-run until all errors are resolved
```

### Step 2: HTTPS Setup & Testing

```bash
# After setting up HTTPS, test it
python scripts/test_https_end_to_end.py https://api.yourdomain.com

# Fix any issues
# Re-test until all tests pass
```

### Step 3: Health Check Verification

```bash
# Verify health endpoints work
python scripts/monitor_health.py https://api.yourdomain.com

# Ensure all components are healthy
```

### Step 4: Follow Deployment Checklist

```bash
# Review comprehensive checklist
cat deployment/DEPLOYMENT_CHECKLIST.md

# Follow each section step-by-step
```

## 🔄 Post-Deployment Workflow

### Daily Monitoring

```bash
# Quick health check
python scripts/monitor_health.py https://api.yourdomain.com

# Check exit code
echo $?  # 0=healthy, 1=degraded, 2=unhealthy
```

### Weekly Validation

```bash
# Run security validation
python scripts/validate_production_security_enhanced.py

# Test HTTPS
python scripts/test_https_end_to_end.py https://api.yourdomain.com
```

## 🤖 Automation Examples

### Cron Job for Health Monitoring

```bash
# Add to crontab (check every 5 minutes)
*/5 * * * * cd /opt/marb2.0 && /opt/marb2.0/venv/bin/python scripts/monitor_health.py https://api.yourdomain.com >> /var/log/marb2.0/health.log 2>&1
```

### Health Check Alert Script

```bash
#!/bin/bash
# health_check_alert.sh

API_URL="https://api.yourdomain.com"
ALERT_EMAIL="admin@yourdomain.com"

cd /opt/marb2.0
python scripts/monitor_health.py "$API_URL"

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    # Send alert email
    python scripts/monitor_health.py "$API_URL" | mail -s "mARB 2.0 Health Alert" "$ALERT_EMAIL"
    exit 1
fi

exit 0
```

### Pre-Deployment Validation Script

```bash
#!/bin/bash
# pre_deployment_validation.sh

set -e

echo "Running pre-deployment validation..."

# Security validation
echo "1. Security validation..."
python scripts/validate_production_security_enhanced.py || exit 1

# HTTPS testing (if URL provided)
if [ -n "$1" ]; then
    echo "2. HTTPS testing..."
    python scripts/test_https_end_to_end.py "$1" || exit 1
fi

# Health check (if URL provided)
if [ -n "$1" ]; then
    echo "3. Health check..."
    python scripts/monitor_health.py "$1" || exit 1
fi

echo "✓ All validations passed!"
```

## 📊 Exit Codes

### validate_production_security_enhanced.py
- `0` - All checks passed (may have warnings)
- `1` - Critical errors found

### test_https_end_to_end.py
- `0` - All tests passed
- `1` - Some tests failed

### monitor_health.py
- `0` - Healthy
- `1` - Degraded
- `2` - Unhealthy

## 🔍 Troubleshooting

### Security Validation Fails

```bash
# Check specific issues
python scripts/validate_production_security_enhanced.py

# Fix errors one by one
# Common fixes:
# - Generate new keys: python generate_keys.py
# - Update .env file
# - Set file permissions: chmod 600 .env
```

### HTTPS Tests Fail

```bash
# Check SSL certificate
openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com

# Check nginx configuration
sudo nginx -t

# Verify certificate
sudo certbot certificates
```

### Health Check Fails

```bash
# Check service status
sudo systemctl status marb2.0.service
sudo systemctl status marb2.0-celery.service

# Check logs
sudo journalctl -u marb2.0.service -n 50
tail -50 logs/app.log

# Test endpoints manually
curl https://api.yourdomain.com/api/v1/health
curl https://api.yourdomain.com/api/v1/health/detailed
```

## 📚 Additional Resources

- `PRODUCTION_READINESS_COMPLETE.md` - Complete feature summary
- `deployment/DEPLOYMENT_CHECKLIST.md` - Comprehensive deployment checklist
- `SECURITY.md` - Security configuration guide
- `deployment/SETUP_HTTPS.md` - HTTPS setup instructions

## ✅ Quick Checklist

Before deploying to production:

- [ ] Run `validate_production_security_enhanced.py` - all errors fixed
- [ ] Run `test_https_end_to_end.py` - all tests pass
- [ ] Run `monitor_health.py` - all components healthy
- [ ] Review `DEPLOYMENT_CHECKLIST.md` - all items checked
- [ ] Test critical workflows manually
- [ ] Verify monitoring alerts configured
- [ ] Document deployment details

