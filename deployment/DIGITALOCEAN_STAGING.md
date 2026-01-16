# DigitalOcean Staging Environment Setup

**Perfect for:** Proper staging/testing environment with full control

**Cost:** $5-6/month (very affordable)

**Time:** 2-3 hours (one-time setup)

---

## Prerequisites

- ✅ DigitalOcean account (you have this!)
- ✅ Domain or subdomain (optional - can use IP for testing)
- ✅ SSH access to server

---

## Step 1: Create Droplet

### Option A: New Droplet for Staging (Recommended)

1. Go to DigitalOcean dashboard
2. Click **"Create"** → **"Droplets"**
3. Configure:
   - **Image**: Ubuntu 22.04 LTS (or 20.04)
   - **Plan**: **Basic** → **Regular** → **$5/month** (1GB RAM) or **$6/month** (1GB RAM + 1 vCPU)
   - **Datacenter**: Choose closest to you
   - **Authentication**: SSH keys (recommended) or password
   - **Hostname**: `marb-staging` (or your preference)
4. Click **"Create Droplet"**

### Option B: Use Existing Droplet

If you already have a droplet, you can:
- Create a separate staging subdomain
- Or use a different port
- Or set up in a subdirectory

---

## Step 2: Initial Server Setup

SSH into your droplet:

```bash
ssh root@your-droplet-ip
```

### 2.1 Update System

```bash
apt update && apt upgrade -y
```

### 2.2 Install System Dependencies

```bash
apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    git \
    certbot \
    python3-certbot-nginx \
    ufw
```

### 2.3 Create Application User

```bash
useradd -m -s /bin/bash marb
usermod -aG sudo marb
```

### 2.4 Configure Firewall

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
ufw status
```

---

## Step 3: Set Up PostgreSQL

### 3.1 Create Database and User

```bash
sudo -u postgres psql
```

In PostgreSQL prompt:

```sql
CREATE DATABASE marb_risk_engine;
CREATE USER marb_user WITH PASSWORD 'your-secure-password-here';
GRANT ALL PRIVILEGES ON DATABASE marb_risk_engine TO marb_user;
\q
```

### 3.2 Configure PostgreSQL for Remote Access (if needed)

Edit `/etc/postgresql/14/main/postgresql.conf`:
```bash
sudo nano /etc/postgresql/14/main/postgresql.conf
```

Find and uncomment:
```
listen_addresses = 'localhost'
```

Edit `/etc/postgresql/14/main/pg_hba.conf`:
```bash
sudo nano /etc/postgresql/14/main/pg_hba.conf
```

Add:
```
host    marb_risk_engine    marb_user    127.0.0.1/32    md5
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

---

## Step 4: Set Up Redis

### 4.1 Configure Redis

Edit Redis config:
```bash
sudo nano /etc/redis/redis.conf
```

Find and set:
```
requirepass your-redis-password-here
```

Restart Redis:
```bash
sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

Test Redis:
```bash
redis-cli -a your-redis-password-here ping
# Should return: PONG
```

---

## Step 5: Deploy Application

### 5.1 Clone Repository

```bash
sudo -u marb git clone <your-repo-url> /opt/marb2.0
cd /opt/marb2.0
```

### 5.2 Create Virtual Environment

```bash
sudo -u marb python3.11 -m venv venv
sudo -u marb source venv/bin/activate
sudo -u marb pip install --upgrade pip
sudo -u marb pip install -r requirements.txt
```

### 5.3 Set Up Environment Variables

```bash
sudo -u marb cp .env.example .env
sudo -u marb nano .env
```

**Important variables to set:**
```bash
# Database
DATABASE_URL=postgresql://marb_user:your-password@localhost:5432/marb_risk_engine?sslmode=require

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password-here
CELERY_BROKER_URL=redis://:your-redis-password-here@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:your-redis-password-here@localhost:6379/0

# Security (use your generated keys)
JWT_SECRET_KEY=<your-generated-key>
ENCRYPTION_KEY=<your-generated-key>

# Environment
ENVIRONMENT=production
DEBUG=false
REQUIRE_AUTH=true

# CORS (update with your domain or IP)
CORS_ORIGINS=https://staging-api.yourdomain.com

