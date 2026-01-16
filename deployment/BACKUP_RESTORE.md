# Backup and Restore Procedures

This document describes backup and restore procedures for mARB 2.0 production deployments.

## ⚠️ PREREQUISITES - READ FIRST

**Before using backup/restore scripts, ensure all prerequisites are met.**

### Required Dependencies
- ✅ PostgreSQL installed and running
- ✅ `pg_dump` command available (`which pg_dump`)
- ✅ `pg_restore` command available (`which pg_restore`)
- ✅ `gzip` / `gunzip` commands available
- ✅ Database user has backup/restore permissions
- ✅ Write permissions to backup directory
- ✅ Sufficient disk space (typically 10-50% of database size)

### Required Configuration
- ✅ `DATABASE_URL` environment variable set (or in `.env` file)
- ✅ Backup directory exists: `/opt/marb2.0/backups/`
- ✅ Database connection verified: `psql $DATABASE_URL -c "SELECT 1;"`

### Optional Dependencies
- `gpg` for encrypted backups (if using encryption)
- `aws-cli` for S3 uploads (if using S3)
- `scp` for remote server backups (if using remote storage)

**Verify dependencies before proceeding:**
```bash
# Check PostgreSQL tools
which pg_dump && echo "✓ pg_dump found" || echo "✗ pg_dump missing"
which pg_restore && echo "✓ pg_restore found" || echo "✗ pg_restore missing"

# Check compression tools
which gzip && echo "✓ gzip found" || echo "✗ gzip missing"

# Check database connection
psql $DATABASE_URL -c "SELECT 1;" && echo "✓ Database accessible" || echo "✗ Database connection failed"

# Check backup directory
test -w /opt/marb2.0/backups && echo "✓ Backup directory writable" || echo "✗ Backup directory not writable"
```

**See [DEPENDENCIES.md](../DEPENDENCIES.md) for complete dependency list and troubleshooting.**

---

## Table of Contents

