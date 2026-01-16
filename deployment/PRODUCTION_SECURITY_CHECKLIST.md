# Production Security Checklist

Use this checklist before deploying mARB 2.0 to production.

## Pre-Deployment Security Validation

### 1. Run Security Validation Script

```bash
# Validate production security settings
python scripts/validate_production_security.py
```

This will check:
- ✅ All default secrets are changed
- ✅ JWT_SECRET_KEY is secure (32+ characters)
- ✅ ENCRYPTION_KEY is secure (32 characters)
- ✅ DEBUG is set to false
- ✅ ENVIRONMENT is set to production
- ✅ REQUIRE_AUTH is set to true
- ✅ CORS_ORIGINS doesn't contain wildcards
- ✅ Redis password is set
- ✅ Database URL uses SSL

### 2. Generate Secure Keys

```bash
# Generate new secure keys
python generate_keys.py

# Copy output to .env file
```

### 3. Set Up Production Environment

```bash
# Create production .env file
python scripts/setup_production_env.py

# Review and update all values
nano .env
```

## Environment Variables Checklist

### Required Changes

- [ ] `ENVIRONMENT=production`
- [ ] `DEBUG=false`
- [ ] `JWT_SECRET_KEY` - Changed from default (use `generate_keys.py`)
- [ ] `ENCRYPTION_KEY` - Changed from default (use `generate_keys.py`)
- [ ] `REDIS_PASSWORD` - Set to strong password
- [ ] `CELERY_BROKER_URL` - Includes Redis password
- [ ] `CELERY_RESULT_BACKEND` - Includes Redis password
- [ ] `DATABASE_URL` - Includes `?sslmode=require`
- [ ] `CORS_ORIGINS` - Set to exact production domains (no wildcards)
- [ ] `REQUIRE_AUTH=true`

### File Permissions

```bash
# Set secure permissions on .env file
chmod 600 .env
```

## HTTPS/TLS Setup

### Using Let's Encrypt (Recommended)

- [ ] Certbot installed
- [ ] SSL certificate obtained
- [ ] nginx configured with SSL
- [ ] HTTP to HTTPS redirect working
- [ ] Auto-renewal configured
- [ ] SSL Labs rating is A or A+

See `deployment/SETUP_HTTPS.md` for detailed instructions.

### Manual Certificate Setup

- [ ] SSL certificates placed in secure location
- [ ] Certificate permissions set correctly (644 for cert, 600 for key)
- [ ] nginx configured with certificate paths
- [ ] SSL configuration tested

## nginx Configuration

- [ ] nginx configuration copied to `/etc/nginx/sites-available/`
- [ ] Site enabled (symlink created)
- [ ] Configuration tested (`nginx -t`)
- [ ] nginx reloaded
- [ ] Security headers present:
  - [ ] Strict-Transport-Security
  - [ ] X-Frame-Options
  - [ ] X-Content-Type-Options
  - [ ] X-XSS-Protection
  - [ ] Referrer-Policy

## Database Security

- [ ] PostgreSQL SSL enabled (`?sslmode=require` in DATABASE_URL)
- [ ] Database user has minimum required permissions
- [ ] Database password is strong
- [ ] Database backups configured
- [ ] Backup encryption enabled (if storing backups)

## Redis Security

- [ ] Redis password set and strong
- [ ] Redis only accessible from localhost (or firewall configured)
- [ ] Celery broker URL includes password
- [ ] Celery result backend includes password

## Application Security

- [ ] Authentication enforced (`REQUIRE_AUTH=true`)
- [ ] Rate limiting configured appropriately
- [ ] CORS configured with exact domains
- [ ] Audit logging enabled
- [ ] Error messages don't expose sensitive information

## Firewall Configuration

- [ ] Only necessary ports open:
  - [ ] 22 (SSH) - or custom port
  - [ ] 80 (HTTP) - for Let's Encrypt
  - [ ] 443 (HTTPS)
- [ ] Firewall enabled and active
- [ ] Fail2ban or similar configured (optional but recommended)

## Monitoring & Logging

- [ ] Log rotation configured
- [ ] Logs stored securely
- [ ] Monitoring set up (health checks, alerts)
- [ ] Error tracking configured (optional: Sentry, etc.)

## Backup & Recovery

- [ ] Database backups automated
- [ ] Backup retention policy defined
- [ ] Backup restoration tested
- [ ] Disaster recovery plan documented

## Post-Deployment Verification

### 1. Test HTTPS

```bash
# Test HTTPS endpoint
curl -I https://api.yourdomain.com/api/v1/health

# Should return 200 OK with security headers
```

### 2. Test HTTP Redirect

```bash
# Test HTTP to HTTPS redirect
curl -I http://api.yourdomain.com/api/v1/health

# Should return 301 redirect to HTTPS
```

### 3. Verify Security Headers

```bash
curl -I https://api.yourdomain.com/api/v1/health | grep -i "strict-transport\|x-frame\|x-content"
```

### 4. Test SSL Rating

Visit [SSL Labs SSL Test](https://www.ssllabs.com/ssltest/) and verify A or A+ rating.

### 5. Test Authentication

```bash
# Should require authentication (if REQUIRE_AUTH=true)
curl https://api.yourdomain.com/api/v1/claims

# Should return 401 Unauthorized
```

### 6. Verify Logs

```bash
# Check application logs
tail -f logs/app.log

# Check nginx logs
sudo tail -f /var/log/nginx/marb2.0_access.log
sudo tail -f /var/log/nginx/marb2.0_error.log
```

## Ongoing Maintenance

### Weekly

- [ ] Review security logs
- [ ] Check for failed authentication attempts
- [ ] Monitor rate limit violations
- [ ] Review error rates

### Monthly

- [ ] Update dependencies: `pip list --outdated`
- [ ] Review and apply security patches
- [ ] Test backup restoration
- [ ] Review SSL certificate expiration

### Quarterly

- [ ] Security audit
- [ ] Review access logs
- [ ] Update SSL/TLS configuration if needed
- [ ] Review and update firewall rules

## Incident Response

- [ ] Incident response plan documented
- [ ] Contact information for security team
- [ ] Backup communication channels
- [ ] Rollback procedures documented

## Compliance

For HIPAA compliance, ensure:

- [ ] All PHI access is logged (audit logging)
- [ ] Data encrypted in transit (HTTPS/TLS)
- [ ] Data encrypted at rest (database encryption)
- [ ] Access controls implemented (authentication)
- [ ] Business Associate Agreements in place
- [ ] Security policies documented
- [ ] Staff trained on security procedures

## Quick Commands Reference

```bash
# Validate security
python scripts/validate_production_security.py

# Generate keys
python generate_keys.py

# Setup production env
python scripts/setup_production_env.py

# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Check SSL certificate
sudo certbot certificates

# Test SSL renewal
sudo certbot renew --dry-run

# Check firewall
sudo ufw status

# View logs
tail -f logs/app.log
sudo journalctl -u marb2.0.service -f
```

## Support

If you encounter issues:

1. Check logs first
2. Run security validation script
3. Review `SECURITY.md` for detailed guidance
4. Review `deployment/SETUP_HTTPS.md` for HTTPS setup
5. Review `deployment/DEPLOYMENT.md` for deployment steps

