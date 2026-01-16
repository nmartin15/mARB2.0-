# mARB 2.0 - Deployment Guide

This guide covers deploying mARB 2.0 to a production environment.

## Prerequisites

- Ubuntu 20.04+ or similar Linux distribution
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- nginx (for reverse proxy)
- SSL certificates (Let's Encrypt recommended)

## Step 1: Server Setup

### 1.1 Update System

```bash
sudo apt update
sudo apt upgrade -y
```

### 1.2 Install System Dependencies

```bash
sudo apt install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib redis-server nginx git
```

### 1.3 Create Application User

```bash
sudo useradd -m -s /bin/bash marb
sudo usermod -aG sudo marb
```

## Step 2: Application Setup

### 2.1 Clone Repository

```bash
sudo -u marb git clone <your-repo-url> /opt/marb2.0
cd /opt/marb2.0
```

### 2.2 Create Virtual Environment

```bash
sudo -u marb python3.11 -m venv venv
sudo -u marb source venv/bin/activate
sudo -u marb pip install --upgrade pip
sudo -u marb pip install -r requirements.txt
```

### 2.3 Generate Secure Keys

```bash
sudo -u marb python generate_keys.py
```

Copy the generated keys to your `.env` file.

### 2.4 Configure Environment

```bash
sudo -u marb cp .env.example .env
sudo -u marb nano .env  # Edit with your configuration
```

**Important settings:**
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET_KEY` - Use generated key
- `ENCRYPTION_KEY` - Use generated key
- `REQUIRE_AUTH=true` - Enable in production
- `CORS_ORIGINS` - Your production domain(s)
- `ENVIRONMENT=production`
- `DEBUG=false`

### 2.5 Set Up Database

```bash
# Create database
sudo -u postgres psql -c "CREATE DATABASE marb_risk_engine;"
sudo -u postgres psql -c "CREATE USER marb_user WITH PASSWORD 'secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE marb_risk_engine TO marb_user;"

# Run migrations
sudo -u marb source venv/bin/activate
sudo -u marb alembic upgrade head
```

### 2.6 Test Application

```bash
sudo -u marb source venv/bin/activate
sudo -u marb python -c "from app.main import app; print('App loads successfully')"
```

## Step 3: SSL/TLS Setup

### 3.1 Install Certbot (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 3.2 Obtain SSL Certificate

```bash
sudo certbot --nginx -d api.yourdomain.com
```

This will:
- Obtain SSL certificate
- Configure nginx automatically
- Set up auto-renewal

### 3.3 Manual Certificate Setup (Alternative)

If using your own certificates:

1. Place certificates in `/etc/ssl/certs/` and `/etc/ssl/private/`
2. Update nginx configuration with certificate paths
3. Ensure proper permissions:
   ```bash
   sudo chmod 644 /etc/ssl/certs/yourdomain.com.crt
   sudo chmod 600 /etc/ssl/private/yourdomain.com.key
   ```

## Step 4: nginx Configuration

### 4.1 Copy Configuration

```bash
sudo cp /opt/marb2.0/deployment/nginx.conf.example /etc/nginx/sites-available/marb2.0
sudo ln -s /etc/nginx/sites-available/marb2.0 /etc/nginx/sites-enabled/
```

### 4.2 Update Configuration

Edit `/etc/nginx/sites-available/marb2.0`:
- Replace `api.yourdomain.com` with your domain
- Update SSL certificate paths if not using Let's Encrypt

### 4.3 Test and Reload

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Step 5: Systemd Services

### 5.1 Create Application Service

Create `/etc/systemd/system/marb2.0.service`:

```ini
[Unit]
Description=mARB 2.0 API Server
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=marb
Group=marb
WorkingDirectory=/opt/marb2.0
Environment="PATH=/opt/marb2.0/venv/bin"
ExecStart=/opt/marb2.0/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5.2 Create Celery Worker Service

Create `/etc/systemd/system/marb2.0-celery.service`:

```ini
[Unit]
Description=mARB 2.0 Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=marb
Group=marb
WorkingDirectory=/opt/marb2.0
Environment="PATH=/opt/marb2.0/venv/bin"
ExecStart=/opt/marb2.0/venv/bin/celery -A app.services.queue.tasks worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5.3 Create Celery Beat Service (if needed)

Create `/etc/systemd/system/marb2.0-celery-beat.service`:

```ini
[Unit]
Description=mARB 2.0 Celery Beat
After=network.target redis.service

[Service]
Type=simple
User=marb
Group=marb
WorkingDirectory=/opt/marb2.0
Environment="PATH=/opt/marb2.0/venv/bin"
ExecStart=/opt/marb2.0/venv/bin/celery -A app.services.queue.tasks beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5.4 Enable and Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable marb2.0.service
sudo systemctl enable marb2.0-celery.service
sudo systemctl start marb2.0.service
sudo systemctl start marb2.0-celery.service
```

### 5.5 Check Status

```bash
sudo systemctl status marb2.0.service
sudo systemctl status marb2.0-celery.service
```

## Step 6: Log Rotation

### 6.1 Create Logrotate Configuration

Create `/etc/logrotate.d/marb2.0`:

```
/opt/marb2.0/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 marb marb
    sharedscripts
    postrotate
        systemctl reload marb2.0.service > /dev/null 2>&1 || true
    endscript
}
```

## Step 7: Firewall Configuration

### 7.1 Configure UFW

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp     # HTTP (for Let's Encrypt)
sudo ufw allow 443/tcp    # HTTPS
sudo ufw enable
```

