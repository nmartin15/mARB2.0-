# Quick Database Fix

## Issue
The server was trying to connect to PostgreSQL with user "postgres" which doesn't exist on your system.

## Fix Applied
Updated `.env` file to use your username (`nathanmartinez`) instead of `postgres`.

**Before:**
```
DATABASE_URL=postgresql://postgres@localhost:5432/marb_risk_engine
```

**After:**
```
DATABASE_URL=postgresql://nathanmartinez@localhost:5432/marb_risk_engine
```

## Verify Database Connection

Test the connection:
```bash
psql -U nathanmartinez -d marb_risk_engine -c "SELECT 1;"
```

## Run Migrations (if needed)

If tables don't exist yet:
```bash
source venv/bin/activate
alembic upgrade head
```

## Start Server

Now you can start the server:
```bash
./start_server.sh
```

Or manually:
```bash
source venv/bin/activate
python run.py
```

## Alternative: Use SQLite for Testing

If you prefer SQLite (no setup needed), update `.env`:
```
DATABASE_URL=sqlite:///./test.db
```

Note: SQLite is fine for development/testing but PostgreSQL is recommended for production.

