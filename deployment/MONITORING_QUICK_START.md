# Monitoring Dashboard Quick Start

Quick guide to set up monitoring dashboards for mARB 2.0.

## Prerequisites

- API server running
- Python virtual environment activated
- Required packages installed: `httpx requests` (for HTTPS testing)

## 1. Set Up Monitoring Dashboard (5 minutes)

### Automated Setup

```bash
# Activate virtual environment
source venv/bin/activate

# Run setup script
python scripts/setup_monitoring_dashboard.py

# Follow prompts to enter your API URL
# Default: http://localhost:8000 (development)
# Production: https://api.yourdomain.com
```

### Manual Setup

```bash
# Create monitoring directory
mkdir -p monitoring

# Run setup script
python scripts/setup_monitoring_dashboard.py https://api.yourdomain.com
```

## 2. Test Dashboard Locally

```bash
# Navigate to monitoring directory
cd monitoring

# Start simple HTTP server
python -m http.server 8080

# Open in browser
# http://localhost:8080/dashboard.html
```

## 3. Deploy Dashboard to Production

### Option A: Serve via nginx

Add to your nginx configuration:

```nginx
location /monitoring {
    alias /opt/marb2.0/monitoring;
    index dashboard.html;
    
    # Optional: Add authentication
    auth_basic "Monitoring Dashboard";
    auth_basic_user_file /etc/nginx/.htpasswd;
}
```

Then access at: `https://api.yourdomain.com/monitoring/dashboard.html`

### Option B: Serve via FastAPI (Development)

Add static file serving to your FastAPI app (not recommended for production):

```python
from fastapi.staticfiles import StaticFiles

app.mount("/monitoring", StaticFiles(directory="monitoring"), name="monitoring")
```

## 4. Set Up Additional Monitoring Tools

### Flower (Celery Queue Monitoring)

```bash
# Install Flower
pip install flower

# Start Flower
celery -A app.services.queue.tasks flower --port=5555

# Access at: http://localhost:5555
```

### Sentry (Error Tracking)

1. Sign up at https://sentry.io
2. Create project (Python/FastAPI)
3. Copy DSN
4. Add to `.env`:
   ```
   SENTRY_DSN=https://your-dsn@sentry.io/project-id
   SENTRY_ENVIRONMENT=production
   ```
5. See `SENTRY_SETUP_CHECKLIST.md` for details

## 5. Test HTTPS Setup (Production Only)

Once you have a production URL with HTTPS:

```bash
# Test HTTPS end-to-end
python scripts/test_https_end_to_end.py https://api.yourdomain.com

# Or set environment variable
export API_URL=https://api.yourdomain.com
python scripts/test_https_end_to_end.py
```

See `deployment/HTTPS_TESTING_GUIDE.md` for detailed information.

## 6. Set Up Automated Health Monitoring

### Using the Health Check Script

```bash
# Test health monitoring script
python scripts/monitor_health.py https://api.yourdomain.com

# Set up cron job (check every 5 minutes)
*/5 * * * * /opt/marb2.0/venv/bin/python /opt/marb2.0/scripts/monitor_health.py https://api.yourdomain.com >> /opt/marb2.0/logs/health_monitor.log 2>&1
```

## Monitoring Endpoints

Your API provides these monitoring endpoints:

- **Basic Health**: `GET /api/v1/health`
- **Detailed Health**: `GET /api/v1/health/detailed`
- **Cache Stats**: `GET /api/v1/cache/stats`
- **Audit Logs**: `GET /api/v1/audit-logs`
- **Audit Stats**: `GET /api/v1/audit-logs/stats`

## Dashboard Features

The monitoring dashboard displays:

- **System Health**: Overall status and version
- **Component Status**: Database, Redis, Celery worker status
- **Cache Performance**: Hit rate, hits, misses
- **Auto-refresh**: Updates every 30 seconds

## Troubleshooting

### Dashboard Not Loading

- Check API URL is correct
- Verify API is accessible
- Check browser console for errors
- Ensure CORS is configured if accessing from different domain

### Health Checks Failing

- Verify database connection
- Check Redis is running
- Ensure Celery worker is active
- Review application logs

### HTTPS Tests Failing

- Verify SSL certificate is installed
- Check nginx configuration
- Ensure port 443 is open
- Review `deployment/HTTPS_TESTING_GUIDE.md`

## Next Steps

1. **Set up Sentry**: Configure error tracking (see `SENTRY_SETUP_CHECKLIST.md`)
2. **Configure Flower**: Set up Celery queue monitoring
3. **Set up alerts**: Configure email/SMS alerts for critical issues
4. **Review logs**: Set up log aggregation (see `deployment/MONITORING_DASHBOARD_SETUP.md`)

## Related Documentation

- `deployment/MONITORING_DASHBOARD_SETUP.md` - Comprehensive monitoring guide
- `deployment/HTTPS_TESTING_GUIDE.md` - HTTPS testing guide
- `SENTRY_SETUP_CHECKLIST.md` - Sentry setup guide
- `scripts/monitor_health.py` - Health monitoring script
- `scripts/test_https_end_to_end.py` - HTTPS testing script

