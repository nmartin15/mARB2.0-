# Sentry DSN Setup Checklist

**Status:** ⏳ Pending User Action  
**Estimated Time:** 5-10 minutes  
**Priority:** ⭐ High (Required for Production Error Tracking)

## Quick Setup Steps

### ✅ Step 1: Create Sentry Account & Project (2-3 minutes)

1. **Sign up/Log in** at https://sentry.io
   - Free tier available (5,000 events/month)
   - No credit card required for free tier

2. **Create a new project:**
   - Click "Projects" → "Create Project"
   - Select **"Python"** → **"FastAPI"**
   - Enter project name: `mARB 2.0`
   - Click "Create Project"

3. **Copy your DSN:**
   - After creating project, you'll see your DSN
   - Format: `https://xxxxx@xxxxx.ingest.sentry.io/xxxxx`
   - **Save this DSN** - you'll need it in Step 2

### ✅ Step 2: Configure Environment Variables (1 minute)

Add to your `.env` file:

```bash
# Sentry Configuration (REQUIRED for production)
SENTRY_DSN=https://your-dsn-here@sentry.io/project-id
SENTRY_ENVIRONMENT=production  # or development, staging

# Optional: Performance Monitoring
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% of transactions (0.0 to 1.0)
SENTRY_ENABLE_TRACING=true

# Optional: Alert Configuration
SENTRY_ENABLE_ALERTS=true
SENTRY_ALERT_ON_ERRORS=true
SENTRY_ALERT_ON_WARNINGS=false

# HIPAA Compliance (already configured)
SENTRY_SEND_DEFAULT_PII=false
```

**Important:** Replace `https://your-dsn-here@sentry.io/project-id` with your actual DSN from Step 1.

### ✅ Step 3: Test Configuration (1 minute)

```bash
source venv/bin/activate
python scripts/test_sentry.py
```

Expected output: `✅ Sentry is configured and working!`

### ✅ Step 4: Restart Services (1 minute)

Restart your FastAPI server and Celery worker to load the new configuration:

```bash
# Terminal 1 - Restart FastAPI
# (Stop current server with Ctrl+C, then:)
python run.py

# Terminal 2 - Restart Celery
# (Stop current worker with Ctrl+C, then:)
celery -A app.services.queue.tasks worker --loglevel=info
```

### ✅ Step 5: Verify It's Working (1 minute)

1. **Check logs** for "Sentry initialized" message
2. **Trigger a test error** (optional):
   ```bash
   curl http://localhost:8000/api/v1/test-error
   ```
3. **Check Sentry dashboard** - you should see the error appear within seconds

## What You Get

Once configured, Sentry will automatically:
- ✅ Capture all application errors and exceptions
- ✅ Track errors in Celery tasks
- ✅ Include request context (path, method, parameters)
- ✅ Filter sensitive data (HIPAA compliant)
- ✅ Send alerts for critical errors (if configured)
- ✅ Track performance metrics (if enabled)

## Troubleshooting

### Sentry Not Capturing Errors

1. **Check DSN:** Ensure `SENTRY_DSN` is set correctly in `.env`
2. **Check Environment:** Verify `SENTRY_ENVIRONMENT` is set
3. **Check Logs:** Look for "Sentry initialized" in application logs
4. **Test Script:** Run `python scripts/test_sentry.py`

### Too Many Alerts

1. Set `SENTRY_ALERT_ON_WARNINGS=false` in `.env`
2. Adjust alert rules in Sentry dashboard
3. Increase alert thresholds

## Next Steps

After setup:
- [ ] Configure alert rules in Sentry dashboard (optional)
- [ ] Set up Slack/Email notifications (optional)
- [ ] Review error patterns in Sentry dashboard

## Documentation

For detailed configuration options, see:
- `docs/guides/SENTRY_SETUP.md` - Full setup guide
- `app/config/sentry.py` - Sentry configuration code

---

**Note:** The code is already implemented and ready. You just need to add your DSN to `.env` and restart the services.

