# mARB 2.0 - Troubleshooting Guide

## Quick Diagnostics

### Check Service Status

```bash
# Check API server
curl http://localhost:8000/api/v1/health

# Check Celery worker
celery -A app.services.queue.tasks inspect active

# Check Redis
redis-cli ping  # Should return: PONG

# Check PostgreSQL
psql -U marb_user -d marb_risk_engine -c "SELECT 1;"
```

### Check Logs

```bash
# Application logs (if file logging enabled)
tail -f logs/app.log

# Systemd service logs (production)
sudo journalctl -u marb2.0.service -f
sudo journalctl -u marb2.0-celery.service -f

# nginx logs (production)
sudo tail -f /var/log/nginx/marb2.0_access.log
sudo tail -f /var/log/nginx/marb2.0_error.log
```

---

## Common Issues

### API Server Won't Start

#### Issue: Port Already in Use

**Symptoms**:
```
Error: [Errno 48] Address already in use
```

**Solutions**:
1. Find process using port 8000:
   ```bash
   lsof -i :8000
   ```
2. Kill the process or use a different port:
   ```bash
   uvicorn app.main:app --port 8001
   ```

#### Issue: Database Connection Error

**Symptoms**:
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solutions**:
1. Verify PostgreSQL is running:
   ```bash
   sudo systemctl status postgresql
   # Or: pg_isready
   ```
2. Check database URL in `.env`:
   ```bash
   echo $DATABASE_URL
   ```
3. Test connection manually:
   ```bash
   psql $DATABASE_URL -c "SELECT 1;"
   ```
4. Verify database exists:
   ```bash
   psql -U postgres -l | grep marb_risk_engine
   ```

#### Issue: Missing Environment Variables

**Symptoms**:
```
KeyError: 'DATABASE_URL'
```

**Solutions**:
1. Ensure `.env` file exists:
   ```bash
   ls -la .env
   ```
2. Copy from example if missing:
   ```bash
   cp .env.example .env
   ```
3. Verify required variables are set:
   ```bash
   grep -E "DATABASE_URL|REDIS_HOST|JWT_SECRET_KEY" .env
   ```

#### Issue: Import Errors

**Symptoms**:
```
ModuleNotFoundError: No module named 'app'
```

**Solutions**:
1. Ensure virtual environment is activated:
   ```bash
   source venv/bin/activate
   which python  # Should show venv path
   ```
2. Verify dependencies are installed:
   ```bash
   pip list | grep fastapi
   ```
3. Reinstall dependencies if needed:
   ```bash
   pip install -r requirements.txt
   ```

---

### Celery Worker Issues

#### Issue: Celery Worker Won't Start

**Symptoms**:
```
celery: error: unrecognized arguments: worker
```

**Solutions**:
1. Verify Celery is installed:
   ```bash
   pip list | grep celery
   ```
2. Check Celery app configuration:
   ```bash
   python -c "from app.services.queue.tasks import celery_app; print(celery_app)"
   ```

#### Issue: Tasks Not Processing

**Symptoms**: Tasks queued but not executing

**Solutions**:
1. Check worker is running:
   ```bash
   celery -A app.services.queue.tasks inspect active
   ```
2. Check Redis connection:
   ```bash
   redis-cli ping
   ```
3. Verify Redis URL in `.env`:
   ```bash
   grep REDIS .env
   ```
4. Check worker logs for errors:
   ```bash
   celery -A app.services.queue.tasks worker --loglevel=info
   ```

#### Issue: Task Failures

**Symptoms**: Tasks failing with errors

**Solutions**:
1. Check task logs:
   ```bash
   celery -A app.services.queue.tasks events
   ```
2. Use Flower for monitoring:
   ```bash
   celery -A app.services.queue.tasks flower
   # Visit http://localhost:5555
   ```
3. Check database connection in tasks (tasks use separate DB sessions)

---

### Database Issues

#### Issue: Migration Errors

**Symptoms**:
```
alembic.util.exc.CommandError: Target database is not up to date
```

**Solutions**:
1. Check current migration version:
   ```bash
   alembic current
   ```
