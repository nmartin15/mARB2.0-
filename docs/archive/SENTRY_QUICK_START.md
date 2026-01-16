# Sentry Quick Start Guide

This guide will help you set up Sentry error tracking in 5 minutes.

## Prerequisites

- Sentry account (sign up at https://sentry.io - free tier available)
- Python virtual environment activated

## Step 1: Create Sentry Project (2 minutes)

1. **Sign up/Log in** to https://sentry.io
2. **Create a new project**:
   - Click "Projects" → "Create Project"
   - Select **"Python"** → **"FastAPI"**
   - Enter project name: `mARB 2.0` (or your preferred name)
   - Click "Create Project"
3. **Copy your DSN**:
   - After creating the project, you'll see your DSN
   - It looks like: `https://xxxxx@xxxxx.ingest.sentry.io/xxxxx`
   - Copy this - you'll need it in the next step

## Step 2: Run Setup Script (1 minute)

Run the interactive setup script:

```bash
source venv/bin/activate
python scripts/setup_sentry.py
```

The script will:
- Ask for your Sentry DSN (paste it from Step 1)
- Ask for your environment (development/staging/production)
- Configure performance monitoring
- Configure alerts
- Save everything to your `.env` file

**Example interaction:**
```
Enter your Sentry DSN: https://xxxxx@xxxxx.ingest.sentry.io/xxxxx
Select environment: 1 (development)
Enable performance tracing? (y/n): y
Enable alerts? (y/n): n
```

## Step 3: Test Configuration (1 minute)

Verify Sentry is working:

```bash
python scripts/test_sentry.py
```

This will:
- Check that sentry-sdk is installed
- Verify your DSN format
- Test Sentry initialization
- Send a test message to Sentry
- Send a test exception to Sentry

**Expected output:**
```
✅ SDK Import: PASS
✅ Configuration: PASS
✅ Initialization: PASS
✅ Message Capture: PASS
✅ Exception Capture: PASS
```

## Step 4: Verify in Sentry Dashboard (1 minute)

1. Go to your Sentry dashboard: https://sentry.io
2. Navigate to your project
3. You should see:
   - Test message: "Test message from mARB 2.0 setup script"
   - Test exception: "Test exception from mARB 2.0 setup script"

If you see these, **Sentry is working!** ✅

## Step 5: Restart Your Application

Restart your FastAPI application to load the new Sentry configuration:

```bash
# Stop your current server (Ctrl+C)
# Then restart:
python run.py
```

You should see in the logs:
```
Sentry initialized environment=development tracing_enabled=True
```

## Manual Configuration (Alternative)

If you prefer to configure manually, add these to your `.env` file:

```bash
# Sentry Configuration
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=development
SENTRY_ENABLE_TRACING=true
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ENABLE_ALERTS=true
SENTRY_ALERT_ON_ERRORS=true
SENTRY_ALERT_ON_WARNINGS=false
```

## Environment-Specific Settings

### Development
```bash
SENTRY_DSN=  # Leave empty to disable
SENTRY_ENVIRONMENT=development
SENTRY_ENABLE_TRACING=false
SENTRY_ENABLE_ALERTS=false
```

### Production
```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_ENABLE_TRACING=true
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ENABLE_ALERTS=true
SENTRY_ALERT_ON_ERRORS=true
SENTRY_ALERT_ON_WARNINGS=false
```

## Next Steps

1. **Set up alerts** in Sentry dashboard:
   - Go to Alerts → Create Alert Rule
   - Configure: "More than 10 errors in 5 minutes" → Email/Slack notification

2. **Monitor errors**:
   - Check Sentry dashboard regularly
   - Review error patterns
   - Fix high-priority issues

3. **Review performance**:
   - Check transaction traces
   - Identify slow endpoints
   - Optimize based on data

## Troubleshooting

### "Sentry DSN not configured"
- Make sure `SENTRY_DSN` is set in your `.env` file
- Run `python scripts/setup_sentry.py` again

### "sentry-sdk not installed"
```bash
pip install sentry-sdk[fastapi]
```

### Test script fails
- Check that your DSN is correct
- Verify you can access sentry.io
- Check application logs for Sentry initialization errors

### No events in Sentry dashboard
- Wait a few minutes (events may take time to appear)
- Check that `SENTRY_ENABLE_ALERTS=true`
- Verify your DSN is correct
- Check application logs for Sentry errors

## Additional Resources

- [Full Sentry Setup Guide](SENTRY_SETUP.md) - Detailed configuration options
- [Sentry Python Docs](https://docs.sentry.io/platforms/python/)
- [Sentry FastAPI Integration](https://docs.sentry.io/platforms/python/guides/fastapi/)

## Support

If you encounter issues:
1. Run `python scripts/test_sentry.py` to diagnose
2. Check application logs for Sentry errors
3. Review [SENTRY_SETUP.md](SENTRY_SETUP.md) for detailed troubleshooting

---

**That's it!** Your Sentry error tracking is now configured. 🎉

