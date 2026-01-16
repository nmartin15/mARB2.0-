# Dependencies and Prerequisites

This document lists all dependencies and prerequisites for mARB 2.0, organized by component and use case.

## ⚠️ Important: Read Before Using Scripts

**Before running any scripts or following deployment procedures, ensure all prerequisites are met. Scripts will fail if dependencies are missing.**

---

## Core Application Dependencies

### Required System Packages

- **Python**: 3.11+ (tested with 3.11, 3.12)
- **PostgreSQL**: 14+ (tested with 14, 15, 16)
- **Redis**: 7+ (tested with 7.0+)
- **Git**: For version control and deployment

### Python Dependencies

All Python dependencies are listed in `requirements.txt`. Install with:
```bash
pip install -r requirements.txt
```

**Key Dependencies**:
- `fastapi==0.104.1` - Web framework
- `sqlalchemy==2.0.23` - ORM
- `alembic==1.12.1` - Database migrations
- `celery==5.3.4` - Task queue
- `redis==5.0.1` - Redis client
- `sentry-sdk[fastapi]==1.38.0` - Error tracking (optional but recommended)
- `pydantic==2.5.0` - Data validation
- `structlog==23.2.0` - Structured logging

### Database Dependencies

- **PostgreSQL client tools**: `psql`, `pg_dump`, `pg_restore`
  - Usually included with PostgreSQL installation
  - Verify: `which pg_dump`

### System Tools

- **bash**: For shell scripts (version 4.0+)
- **gzip**: For backup compression
- **find**: For backup cleanup
- **cron** or **systemd**: For scheduled tasks

---

## Script Dependencies

### `scripts/verify_env.py`

**Prerequisites**:
- ✅ Python 3.11+
- ✅ `.env` file exists (or specify with `--env-file`)
- ✅ Standard library only (no external dependencies)

**What it does**: Validates environment variable format and values

**Dependencies**: None (uses only Python standard library)

---

### `scripts/validate_production_security.py`

**Prerequisites**:
- ✅ Python 3.11+
- ✅ `.env` file exists
- ✅ `scripts/setup_production_env.py` exists (imported dependency)

**What it does**: Validates production security settings

**Dependencies**:
- `scripts/setup_production_env.py` (must exist in same directory)

---

### `scripts/setup_production_env.py`

**Prerequisites**:
- ✅ Python 3.11+
- ✅ Standard library only

**What it does**: Generates secure keys and validates environment

**Dependencies**: None (uses only Python standard library)

---

### Backup Scripts (`scripts/backup_db.sh`)

**Prerequisites**:
- ✅ PostgreSQL installed and running
- ✅ `pg_dump` command available
- ✅ `gzip` command available
- ✅ `find` command available
- ✅ `DATABASE_URL` environment variable set (or in `.env` file)
- ✅ Write permissions to `/opt/marb2.0/backups/` directory
- ✅ Database user has backup permissions

**What it does**: Creates database backups

**Dependencies**:
- PostgreSQL client tools (`pg_dump`)
- System utilities (`gzip`, `find`, `date`)
- Environment variables loaded from `.env` file

**Before using**:
1. Verify PostgreSQL is installed: `which pg_dump`
2. Verify database connection: `psql $DATABASE_URL -c "SELECT 1;"`
3. Create backup directory: `mkdir -p /opt/marb2.0/backups`
4. Set permissions: `chmod 755 /opt/marb2.0/backups`

---

### Restore Scripts (`scripts/restore_db.sh`)

**Prerequisites**:
- ✅ PostgreSQL installed and running
- ✅ `pg_restore` command available
- ✅ `gunzip` command available (if backup is compressed)
- ✅ `gpg` command available (if backup is encrypted)
- ✅ Backup file exists and is readable
- ✅ Database user has restore permissions
- ✅ **Current database backup exists** (safety measure)

**What it does**: Restores database from backup

**Dependencies**:
- PostgreSQL client tools (`pg_restore`, `pg_dump`)
- System utilities (`gunzip`, `gpg` if encrypted)
- Alembic for migrations (`alembic upgrade head`)