2. View migration history:
   ```bash
   alembic history
   ```
3. Apply migrations:
   ```bash
   alembic upgrade head
   ```
4. If stuck, check migration status:
   ```bash
   psql $DATABASE_URL -c "SELECT * FROM alembic_version;"
   ```

#### Issue: Connection Pool Exhausted

**Symptoms**:
```
QueuePool limit of size 10 overflow 20 reached
```

**Solutions**:
1. Increase pool size in `app/config/database.py`:
   ```python
   pool_size=20,
   max_overflow=40,
   ```
2. Check for connection leaks (unclosed sessions)
3. Restart application to reset pool

#### Issue: Table Not Found

**Symptoms**:
```
sqlalchemy.exc.ProgrammingError: relation "claims" does not exist
```

**Solutions**:
1. Verify migrations have been applied:
   ```bash
   alembic current
   alembic upgrade head
   ```
2. Check tables exist:
   ```bash
   psql $DATABASE_URL -c "\dt"
   ```
3. Re-run migrations if needed:
   ```bash
   alembic downgrade base
   alembic upgrade head
   ```

---

### EDI Parsing Issues

#### Issue: File Upload Fails

**Symptoms**: 400 or 500 error on file upload

**Solutions**:
1. Check file format (should be text/EDI):
   ```bash
   file your_file.txt
   ```
2. Verify file encoding (should be UTF-8):
   ```bash
   file -bi your_file.txt
   ```
3. Check file size (very large files may timeout)
4. Review error response for specific issue

#### Issue: Claims Not Extracted

**Symptoms**: File processes but no claims created

**Solutions**:
1. Verify file is valid 837 format:
   ```bash
   grep "^CLM" file.txt | wc -l  # Should have CLM segments
   ```
2. Check parsing warnings in API response
3. Review application logs for parsing errors
4. Verify file has required segments (ISA, GS, ST, CLM)

#### Issue: Incomplete Claims

**Symptoms**: Claims marked as `is_incomplete: true`

**Solutions**:
1. Check parsing warnings:
   ```bash
   curl "http://localhost:8000/api/v1/claims/1" | jq '.parsing_warnings'
   ```
2. Review missing segments in warnings
3. Verify file has all required segments
4. Check format matches expected structure

#### Issue: Remittances Not Linking

**Symptoms**: Remittances processed but episodes not created

**Solutions**:
1. Verify claim control numbers match:
   ```bash
   # Get claim control number
   curl "http://localhost:8000/api/v1/claims/1" | jq '.claim_control_number'
   
   # Get remittance claim control number
   curl "http://localhost:8000/api/v1/remits/1" | jq '.claim_control_number'
   ```
