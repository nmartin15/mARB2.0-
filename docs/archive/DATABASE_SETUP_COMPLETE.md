# Database Setup Complete! ✅

## What Was Done

1. ✅ **PostgreSQL Installed** - PostgreSQL 14 installed via Homebrew
2. ✅ **PostgreSQL Service Started** - Running as a background service
3. ✅ **Database Created** - `marb_risk_engine` database exists
4. ✅ **Migrations Run** - All database tables created
5. ✅ **835 Processing Tested** - Successfully saved 8 remittances to database

## Current Configuration

- **Database**: `marb_risk_engine`
- **User**: `nathanmartinez`
- **Connection**: `postgresql://nathanmartinez@localhost:5432/marb_risk_engine`
- **Status**: ✅ Working

## Test Results

The 835 processing pipeline was successfully tested:
- ✅ Parsed 8 remittances from sample file
- ✅ Extracted all claim data, adjustments, and service lines
- ✅ Saved all 8 remittances to database
- ✅ Payment amounts, dates, and adjustment codes correctly stored

## Next Steps

### 1. Make PostgreSQL PATH Permanent (Optional)

Add PostgreSQL to your PATH in `~/.zshrc` or `~/.bash_profile`:

```bash
export PATH="/usr/local/opt/postgresql@14/bin:$PATH"
```

Then reload: `source ~/.zshrc`

### 2. Update .env File (Recommended)

The `.env` file should have `DATABASE_URL` set. To ensure it's loaded automatically, you can:

1. Install python-dotenv (already done): `pip install python-dotenv`
2. Make sure your application loads it (FastAPI should handle this)

### 3. Start All Services

**Terminal 1 - Redis:**
```bash
redis-server
```

**Terminal 2 - Celery Worker:**
```bash
source venv/bin/activate
export PATH="/usr/local/opt/postgresql@14/bin:$PATH"
export DATABASE_URL="postgresql://nathanmartinez@localhost:5432/marb_risk_engine"
celery -A app.services.queue.tasks worker --loglevel=info
```

**Terminal 3 - FastAPI Server:**
```bash
source venv/bin/activate
export PATH="/usr/local/opt/postgresql@14/bin:$PATH"
export DATABASE_URL="postgresql://nathanmartinez@localhost:5432/marb_risk_engine"
python run.py
```

### 4. Test Full Upload Flow

Once all services are running, test the full upload:

```bash
python test_835_upload.py
```

Or use curl:

```bash
curl -X POST "http://localhost:8000/api/v1/remits/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@samples/sample_835.txt"
```

## Useful Commands

**Check PostgreSQL status:**
```bash
brew services list | grep postgresql
```

**Start PostgreSQL:**
```bash
brew services start postgresql@14
```

**Stop PostgreSQL:**
```bash
brew services stop postgresql@14
```

**Connect to database:**
```bash
/usr/local/opt/postgresql@14/bin/psql -U nathanmartinez -d marb_risk_engine
```

**View remittances:**
```sql
SELECT id, remittance_control_number, claim_control_number, payment_amount, status 
FROM remittances 
ORDER BY created_at DESC;
```

## Troubleshooting

**If you get "role does not exist" error:**
- Make sure `DATABASE_URL` in `.env` uses your actual username (`nathanmartinez`)
- Or create the role: `/usr/local/opt/postgresql@14/bin/createuser -U postgres nathanmartinez`

**If PostgreSQL won't start:**
```bash
brew services restart postgresql@14
```

**If migrations fail:**
```bash
export DATABASE_URL="postgresql://nathanmartinez@localhost:5432/marb_risk_engine"
alembic upgrade head
```