1. [Backup Strategy](#backup-strategy)
2. [Database Backups](#database-backups)
3. [File System Backups](#file-system-backups)
4. [Backup Automation](#backup-automation)
5. [Restore Procedures](#restore-procedures)
6. [Backup Verification](#backup-verification)
7. [Disaster Recovery](#disaster-recovery)

---

## Backup Strategy

### Backup Types

1. **Full Database Backup**: Complete PostgreSQL database dump
2. **Incremental Backup**: Transaction logs (WAL archiving) - optional
3. **Configuration Backup**: Environment files, SSL certificates, nginx configs
4. **Application Code Backup**: Git repository (version controlled)

### Backup Frequency

- **Database**: Daily at 2:00 AM (configurable)
- **Configuration**: Weekly or after changes
- **Application Code**: Managed via Git (no separate backup needed)

### Retention Policy

- **Daily Backups**: Keep for 30 days
- **Weekly Backups**: Keep for 12 weeks
- **Monthly Backups**: Keep for 12 months
- **Yearly Backups**: Keep indefinitely (archive)

---

## Database Backups

### Manual Database Backup

```bash
#!/bin/bash
# Manual backup script

# Set variables
BACKUP_DIR="/opt/marb2.0/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="marb_risk_engine"
DB_USER="marb_user"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create backup
pg_dump -U $DB_USER -h localhost -F c -b -v -f "$BACKUP_DIR/db_backup_$DATE.dump" $DB_NAME

# Compress backup
gzip "$BACKUP_DIR/db_backup_$DATE.dump"

# Remove backups older than 30 days
find $BACKUP_DIR -name "db_backup_*.dump.gz" -mtime +30 -delete

echo "Backup completed: db_backup_$DATE.dump.gz"
```

### Automated Database Backup Script

**⚠️ PREREQUISITES**: See [Prerequisites](#-prerequisites---read-first) above.

**Dependencies**:
- PostgreSQL client tools (`pg_dump`)
- Environment variables loaded from `.env`
- Write permissions to backup directory

Create `/opt/marb2.0/scripts/backup_db.sh`:

```bash
#!/bin/bash
# Automated database backup script for mARB 2.0

set -e  # Exit on error

# Configuration
BACKUP_DIR="/opt/marb2.0/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="marb_risk_engine"
RETENTION_DAYS=30

# Load environment variables
if [ -f /opt/marb2.0/.env ]; then
    export $(cat /opt/marb2.0/.env | grep -v '^#' | xargs)
fi

# Create backup directory
mkdir -p $BACKUP_DIR

# Log backup start
echo "[$(date)] Starting database backup..."

# Create backup (custom format for flexibility)
pg_dump "$DATABASE_URL" \
    --format=custom \
    --verbose \
    --file="$BACKUP_DIR/db_backup_$DATE.dump" \
    2>&1 | tee "$BACKUP_DIR/backup_$DATE.log"

# Compress backup
echo "[$(date)] Compressing backup..."
gzip "$BACKUP_DIR/db_backup_$DATE.dump"

# Create backup metadata
cat > "$BACKUP_DIR/db_backup_$DATE.meta" << EOF
BACKUP_DATE=$DATE
BACKUP_FILE=db_backup_$DATE.dump.gz
BACKUP_SIZE=$(du -h "$BACKUP_DIR/db_backup_$DATE.dump.gz" | cut -f1)
DATABASE=$DB_NAME
HOSTNAME=$(hostname)
EOF

# Remove old backups
echo "[$(date)] Removing backups older than $RETENTION_DAYS days..."
find $BACKUP_DIR -name "db_backup_*.dump.gz" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "backup_*.log" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "db_backup_*.meta" -mtime +$RETENTION_DAYS -delete

# Log completion
echo "[$(date)] Backup completed: db_backup_$DATE.dump.gz"
echo "[$(date)] Backup size: $(du -h "$BACKUP_DIR/db_backup_$DATE.dump.gz" | cut -f1)"

# Optional: Send notification (email, Slack, etc.)
# /opt/marb2.0/scripts/notify_backup.sh "$BACKUP_DIR/db_backup_$DATE.dump.gz"
```

Make executable:
```bash
chmod +x /opt/marb2.0/scripts/backup_db.sh
```

### Backup with Encryption (Recommended for Production)

```bash
#!/bin/bash
# Encrypted backup script

BACKUP_DIR="/opt/marb2.0/backups"
DATE=$(date +%Y%m%d_%H%M%S)
ENCRYPTION_KEY_FILE="/opt/marb2.0/.backup_key"  # Store securely

# Create unencrypted backup
pg_dump "$DATABASE_URL" --format=custom --file="$BACKUP_DIR/db_backup_$DATE.dump"

# Encrypt backup
gpg --symmetric --cipher-algo AES256 \
    --output "$BACKUP_DIR/db_backup_$DATE.dump.gpg" \
    "$BACKUP_DIR/db_backup_$DATE.dump"

# Remove unencrypted backup
rm "$BACKUP_DIR/db_backup_$DATE.dump"

# Compress encrypted backup
gzip "$BACKUP_DIR/db_backup_$DATE.dump.gpg"

echo "Encrypted backup created: db_backup_$DATE.dump.gpg.gz"
```

---

## File System Backups

### Configuration Files Backup

```bash
#!/bin/bash
# Backup configuration files

BACKUP_DIR="/opt/marb2.0/backups/config"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup .env file (encrypted or with restricted permissions)
cp /opt/marb2.0/.env "$BACKUP_DIR/.env.backup_$DATE"
chmod 600 "$BACKUP_DIR/.env.backup_$DATE"

# Backup nginx configuration
sudo cp /etc/nginx/sites-available/marb2.0 "$BACKUP_DIR/nginx_marb2.0_$DATE"

# Backup systemd service files
sudo cp /etc/systemd/system/marb2.0.service "$BACKUP_DIR/marb2.0.service_$DATE"
sudo cp /etc/systemd/system/marb2.0-celery.service "$BACKUP_DIR/marb2.0-celery.service_$DATE"

# Backup SSL certificates (if not using Let's Encrypt)
# sudo cp -r /etc/ssl/certs/yourdomain.com* "$BACKUP_DIR/ssl_$DATE/"

# Create archive
tar -czf "$BACKUP_DIR/config_backup_$DATE.tar.gz" \
    "$BACKUP_DIR/.env.backup_$DATE" \
    "$BACKUP_DIR/nginx_marb2.0_$DATE" \
    "$BACKUP_DIR/marb2.0.service_$DATE" \
    "$BACKUP_DIR/marb2.0-celery.service_$DATE"

# Remove individual files
rm "$BACKUP_DIR/.env.backup_$DATE" \
   "$BACKUP_DIR/nginx_marb2.0_$DATE" \
   "$BACKUP_DIR/marb2.0.service_$DATE" \
   "$BACKUP_DIR/marb2.0-celery.service_$DATE"

echo "Configuration backup created: config_backup_$DATE.tar.gz"
```

---

## Backup Automation

### Cron Job Setup

```bash
# Edit crontab for application user
sudo -u marb crontab -e

# Add daily backup at 2:00 AM
0 2 * * * /opt/marb2.0/scripts/backup_db.sh >> /opt/marb2.0/logs/backup.log 2>&1

# Add weekly configuration backup (Sunday at 3:00 AM)
0 3 * * 0 /opt/marb2.0/scripts/backup_config.sh >> /opt/marb2.0/logs/backup.log 2>&1
```

### Systemd Timer (Alternative to Cron)

Create `/etc/systemd/system/marb2.0-backup.service`:

```ini
[Unit]
Description=mARB 2.0 Database Backup
After=network.target postgresql.service

[Service]
Type=oneshot
User=marb
Group=marb
WorkingDirectory=/opt/marb2.0
Environment="PATH=/opt/marb2.0/venv/bin"
EnvironmentFile=/opt/marb2.0/.env
ExecStart=/opt/marb2.0/scripts/backup_db.sh
StandardOutput=journal
StandardError=journal
```

Create `/etc/systemd/system/marb2.0-backup.timer`:

```ini
[Unit]
Description=Daily mARB 2.0 Database Backup
Requires=marb2.0-backup.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable timer:
```bash
sudo systemctl enable marb2.0-backup.timer
sudo systemctl start marb2.0-backup.timer
```

---

## Restore Procedures

### Full Database Restore

**⚠️ PREREQUISITES**:
- ✅ `pg_restore` command available
- ✅ `gunzip` command available (if backup is compressed)
- ✅ `gpg` command available (if backup is encrypted)
- ✅ Backup file exists and is readable
- ✅ Database user has restore permissions
- ✅ **Current database backup exists** (safety measure - script creates one)
- ✅ Alembic available for migrations

**⚠️ WARNING**: This will replace the current database. Ensure you have a backup of the current state.

```bash
#!/bin/bash
# Database restore script

set -e

BACKUP_FILE=$1
DB_NAME="marb_risk_engine"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.dump.gz>"
    exit 1
fi

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Decompress if needed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "Decompressing backup..."
    gunzip -c "$BACKUP_FILE" > "${BACKUP_FILE%.gz}"
    BACKUP_FILE="${BACKUP_FILE%.gz}"
fi

# Decrypt if needed
if [[ "$BACKUP_FILE" == *.gpg ]]; then
    echo "Decrypting backup..."
    gpg --decrypt "$BACKUP_FILE" > "${BACKUP_FILE%.gpg}"
    BACKUP_FILE="${BACKUP_FILE%.gpg}"
fi

# Stop application services
echo "Stopping application services..."
sudo systemctl stop marb2.0.service
sudo systemctl stop marb2.0-celery.service

# Create backup of current database (safety measure)
CURRENT_BACKUP="/opt/marb2.0/backups/pre_restore_$(date +%Y%m%d_%H%M%S).dump"
echo "Creating backup of current database..."
pg_dump "$DATABASE_URL" --format=custom --file="$CURRENT_BACKUP"

# Drop and recreate database (or restore to existing)
echo "Restoring database..."
pg_restore "$DATABASE_URL" \
    --clean \
    --if-exists \
    --verbose \
    "$BACKUP_FILE"

# Run migrations to ensure schema is up to date
echo "Running migrations..."
cd /opt/marb2.0
source venv/bin/activate
alembic upgrade head

# Restart services
echo "Restarting application services..."
sudo systemctl start marb2.0.service
sudo systemctl start marb2.0-celery.service

# Verify restore
echo "Verifying restore..."
sleep 5
curl -f http://localhost:8000/api/v1/health || echo "Warning: Health check failed"

echo "Restore completed!"
```

### Partial Restore (Specific Tables)

```bash
#!/bin/bash
# Restore specific tables

BACKUP_FILE=$1
TABLES="claims remittances episodes"  # Space-separated list

# Restore only specific tables
pg_restore "$DATABASE_URL" \
    --table=claims \
    --table=remittances \
    --table=episodes \
    --clean \
    --if-exists \
    "$BACKUP_FILE"
```

### Point-in-Time Recovery (If WAL Archiving Enabled)

```bash
# Restore to specific point in time
pg_basebackup -D /var/lib/postgresql/restore \
    --format=tar \
    --write-recovery-conf \
    --checkpoint=fast

# Edit recovery.conf to set recovery target time
echo "recovery_target_time = '2024-01-15 14:30:00'" >> /var/lib/postgresql/restore/recovery.conf

# Start PostgreSQL with restored data
```

---

## Backup Verification

### Verify Backup Integrity

```bash
#!/bin/bash
# Verify backup file integrity

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.dump.gz>"
    exit 1
fi

# Decompress if needed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "Decompressing for verification..."
    TEMP_FILE=$(mktemp)
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
    BACKUP_FILE="$TEMP_FILE"
    CLEANUP_TEMP=true
fi

# Verify backup format
echo "Verifying backup format..."
pg_restore --list "$BACKUP_FILE" > /dev/null

if [ $? -eq 0 ]; then
    echo "✓ Backup file is valid"
    
    # List contents
    echo "Backup contents:"
    pg_restore --list "$BACKUP_FILE" | head -20
    
    # Get backup size
    echo "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
else
    echo "✗ Backup file is corrupted or invalid"
    exit 1
fi

# Cleanup
if [ "$CLEANUP_TEMP" = true ]; then
    rm "$TEMP_FILE"
fi
```

### Test Restore on Staging

**Best Practice**: Periodically test restores on a staging environment.

```bash
# 1. Create staging database
createdb marb_risk_engine_staging

# 2. Restore backup to staging
pg_restore -d marb_risk_engine_staging /opt/marb2.0/backups/db_backup_YYYYMMDD_HHMMSS.dump.gz

# 3. Verify data
psql -d marb_risk_engine_staging -c "SELECT COUNT(*) FROM claims;"
psql -d marb_risk_engine_staging -c "SELECT COUNT(*) FROM remittances;"

# 4. Test application with restored data
# Update .env to point to staging database
# Start application and verify functionality
```

---

## Disaster Recovery

### Complete System Recovery

**Scenario**: Complete server failure, need to restore on new server.

#### Step 1: Server Setup
Follow initial deployment procedure (see `DEPLOYMENT.md`)

#### Step 2: Restore Database
```bash
# Copy backup to new server
scp /backup/location/db_backup_YYYYMMDD_HHMMSS.dump.gz user@new-server:/opt/marb2.0/backups/

# Restore database
./scripts/restore_db.sh /opt/marb2.0/backups/db_backup_YYYYMMDD_HHMMSS.dump.gz
```

#### Step 3: Restore Configuration
```bash
# Copy configuration backup
scp /backup/location/config_backup_YYYYMMDD.tar.gz user@new-server:/tmp/

# Extract and restore
cd /tmp
tar -xzf config_backup_YYYYMMDD.tar.gz
sudo cp nginx_marb2.0_* /etc/nginx/sites-available/marb2.0
sudo cp marb2.0.service_* /etc/systemd/system/marb2.0.service
sudo cp marb2.0-celery.service_* /etc/systemd/system/marb2.0-celery.service

# Restore .env (handle with care - contains secrets)
cp .env.backup_* /opt/marb2.0/.env
chmod 600 /opt/marb2.0/.env
```

#### Step 4: Restore SSL Certificates
```bash
# If using Let's Encrypt, re-run certbot
sudo certbot --nginx -d api.yourdomain.com

# If using custom certificates, restore from backup
sudo cp -r /backup/ssl/* /etc/ssl/certs/
sudo cp -r /backup/ssl/private/* /etc/ssl/private/
```

#### Step 5: Verify and Start Services
```bash
# Reload systemd
sudo systemctl daemon-reload

# Start services
sudo systemctl start marb2.0.service
sudo systemctl start marb2.0-celery.service
sudo systemctl reload nginx

# Verify
curl https://api.yourdomain.com/api/v1/health
```

### Recovery Time Objectives (RTO)

- **Database Restore**: 15-30 minutes
- **Full System Recovery**: 1-2 hours
- **Configuration Restore**: 10-15 minutes

### Recovery Point Objectives (RPO)

- **With Daily Backups**: Up to 24 hours of data loss
- **With WAL Archiving**: Near-zero data loss (minutes)

---

## Backup Storage

### Local Storage

- **Location**: `/opt/marb2.0/backups/`
- **Retention**: 30 days
- **Size**: ~100MB-1GB per backup (depends on database size)

### Remote Storage (Recommended)

#### Option 1: S3-Compatible Storage

```bash
#!/bin/bash
# Upload backup to S3

BACKUP_FILE=$1
S3_BUCKET="marb2.0-backups"
S3_PATH="database/$(date +%Y/%m)/"

# Upload using AWS CLI
aws s3 cp "$BACKUP_FILE" "s3://$S3_BUCKET/$S3_PATH"

# Set lifecycle policy to delete after 90 days
aws s3api put-object-tagging \
    --bucket "$S3_BUCKET" \
    --key "$S3_PATH$(basename $BACKUP_FILE)" \
    --tagging "TagSet=[{Key=RetentionDays,Value=90}]"
```

#### Option 2: Remote Server

```bash
#!/bin/bash
# Copy backup to remote server

BACKUP_FILE=$1
REMOTE_USER="backup"
REMOTE_HOST="backup-server.example.com"
REMOTE_PATH="/backups/marb2.0/"

scp "$BACKUP_FILE" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH"
```

#### Option 3: Cloud Storage (Google Cloud, Azure)

Similar to S3, use respective CLI tools.

---

## Monitoring and Alerts

### Backup Success/Failure Monitoring

```bash
#!/bin/bash
# Check backup status and send alerts

BACKUP_DIR="/opt/marb2.0/backups"
LATEST_BACKUP=$(ls -t $BACKUP_DIR/db_backup_*.dump.gz 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "ALERT: No backups found!"
    # Send alert (email, Slack, etc.)
    exit 1
fi

# Check backup age (should be less than 25 hours)
BACKUP_AGE=$(( $(date +%s) - $(stat -c %Y "$LATEST_BACKUP") ))
MAX_AGE=90000  # 25 hours in seconds

if [ $BACKUP_AGE -gt $MAX_AGE ]; then
    echo "ALERT: Latest backup is older than 25 hours!"
    # Send alert
    exit 1
fi

# Check backup size (should be reasonable)
BACKUP_SIZE=$(stat -c %s "$LATEST_BACKUP")
MIN_SIZE=1000000  # 1MB minimum

if [ $BACKUP_SIZE -lt $MIN_SIZE ]; then
    echo "ALERT: Backup file seems too small!"
    # Send alert
    exit 1
fi

echo "Backup status: OK"
```

### Integration with Monitoring Systems

- **Nagios/Icinga**: Check backup file existence and age
- **Prometheus**: Export backup metrics
- **Sentry**: Alert on backup failures
- **Custom Dashboard**: Display backup status

---

## Best Practices

1. **Test Restores Regularly**: Monthly restore tests on staging
2. **Encrypt Backups**: Especially for off-site storage
3. **Multiple Backup Locations**: Local + remote storage
4. **Document Procedures**: Keep this document updated
5. **Monitor Backup Success**: Automated alerts for failures
6. **Version Control**: Tag backups with application version
7. **Retention Policy**: Clear policy for backup retention
8. **Access Control**: Restrict backup file access (600 permissions)
9. **Regular Verification**: Verify backup integrity periodically
10. **Disaster Recovery Drills**: Practice full recovery annually

---

## Quick Reference

### Backup Commands

```bash
# Manual backup
./scripts/backup_db.sh

# Verify backup
./scripts/verify_backup.sh /opt/marb2.0/backups/db_backup_YYYYMMDD_HHMMSS.dump.gz

# List backups
ls -lh /opt/marb2.0/backups/

# Check backup age
find /opt/marb2.0/backups/ -name "db_backup_*.dump.gz" -mtime -1
```

### Restore Commands

```bash
# Full restore
./scripts/restore_db.sh /opt/marb2.0/backups/db_backup_YYYYMMDD_HHMMSS.dump.gz

# Restore specific table
pg_restore -d marb_risk_engine --table=claims backup.dump
```

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Maintained By**: DevOps Team