2. Manually trigger linking:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/remits/1/link"
   ```
3. Check episode linker logs for matching issues
4. Verify patient control numbers match if using patient/date matching

---

### Redis/Caching Issues

#### Issue: Redis Connection Error

**Symptoms**:
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solutions**:
1. Verify Redis is running:
   ```bash
   redis-cli ping  # Should return: PONG
   ```
2. Check Redis configuration:
   ```bash
   grep REDIS .env
   ```
3. Test connection:
   ```bash
   redis-cli -h localhost -p 6379 ping
   ```
4. Check Redis logs:
   ```bash
   # macOS
   tail -f /usr/local/var/log/redis.log
   
   # Linux
   sudo journalctl -u redis -f
   ```

#### Issue: Cache Not Working

**Symptoms**: Responses not cached, always hitting database

**Solutions**:
1. Verify Redis is connected:
   ```bash
   redis-cli ping
   ```
2. Check cache statistics:
   ```bash
   curl "http://localhost:8000/api/v1/cache/stats"
   ```
3. Verify cache TTL configuration in `app/config/cache_ttl.py`
4. Check cache key generation in `app/utils/cache.py`

---

### Performance Issues

#### Issue: Slow API Responses

**Symptoms**: API responses taking >1 second

**Solutions**:
1. Check database query performance:
   ```bash
   # Enable query logging in database config
   # Review slow queries
   ```
2. Verify indexes exist:
   ```bash
   psql $DATABASE_URL -c "\d+ claims"  # Check indexes
   ```
3. Check cache hit rate:
   ```bash
   curl "http://localhost:8000/api/v1/cache/stats" | jq '.overall.hit_rate'
   ```
4. Review application logs for slow operations
5. Consider increasing database connection pool

#### Issue: High Memory Usage

**Symptoms**: Application using excessive memory, memory threshold warnings in logs

**Solutions**:
1. **Check memory monitoring logs**:
   ```bash
   # Look for memory warnings in logs
   grep "Memory checkpoint" logs/app.log | jq '.thresholds_exceeded'
   grep "CRITICAL.*memory" logs/app.log
   ```

2. **Review memory checkpoints**:
   - Memory monitoring automatically tracks usage at key checkpoints
   - Check logs for operations with high `memory_delta_mb`
   - Look for `thresholds_exceeded` in checkpoint logs
   - See [MEMORY_MONITORING.md](MEMORY_MONITORING.md) for details

3. **Adjust memory thresholds** (if warnings are false positives):
   ```bash
   # In .env file
   MEMORY_WARNING_THRESHOLD_MB=1024
   MEMORY_CRITICAL_THRESHOLD_MB=2048
   MEMORY_DELTA_WARNING_MB=512
   MEMORY_DELTA_CRITICAL_MB=1024
   ```

4. **Investigate high memory operations**:
   - Check EDI file processing (large files use more memory)
   - Review ML model loading (models can be memory-intensive)
   - Monitor Celery worker memory usage
   - Check for memory leaks (unclosed sessions, large cached objects)

5. **Optimize memory usage**:
   - Reduce batch sizes for EDI processing
   - Process files in smaller chunks
   - Increase available system memory
   - Check for memory leaks in custom extractors
   - See [PERFORMANCE_OPTIMIZATION_EDI.md](PERFORMANCE_OPTIMIZATION_EDI.md) for optimization tips
4. Consider processing files in chunks for very large files

#### Issue: Database Connection Timeouts

**Symptoms**: Database connection timeouts under load

**Solutions**:
1. Increase connection pool size
2. Check database max connections:
   ```bash
   psql $DATABASE_URL -c "SHOW max_connections;"
   ```
3. Review connection pool configuration
4. Consider connection pooling at database level (PgBouncer)

---

### Authentication/Authorization Issues

#### Issue: 401 Unauthorized Errors

**Symptoms**: API returns 401 even with valid token

**Solutions**:
1. Verify `REQUIRE_AUTH` setting:
   ```bash
   grep REQUIRE_AUTH .env
   ```
2. Check JWT secret key matches:
   ```bash
   grep JWT_SECRET_KEY .env
   ```
3. Verify token format (should be `Bearer <token>`)
4. Check token expiration
5. Review authentication middleware logs

#### Issue: Rate Limiting Too Aggressive

**Symptoms**: 429 errors even with normal usage

**Solutions**:
1. Adjust rate limits in `.env`:
   ```bash
   RATE_LIMIT_PER_MINUTE=120
   RATE_LIMIT_PER_HOUR=2000
   ```
2. Check rate limit headers in responses
3. Review rate limit middleware configuration
4. Consider per-user rate limiting instead of per-IP

---

### WebSocket Issues

#### Issue: WebSocket Connection Fails

**Symptoms**: Cannot connect to `/ws/notifications`

**Solutions**:
1. Verify WebSocket endpoint is accessible:
   ```bash
   curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
     http://localhost:8000/ws/notifications
   ```
2. Check nginx configuration (if using reverse proxy):
   - WebSocket requires special nginx config
   - See `deployment/nginx.conf.example`
3. Verify CORS settings allow WebSocket connections
4. Check firewall settings

#### Issue: WebSocket Disconnects Frequently

**Symptoms**: WebSocket connections drop unexpectedly

**Solutions**:
1. Check for timeout settings (nginx, load balancer)
2. Implement WebSocket ping/pong in client
3. Review connection manager logs
4. Check for network issues

---

### Production Deployment Issues

#### Issue: Service Won't Start on Boot

**Symptoms**: Services not starting after server reboot

**Solutions**:
1. Verify services are enabled:
   ```bash
   sudo systemctl is-enabled marb2.0.service
   sudo systemctl is-enabled marb2.0-celery.service
   ```
2. Enable if not:
   ```bash
   sudo systemctl enable marb2.0.service
   sudo systemctl enable marb2.0-celery.service
   ```
3. Check service dependencies in systemd unit files
4. Verify database and Redis start before application

#### Issue: SSL Certificate Errors

**Symptoms**: SSL certificate validation failures

**Solutions**:
1. Verify certificate is valid:
   ```bash
   openssl x509 -in /etc/ssl/certs/yourdomain.com.crt -text -noout
   ```
2. Check certificate expiration:
   ```bash
   certbot certificates
   ```
3. Renew if expired:
   ```bash
   sudo certbot renew
   ```
4. Verify nginx SSL configuration

#### Issue: nginx 502 Bad Gateway

**Symptoms**: nginx returns 502 errors

**Solutions**:
1. Verify application is running:
   ```bash
   sudo systemctl status marb2.0.service
   ```
2. Check application is listening on correct port:
   ```bash
   netstat -tlnp | grep 8000
   ```
3. Review nginx error logs:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```
4. Verify nginx can connect to application (check firewall)

