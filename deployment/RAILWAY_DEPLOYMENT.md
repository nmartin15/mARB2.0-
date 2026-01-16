# Railway Deployment Guide (Free Tier - Perfect for Testing)

**Why Railway?**
- ✅ **FREE** for testing (generous free tier)
- ✅ **Proper HTTPS** with automatic SSL certificates
- ✅ **PostgreSQL + Redis** included
- ✅ **Easy setup** - Git-based deployment
- ✅ **Production-like** environment
- ✅ **No credit card required** for free tier

**Perfect for:** Staging/testing environment with proper HTTPS validation

---

## Step 1: Sign Up for Railway

1. Go to https://railway.app
2. Sign up with GitHub (recommended) or email
3. No credit card required for free tier

---

## Step 2: Create New Project

1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"** (or upload code)
3. Connect your repository: `mARB 2.0`

---

## Step 3: Add PostgreSQL Database

1. In your Railway project, click **"+ New"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway will automatically create:
   - Database instance
   - Connection string (we'll use this in `.env`)

---

## Step 4: Add Redis

1. Click **"+ New"** again
2. Select **"Database"** → **"Add Redis"**
3. Railway will create Redis instance

---

## Step 5: Configure Environment Variables

1. Go to your **service** (the main app)
2. Click **"Variables"** tab
3. Add all environment variables from your `.env` file

**Key variables to set:**
```bash
# Database (use Railway's PostgreSQL connection string)
DATABASE_URL=<railway-postgres-url>?sslmode=require

# Redis (use Railway's Redis URL)
REDIS_HOST=<railway-redis-host>
REDIS_PORT=<railway-redis-port>
REDIS_PASSWORD=<railway-redis-password>
CELERY_BROKER_URL=redis://:<password>@<host>:<port>/0
CELERY_RESULT_BACKEND=redis://:<password>@<host>:<port>/0

# Security (use your generated keys)
JWT_SECRET_KEY=<your-generated-key>
ENCRYPTION_KEY=<your-generated-key>
REDIS_PASSWORD=<your-redis-password>

# Environment
ENVIRONMENT=production
DEBUG=false
REQUIRE_AUTH=true

# CORS (update with Railway domain)
CORS_ORIGINS=https://your-app.railway.app

# Logging
LOG_LEVEL=info
LOG_FORMAT=json
LOG_FILE=app.log
```

**How to get connection strings:**
- **PostgreSQL**: Click on PostgreSQL service → "Variables" → Copy `DATABASE_URL`
- **Redis**: Click on Redis service → "Variables" → Copy connection details

---

## Step 6: Configure Build Settings

1. Go to your **service** → **"Settings"**
2. Set **Root Directory**: `/` (or leave default)
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Note:** Railway automatically sets `$PORT` environment variable

---

## Step 7: Update App for Railway Port

Railway uses dynamic ports. Update `app/main.py` to use `PORT` env var:

```python
import os

# In your startup or main function
port = int(os.getenv("PORT", 8000))
```

Actually, Railway handles this automatically - just use `$PORT` in start command.

---

## Step 8: Deploy

1. Railway will automatically deploy when you push to GitHub
2. Or click **"Deploy"** button
3. Watch the build logs

---

## Step 9: Get Your HTTPS URL

1. After deployment, Railway provides a URL like: `https://your-app.up.railway.app`
2. This URL has **automatic HTTPS** with valid SSL certificate
3. Copy this URL

---

## Step 10: Run Production Validation

Now you can run your validation scripts:

```bash
# Test HTTPS
python scripts/test_https_end_to_end.py https://your-app.up.railway.app

# Monitor health
python scripts/monitor_health.py https://your-app.up.railway.app
```

---

## Step 11: Set Up Custom Domain (Optional)

1. Go to service → **"Settings"** → **"Networking"**
2. Click **"Generate Domain"** or add custom domain
3. Railway automatically provisions SSL certificate

---

## Railway Free Tier Limits

- **$5 credit/month** (usually enough for testing)
- **500 hours** of usage
- **PostgreSQL**: 256 MB storage
- **Redis**: 25 MB storage
- **Bandwidth**: 100 GB/month

**For testing/validation, this is more than enough!**

---

## Troubleshooting

### Database Connection Issues
- Ensure `DATABASE_URL` includes `?sslmode=require`
- Check PostgreSQL service is running in Railway

### Redis Connection Issues
- Verify Redis URL format: `redis://:<password>@<host>:<port>/0`
- Check Redis service is running

### Build Failures
- Check build logs in Railway dashboard
- Ensure `requirements.txt` is correct
- Verify Python version (Railway auto-detects)

### Port Issues
- Railway sets `PORT` automatically
- Use `$PORT` in start command, not hardcoded port

---

## Cost

**FREE** for testing! Railway's free tier is very generous for staging/testing environments.

If you exceed free tier, it's pay-as-you-go, very affordable.

---

## Next Steps

1. Deploy to Railway (30-60 minutes)
2. Get HTTPS URL
3. Run validation scripts ✅
4. Test deployment ✅
5. Mark production validation complete! ✅

