# Monitoring Dashboard Troubleshooting

## Issue: Dashboard Shows URL But No Data

If the dashboard loads but shows "Loading..." or error messages instead of data, follow these steps:

### Step 1: Check if API Server is Running

The dashboard needs the API server to be running. Check:

```bash
# Test if API is responding
curl http://localhost:8000/api/v1/health

# Should return:
# {"status":"healthy","version":"2.0.0"}
```

**If this fails:**
- Start the API server: `python run.py`
- Or check if it's running on a different port

### Step 2: Fix CORS Configuration

The dashboard is served from `http://localhost:8080` (via `python -m http.server`), but the API defaults to allowing only `http://localhost:3000`.

**Solution:** Add `http://localhost:8080` to your CORS origins in `.env`:

```bash
# In your .env file, update CORS_ORIGINS:
CORS_ORIGINS=http://localhost:3000,http://localhost:8000,http://localhost:8080
```

**Then restart your API server** for the changes to take effect.

### Step 3: Check Browser Console

Open browser developer tools (F12) and check the Console tab for errors:

- **CORS errors**: "Access to fetch at ... has been blocked by CORS policy"
  - Fix: Update CORS_ORIGINS as shown in Step 2
  
- **Network errors**: "Failed to fetch" or "NetworkError"
  - Fix: Make sure API server is running (Step 1)

- **404 errors**: "Not Found"
  - Fix: Check that the API URL in the dashboard matches your server URL

### Step 4: Verify Endpoints Work Directly

Test the endpoints the dashboard uses:

```bash
# Health endpoint
curl http://localhost:8000/api/v1/health/detailed

# Cache stats endpoint
curl http://localhost:8000/api/v1/cache/stats
```

Both should return JSON data. If they don't, the API server may not be fully started.

### Step 5: Regenerate Dashboard with Correct URL

If you're using a different API URL, regenerate the dashboard:

```bash
python scripts/setup_monitoring_dashboard.py http://localhost:8000
```

Or for production:

```bash
python scripts/setup_monitoring_dashboard.py https://api.yourdomain.com
```

## Quick Fix Checklist

- [ ] API server is running (`python run.py`)
- [ ] CORS_ORIGINS includes `http://localhost:8080` (or your dashboard origin)
- [ ] API server restarted after changing `.env`
- [ ] Browser console shows no CORS errors
- [ ] Health endpoint works: `curl http://localhost:8000/api/v1/health/detailed`

## Alternative: Serve Dashboard from API Server

Instead of using `python -m http.server`, you can serve the dashboard from the same origin as the API to avoid CORS issues:

1. Add to `app/main.py`:
```python
from fastapi.staticfiles import StaticFiles

app.mount("/monitoring", StaticFiles(directory="monitoring"), name="monitoring")
```

2. Access at: `http://localhost:8000/monitoring/dashboard.html`

This eliminates CORS issues since the dashboard and API are on the same origin.

## Still Having Issues?

1. Check the browser console (F12) for specific error messages
2. Verify API server logs for errors
3. Test endpoints directly with `curl` or Postman
4. Ensure Redis and Database are running (for detailed health check)