---

## Debugging Tips

### Enable Debug Logging

Set in `.env`:
```bash
LOG_LEVEL=debug
ENVIRONMENT=development
```

### Database Query Logging

Enable SQLAlchemy echo in `app/config/database.py`:
```python
engine = create_engine(
    database_url,
    echo=True,  # Enable query logging
)
```

### Test Individual Components

```bash
# Test database connection
python -c "from app.config.database import SessionLocal; db = SessionLocal(); print('DB OK')"

# Test Redis connection
python -c "from app.config.redis import get_redis; r = get_redis(); print(r.ping())"

# Test EDI parser
python -c "from app.services.edi.parser import EDIParser; p = EDIParser(); print('Parser OK')"
```

### Use Interactive Python Shell

```bash
source venv/bin/activate
python
>>> from app.main import app
>>> from app.config.database import SessionLocal
>>> db = SessionLocal()
>>> # Test queries here
```

---

## Getting Help

### Information to Collect

When reporting issues, include:

1. **Error Messages**: Full error traceback
2. **Logs**: Relevant log entries
3. **Configuration**: Environment variables (sanitized, no secrets)
4. **Steps to Reproduce**: Detailed steps
5. **Environment**: OS, Python version, dependencies versions
6. **File Samples**: Sample EDI files (sanitized, no PHI)

### Useful Commands

```bash
# System information
python --version
pip list
uname -a

# Service status
sudo systemctl status marb2.0.service
sudo systemctl status marb2.0-celery.service
sudo systemctl status postgresql
sudo systemctl status redis

# Database information
psql $DATABASE_URL -c "SELECT version();"
psql $DATABASE_URL -c "\dt"  # List tables
psql $DATABASE_URL -c "\di"  # List indexes

# Application information
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/cache/stats
```

---

## Prevention

### Regular Maintenance

1. **Monitor Logs**: Regularly review application logs
2. **Check Disk Space**: Ensure adequate disk space for logs and database
3. **Update Dependencies**: Keep dependencies up to date (security patches)
4. **Backup Database**: Regular database backups
5. **Monitor Performance**: Track response times and resource usage

### Health Checks

Set up monitoring for:
- API health endpoint (`/api/v1/health`)
- Database connectivity
- Redis connectivity
- Celery worker status
- Disk space
- Memory usage

### Best Practices

1. **Use Environment Variables**: Never hardcode configuration
2. **Validate Input**: Always validate EDI files before processing
3. **Handle Errors Gracefully**: Implement proper error handling
4. **Log Appropriately**: Log errors with context, avoid logging PHI
5. **Test Changes**: Test in development before production

---

**Last Updated**: 2024-12-20  
**Version**: 2.0.0

