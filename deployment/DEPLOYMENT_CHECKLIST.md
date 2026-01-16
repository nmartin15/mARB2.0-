# mARB 2.0 - Comprehensive Production Deployment Checklist

This checklist covers all aspects of deploying mARB 2.0 to production. Use this as your guide to ensure a secure, reliable deployment.

## 📋 Pre-Deployment Checklist

### 1. Security Validation

- [ ] **Run Enhanced Security Validation**
  ```bash
  python scripts/validate_production_security_enhanced.py
  ```
  - All errors must be resolved before deployment
  - Review all warnings

- [ ] **Run Basic Security Validation**
  ```bash
  python scripts/validate_production_security.py
  ```
  - Verify no critical security issues

- [ ] **Check Dependency Vulnerabilities**
  ```bash
  pip install safety
  safety check
  ```
  - Review and update any vulnerable packages

- [ ] **Review Outdated Packages**
  ```bash
  pip list --outdated
  ```
  - Update critical packages if needed
  - Test updates in staging first

### 2. Environment Configuration

- [ ] **Generate Secure Keys**
  ```bash
  python generate_keys.py
  ```
  - Copy generated keys to `.env` file

- [ ] **Set Up Production Environment**
  ```bash
  python scripts/setup_production_env.py
  ```
  - Review all environment variables
  - Update with production values

- [ ] **Verify Environment Variables**
  ```bash
  python scripts/verify_env.py
  ```
  - All required variables are set
  - No placeholder values remain

- [ ] **Set File Permissions**
  ```bash
  chmod 600 .env
  ```
  - `.env` file should be readable only by owner

### 3. Database Setup

- [ ] **Run Database Migrations**
  ```bash
  alembic upgrade head
  ```
  - Verify all migrations applied successfully
  - Check migration status: `alembic current`

- [ ] **Verify Database Connection**
  ```bash
  psql $DATABASE_URL -c "SELECT 1;"
  ```
  - Connection works with SSL
  - SSL mode is `require` or `prefer`

- [ ] **Test Database Backup**
  ```bash
  # Create test backup
  pg_dump $DATABASE_URL > test_backup.sql
  
  # Verify backup
  head -20 test_backup.sql
  ```
  - Backup completes successfully
  - Backup contains expected data

- [ ] **Configure Database Backups**
  - Set up automated backup schedule
  - Configure backup retention policy
  - Test backup restoration process

### 4. Redis Setup

- [ ] **Verify Redis Connection**
  ```bash
  redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping
  ```
  - Connection works with password
  - PING returns PONG

- [ ] **Verify Celery Configuration**
  - `CELERY_BROKER_URL` includes Redis password
  - `CELERY_RESULT_BACKEND` includes Redis password
  - Test Celery connection

- [ ] **Configure Redis Persistence**
  - AOF or RDB persistence enabled
  - Backup strategy configured

### 5. HTTPS/TLS Configuration

- [ ] **Obtain SSL Certificate**
  ```bash
  # Using Let's Encrypt (recommended)
  sudo certbot --nginx -d api.yourdomain.com
  ```
  - Certificate obtained successfully
  - Auto-renewal configured

- [ ] **Configure nginx**
  ```bash
  # Copy configuration
  sudo cp deployment/nginx.conf.example /etc/nginx/sites-available/marb2.0
  
  # Update with your domain and certificate paths
  sudo nano /etc/nginx/sites-available/marb2.0
  
  # Enable site
  sudo ln -s /etc/nginx/sites-available/marb2.0 /etc/nginx/sites-enabled/
  
  # Test configuration
  sudo nginx -t
  
  # Reload nginx
  sudo systemctl reload nginx
  ```

- [ ] **Test HTTPS End-to-End**
  ```bash
  python scripts/test_https_end_to_end.py https://api.yourdomain.com
  ```
  - All HTTPS tests pass
  - SSL certificate valid
  - HTTP redirects to HTTPS
  - Security headers present