# Logging
LOG_LEVEL=info
LOG_FORMAT=json
LOG_FILE=app.log
LOG_DIR=/opt/marb2.0/logs
```

Set secure permissions:
```bash
sudo chmod 600 /opt/marb2.0/.env
sudo chown marb:marb /opt/marb2.0/.env
```

### 5.4 Run Database Migrations

```bash
sudo -u marb source venv/bin/activate
sudo -u marb alembic upgrade head
```

### 5.5 Test Application

```bash
sudo -u marb source venv/bin/activate
sudo -u marb python -c "from app.main import app; print('App loads successfully')"
```

---

## Step 6: Set Up Systemd Services

### 6.1 Create Application Service

```bash
sudo nano /etc/systemd/system/marb2.0.service
```

Add:
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
EnvironmentFile=/opt/marb2.0/.env
ExecStart=/opt/marb2.0/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 6.2 Create Celery Worker Service

```bash
sudo nano /etc/systemd/system/marb2.0-celery.service
```

Add:
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
EnvironmentFile=/opt/marb2.0/.env
ExecStart=/opt/marb2.0/venv/bin/celery -A app.services.queue.tasks worker --loglevel=info --concurrency=2
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 6.3 Enable and Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable marb2.0.service
sudo systemctl enable marb2.0-celery.service
sudo systemctl start marb2.0.service
sudo systemctl start marb2.0-celery.service

# Check status
sudo systemctl status marb2.0.service
sudo systemctl status marb2.0-celery.service
```

---

## Step 7: Set Up nginx

### 7.1 Configure nginx

```bash
sudo cp /opt/marb2.0/deployment/nginx.conf.example /etc/nginx/sites-available/marb2.0
sudo nano /etc/nginx/sites-available/marb2.0
```

Update:
- `server_name`: Your domain or IP
- SSL certificate paths (we'll set up SSL next)

### 7.2 Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/marb2.0 /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Step 8: Set Up HTTPS with Let's Encrypt

### Option A: With Domain Name (Recommended)

If you have a domain/subdomain:

```bash
# Update DNS: Point staging-api.yourdomain.com to your droplet IP
# Wait for DNS propagation (5-60 minutes)

# Get SSL certificate
sudo certbot --nginx -d staging-api.yourdomain.com

# Certbot will automatically configure nginx
```

### Option B: Without Domain (IP Only - Limited HTTPS Testing)

If you only have an IP address:

1. You can test HTTP endpoints
2. For proper HTTPS, you'll need a domain
3. Consider using a free subdomain service or your existing domain

**Note:** Let's Encrypt requires a domain name, not just an IP.

---

## Step 9: Verify Deployment

### 9.1 Check Services

```bash
# Application
sudo systemctl status marb2.0.service

# Celery
sudo systemctl status marb2.0-celery.service

# nginx
sudo systemctl status nginx

# PostgreSQL
sudo systemctl status postgresql

# Redis
sudo systemctl status redis-server
```

### 9.2 Test Locally

```bash
# Test API (from server)
curl http://localhost:8000/api/v1/health

# Test through nginx
curl http://localhost/api/v1/health
```

### 9.3 Test from Your Local Machine

```bash
# Replace with your domain or IP
curl https://staging-api.yourdomain.com/api/v1/health
```

---

## Step 10: Run Production Validation

From your local machine:

```bash
# Test HTTPS
python scripts/test_https_end_to_end.py https://staging-api.yourdomain.com

# Monitor health
python scripts/monitor_health.py https://staging-api.yourdomain.com
```

---

## Quick Setup Script

I can create a setup script to automate most of this. Would you like me to create it?

---

## Troubleshooting

### Application Won't Start
```bash
# Check logs
sudo journalctl -u marb2.0.service -f

# Check environment
sudo -u marb source /opt/marb2.0/venv/bin/activate
sudo -u marb python -c "from app.main import app; print('OK')"
```

### Database Connection Issues
```bash
# Test connection
sudo -u postgres psql -c "\l"  # List databases
sudo -u postgres psql marb_risk_engine -c "SELECT 1;"
```

### Redis Connection Issues
```bash
# Test Redis
redis-cli -a your-password ping
```

### nginx Issues
```bash
# Check config
sudo nginx -t

# Check logs
sudo tail -f /var/log/nginx/error.log
```

---

## Cost Summary

- **Droplet**: $5-6/month
- **Domain**: Free (if you have one) or ~$10/year
- **SSL**: Free (Let's Encrypt)
- **Total**: ~$5-6/month for proper staging environment

---

## Next Steps

1. ✅ Set up droplet
2. ✅ Deploy application
3. ✅ Configure HTTPS
4. ✅ Run validation scripts
5. ✅ Mark production validation complete!

**Ready to start?** Let me know if you want help with any specific step!

