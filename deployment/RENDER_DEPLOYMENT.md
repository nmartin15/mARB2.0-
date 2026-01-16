# Render Deployment Guide (Free Tier - Alternative Option)

**Why Render?**
- ✅ **FREE** tier available
- ✅ **Proper HTTPS** with automatic SSL
- ✅ **PostgreSQL** included (free tier)
- ✅ **Redis** available (may need paid for production)
- ✅ **Easy Git-based deployment**
- ✅ **Production-like** environment

**Perfect for:** Staging/testing with proper HTTPS validation

---

## Step 1: Sign Up for Render

1. Go to https://render.com
2. Sign up with GitHub (recommended)
3. Free tier available (no credit card required initially)

---

## Step 2: Create PostgreSQL Database

1. In Render dashboard, click **"New +"**
2. Select **"PostgreSQL"**
3. Configure:
   - **Name**: `marb-staging-db`
   - **Database**: `marb_risk_engine`
   - **Region**: Choose closest
   - **Plan**: **Free** (for testing)
4. Click **"Create Database"**
5. Copy the **Internal Database URL** (we'll use this)

---

## Step 3: Create Redis Instance

1. Click **"New +"** → **"Redis"**
2. Configure:
   - **Name**: `marb-staging-redis`
   - **Region**: Same as database
   - **Plan**: **Free** (if available) or **Starter** ($7/mo)
3. Click **"Create Redis"**
4. Copy connection details

**Note:** Free Redis may not be available. For testing, you can:
- Use Redis Cloud free tier (separate service)
- Or skip Redis for basic testing (if app can run without it)

---

## Step 4: Create Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository: `mARB 2.0`
3. Configure:
   - **Name**: `marb-staging`
   - **Region**: Same as database
   - **Branch**: `main` (or your branch)
   - **Root Directory**: `/` (or leave default)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

---

## Step 5: Configure Environment Variables

In your Web Service → **"Environment"** tab, add:

```bash
# Database (use Render's PostgreSQL internal URL)
DATABASE_URL=<render-postgres-internal-url>?sslmode=require

# Redis (if using Render Redis)
REDIS_HOST=<render-redis-host>
REDIS_PORT=<render-redis-port>
REDIS_PASSWORD=<render-redis-password>
CELERY_BROKER_URL=redis://:<password>@<host>:<port>/0
CELERY_RESULT_BACKEND=redis://:<password>@<host>:<port>/0

# Security
JWT_SECRET_KEY=<your-generated-key>
ENCRYPTION_KEY=<your-generated-key>

# Environment
ENVIRONMENT=production
DEBUG=false
REQUIRE_AUTH=true

# CORS (update with Render domain)
CORS_ORIGINS=https://marb-staging.onrender.com

# Logging
LOG_LEVEL=info
LOG_FORMAT=json
LOG_FILE=app.log
```

**To get connection strings:**
- **PostgreSQL**: Go to PostgreSQL service → "Connections" → Copy "Internal Database URL"
- **Redis**: Go to Redis service → "Connections" → Copy connection details

---

## Step 6: Deploy

1. Render will automatically deploy on git push
2. Or click **"Manual Deploy"** → **"Deploy latest commit"**
3. Watch build logs

---

## Step 7: Get HTTPS URL

1. After deployment, Render provides: `https://marb-staging.onrender.com`
2. **Automatic HTTPS** with valid SSL certificate
3. Copy this URL

---

## Step 8: Run Production Validation

```bash
# Test HTTPS
python scripts/test_https_end_to_end.py https://marb-staging.onrender.com

# Monitor health
python scripts/monitor_health.py https://marb-staging.onrender.com
```

---

## Render Free Tier Limits

- **Web Services**: Free tier available (spins down after 15 min inactivity)
- **PostgreSQL**: 90 days free, then $7/mo (or delete/recreate)
- **Redis**: May require paid plan ($7/mo)
- **Bandwidth**: Generous free tier

**For testing/validation:**
- Free tier is perfect for initial testing
- Can recreate database every 90 days if needed
- Or pay $7-14/mo for persistent staging

---

## Comparison: Railway vs Render

| Feature | Railway | Render |
|--------|---------|--------|
| **Free Tier** | ✅ $5 credit/month | ✅ Free web service |
| **PostgreSQL** | ✅ Free | ⚠️ 90 days free |
| **Redis** | ✅ Free | ⚠️ May need paid |
| **HTTPS** | ✅ Automatic | ✅ Automatic |
| **Setup Time** | ~30 min | ~30 min |
| **Best For** | Testing | Testing |

**Recommendation:** Railway is better for free testing (more generous free tier)

---

## Next Steps

1. Choose Railway (recommended) or Render
2. Follow deployment guide
3. Get HTTPS URL
4. Run validation scripts ✅