## Step 8: Monitoring Setup

### 8.1 Install Flower (Celery Monitoring)

Flower is already in requirements.txt. To run it:

```bash
sudo -u marb source venv/bin/activate
sudo -u marb celery -A app.services.queue.tasks flower --port=5555
```

Or create a systemd service (see `deployment/flower.service.example`).

### 8.2 Health Checks

Set up monitoring to check:
- `/api/v1/health` endpoint
- Service status: `systemctl status marb2.0.service`
- Database connectivity
- Redis connectivity

## Step 9: Backup Configuration

### 9.1 Database Backups

Create `/opt/marb2.0/scripts/backup_db.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/marb2.0/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
pg_dump -U marb_user marb_risk_engine > $BACKUP_DIR/db_backup_$DATE.sql
# Keep only last 30 days
find $BACKUP_DIR -name "db_backup_*.sql" -mtime +30 -delete
```

Make executable:
```bash
chmod +x /opt/marb2.0/scripts/backup_db.sh
```

Add to crontab:
```bash
sudo -u marb crontab -e
# Add: 0 2 * * * /opt/marb2.0/scripts/backup_db.sh
```

## Step 10: Post-Deployment Verification

### 10.1 Test Endpoints

```bash
# Health check
curl https://api.yourdomain.com/api/v1/health

# API documentation
curl https://api.yourdomain.com/docs
```

### 10.2 Check Logs

```bash
# Application logs
sudo journalctl -u marb2.0.service -f

# Celery logs
sudo journalctl -u marb2.0-celery.service -f

# nginx logs
sudo tail -f /var/log/nginx/marb2.0_access.log
sudo tail -f /var/log/nginx/marb2.0_error.log
```

### 10.3 Verify Security

- [ ] HTTPS is working (check browser)
- [ ] Rate limiting is active (check headers)
- [ ] Authentication is enforced (if enabled)
- [ ] CORS is configured correctly
- [ ] SSL certificate is valid

## Maintenance

### Updating Application

```bash
cd /opt/marb2.0
sudo -u marb git pull
sudo -u marb source venv/bin/activate
sudo -u marb pip install -r requirements.txt
sudo -u marb alembic upgrade head
sudo systemctl restart marb2.0.service
sudo systemctl restart marb2.0-celery.service
```

### Viewing Logs

```bash
# Application
sudo journalctl -u marb2.0.service -n 100

# Celery
sudo journalctl -u marb2.0-celery.service -n 100

# nginx
sudo tail -f /var/log/nginx/marb2.0_access.log
```

### Restarting Services

```bash
sudo systemctl restart marb2.0.service
sudo systemctl restart marb2.0-celery.service
sudo systemctl reload nginx
```

## Troubleshooting

### Service Won't Start

1. Check logs: `sudo journalctl -u marb2.0.service -n 50`
2. Verify environment variables in `.env`
3. Check database connectivity
4. Verify file permissions

### Database Connection Issues

1. Verify PostgreSQL is running: `sudo systemctl status postgresql`
2. Check connection string in `.env`
3. Verify user permissions: `sudo -u postgres psql -c "\du"`

### Redis Connection Issues

1. Verify Redis is running: `sudo systemctl status redis`
2. Check Redis connection in `.env`
3. Test connection: `redis-cli ping`

### nginx Issues

1. Test configuration: `sudo nginx -t`
2. Check error logs: `sudo tail -f /var/log/nginx/error.log`
3. Verify SSL certificates are valid

## Security Checklist

Before going live, verify:

- [ ] All default secrets changed
- [ ] `REQUIRE_AUTH=true` is set
- [ ] CORS origins configured correctly
- [ ] HTTPS/TLS is working
- [ ] Firewall is configured
- [ ] Log rotation is set up
- [ ] Backups are configured
- [ ] Monitoring is in place
- [ ] SSL certificate auto-renewal is working

## Support

For issues or questions:
- Check logs first
- Review `SECURITY.md` for security concerns
- Check `TODO.md` for known issues
- Review application logs in `/opt/marb2.0/logs/`

