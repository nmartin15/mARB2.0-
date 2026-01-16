# mARB 2.0 - Deployment Runbook

**Purpose**: Step-by-step operational guide for deploying and maintaining mARB 2.0 in production.

**Audience**: DevOps engineers, system administrators, and developers deploying the application.

**Last Updated**: 2024

---

## ⚠️ PREREQUISITES - READ FIRST

**Before proceeding, ensure all prerequisites are met. See [DEPENDENCIES.md](../DEPENDENCIES.md) for complete list.**

### Required System Packages
- ✅ Python 3.11+
- ✅ PostgreSQL 14+
- ✅ Redis 7+
- ✅ nginx
- ✅ Git
- ✅ Systemd (for service management)

### Required Tools
- ✅ `pg_dump` / `pg_restore` (PostgreSQL client tools)
- ✅ `gzip` / `gunzip` (compression)
- ✅ `find` (file management)
- ✅ `curl` (for health checks)

### Required Access
- ✅ Root or sudo access
- ✅ Database admin access
- ✅ Application user created (`marb`)

### Required Configuration
- ✅ `.env` file configured
- ✅ Database created
- ✅ SSL certificates obtained (for production)

**If any prerequisites are missing, the deployment will fail. Verify with:**
```bash
# Check system packages
python3 --version
psql --version
redis-cli --version
nginx -v

# Check tools
which pg_dump
which gzip
which curl
```

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Initial Deployment Procedure](#initial-deployment-procedure)
3. [Update/Upgrade Procedure](#updateupgrade-procedure)
4. [Rollback Procedure](#rollback-procedure)
5. [Health Check Procedures](#health-check-procedures)
6. [Common Issues & Solutions](#common-issues--solutions)
7. [Emergency Procedures](#emergency-procedures)
8. [Maintenance Windows](#maintenance-windows)

---

## Pre-Deployment Checklist

### Before Starting Deployment

- [ ] **Review Changes**: Review git commits/changelog for this deployment
- [ ] **Test Environment**: Verify changes work in staging/test environment
- [ ] **Database Migrations**: Review Alembic migrations that will run
- [ ] **Dependencies**: Check if `requirements.txt` has new dependencies
- [ ] **Breaking Changes**: Identify any breaking changes or required config updates
- [ ] **Backup**: Ensure database backup is current (see [Backup Procedure](#backup-procedure))
- [ ] **Maintenance Window**: Schedule maintenance window if needed
- [ ] **Team Notification**: Notify team of deployment time
- [ ] **Rollback Plan**: Have rollback plan ready (see [Rollback Procedure](#rollback-procedure))

### Environment Verification

```bash
# Verify current environment
cd /opt/marb2.0
source venv/bin/activate

# Check current version
git log -1 --oneline

# Verify services are running
sudo systemctl status marb2.0.service
sudo systemctl status marb2.0-celery.service

# Check database connectivity
python -c "from app.config.database import engine; engine.connect(); print('DB OK')"

# Check Redis connectivity
redis-cli ping
```

---

## Initial Deployment Procedure

### Step 1: Server Preparation

```bash
# SSH into production server
ssh user@production-server

# Switch to application user
sudo su - marb
cd /opt/marb2.0
```

### Step 2: Clone Repository

```bash
# Clone repository (if not already done)
git clone <repository-url> /opt/marb2.0
cd /opt/marb2.0

# Verify you're on correct branch
git checkout main  # or production branch
git pull origin main
```

### Step 3: Set Up Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import fastapi; print('FastAPI installed')"
```

### Step 4: Generate Secure Keys

```bash
# Generate secure keys
python generate_keys.py

# Copy output to .env file
# Edit .env and replace JWT_SECRET_KEY and ENCRYPTION_KEY
nano .env
```

### Step 5: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit environment file
nano .env

# Set secure permissions
chmod 600 .env
```

**Required Environment Variables**:
- `DATABASE_URL` - PostgreSQL connection string with SSL
- `JWT_SECRET_KEY` - Generated secure key (32+ chars)
- `ENCRYPTION_KEY` - Generated secure key (32 chars)
- `ENVIRONMENT=production`
- `DEBUG=false`
- `REQUIRE_AUTH=true`
- `CORS_ORIGINS` - Production domain(s), no wildcards
- `SENTRY_DSN` - Sentry error tracking DSN (optional but recommended)
- `REDIS_HOST` and `REDIS_PORT`
- `CELERY_BROKER_URL` - Redis URL with password
- `CELERY_RESULT_BACKEND` - Redis URL with password

### Step 6: Database Setup

```bash
# Create database (if not exists)
sudo -u postgres psql << EOF
CREATE DATABASE marb_risk_engine;
CREATE USER marb_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE marb_risk_engine TO marb_user;
\q
EOF

# Run migrations
source venv/bin/activate
alembic upgrade head

# Verify tables created
psql $DATABASE_URL -c "\dt"
```

### Step 7: Test Application Load

```bash
# Test that application loads without errors
source venv/bin/activate
python -c "from app.main import app; print('✓ Application loads successfully')"

# Test database connection
python -c "from app.config.database import engine; conn = engine.connect(); conn.close(); print('✓ Database connection OK')"

# Test Redis connection
python -c "import redis; r = redis.from_url(os.getenv('CELERY_BROKER_URL')); r.ping(); print('✓ Redis connection OK')"
```

### Step 8: Set Up Systemd Services

```bash
# Use provided script or create manually
sudo bash deployment/systemd-services.sh

# Or create services manually (see deployment/DEPLOYMENT.md)

# Enable services
sudo systemctl daemon-reload
sudo systemctl enable marb2.0.service
sudo systemctl enable marb2.0-celery.service
```

### Step 9: Start Services

```bash
# Start services
sudo systemctl start marb2.0.service
sudo systemctl start marb2.0-celery.service

# Check status
sudo systemctl status marb2.0.service
sudo systemctl status marb2.0-celery.service

# Follow logs
sudo journalctl -u marb2.0.service -f
```

### Step 10: Configure nginx

```bash
# Copy nginx configuration
sudo cp deployment/nginx.conf.example /etc/nginx/sites-available/marb2.0

# Edit configuration
sudo nano /etc/nginx/sites-available/marb2.0
# Update: server_name, SSL certificate paths

# Enable site
sudo ln -s /etc/nginx/sites-available/marb2.0 /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### Step 11: SSL/TLS Setup

```bash
# Install Certbot (if using Let's Encrypt)
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d api.yourdomain.com

# Verify auto-renewal
sudo certbot renew --dry-run
```

### Step 12: Post-Deployment Verification

See [Health Check Procedures](#health-check-procedures) for detailed verification steps.

---

## Update/Upgrade Procedure

### Standard Update (No Breaking Changes)

**Estimated Time**: 15-30 minutes

```bash
# 1. SSH into server
ssh user@production-server
sudo su - marb
cd /opt/marb2.0

# 2. Create backup (see Backup Procedure)
./scripts/backup_db.sh

# 3. Pull latest code
git fetch origin
git checkout main  # or production branch
git pull origin main

# 4. Activate virtual environment
source venv/bin/activate

# 5. Update dependencies (if requirements.txt changed)
pip install -r requirements.txt

# 6. Run database migrations
alembic upgrade head

# 7. Restart services (zero-downtime with multiple workers)
sudo systemctl restart marb2.0.service
sudo systemctl restart marb2.0-celery.service

# 8. Verify services are running
sudo systemctl status marb2.0.service
sudo systemctl status marb2.0-celery.service

# 9. Health check
curl https://api.yourdomain.com/api/v1/health

# 10. Monitor logs for errors
sudo journalctl -u marb2.0.service -f --since "5 minutes ago"
```

### Update with Breaking Changes

**Estimated Time**: 30-60 minutes (may require maintenance window)

1. **Schedule Maintenance Window**: Notify users of downtime
2. **Review Migration Scripts**: Test migrations in staging first
3. **Follow Standard Update Procedure** (above)
4. **Extended Verification**: Run full health check suite
5. **Monitor Closely**: Watch logs and metrics for 30+ minutes

### Update with Database Schema Changes

```bash
# 1. Backup database (critical!)
./scripts/backup_db.sh

# 2. Review migration
alembic show head

# 3. Test migration on backup (if possible)
# Create test database from backup and test migration

# 4. Run migration
alembic upgrade head

# 5. Verify migration
psql $DATABASE_URL -c "\d table_name"  # Check specific tables

# 6. Restart services
sudo systemctl restart marb2.0.service
sudo systemctl restart marb2.0-celery.service
```

---

## Rollback Procedure

### Quick Rollback (Code Only, No DB Changes)

**Estimated Time**: 5-10 minutes

```bash
# 1. SSH into server
ssh user@production-server
sudo su - marb
cd /opt/marb2.0

# 2. Identify previous working commit
git log --oneline -10

# 3. Checkout previous commit
git checkout <previous-commit-hash>

# 4. Restart services
sudo systemctl restart marb2.0.service
sudo systemctl restart marb2.0-celery.service

# 5. Verify health
curl https://api.yourdomain.com/api/v1/health

# 6. Monitor logs
sudo journalctl -u marb2.0.service -f
```

### Rollback with Database Migration

**⚠️ WARNING**: This requires database migration rollback. Test in staging first!

**Estimated Time**: 30-60 minutes

```bash
# 1. Stop services
sudo systemctl stop marb2.0.service
sudo systemctl stop marb2.0-celery.service

# 2. Rollback database migration
cd /opt/marb2.0
source venv/bin/activate
alembic downgrade -1  # Or specific revision

# 3. Checkout previous code
git checkout <previous-commit-hash>

# 4. Restart services
sudo systemctl start marb2.0.service
sudo systemctl start marb2.0-celery.service

# 5. Verify health
curl https://api.yourdomain.com/api/v1/health

# 6. Full health check
# Run all health check procedures
```

### Emergency Rollback (Service Unavailable)

**Estimated Time**: 2-5 minutes

```bash
# 1. Quick code rollback
cd /opt/marb2.0
git checkout <last-known-good-commit>
sudo systemctl restart marb2.0.service
sudo systemctl restart marb2.0-celery.service

# 2. Verify basic functionality
curl https://api.yourdomain.com/api/v1/health

# 3. If still failing, check logs immediately
sudo journalctl -u marb2.0.service -n 50 --no-pager
```

---

## Health Check Procedures

### Quick Health Check (30 seconds)

```bash
# 1. Service status
sudo systemctl status marb2.0.service --no-pager
sudo systemctl status marb2.0-celery.service --no-pager

# 2. API health endpoint
curl -s https://api.yourdomain.com/api/v1/health | jq .

# Expected response:
# {
#   "status": "healthy",
#   "database": "connected",
#   "redis": "connected",
#   "version": "2.0.0"
# }
```

### Comprehensive Health Check (5 minutes)

```bash
# 1. Service Status
sudo systemctl is-active marb2.0.service
sudo systemctl is-active marb2.0-celery.service

# 2. API Endpoints
curl -I https://api.yourdomain.com/api/v1/health
curl -I https://api.yourdomain.com/docs
curl -I https://api.yourdomain.com/api/v1/claims

# 3. Database Connectivity
psql $DATABASE_URL -c "SELECT 1;"

# 4. Redis Connectivity
redis-cli -h $REDIS_HOST -p $REDIS_PORT ping

# 5. Check Recent Logs for Errors
sudo journalctl -u marb2.0.service --since "10 minutes ago" | grep -i error

# 6. Check Celery Tasks
# Visit Flower dashboard (if enabled): http://yourdomain.com:5555
# Or check Redis for pending tasks
redis-cli LLEN celery

# 7. Check Disk Space
df -h /opt/marb2.0

# 8. Check Memory Usage
free -h

# 9. Check Application Logs
tail -n 50 /opt/marb2.0/logs/app.log  # If file logging enabled
```

### Health Check Script

Create `/opt/marb2.0/scripts/health_check.sh`:

```bash
#!/bin/bash
set -e

echo "=== mARB 2.0 Health Check ==="
echo ""

# Service status
echo "1. Service Status:"
systemctl is-active marb2.0.service && echo "  ✓ API service running" || echo "  ✗ API service NOT running"
systemctl is-active marb2.0-celery.service && echo "  ✓ Celery service running" || echo "  ✗ Celery service NOT running"
echo ""

# API health
echo "2. API Health:"
HEALTH=$(curl -s https://api.yourdomain.com/api/v1/health)
echo "$HEALTH" | jq .
echo ""

# Database
echo "3. Database:"
psql $DATABASE_URL -c "SELECT 1;" > /dev/null && echo "  ✓ Database connected" || echo "  ✗ Database connection failed"
echo ""

# Redis
echo "4. Redis:"
redis-cli ping > /dev/null && echo "  ✓ Redis connected" || echo "  ✗ Redis connection failed"
echo ""

# Recent errors
echo "5. Recent Errors (last 10 minutes):"
ERROR_COUNT=$(journalctl -u marb2.0.service --since "10 minutes ago" | grep -i error | wc -l)
echo "  Found $ERROR_COUNT errors"
if [ $ERROR_COUNT -gt 0 ]; then
    journalctl -u marb2.0.service --since "10 minutes ago" | grep -i error | tail -5
fi
echo ""

echo "=== Health Check Complete ==="
```

Make executable:
```bash
chmod +x /opt/marb2.0/scripts/health_check.sh
```

---

## Common Issues & Solutions

### Issue 1: Service Won't Start

**Symptoms**: `systemctl status` shows "failed" or "inactive"

**Diagnosis**:
```bash
# Check service status
sudo systemctl status marb2.0.service -l --no-pager

# Check logs
sudo journalctl -u marb2.0.service -n 50 --no-pager
```

**Common Causes & Solutions**:

1. **Environment Variables Missing**
   ```bash
   # Check .env file exists and has correct permissions
   ls -la /opt/marb2.0/.env
   # Should be: -rw------- (600)
   
   # Verify variables are set
   source venv/bin/activate
   python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('DATABASE_URL'))"
   ```

2. **Database Connection Failed**
   ```bash
   # Test database connection
   psql $DATABASE_URL -c "SELECT 1;"
   
   # Check PostgreSQL is running
   sudo systemctl status postgresql
   ```

3. **Port Already in Use**
   ```bash
   # Check if port 8000 is in use
   sudo lsof -i :8000
   
   # Kill process if needed
   sudo kill -9 <PID>
   ```

4. **Python Import Errors**
   ```bash
   # Test imports
   source venv/bin/activate
   python -c "from app.main import app"
   
   # Reinstall dependencies if needed
   pip install -r requirements.txt
   ```

### Issue 2: Database Migration Failures

**Symptoms**: `alembic upgrade head` fails

**Diagnosis**:
```bash
# Check migration status
alembic current

# Check migration history
alembic history
```

**Solutions**:

1. **Migration Conflict**
   ```bash
   # Check current database state
   psql $DATABASE_URL -c "\d"
   
   # Manually resolve conflicts or rollback
   alembic downgrade -1
   alembic upgrade head
   ```

2. **Missing Migration**
   ```bash
   # Create new migration
   alembic revision --autogenerate -m "fix_migration"
   # Review and edit migration file
   alembic upgrade head
   ```

### Issue 3: High Memory Usage

**Symptoms**: System running out of memory, services killed

**Diagnosis**:
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head -10

# Check service memory
systemctl status marb2.0.service | grep Memory
```

**Solutions**:

1. **Reduce Worker Count**
   ```bash
   # Edit systemd service
   sudo nano /etc/systemd/system/marb2.0.service
   # Change: --workers 4 to --workers 2
   sudo systemctl daemon-reload
   sudo systemctl restart marb2.0.service
   ```

2. **Reduce Celery Concurrency**
   ```bash
   # Edit Celery service
   sudo nano /etc/systemd/system/marb2.0-celery.service
   # Change: --concurrency=4 to --concurrency=2
   sudo systemctl daemon-reload
   sudo systemctl restart marb2.0-celery.service
   ```

3. **Add Swap Space** (temporary solution)
   ```bash
   # Create 2GB swap file
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

### Issue 4: Celery Tasks Not Processing

**Symptoms**: Tasks queued but not executing

**Diagnosis**:
```bash
# Check Celery worker status
sudo systemctl status marb2.0-celery.service

# Check Redis for pending tasks
redis-cli LLEN celery

# Check Celery logs
sudo journalctl -u marb2.0-celery.service -n 50
```

**Solutions**:

1. **Restart Celery Worker**
   ```bash
   sudo systemctl restart marb2.0-celery.service
   ```

2. **Check Redis Connection**
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

3. **Clear Stuck Tasks** (use with caution)
   ```bash
   redis-cli FLUSHDB  # Clears entire Redis database
   # Or clear specific queue
   redis-cli DEL celery
   ```

### Issue 5: nginx 502 Bad Gateway

**Symptoms**: API returns 502 errors

**Diagnosis**:
```bash
# Check nginx error logs
sudo tail -f /var/log/nginx/marb2.0_error.log

# Check if API service is running
sudo systemctl status marb2.0.service

# Test API directly (bypassing nginx)
curl http://127.0.0.1:8000/api/v1/health
```

**Solutions**:

1. **API Service Not Running**
   ```bash
   sudo systemctl start marb2.0.service
   ```

2. **API Service Crashed**
   ```bash
   # Check logs for crash reason
   sudo journalctl -u marb2.0.service -n 100
   # Fix underlying issue, then restart
   sudo systemctl restart marb2.0.service
   ```

3. **Port Mismatch**
   ```bash
   # Verify nginx upstream matches service port
   grep "127.0.0.1:8000" /etc/nginx/sites-available/marb2.0
   # Should match ExecStart port in systemd service
   ```

---

## Emergency Procedures

### Service Completely Down

**Priority**: P0 - Critical

**Steps**:

1. **Immediate Assessment** (2 minutes)
   ```bash
   # Check all services
   sudo systemctl status marb2.0.service
   sudo systemctl status marb2.0-celery.service
   sudo systemctl status postgresql
   sudo systemctl status redis
   sudo systemctl status nginx
   ```

2. **Quick Restart** (5 minutes)
   ```bash
   # Restart all services
   sudo systemctl restart marb2.0.service
   sudo systemctl restart marb2.0-celery.service
   sudo systemctl restart nginx
   
   # Verify
   curl https://api.yourdomain.com/api/v1/health
   ```

3. **If Still Failing** (10 minutes)
   ```bash
   # Check logs
   sudo journalctl -u marb2.0.service -n 100 --no-pager
   
   # Rollback to last known good version
   cd /opt/marb2.0
   git log --oneline -5
   git checkout <last-good-commit>
   sudo systemctl restart marb2.0.service
   ```

### Database Corruption or Data Loss

**Priority**: P0 - Critical

**Steps**:

1. **Stop Services Immediately**
   ```bash
   sudo systemctl stop marb2.0.service
   sudo systemctl stop marb2.0-celery.service
   ```

2. **Assess Damage**
   ```bash
   # Check database
   psql $DATABASE_URL -c "\dt"  # List tables
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM claims;"  # Check data
   ```

3. **Restore from Backup**
   ```bash
   # Find latest backup
   ls -lt /opt/marb2.0/backups/
   
   # Restore database
   psql $DATABASE_URL < /opt/marb2.0/backups/db_backup_YYYYMMDD_HHMMSS.sql
   ```

4. **Verify and Restart**
   ```bash
   # Verify data
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM claims;"
   
   # Restart services
   sudo systemctl start marb2.0.service
   sudo systemctl start marb2.0-celery.service
   ```

### Security Breach

**Priority**: P0 - Critical

**Steps**:

1. **Immediate Actions**
   ```bash
   # Rotate all secrets immediately
   python generate_keys.py
   # Update .env with new keys
   
   # Revoke all JWT tokens (if token blacklist implemented)
   # Or restart services to invalidate sessions
   sudo systemctl restart marb2.0.service
   ```

2. **Assess Impact**
   - Review audit logs: `/opt/marb2.0/logs/`
   - Check database for unauthorized changes
   - Review nginx access logs for suspicious activity

3. **Containment**
   - Block suspicious IPs in firewall
   - Enable additional rate limiting
   - Review and update security settings

---

## Maintenance Windows

### Scheduled Maintenance Procedure

**Before Maintenance**:

1. Notify users 24-48 hours in advance
2. Schedule maintenance window (typically 2-4 hours)
3. Create database backup
4. Prepare rollback plan

**During Maintenance**:

1. **Put Application in Maintenance Mode** (optional)
   ```bash
   # Create maintenance page
   echo "Maintenance in progress" > /var/www/maintenance.html
   # Update nginx to serve maintenance page
   ```

2. **Stop Services**
   ```bash
   sudo systemctl stop marb2.0.service
   sudo systemctl stop marb2.0-celery.service
   ```

3. **Perform Updates**
   - Code updates
   - Database migrations
   - Configuration changes

4. **Verify Changes**
   - Run health checks
   - Test critical functionality

5. **Restart Services**
   ```bash
   sudo systemctl start marb2.0.service
   sudo systemctl start marb2.0-celery.service
   ```

6. **Post-Maintenance Verification**
   - Full health check
   - Monitor for 30+ minutes
   - Check error rates

**After Maintenance**:

1. Remove maintenance mode
2. Notify users maintenance complete
3. Monitor closely for 24 hours

---

## Backup Procedure

### Database Backup

```bash
# Manual backup
cd /opt/marb2.0
source venv/bin/activate
./scripts/backup_db.sh

# Or manually:
BACKUP_DIR="/opt/marb2.0/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
pg_dump $DATABASE_URL > $BACKUP_DIR/db_backup_$DATE.sql
gzip $BACKUP_DIR/db_backup_$DATE.sql
```

### Automated Backups

Backups should be configured via cron (see `deployment/DEPLOYMENT.md`).

### Backup Verification

```bash
# List backups
ls -lh /opt/marb2.0/backups/

# Test restore (on test database)
createdb test_restore
gunzip -c backups/db_backup_YYYYMMDD_HHMMSS.sql.gz | psql test_restore
```

---

## Contact & Escalation

### On-Call Rotation

- **Primary**: [Contact Info]
- **Secondary**: [Contact Info]
- **Escalation**: [Contact Info]

### External Resources

- **Sentry Dashboard**: [URL] (for error tracking)
- **Monitoring Dashboard**: [URL]
- **Documentation**: `/opt/marb2.0/README.md`

---

## Appendix: Quick Reference Commands

```bash
# Service Management
sudo systemctl status marb2.0.service
sudo systemctl restart marb2.0.service
sudo systemctl stop marb2.0.service
sudo systemctl start marb2.0.service

# Logs
sudo journalctl -u marb2.0.service -f
sudo journalctl -u marb2.0-celery.service -f
tail -f /opt/marb2.0/logs/app.log

# Database
alembic current
alembic upgrade head
alembic downgrade -1
psql $DATABASE_URL

# Health Checks
curl https://api.yourdomain.com/api/v1/health
./scripts/health_check.sh

# Git Operations
git pull origin main
git checkout <commit-hash>
git log --oneline -10
```

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Maintained By**: DevOps Team

