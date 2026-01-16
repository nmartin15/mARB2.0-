# mARB 2.0 - Monitoring Dashboard Setup Guide

This guide covers setting up comprehensive monitoring dashboards for mARB 2.0, including system health, performance metrics, error tracking, and queue monitoring.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Built-in Monitoring Endpoints](#built-in-monitoring-endpoints)
4. [Enhanced Health Check Endpoint](#enhanced-health-check-endpoint)
5. [Sentry Error Tracking Dashboard](#sentry-error-tracking-dashboard)
6. [Flower - Celery Queue Monitoring](#flower---celery-queue-monitoring)
7. [Simple API-Based Dashboard](#simple-api-based-dashboard)
8. [Grafana Dashboard (Advanced)](#grafana-dashboard-advanced)
9. [Log Aggregation](#log-aggregation)
10. [Alerting Setup](#alerting-setup)
11. [Best Practices](#best-practices)

---

## Overview

mARB 2.0 provides multiple layers of monitoring:

- **System Health**: API, database, Redis, Celery worker status
- **Performance Metrics**: Response times, cache hit rates, queue lengths
- **Error Tracking**: Sentry integration for exception monitoring
- **Queue Monitoring**: Flower dashboard for Celery tasks
- **Log Aggregation**: Structured logging with file rotation

### Monitoring Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Monitoring Stack                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Sentry     │  │   Flower    │  │   Grafana   │    │
│  │ (Errors)     │  │  (Celery)   │  │ (Metrics)   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│         │                 │                 │           │
│         └─────────────────┴─────────────────┘           │
│                         │                               │
│              ┌──────────▼──────────┐                   │
│              │   mARB 2.0 API      │                   │
│              │  /api/v1/health     │                   │
│              │  /api/v1/metrics    │                   │
│              └─────────────────────┘                   │
│                         │                               │
│         ┌───────────────┼───────────────┐               │
│         │               │               │               │
│    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐          │
│    │PostgreSQL│    │  Redis  │    │ Celery  │          │
│    └─────────┘    └─────────┘    └─────────┘          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Required Services

- **PostgreSQL**: Database for application data
- **Redis**: Cache and Celery message broker
- **Celery Worker**: Background task processor
- **FastAPI Application**: Main API server

### Optional Services

- **Sentry**: Error tracking (recommended for production)
- **Flower**: Celery monitoring (recommended)
- **Grafana**: Advanced metrics visualization (optional)
- **Prometheus**: Metrics collection (optional, for Grafana)

---

## Built-in Monitoring Endpoints

mARB 2.0 includes several built-in monitoring endpoints:

### 1. Basic Health Check

**Endpoint**: `GET /api/v1/health`

**Response**:
```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```

**Usage**:
```bash
curl http://localhost:8000/api/v1/health
```

### 2. Cache Statistics

**Endpoint**: `GET /api/v1/cache/stats`

**Response**:
```json
{
  "overall": {
    "hits": 1500,
    "misses": 200,
    "total": 1700,
    "hit_rate": 0.88
  },
  "by_key": {
    "claim:123": {
      "hits": 50,
      "misses": 5
    }
  }
}
```

**Usage**:
```bash
# Overall stats
curl http://localhost:8000/api/v1/cache/stats

# Specific key stats
curl http://localhost:8000/api/v1/cache/stats?key=claim:123
```

### 3. Reset Cache Statistics

**Endpoint**: `POST /api/v1/cache/stats/reset`

**Usage**:
```bash
curl -X POST http://localhost:8000/api/v1/cache/stats/reset
```

---

## Enhanced Health Check Endpoint

The current health endpoint is basic. We can enhance it to check all dependencies. Here's how to add a comprehensive health check:

### Implementation

Create or update `app/api/routes/health.py` to include dependency checks:

```python
@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed health check including all dependencies.
    
    Returns:
        Health status for API, database, Redis, and Celery
    """
    from app.config.database import SessionLocal
    from app.config.redis import get_redis
    from app.services.queue.tasks import celery_app
    
    health_status = {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }
    
    # Check database
    try:
        db.execute(text("SELECT 1"))
        health_status["components"]["database"] = {
            "status": "healthy",
            "response_time_ms": 0  # Could measure this
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check Redis
    try:
        redis_client = get_redis_client()
        start = time.time()
        redis_client.ping()
        response_time = (time.time() - start) * 1000
        health_status["components"]["redis"] = {
            "status": "healthy",
            "response_time_ms": round(response_time, 2)
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check Celery
    try:
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        if active_workers:
            health_status["components"]["celery"] = {
                "status": "healthy",
                "active_workers": len(active_workers)
            }
        else:
            health_status["status"] = "degraded"
            health_status["components"]["celery"] = {
                "status": "unhealthy",
                "error": "No active workers"
            }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["celery"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    return health_status
```

**Usage**:
```bash
curl http://localhost:8000/api/v1/health/detailed | jq .
```

---

## Sentry Error Tracking Dashboard

Sentry provides a comprehensive error tracking dashboard. See [SENTRY_SETUP.md](../SENTRY_SETUP.md) for detailed setup instructions.

### Quick Setup

1. **Sign up for Sentry**: https://sentry.io
2. **Create a project**: Select Python/FastAPI
3. **Get your DSN**: Copy from project settings
4. **Configure environment variables**:

```bash
# .env
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ENABLE_ALERTS=true
```

5. **Access Dashboard**: https://sentry.io/organizations/your-org/projects/

### Key Metrics in Sentry

- **Error Rate**: Errors per minute/hour
- **Error Types**: Grouped by exception type
- **Affected Users**: Impact assessment
- **Performance**: Transaction timing
- **Release Tracking**: Errors by version

### Recommended Alert Rules

1. **Critical Errors**: > 10 errors in 5 minutes → PagerDuty
2. **High Error Rate**: > 5% error rate in 10 minutes → Email
3. **New Error Types**: New issue created → Slack
4. **Performance**: P95 latency > 2 seconds → Email

---

## Flower - Celery Queue Monitoring

Flower is a web-based tool for monitoring Celery workers and tasks.

### Installation

Flower is already in `requirements.txt`. If not installed:

```bash
source venv/bin/activate
pip install flower==2.0.1
```

### Running Flower

#### Development

```bash
source venv/bin/activate
celery -A app.services.queue.tasks flower --port=5555
```

Access at: http://localhost:5555

#### Production (systemd service)

Create `/etc/systemd/system/marb2.0-flower.service`:

```ini
[Unit]
Description=mARB 2.0 Flower Monitoring
After=network.target redis.service

[Service]
Type=simple
User=marb
WorkingDirectory=/opt/marb2.0
Environment="PATH=/opt/marb2.0/venv/bin"
ExecStart=/opt/marb2.0/venv/bin/celery -A app.services.queue.tasks flower --port=5555 --broker=redis://localhost:6379/0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable marb2.0-flower.service
sudo systemctl start marb2.0-flower.service
```

#### Production (with authentication)

For production, add basic authentication:

```bash
celery -A app.services.queue.tasks flower \
  --port=5555 \
  --broker=redis://localhost:6379/0 \
  --basic_auth=admin:secure_password_here
```

### Flower Dashboard Features

- **Workers**: Active worker status and statistics
- **Tasks**: Task history, success/failure rates
- **Broker**: Redis connection and queue status
- **Monitoring**: Real-time task execution
- **Task Details**: Individual task traces and logs

### Accessing Flower

- **Development**: http://localhost:5555
- **Production**: http://yourdomain.com:5555 (or via nginx reverse proxy)

### nginx Reverse Proxy (Optional)

Add to nginx config for secure access:

```nginx
server {
    listen 443 ssl;
    server_name flower.yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5555;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Simple API-Based Dashboard

You can build a simple dashboard using the existing API endpoints. Here's a basic HTML dashboard:

### Create `monitoring/dashboard.html`

```html
<!DOCTYPE html>
<html>
<head>
    <title>mARB 2.0 Monitoring Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
        .healthy { background-color: #d4edda; color: #155724; }
        .unhealthy { background-color: #f8d7da; color: #721c24; }
        .metric { display: inline-block; margin: 10px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .metric-value { font-size: 24px; font-weight: bold; }
    </style>
</head>
<body>
    <h1>mARB 2.0 Monitoring Dashboard</h1>
    <div id="status"></div>
    <div id="metrics"></div>
    
    <script>
        const API_BASE = 'http://localhost:8000/api/v1';
        
        async function fetchHealth() {
            try {
                const response = await fetch(`${API_BASE}/health/detailed`);
                const data = await response.json();
                updateStatus(data);
            } catch (error) {
                document.getElementById('status').innerHTML = 
                    '<div class="status unhealthy">Error fetching health status</div>';
            }
        }
        
        async function fetchCacheStats() {
            try {
                const response = await fetch(`${API_BASE}/cache/stats`);
                const data = await response.json();
                updateMetrics(data);
            } catch (error) {
                console.error('Error fetching cache stats:', error);
            }
        }
        
        function updateStatus(data) {
            const statusDiv = document.getElementById('status');
            const statusClass = data.status === 'healthy' ? 'healthy' : 'unhealthy';
            statusDiv.innerHTML = `
                <div class="status ${statusClass}">
                    <h2>System Status: ${data.status.toUpperCase()}</h2>
                    <p>Version: ${data.version}</p>
                    <p>Timestamp: ${data.timestamp}</p>
                    <h3>Components:</h3>
                    <ul>
                        ${Object.entries(data.components).map(([name, comp]) => 
                            `<li>${name}: ${comp.status} ${comp.error ? `(${comp.error})` : ''}</li>`
                        ).join('')}
                    </ul>
                </div>
            `;
        }
        
        function updateMetrics(data) {
            const metricsDiv = document.getElementById('metrics');
            const hitRate = (data.overall.hit_rate * 100).toFixed(2);
            metricsDiv.innerHTML = `
                <h2>Cache Metrics</h2>
                <div class="metric">
                    <div class="metric-label">Cache Hits</div>
                    <div class="metric-value">${data.overall.hits}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Cache Misses</div>
                    <div class="metric-value">${data.overall.misses}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Hit Rate</div>
                    <div class="metric-value">${hitRate}%</div>
                </div>
            `;
        }
        
        // Refresh every 30 seconds
        fetchHealth();
        fetchCacheStats();
        setInterval(() => {
            fetchHealth();
            fetchCacheStats();
        }, 30000);
    </script>
</body>
</html>
```

### Serving the Dashboard

You can serve this file using:

1. **Simple HTTP server**:
```bash
python -m http.server 8080
# Access at: http://localhost:8080/monitoring/dashboard.html
```

2. **nginx** (production):
```nginx
location /monitoring {
    alias /opt/marb2.0/monitoring;
    index dashboard.html;
}
```

---

## Grafana Dashboard (Advanced)

For advanced metrics visualization, you can set up Grafana with Prometheus.

### Architecture

```
mARB 2.0 API → Prometheus Exporter → Prometheus → Grafana
```

### Step 1: Install Prometheus

```bash
# Download Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*

# Create config
cat > prometheus.yml <<EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'marb2.0'
    static_configs:
      - targets: ['localhost:8000']
EOF
```

### Step 2: Add Metrics Endpoint to mARB 2.0

Create `app/api/routes/metrics.py`:

```python
"""Prometheus metrics endpoint."""
from fastapi import APIRouter
from prometheus_client import generate_latest, Counter, Histogram, Gauge
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST

router = APIRouter()

# Define metrics
request_count = Counter('marb_requests_total', 'Total requests', ['method', 'endpoint'])
request_duration = Histogram('marb_request_duration_seconds', 'Request duration')
cache_hits = Counter('marb_cache_hits_total', 'Cache hits')
cache_misses = Counter('marb_cache_misses_total', 'Cache misses')
active_claims = Gauge('marb_active_claims', 'Active claims count')

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

### Step 3: Install Grafana

```bash
# Ubuntu/Debian
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
sudo apt-get update
sudo apt-get install grafana

# Start Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

### Step 4: Configure Grafana

1. Access Grafana: http://localhost:3000 (default: admin/admin)
2. Add Prometheus data source:
   - URL: http://localhost:9090
   - Access: Server (default)
3. Create dashboard with panels for:
   - Request rate
   - Response times
   - Cache hit rate
   - Error rate
   - Active claims

### Step 5: Import Pre-built Dashboard

Grafana provides dashboard templates. Search for "FastAPI" or "Python" dashboards.

---

## Log Aggregation

### Current Logging Setup

mARB 2.0 uses structured logging with file rotation. Logs are written to:

- **Development**: Console output
- **Production**: `/opt/marb2.0/logs/app.log` (if configured)

### Log Locations

```bash
# Application logs
tail -f /opt/marb2.0/logs/app.log

# Systemd logs
sudo journalctl -u marb2.0.service -f
sudo journalctl -u marb2.0-celery.service -f

# nginx logs
sudo tail -f /var/log/nginx/marb2.0_access.log
sudo tail -f /var/log/nginx/marb2.0_error.log
```

### Log Aggregation Options

#### Option 1: ELK Stack (Elasticsearch, Logstash, Kibana)

For large-scale log aggregation:

1. **Install ELK Stack**
2. **Configure Logstash** to read from log files
3. **Visualize in Kibana**

#### Option 2: Loki + Grafana

Lighter-weight alternative:

1. **Install Loki**: https://grafana.com/docs/loki/latest/installation/
2. **Configure Promtail** to ship logs
3. **Add Loki data source in Grafana**

#### Option 3: Cloud Services

- **Datadog**: Log management and monitoring
- **New Relic**: Application performance monitoring
- **Splunk**: Enterprise log analysis

---

## Alerting Setup

### Health Check Monitoring Script

Create `scripts/monitor_health.sh`:

```bash
#!/bin/bash
# Health check monitoring script

API_URL="${API_URL:-http://localhost:8000}"
ALERT_EMAIL="${ALERT_EMAIL:-admin@yourdomain.com}"

# Check health
HEALTH=$(curl -s "${API_URL}/api/v1/health/detailed")
STATUS=$(echo "$HEALTH" | jq -r '.status')

if [ "$STATUS" != "healthy" ]; then
    echo "ALERT: System status is $STATUS"
    echo "$HEALTH" | mail -s "mARB 2.0 Health Alert" "$ALERT_EMAIL"
    exit 1
fi

# Check components
DB_STATUS=$(echo "$HEALTH" | jq -r '.components.database.status')
REDIS_STATUS=$(echo "$HEALTH" | jq -r '.components.redis.status')
CELERY_STATUS=$(echo "$HEALTH" | jq -r '.components.celery.status')

if [ "$DB_STATUS" != "healthy" ] || [ "$REDIS_STATUS" != "healthy" ] || [ "$CELERY_STATUS" != "healthy" ]; then
    echo "ALERT: Component failure detected"
    echo "$HEALTH" | mail -s "mARB 2.0 Component Alert" "$ALERT_EMAIL"
    exit 1
fi

echo "All systems healthy"
exit 0
```

### Cron Job Setup

```bash
# Add to crontab (check every 5 minutes)
*/5 * * * * /opt/marb2.0/scripts/monitor_health.sh
```

### Sentry Alerts

Configure alerts in Sentry dashboard (see [SENTRY_SETUP.md](../SENTRY_SETUP.md)).

### PagerDuty Integration

For critical alerts:

1. **Create PagerDuty account**
2. **Add Sentry integration** in PagerDuty
3. **Configure escalation policies**

---

## Best Practices

### 1. Monitor Key Metrics

- **API Response Times**: P50, P95, P99
- **Error Rates**: Errors per minute
- **Cache Hit Rate**: Should be > 70%
- **Queue Length**: Celery task backlog
- **Database Connections**: Active connections
- **Memory Usage**: Application memory consumption

### 2. Set Up Alerts

- **Critical**: System down, database unavailable
- **Warning**: High error rate, slow responses
- **Info**: Deployment notifications, maintenance windows

### 3. Regular Reviews

- **Daily**: Check error logs and Sentry dashboard
- **Weekly**: Review performance metrics and trends
- **Monthly**: Analyze patterns and optimize

### 4. Dashboard Access

- **Development**: Open access for team
- **Production**: Secure with authentication
- **Sensitive Data**: Ensure HIPAA compliance (no PII/PHI in dashboards)

### 5. Performance Monitoring

- **Track Slow Queries**: Database query performance
- **Monitor Cache**: Cache hit rates and TTL effectiveness
- **Queue Monitoring**: Task processing times
- **Resource Usage**: CPU, memory, disk I/O

---

## Quick Reference

### Health Check URLs

```bash
# Basic health
curl http://localhost:8000/api/v1/health

# Detailed health (if implemented)
curl http://localhost:8000/api/v1/health/detailed

# Cache stats
curl http://localhost:8000/api/v1/cache/stats
```

### Monitoring Services

```bash
# Flower (Celery)
http://localhost:5555

# Sentry
https://sentry.io/organizations/your-org/projects/

# Grafana (if installed)
http://localhost:3000
```

### Log Locations

```bash
# Application logs
/opt/marb2.0/logs/app.log

# Systemd logs
sudo journalctl -u marb2.0.service
sudo journalctl -u marb2.0-celery.service

# nginx logs
/var/log/nginx/marb2.0_access.log
/var/log/nginx/marb2.0_error.log
```

---

## Troubleshooting

### Health Check Fails

1. **Check service status**: `systemctl status marb2.0.service`
2. **Check logs**: `journalctl -u marb2.0.service -n 50`
3. **Test database**: `psql $DATABASE_URL -c "SELECT 1;"`
4. **Test Redis**: `redis-cli ping`

### Flower Not Accessible

1. **Check if running**: `systemctl status marb2.0-flower.service`
2. **Check port**: `netstat -tlnp | grep 5555`
3. **Check firewall**: `sudo ufw status`
4. **Check nginx**: If using reverse proxy, check nginx config

### Metrics Not Appearing

1. **Check endpoint**: `curl http://localhost:8000/api/v1/metrics`
2. **Check Prometheus**: Verify scrape config
3. **Check Grafana**: Verify data source connection

---

## Next Steps

1. **Implement Enhanced Health Check**: Add detailed health endpoint
2. **Set Up Sentry**: Configure error tracking (see [SENTRY_SETUP.md](../SENTRY_SETUP.md))
3. **Deploy Flower**: Set up Celery monitoring
4. **Create Simple Dashboard**: Build HTML dashboard for quick overview
5. **Set Up Alerts**: Configure email/Slack notifications
6. **Consider Grafana**: For advanced metrics visualization

---

## Resources

- [Sentry Setup Guide](../SENTRY_SETUP.md)
- [Deployment Runbook](./DEPLOYMENT_RUNBOOK.md)
- [Troubleshooting Guide](../TROUBLESHOOTING.md)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)

---

**Last Updated**: 2024-12-20