**Before using**:
1. **CRITICAL**: Create backup of current database first
2. Verify backup file integrity: `pg_restore --list backup.dump`
3. Ensure sufficient disk space for restore
4. Stop application services before restore
5. Verify Alembic is available: `which alembic`

---

## Deployment Dependencies

### Initial Deployment

**Prerequisites**:
- ✅ Ubuntu 20.04+ or similar Linux distribution
- ✅ Root or sudo access
- ✅ Internet connection for package installation
- ✅ Domain name configured (for SSL)
- ✅ DNS records pointing to server

**System Packages Required**:
```bash
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    git \
    certbot \
    python3-certbot-nginx
```

**Before deployment**:
1. Verify all system packages are installed
2. Verify PostgreSQL is running: `sudo systemctl status postgresql`
3. Verify Redis is running: `sudo systemctl status redis`
4. Verify nginx is installed: `nginx -v`

---

### Deployment Runbook (`deployment/DEPLOYMENT_RUNBOOK.md`)

**Prerequisites**:
- ✅ All initial deployment prerequisites met
- ✅ Application code deployed to `/opt/marb2.0`
- ✅ Virtual environment created and dependencies installed
- ✅ Database created and migrations run
- ✅ Environment variables configured
- ✅ SSL certificates obtained (for HTTPS)

