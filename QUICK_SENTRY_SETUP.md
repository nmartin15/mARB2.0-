# Quick Sentry Setup Guide

**Time Required:** 5-10 minutes  
**Status:** Code ready, just needs DSN configuration

## Step-by-Step Instructions

### 1. Create Sentry Account (2 minutes)

1. Go to https://sentry.io
2. Click **"Sign Up"** (or log in if you have an account)
3. Choose **"Start with the free plan"** (5,000 events/month - perfect for getting started)

### 2. Create Project (1 minute)

1. After signing up, you'll be prompted to create a project
2. Select **"Python"** as the platform
3. Select **"FastAPI"** as the framework
4. Enter project name: `mARB 2.0`
5. Click **"Create Project"**

### 3. Copy Your DSN (30 seconds)

1. After creating the project, you'll see a page with setup instructions
2. **Copy the DSN** - it looks like:
   ```
   https://xxxxx@xxxxx.ingest.sentry.io/xxxxx
   ```
3. **Save it somewhere** - you'll need it in the next step

### 4. Add DSN to .env File (1 minute)

1. Open your `.env` file in the project root
2. Add or update these lines:
   ```bash
   # Sentry Configuration
   SENTRY_DSN=https://your-actual-dsn-here@sentry.io/project-id
   SENTRY_ENVIRONMENT=development  # Change to 'production' when deploying
   ```
3. **Important:** Replace `https://your-actual-dsn-here@sentry.io/project-id` with the DSN you copied in step 3
4. Save the file

### 5. Test the Configuration (1 minute)

Run the test script:

```bash
source venv/bin/activate
python scripts/test_sentry.py
```

**Expected Output:**
```
✅ Sentry DSN configured: https://xxxxx@xxxxx.ingest.sentry.io/xxxxx
✅ Environment: development
✅ Tracing: Enabled
✅ Alerts: Enabled
✅ Test message sent successfully!
```

### 6. Verify in Sentry Dashboard (1 minute)

1. Go back to your Sentry dashboard
2. Click on your project (`mARB 2.0`)
3. You should see:
   - A test message: "🧪 Test message from mARB 2.0 Sentry test script"
   - A test exception (if you chose to send one)

### 7. Restart Your Application (1 minute)

Restart your FastAPI server and Celery worker to ensure Sentry is initialized:

```bash
# Terminal 1 - Restart FastAPI
# (Stop current server with Ctrl+C, then:)
python run.py

# Terminal 2 - Restart Celery
# (Stop current worker with Ctrl+C, then:)
celery -A app.services.queue.tasks worker --loglevel=info
```

**Check the logs** - you should see:
```
✅ Sentry initialized
```

## Troubleshooting

### "Sentry DSN not configured"
- Make sure you added `SENTRY_DSN` to your `.env` file
- Check that the DSN starts with `https://` and ends with the project ID
- Make sure there are no extra spaces or quotes around the DSN

### "Sentry connection test failed"
- Check your internet connection
- Verify the DSN is correct (copy it again from Sentry dashboard)
- Make sure `sentry-sdk` is installed: `pip install sentry-sdk`

### "No events in Sentry dashboard"
- Wait 10-30 seconds for events to appear
- Check that you're looking at the correct project
- Make sure `SENTRY_ENVIRONMENT` matches your environment

## What Happens Next?

Once configured, Sentry will automatically:
- ✅ Capture all application errors and exceptions
- ✅ Track errors in Celery tasks
- ✅ Include request context (path, method, parameters)
- ✅ Filter sensitive data (HIPAA compliant)
- ✅ Send alerts for critical errors (if configured)

## Optional: Configure Alerts

1. Go to Sentry dashboard → **Alerts** → **Create Alert Rule**
2. Recommended alerts:
   - **Critical Errors**: More than 10 errors in 5 minutes
   - **New Error Types**: New issue created
   - **High Error Rate**: Error rate > 5% in 10 minutes

## Need Help?

- See `docs/guides/SENTRY_SETUP.md` for detailed documentation
- See `SENTRY_SETUP_CHECKLIST.md` for a checklist version
- Check Sentry docs: https://docs.sentry.io/platforms/python/guides/fastapi/

---

**That's it!** Once you complete these steps, Sentry will be tracking errors in your application. 🎉

