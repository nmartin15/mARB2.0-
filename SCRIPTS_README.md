# Scripts and Tools Reference

This document provides a quick reference for all scripts and tools in mARB 2.0, including their dependencies and prerequisites.

## ⚠️ Before Running Any Script

**Always check dependencies first:**
```bash
./scripts/check_dependencies.sh
```

This will verify all required tools and packages are installed.

---

## Available Scripts

### `scripts/check_dependencies.sh`

**Purpose**: Verify all dependencies are installed before running other scripts.

**Prerequisites**: None (checks for everything else)

**Usage**:
```bash
./scripts/check_dependencies.sh
```

**Output**: Lists all dependencies with ✓ (found) or ✗ (missing)

**Exit Codes**:
- `0`: All dependencies satisfied (or only warnings)
- `1`: Missing required dependencies

---

### `scripts/verify_env.py`

**Purpose**: Validate environment variables in `.env` file.

**Prerequisites**:
- ✅ Python 3.11+
- ✅ `.env` file exists (or use `--env-file`)

**Dependencies**: None (uses only Python standard library)

**Usage**:
```bash
# Check default .env file
python scripts/verify_env.py

# Check specific file
python scripts/verify_env.py --env-file /path/to/.env

# Quiet mode (only errors/warnings)
python scripts/verify_env.py --quiet
```

**What it checks**:
- Required variables are set
- Secret lengths meet requirements
- URLs are valid format
- Boolean values are correct
- CORS origins don't have wildcards in production

---

### `scripts/validate_production_security.py`

**Purpose**: Validate production security settings.

**Prerequisites**:
- ✅ Python 3.11+
- ✅ `.env` file exists
- ✅ `scripts/setup_production_env.py` exists

**Dependencies**: `scripts/setup_production_env.py`

**Usage**:
```bash
python scripts/validate_production_security.py
```

**What it checks**:
- Default secrets are changed
- JWT_SECRET_KEY is secure (32+ chars)
- ENCRYPTION_KEY is secure (32 chars)
- DEBUG is false in production
- REQUIRE_AUTH is true in production
- CORS_ORIGINS doesn't contain wildcards

---

### `scripts/setup_production_env.py`

**Purpose**: Generate secure keys and set up production environment.

**Prerequisites**:
- ✅ Python 3.11+

**Dependencies**: None (uses only Python standard library)

**Usage**:
```bash
python scripts/setup_production_env.py
```

**What it does**:
- Generates secure JWT_SECRET_KEY
- Generates secure ENCRYPTION_KEY
- Validates environment settings
- Creates production-ready .env file

---

### `scripts/backup_db.sh`

**Purpose**: Create database backup.

**Prerequisites**:
- ✅ PostgreSQL installed
- ✅ `pg_dump` command available
- ✅ `DATABASE_URL` in `.env` file
- ✅ Write permissions to `/opt/marb2.0/backups/`

**Dependencies**:
- PostgreSQL client tools
- `gzip` for compression
- `find` for cleanup

**Usage**:
```bash
./scripts/backup_db.sh
```

**What it does**:
- Creates compressed database backup
- Stores in `/opt/marb2.0/backups/`
- Removes backups older than 30 days
- Creates backup metadata file

**Before using**:
1. Verify PostgreSQL: `which pg_dump`
2. Verify database connection: `psql $DATABASE_URL -c "SELECT 1;"`
3. Create backup directory: `mkdir -p /opt/marb2.0/backups`
4. Set permissions: `chmod 755 /opt/marb2.0/backups`

---

### `scripts/restore_db.sh`

**Purpose**: Restore database from backup.

**Prerequisites**:
- ✅ PostgreSQL installed
- ✅ `pg_restore` command available
- ✅ Backup file exists
- ✅ Database user has restore permissions
- ✅ **Current database backup exists** (safety)

**Dependencies**:
- PostgreSQL client tools
- `gunzip` (if backup is compressed)
- `gpg` (if backup is encrypted)
- Alembic for migrations

**Usage**:
```bash
./scripts/restore_db.sh /path/to/backup.dump.gz
```

**⚠️ WARNING**: This replaces the current database. Creates safety backup first.

**Before using**:
1. **CRITICAL**: Ensure you have a backup of current database
2. Verify backup file: `pg_restore --list backup.dump`
3. Stop application services
4. Ensure sufficient disk space

---

### `scripts/load_test_large_files.py`

**Purpose**: Load test the API with large EDI files (100MB+) to validate file-based processing and memory usage.

**Prerequisites**:
- ✅ Python 3.11+
- ✅ API server running
- ✅ Celery worker running
- ✅ Redis running (for Celery)
- ✅ Database accessible

**Dependencies**:
- `httpx` (for HTTP requests)
- `psutil` (for memory monitoring)
- `scripts/generate_large_edi_files.py` (for generating test files)

**Usage**:
```bash
# Test with 100MB files (default)
python scripts/load_test_large_files.py

# Test with specific file size
python scripts/load_test_large_files.py --file-size 150

# Test only 837 files
python scripts/load_test_large_files.py --file-type 837

# Test with custom API URL
python scripts/load_test_large_files.py --base-url http://localhost:8000

# Keep generated test files
python scripts/load_test_large_files.py --keep-files

# Set custom memory limit
python scripts/load_test_large_files.py --max-memory 3000
```

**What it does**:
- Generates large EDI files (100MB+ by default)
- Uploads files via API endpoints
- Monitors memory usage during processing
- Validates file-based processing path is used
- Checks memory usage stays within reasonable limits
- Provides detailed performance metrics

**Output**: Summary report with memory usage, processing times, and validation results

**See Also**: `tests/test_large_file_load.py` for pytest-based load tests

---

## Quick Reference

### Check Dependencies
```bash
./scripts/check_dependencies.sh
```

### Verify Environment
```bash
python scripts/verify_env.py
```

### Validate Security
```bash
python scripts/validate_production_security.py
```

### Create Backup
```bash
./scripts/backup_db.sh
```

### Restore Database
```bash
./scripts/restore_db.sh backups/db_backup_YYYYMMDD_HHMMSS.dump.gz
```

---

## Common Issues

### Script Not Executable
```bash
chmod +x scripts/backup_db.sh
```

### Missing Dependencies
See [DEPENDENCIES.md](DEPENDENCIES.md) for installation instructions.

### Permission Denied
```bash
# Check file permissions
ls -la scripts/

# Make executable
chmod +x scripts/*.sh
```

### Database Connection Failed
```bash
# Verify DATABASE_URL
grep DATABASE_URL .env

# Test connection
psql $DATABASE_URL -c "SELECT 1;"
```

---

## Script Development Guidelines

When creating new scripts:

1. **Add dependency checks** at the start
2. **Document prerequisites** in script header
3. **Use `set -e`** in bash scripts (exit on error)
4. **Provide clear error messages**
5. **Check for required files/tools** before using
6. **Update DEPENDENCIES.md** with new dependencies

Example script template:
```bash
#!/bin/bash
# Script description
# 
# PREREQUISITES:
# - Tool 1 installed
# - File X exists
# - Permission Y required
#
# DEPENDENCIES:
# - command1
# - command2

set -e

# Check dependencies
command -v command1 >/dev/null 2>&1 || { echo "Error: command1 not found"; exit 1; }

# Rest of script...
```

---

**Last Updated**: 2024  
**See Also**: [DEPENDENCIES.md](DEPENDENCIES.md) for complete dependency list

