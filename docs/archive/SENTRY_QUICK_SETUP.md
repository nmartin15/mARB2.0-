# Sentry Quick Setup Guide

## 🚀 Quick Setup (5 minutes)

### ⚠️ IMPORTANT: You MUST set up a Sentry account first!

**You cannot configure Sentry without a Sentry account and DSN.** Follow these steps in order:

---

### Step 1: Create Your Sentry Account (FIRST!)

1. **Go to Sentry Signup**: https://sentry.io/signup/
   - Or if you already have an account: https://sentry.io/auth/login/

2. **Sign Up** (if new):
   - Enter your email address
   - Create a password
   - Complete the signup process
   - **Free tier is available** - no credit card required for basic error tracking

3. **Log In** (if you already have an account):
   - Go to https://sentry.io/auth/login/
   - Enter your credentials

---

### Step 2: Create a Project (Get Your DSN)

1. **After logging in**, you'll be taken to your Sentry dashboard

2. **Create a New Project**:
   - Click **"Create Project"** (or go to Projects → Create Project)
   - Select **"Python"** → **"FastAPI"**
   - Give it a name: `mARB 2.0` (or your preferred name)
   - Click **"Create Project"**

3. **Copy Your DSN**:
   - After creating the project, you'll see a setup page
   - Copy the **DSN** (it looks like: `https://xxxxx@xxxxx.ingest.sentry.io/xxxxx`)
   - You can also find it later in: **Settings** → **Projects** → **Your Project** → **Client Keys (DSN)**

### Step 2: Configure Your .env File

Add these lines to your `.env` file:

```bash
# Sentry Error Tracking Configuration
SENTRY_DSN=https://your-dsn-here@sentry.io/project-id
SENTRY_ENVIRONMENT=development  # or staging, production
SENTRY_RELEASE=v2.0.0  # Optional: your version/release identifier

# Performance Monitoring (optional, defaults shown)
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% of transactions
SENTRY_ENABLE_TRACING=true

# Alert Configuration (optional, defaults shown)
SENTRY_ENABLE_ALERTS=true
SENTRY_ALERT_ON_ERRORS=true
SENTRY_ALERT_ON_WARNINGS=false

# HIPAA Compliance (keep as false)
SENTRY_SEND_DEFAULT_PII=false
```

### Step 3: Test Your Configuration

Run the test script:

```bash
source venv/bin/activate
python scripts/test_sentry.py
```

This will:
- ✅ Check if Sentry is configured
- ✅ Send a test message to Sentry
- ✅ Send a test exception to Sentry
- ✅ Verify everything is working

### Step 4: Restart Your Application

Restart your FastAPI server and Celery worker to load the new configuration:

```bash
# Terminal 1: Restart FastAPI
python run.py

# Terminal 2: Restart Celery
celery -A app.services.queue.tasks worker --loglevel=info
```

### Step 5: Verify It's Working

1. Check your application logs - you should see:
   ```
   Sentry initialized environment=development release=v2.0.0 tracing_enabled=True
   ```

2. Check your Sentry dashboard - you should see:
   - The test message from `test_sentry.py`
   - Any errors that occur in your application

## 📋 Environment-Specific Settings

### Development
```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0.0  # Disable tracing in dev
SENTRY_ENABLE_ALERTS=false  # Don't spam alerts
```

### Staging
```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=staging
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ENABLE_ALERTS=true
```

### Production
```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1  # Adjust based on traffic
SENTRY_ENABLE_ALERTS=true
SENTRY_ALERT_ON_ERRORS=true
SENTRY_ALERT_ON_WARNINGS=false  # Usually too noisy
```

## 🎯 What's Already Done

✅ **Sentry SDK installed** (`sentry-sdk[fastapi]` in requirements.txt)  
✅ **Sentry code integrated** (in `app/config/sentry.py`)  
✅ **Automatic error capture** (FastAPI, Celery, SQLAlchemy integrations)  
✅ **HIPAA compliance** (sensitive data filtering)  
✅ **Error handlers** (capture exceptions with context)  

**You just need to add your DSN!**

## 🔧 Using the Setup Script (Alternative)

If you prefer an interactive setup:

```bash
source venv/bin/activate
python scripts/configure_sentry.py
```

This script will:
- Guide you through getting your DSN
- Configure all settings interactively
- Test the connection
- Update your `.env` file automatically

## 📚 More Information

- **Full Documentation**: See `SENTRY_SETUP.md` for detailed configuration options
- **Sentry Dashboard**: https://sentry.io (login to see your errors)
- **Sentry Docs**: https://docs.sentry.io/platforms/python/guides/fastapi/

## ❓ Troubleshooting

### "Sentry DSN not configured"
- Make sure you added `SENTRY_DSN` to your `.env` file
- Check that the DSN starts with `https://`
- Restart your application after adding the DSN

### "sentry-sdk not installed"
- Run: `pip install sentry-sdk[fastapi]`
- Or: `pip install -r requirements.txt`

### Not seeing errors in Sentry
- Check your Sentry dashboard (make sure you're looking at the right project)
- Verify the DSN is correct
- Check application logs for "Sentry initialized" message
- Make sure `SENTRY_ENABLE_ALERTS=true`

### Too many alerts
- Set `SENTRY_ALERT_ON_WARNINGS=false` in `.env`
- Configure alert rules in Sentry dashboard to be less sensitive

## ✅ Success Checklist

- [ ] Sentry account created
- [ ] Project created (Python/FastAPI)
- [ ] DSN copied and added to `.env`
- [ ] `test_sentry.py` runs successfully
- [ ] Application logs show "Sentry initialized"
- [ ] Test messages appear in Sentry dashboard
- [ ] Alert rules configured (optional)

---

**That's it!** Your Sentry error tracking is now configured. 🎉

