# Setting Up Sentry Right Now

## Quick Setup (5 minutes)

### Step 1: Get Your Sentry DSN

**If you already have a Sentry account:**
1. Go to https://sentry.io and log in
2. Navigate to your project (or create a new one)
3. Go to Settings → Client Keys (DSN)
4. Copy your DSN

**If you need to create an account:**
1. Go to https://sentry.io
2. Click "Sign Up" (free tier available)
3. Create a new project:
   - Select "Python" → "FastAPI"
   - Name it "mARB 2.0" (or your preferred name)
4. Copy your DSN from the project setup page

Your DSN will look like:
```
https://xxxxx@xxxxx.ingest.sentry.io/xxxxx
```

### Step 2: Run Setup Script

```bash
source venv/bin/activate
python scripts/setup_sentry.py
```

The script will:
- Ask for your DSN (paste it)
- Ask for environment (1=development, 2=staging, 3=production)
- Configure performance monitoring
- Configure alerts
- Save everything to `.env`

### Step 3: Test It

```bash
python scripts/test_sentry.py
```

You should see:
- ✅ SDK Import: PASS
- ✅ Configuration: PASS
- ✅ Initialization: PASS
- ✅ Message Capture: PASS
- ✅ Exception Capture: PASS

### Step 4: Verify in Sentry

1. Go to your Sentry dashboard
2. You should see test messages and exceptions
3. If you see them, Sentry is working! ✅

### Step 5: Restart Application

Restart your FastAPI server to load the new configuration:

```bash
# Stop current server (Ctrl+C)
python run.py
```

Look for this in the logs:
```
Sentry initialized environment=development tracing_enabled=True
```

## Alternative: Manual Setup

If you prefer to set it up manually, add this to your `.env` file:

```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=development
SENTRY_ENABLE_TRACING=true
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ENABLE_ALERTS=true
SENTRY_ALERT_ON_ERRORS=true
SENTRY_ALERT_ON_WARNINGS=false
```

Then test:
```bash
python scripts/test_sentry.py
```

## Need Help?

- See [SENTRY_QUICK_START.md](SENTRY_QUICK_START.md) for detailed guide
- See [SENTRY_SETUP.md](SENTRY_SETUP.md) for full documentation
- Run `python scripts/test_sentry.py` to diagnose issues

