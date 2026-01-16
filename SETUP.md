# Setup Guide

## Quick Start

1. **Install dependencies** (already done):
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your database and Redis URLs
   ```

3. **Set up database**:
   ```bash
   # Make sure PostgreSQL is running
   alembic upgrade head
   ```

4. **Start services**:

   **Terminal 1 - Redis:**
   ```bash
   redis-server
   ```

   **Terminal 2 - Celery Worker:**
   ```bash
   source venv/bin/activate
   celery -A app.services.queue.tasks worker --loglevel=info
   ```

   **Terminal 3 - FastAPI Server:**
   ```bash
   source venv/bin/activate
   python run.py
   # or: ./start.sh
   ```

5. **Access the API**:
   - API: http://localhost:8000
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## Environment Variables

Required in `.env`:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_HOST` - Redis host (default: localhost)
- `REDIS_PORT` - Redis port (default: 6379)
- `JWT_SECRET_KEY` - Secret key for JWT tokens (min 32 chars)
- `ENCRYPTION_KEY` - Encryption key (32 characters)

Optional (for error tracking):
- `SENTRY_DSN` - Sentry DSN for error tracking (see [SENTRY_SETUP.md](SENTRY_SETUP.md))
- `SENTRY_ENVIRONMENT` - Environment name (development, staging, production)
- `SENTRY_RELEASE` - Release version identifier

Optional (for memory monitoring):
- `MEMORY_WARNING_THRESHOLD_MB` - Process memory warning threshold (default: 512)
- `MEMORY_CRITICAL_THRESHOLD_MB` - Process memory critical threshold (default: 1024)
- `MEMORY_DELTA_WARNING_MB` - Memory increase warning threshold (default: 256)
- `MEMORY_DELTA_CRITICAL_MB` - Memory increase critical threshold (default: 512)
- `SYSTEM_MEMORY_WARNING_PCT` - System memory warning percentage (default: 75.0)
- `SYSTEM_MEMORY_CRITICAL_PCT` - System memory critical percentage (default: 90.0)

See [MEMORY_MONITORING.md](MEMORY_MONITORING.md) for detailed configuration.

## Database Setup

1. Create PostgreSQL database:
   ```sql
   CREATE DATABASE marb_risk_engine;
   ```

2. Update `DATABASE_URL` in `.env`:
   ```
   DATABASE_URL=postgresql://username:password@localhost:5432/marb_risk_engine
   ```

3. Run migrations:
   ```bash
   alembic upgrade head
   ```

## Testing

```bash
# Run tests
pytest

# Test EDI upload
curl -X POST "http://localhost:8000/api/v1/claims/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_837.txt"
```

## Troubleshooting

**Import errors in IDE:**
- Select Python interpreter: `Cmd+Shift+P` → "Python: Select Interpreter"
- Choose: `./venv/bin/python`

**Database connection errors:**
- Verify PostgreSQL is running
- Check `DATABASE_URL` in `.env`
- Ensure database exists

**Redis connection errors:**
- Verify Redis is running: `redis-cli ping`
- Check `REDIS_HOST` and `REDIS_PORT` in `.env`