- [ ] **Verify SSL Rating**
  - Visit [SSL Labs SSL Test](https://www.ssllabs.com/ssltest/)
  - Achieve A or A+ rating
  - Address any warnings

### 6. Application Deployment

- [ ] **Install Dependencies**
  ```bash
  pip install -r requirements.txt
  ```
  - All dependencies installed
  - No installation errors

- [ ] **Verify Application Starts**
  ```bash
  python run.py
  ```
  - Application starts without errors
  - All services connect successfully

- [ ] **Set Up Systemd Services**
  ```bash
  # Review and update service files
  sudo nano /etc/systemd/system/marb2.0.service
  sudo nano /etc/systemd/system/marb2.0-celery.service
  
  # Enable and start services
  sudo systemctl daemon-reload
  sudo systemctl enable marb2.0.service
  sudo systemctl enable marb2.0-celery.service
  sudo systemctl start marb2.0.service
  sudo systemctl start marb2.0-celery.service
  ```

- [ ] **Verify Services Running**
  ```bash
  sudo systemctl status marb2.0.service
  sudo systemctl status marb2.0-celery.service
  ```
  - Both services active and running
  - No errors in logs

### 7. Monitoring & Health Checks

- [ ] **Test Health Check Endpoints**
  ```bash
  # Basic health
  curl https://api.yourdomain.com/api/v1/health
  
  # Detailed health
  curl https://api.yourdomain.com/api/v1/health/detailed
  ```
  - Both endpoints return 200 OK
  - All components healthy

- [ ] **Run Health Check Monitoring**
  ```bash
  python scripts/monitor_health.py https://api.yourdomain.com
  ```
  - All checks pass
  - Response times acceptable

- [ ] **Set Up Monitoring Alerts**
  - Configure health check monitoring (cron or monitoring service)
  - Set up alerting for failures
  - Test alert delivery

- [ ] **Configure Logging**
  - Log rotation configured
  - Log levels appropriate for production
  - Log storage secure

### 8. Firewall Configuration

- [ ] **Configure Firewall Rules**
  ```bash
  # Allow SSH
  sudo ufw allow 22/tcp
  
  # Allow HTTP (for Let's Encrypt)
  sudo ufw allow 80/tcp
  
  # Allow HTTPS
  sudo ufw allow 443/tcp
  
  # Enable firewall
  sudo ufw enable
  
  # Verify
  sudo ufw status
  ```
  - Only necessary ports open
  - Firewall active and enabled

### 9. Authentication & Authorization

- [ ] **Verify Authentication Enabled**
  - `REQUIRE_AUTH=true` in `.env`
  - Test unauthenticated request returns 401
  - Test authenticated request succeeds

- [ ] **Test Rate Limiting**
  - Verify rate limits enforced
  - Test rate limit headers present
  - Verify exempt paths work

- [ ] **Verify CORS Configuration**
  - CORS origins set to production domains only
  - No wildcards (`*`) in production
  - Test CORS headers present

### 10. Final Verification

- [ ] **Run All Validation Scripts**
  ```bash
  # Security validation
  python scripts/validate_production_security_enhanced.py
  
  # HTTPS testing
  python scripts/test_https_end_to_end.py https://api.yourdomain.com
  
  # Health monitoring
  python scripts/monitor_health.py https://api.yourdomain.com
  ```
  - All scripts pass
  - No critical issues

- [ ] **Test Critical Endpoints**
  - Health check: `/api/v1/health`
  - Detailed health: `/api/v1/health/detailed`
  - API documentation: `/api/v1/docs`
  - All endpoints accessible and working

- [ ] **Verify Logs**
  ```bash
  # Application logs
  tail -f logs/app.log
  
  # Systemd logs
  sudo journalctl -u marb2.0.service -f
  sudo journalctl -u marb2.0-celery.service -f
  
  # nginx logs
  sudo tail -f /var/log/nginx/marb2.0_access.log
  sudo tail -f /var/log/nginx/marb2.0_error.log
  ```
  - No errors in logs
  - Requests being logged correctly

## 📊 Post-Deployment Checklist

### 1. Immediate Verification (First 24 Hours)

- [ ] **Monitor Application Logs**
  - Check for errors
  - Verify request patterns
  - Monitor response times

- [ ] **Monitor System Resources**
  - CPU usage acceptable
  - Memory usage acceptable
  - Disk space sufficient

- [ ] **Verify Health Checks**
  - Health checks passing
  - All components healthy
  - Response times acceptable

- [ ] **Test Critical Workflows**
  - File upload works
  - Processing completes
  - Results returned correctly

### 2. Security Verification

- [ ] **Verify Security Headers**
  ```bash
  curl -I https://api.yourdomain.com/api/v1/health | grep -i "strict-transport\|x-frame\|x-content"
  ```
  - All security headers present

- [ ] **Test Authentication**
  - Unauthenticated requests blocked
  - Authenticated requests work
  - Rate limiting enforced

- [ ] **Review Access Logs**
  - No suspicious activity
  - Failed authentication attempts monitored
  - Rate limit violations reviewed

### 3. Performance Verification

- [ ] **Monitor Response Times**
  - API response times acceptable
  - Database query times acceptable
  - Cache hit rates acceptable

- [ ] **Monitor Queue Processing**
  - Celery tasks processing
  - Queue length manageable
  - No stuck tasks

- [ ] **Monitor Resource Usage**
  - CPU usage within limits
  - Memory usage within limits
  - Disk I/O acceptable

### 4. Backup Verification

- [ ] **Verify Automated Backups**
  - Backups running on schedule
  - Backup files created successfully
  - Backup retention policy working

- [ ] **Test Backup Restoration**
  - Restore from backup to test environment
  - Verify data integrity
  - Document restoration process

## 🔄 Ongoing Maintenance Checklist

### Daily

- [ ] Check application logs for errors
- [ ] Monitor health check endpoints
- [ ] Review error rates
- [ ] Check system resource usage

### Weekly

- [ ] Review security logs
- [ ] Check for failed authentication attempts
- [ ] Monitor rate limit violations
- [ ] Review performance metrics
- [ ] Check backup completion

### Monthly

- [ ] Update dependencies: `pip list --outdated`
- [ ] Review and apply security patches
- [ ] Test backup restoration
- [ ] Review SSL certificate expiration
- [ ] Review and update firewall rules
- [ ] Security audit

### Quarterly

- [ ] Comprehensive security review
- [ ] Performance optimization review
- [ ] Disaster recovery drill
- [ ] Update SSL/TLS configuration if needed
- [ ] Review and update monitoring alerts

## 🚨 Incident Response

### If Issues Detected

1. **Check Health Status**
   ```bash
   python scripts/monitor_health.py https://api.yourdomain.com
   ```

2. **Review Logs**
   ```bash
   sudo journalctl -u marb2.0.service -n 100
   tail -100 logs/app.log
   ```

3. **Check System Resources**
   ```bash
   top
   df -h
   free -h
   ```

4. **Restart Services if Needed**
   ```bash
   sudo systemctl restart marb2.0.service
   sudo systemctl restart marb2.0-celery.service
   ```

5. **Rollback if Necessary**
   - Revert to previous deployment
   - Restore from backup if needed
   - Document incident

## 📞 Support & Resources

### Documentation

- `SECURITY.md` - Security configuration guide
- `deployment/SETUP_HTTPS.md` - HTTPS setup instructions
- `deployment/DEPLOYMENT.md` - Deployment guide
- `deployment/PRODUCTION_SECURITY_CHECKLIST.md` - Security checklist

### Scripts

- `scripts/validate_production_security_enhanced.py` - Enhanced security validation
- `scripts/test_https_end_to_end.py` - HTTPS testing
- `scripts/monitor_health.py` - Health check monitoring
- `scripts/validate_production_security.py` - Basic security validation

### Quick Commands

```bash
# Security validation
python scripts/validate_production_security_enhanced.py

# HTTPS testing
python scripts/test_https_end_to_end.py https://api.yourdomain.com

# Health monitoring
python scripts/monitor_health.py https://api.yourdomain.com

# Check services
sudo systemctl status marb2.0.service
sudo systemctl status marb2.0-celery.service

# View logs
sudo journalctl -u marb2.0.service -f
tail -f logs/app.log
```

## ✅ Deployment Sign-Off

Before marking deployment as complete, ensure:

- [ ] All pre-deployment checklist items completed
- [ ] All validation scripts pass
- [ ] Health checks passing
- [ ] Security verified
- [ ] Monitoring configured
- [ ] Documentation updated
- [ ] Team notified of deployment

**Deployment Date**: _______________

**Deployed By**: _______________

**Verified By**: _______________

**Notes**: _______________

