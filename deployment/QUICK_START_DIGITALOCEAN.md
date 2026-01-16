# Quick Start: DigitalOcean Staging Setup

**Time:** ~30-45 minutes  
**Cost:** $5-6/month  
**Result:** Fully deployed staging environment

---

## Prerequisites

- ✅ DigitalOcean account
- ✅ SSH key added to DigitalOcean
- ✅ Repository URL (GitHub/GitLab/etc.)

---

## Step 1: Create New Droplet

1. Go to DigitalOcean dashboard
2. Click **"Create"** → **"Droplets"**
3. Configure:
   - **Image**: Ubuntu 22.04 LTS
   - **Plan**: Basic → Regular → **$5/month** (1GB RAM) or **$6/month** (1GB RAM + 1 vCPU)
   - **Datacenter**: Choose closest
   - **Authentication**: SSH keys (recommended)
   - **Hostname**: `marb-staging`
4. Click **"Create Droplet"**
5. Wait for droplet to be created
6. **Copy the IP address**

---

## Step 2: Initial Server Setup

SSH into your new droplet:

```bash
ssh root@YOUR_DROPLET_IP
```

Once connected, run the setup script:

```bash
# Clone repository (if you have it)
# Or download the setup script directly
wget https://raw.githubusercontent.com/YOUR_USERNAME/mARB-2.0/main/deployment/setup_droplet.sh
# OR if you've already cloned locally, upload it:
# scp deployment/setup_droplet.sh root@YOUR_DROPLET_IP:/root/

# Make executable and run
chmod +x setup_droplet.sh
sudo bash setup_droplet.sh
```

**This will:**
- Update system packages
- Install all dependencies (Python, PostgreSQL, Redis, nginx)
- Create application user
- Configure firewall
- Set up PostgreSQL database
- Set up Redis
- Generate secure passwords

**⚠️ IMPORTANT:** Save the passwords that are displayed! You'll need them for the `.env` file.

---

## Step 3: Clone Repository

On the droplet, clone your repository:

```bash
# As the marb user
sudo -u marb git clone <YOUR_REPO_URL> /opt/marb2.0
```

Or if you need to upload manually:

```bash
# From your local machine
scp -r /path/to/mARB\ 2.0 root@YOUR_DROPLET_IP:/opt/marb2.0
chown -R marb:marb /opt/marb2.0
```

---

## Step 4: Deploy Application

On the droplet:

```bash
cd /opt/marb2.0
sudo bash deployment/deploy_app.sh
```

**This will:**
- Create Python virtual environment
- Install dependencies
- Set up `.env` file
- Generate secure keys
- Run database migrations
- Create systemd services
- Configure nginx
- Start services

---

## Step 5: Configure Environment Variables

Edit the `.env` file with the passwords from Step 2:

```bash
sudo -u marb nano /opt/marb2.0/.env
```

**Update these values:**
```bash
# Database (use password from Step 2)
DATABASE_URL=postgresql://marb_user:YOUR_DB_PASSWORD@localhost:5432/marb_risk_engine?sslmode=require

# Redis (use password from Step 2)
REDIS_PASSWORD=YOUR_REDIS_PASSWORD
CELERY_BROKER_URL=redis://:YOUR_REDIS_PASSWORD@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:YOUR_REDIS_PASSWORD@localhost:6379/0

# Security (use keys from Step 4 output)
JWT_SECRET_KEY=<from generate_keys.py output>
ENCRYPTION_KEY=<from generate_keys.py output>

# Environment
ENVIRONMENT=production
DEBUG=false
REQUIRE_AUTH=true

# CORS (use your droplet IP)
CORS_ORIGINS=http://YOUR_DROPLET_IP

# Logging
LOG_LEVEL=info
LOG_FORMAT=json
LOG_FILE=app.log
```

**Restart services after updating .env:**
```bash
sudo systemctl restart marb2.0.service
sudo systemctl restart marb2.0-celery.service
```

---

## Step 6: Test Deployment

### On the Server

```bash
# Test health endpoint
curl http://localhost:8000/api/v1/health

# Test through nginx
curl http://localhost/api/v1/health
```

### From Your Local Machine

```bash
# Replace with your droplet IP
curl http://YOUR_DROPLET_IP/api/v1/health

# Run validation scripts
python scripts/test_https_end_to_end.py http://YOUR_DROPLET_IP
python scripts/monitor_health.py http://YOUR_DROPLET_IP
```

**Note:** HTTPS testing will be limited without a domain. HTTP testing will work fine.

---

## Step 7: Set Up HTTPS (Optional - Requires Domain)

If you have a domain:

1. Point DNS A record to your droplet IP:
   ```
   staging-api.yourdomain.com → YOUR_DROPLET_IP
   ```

2. Wait for DNS propagation (5-60 minutes)

3. Get SSL certificate:
   ```bash
   sudo certbot --nginx -d staging-api.yourdomain.com
   ```

4. Update `.env`:
   ```bash
   CORS_ORIGINS=https://staging-api.yourdomain.com
   ```

5. Restart services:
   ```bash
   sudo systemctl restart marb2.0.service
   ```

6. Test HTTPS:
   ```bash
   python scripts/test_https_end_to_end.py https://staging-api.yourdomain.com
   ```

---

## Troubleshooting

### Application Won't Start

```bash
# Check logs
sudo journalctl -u marb2.0.service -n 50

# Check if .env is configured correctly
sudo -u marb cat /opt/marb2.0/.env | grep -v "^#"

# Test application import
sudo -u marb /opt/marb2.0/venv/bin/python -c "from app.main import app; print('OK')"
```

### Database Connection Issues

```bash
# Test PostgreSQL
sudo -u postgres psql -c "\l"  # List databases
sudo -u postgres psql marb_risk_engine -c "SELECT 1;"

# Check .env DATABASE_URL
sudo -u marb grep DATABASE_URL /opt/marb2.0/.env
```

### Redis Connection Issues

```bash
# Test Redis
redis-cli -a YOUR_REDIS_PASSWORD ping

# Check Redis is running
sudo systemctl status redis-server
```

### nginx Issues

```bash
# Check config
sudo nginx -t

# Check logs
sudo tail -f /var/log/nginx/error.log

# Check if nginx is running
sudo systemctl status nginx
```

---

## Service Management

```bash
# Check status
sudo systemctl status marb2.0.service
sudo systemctl status marb2.0-celery.service

# View logs
sudo journalctl -u marb2.0.service -f
sudo journalctl -u marb2.0-celery.service -f

# Restart services
sudo systemctl restart marb2.0.service
sudo systemctl restart marb2.0-celery.service

# Stop services
sudo systemctl stop marb2.0.service
sudo systemctl stop marb2.0-celery.service
```

---

## Next Steps

1. ✅ Deploy to droplet
2. ✅ Test HTTP endpoints
3. ✅ Run validation scripts
4. ⏳ Set up domain + HTTPS (optional)
5. ✅ Mark production validation complete!

---

## Quick Reference

**Server IP:** `YOUR_DROPLET_IP`  
**App Directory:** `/opt/marb2.0`  
**App User:** `marb`  
**Health Endpoint:** `http://YOUR_DROPLET_IP/api/v1/health`

**Scripts:**
- `deployment/setup_droplet.sh` - Initial server setup
- `deployment/deploy_app.sh` - Application deployment
- `deployment/systemd-services.sh` - Service file creation