**Dependencies**:
- See [Initial Deployment](#initial-deployment) above
- Systemd services configured
- nginx configured
- Application user (`marb`) created

---

## Testing Dependencies

### Unit Tests (`tests/test_*.py`)

**Prerequisites**:
- ✅ Python 3.11+
- ✅ All dependencies from `requirements.txt` installed
- ✅ `pytest` installed: `pip install pytest pytest-asyncio`
- ✅ Test database configured (or use in-memory SQLite)
- ✅ Redis available (or mocked)

**Test-Specific Dependencies**:
- `pytest==7.4.3`
- `pytest-asyncio==0.21.1`
- `pytest-cov==4.1.0`
- `pytest-mock==3.12.0`
- `factory-boy==3.3.0` (for test data factories)
- `faker==20.1.0` (for fake data generation)

**Before running tests**:
1. Install test dependencies: `pip install -r requirements.txt`
2. Verify pytest: `pytest --version`
3. Check test database connection (if using real DB)

---

### Edge Case Tests (`tests/test_edge_cases.py`)

**Prerequisites**:
- ✅ All unit test prerequisites
- ✅ Test factories available (`tests/factories.py`)
- ✅ Test fixtures available (`tests/conftest.py`)
- ✅ Database models accessible

**Dependencies**:
- All dependencies from [Unit Tests](#unit-tests)
- `tests/factories.py` (must exist)
- `tests/conftest.py` (must exist)
- Database session fixture

**Before running**:
1. Verify factories exist: `ls tests/factories.py`
2. Verify conftest exists: `ls tests/conftest.py`
3. Run basic test first: `pytest tests/test_health_api.py -v`

---

## Monitoring Dependencies

### Sentry Error Tracking

**Prerequisites**:
- ✅ `sentry-sdk[fastapi]==1.38.0` installed
- ✅ Sentry account created
- ✅ `SENTRY_DSN` environment variable set

**Dependencies**:
- Sentry account (free tier available)
- Internet connection for error reporting

**Before using**:
1. Sign up at https://sentry.io
2. Create project and get DSN
3. Add `SENTRY_DSN` to `.env` file

---

### Flower (Celery Monitoring)

**Prerequisites**:
- ✅ `flower==2.0.1` installed (in requirements.txt)
- ✅ Celery broker accessible
- ✅ Port 5555 available (or configure different port)

**Dependencies**:
- Redis running (Celery broker)
- Network access to Flower dashboard

---

## Backup/Restore Dependencies

### Database Backups

**Prerequisites**:
- ✅ PostgreSQL installed
- ✅ `pg_dump` command available
- ✅ Database user has backup permissions
- ✅ Sufficient disk space (typically 10-50% of database size)
- ✅ Write permissions to backup directory

**Optional Dependencies**:
- `gpg` for encrypted backups
- `aws-cli` for S3 uploads
- `scp` for remote server backups

---

### Backup Automation

**Prerequisites**:
- ✅ Backup script exists and is executable
- ✅ Cron or systemd timer configured
- ✅ Log directory exists: `/opt/marb2.0/logs/`
- ✅ Backup directory exists: `/opt/marb2.0/backups/`

**Dependencies**:
- `cron` service running OR
- `systemd` with timer support

---

## Missing Dependencies: Common Issues

### Issue: `pg_dump: command not found`

**Solution**:
```bash
# Ubuntu/Debian
sudo apt install postgresql-client

# macOS
brew install postgresql

# Verify
which pg_dump
```

---

### Issue: `alembic: command not found`

**Solution**:
```bash
# Activate virtual environment
source venv/bin/activate

# Verify
which alembic

# If missing, reinstall
pip install alembic
```

---

### Issue: `redis-cli: command not found`

**Solution**:
```bash
# Ubuntu/Debian
sudo apt install redis-tools

# macOS
brew install redis

# Verify
redis-cli ping
```

---

### Issue: Script fails with "Permission denied"

**Solution**:
```bash
# Make script executable
chmod +x scripts/backup_db.sh

# Check directory permissions
ls -la /opt/marb2.0/backups/

# Fix permissions if needed
chmod 755 /opt/marb2.0/backups
```

---

### Issue: Test factories not found

**Solution**:
```bash
# Verify factories exist
ls tests/factories.py

# If missing, check if tests are complete
# Some tests may depend on factories that need to be created
```

---

## Dependency Verification Checklist

Before running any script or procedure, verify:

### For Scripts
- [ ] Required command-line tools installed (`which <command>`)
- [ ] Python version correct (`python --version`)
- [ ] Virtual environment activated (if needed)
- [ ] Required files exist (`.env`, scripts, etc.)
- [ ] Permissions correct (scripts executable, directories writable)

### For Deployment
- [ ] All system packages installed
- [ ] Services running (PostgreSQL, Redis, nginx)
- [ ] Database created and accessible
- [ ] Environment variables configured
- [ ] SSL certificates obtained (for production)

### For Testing
- [ ] Test dependencies installed
- [ ] Test database configured
- [ ] Test fixtures available
- [ ] Redis available (or mocked)

### For Backups
- [ ] PostgreSQL tools available
- [ ] Backup directory exists and is writable
- [ ] Database connection works
- [ ] Sufficient disk space

---

## Quick Dependency Check Script

Create `scripts/check_dependencies.sh`:

```bash
#!/bin/bash
# Quick dependency check

echo "Checking dependencies..."

# Python
python --version || echo "✗ Python not found"

# PostgreSQL
pg_dump --version || echo "✗ pg_dump not found"
psql --version || echo "✗ psql not found"

# Redis
redis-cli --version || echo "✗ redis-cli not found"

# System tools
which gzip || echo "✗ gzip not found"
which find || echo "✗ find not found"

# Python packages (if venv activated)
if [ -n "$VIRTUAL_ENV" ]; then
    python -c "import fastapi" || echo "✗ fastapi not installed"
    python -c "import sqlalchemy" || echo "✗ sqlalchemy not installed"
    python -c "import alembic" || echo "✗ alembic not installed"
fi

echo "Dependency check complete"
```

---

## Version Compatibility

### Tested Versions

- **Python**: 3.11.0, 3.11.5, 3.12.0
- **PostgreSQL**: 14.9, 15.4, 16.0
- **Redis**: 7.0.0, 7.2.0
- **Ubuntu**: 20.04, 22.04
- **macOS**: 13.x, 14.x

### Known Incompatibilities

- Python < 3.11: Not supported (uses 3.11+ features)
- PostgreSQL < 14: May work but not tested
- Redis < 7: May work but not tested

---

**Last Updated**: 2024  
**Maintained By**: Development Team

