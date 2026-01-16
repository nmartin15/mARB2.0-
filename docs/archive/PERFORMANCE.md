# Performance Optimization Guide

## Overview

This document outlines performance optimizations implemented in mARB 2.0 and best practices for maintaining high performance.

## Caching Strategy

### Redis Caching

mARB 2.0 uses Redis for caching frequently accessed data to reduce database load and improve response times.

### Cache Keys

All cache keys use a namespace prefix (`marb:`) and follow a consistent pattern:

- **Claims**: `marb:claim:{claim_id}`
- **Risk Scores**: `marb:risk_score:{claim_id}`
- **Payers**: `marb:payer:{payer_id}`
- **Remittances**: `marb:remittance:{remittance_id}`
- **Episodes**: `marb:episode:{episode_id}`

### Cache TTL (Time To Live)

Different data types have different cache durations based on how frequently they change:

| Data Type | TTL | Reason |
|-----------|-----|--------|
| Risk Scores | 1 hour | Recalculated periodically, but stable for short term |
| Claims | 30 minutes | May be updated during processing |
| Payer Rules | 24 hours | Rarely change, long-lived configuration |
| Remittances | 1 hour | Stable after processing |
| Episodes | 1 hour | Stable after linking |

### Cache Invalidation

Cache is automatically invalidated when:

1. **Risk scores are recalculated** - Old cached score is deleted, new one is cached
2. **Claims are updated** - Claim cache is invalidated (handled by TTL)
3. **Payer rules are updated** - Payer cache should be manually invalidated

### Using the Cache

#### Basic Usage

```python
from app.utils.cache import cache, risk_score_cache_key

# Get from cache
cache_key = risk_score_cache_key(claim_id)
cached_value = cache.get(cache_key)
if cached_value:
    return cached_value

# Set in cache
cache.set(cache_key, result, ttl_seconds=3600)
```

#### Using the Decorator

```python
from app.utils.cache import cached

@cached(ttl_seconds=3600, key_prefix="risk_score")
def calculate_risk_score(claim_id: int):
    # Expensive calculation
    return score
```

### Cache Utilities

The `app/utils/cache.py` module provides:

- `Cache` class - Main caching interface
- `cached` decorator - Automatic caching decorator
- `cache_key()` - Helper to create cache keys
- Key generators: `claim_cache_key()`, `risk_score_cache_key()`, etc.

## Database Optimization

### Connection Pooling

Database connection pooling is configured in `app/config/database.py`:

- **Pool size**: 10 connections
- **Max overflow**: 20 connections
- **Pool recycle**: 3600 seconds (1 hour)

### Query Optimization

#### Use Eager Loading

Avoid N+1 queries by using `joinedload()`:

```python
from sqlalchemy.orm import joinedload

# Bad: N+1 queries
claims = db.query(Claim).all()
for claim in claims:
    print(claim.claim_lines)  # Separate query for each claim

# Good: Single query with join
claims = db.query(Claim).options(joinedload(Claim.claim_lines)).all()
for claim in claims:
    print(claim.claim_lines)  # Already loaded
```

#### Use Indexes

Ensure database indexes exist for frequently queried columns:

- `claim_control_number`
- `patient_control_number`
- `payer_id`
- `provider_id`
- `service_date`
- `created_at`

#### Limit Results

Always use pagination for list endpoints:

```python
@router.get("/claims")
async def get_claims(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    claims = db.query(Claim).offset(skip).limit(limit).all()
    return claims
```

## Async Processing

### Celery Tasks

Long-running operations should be queued as Celery tasks:

- **EDI file processing** - Parsing large files
- **Risk score calculation** - Complex ML inference
- **Episode linking** - Matching claims to remittances
- **Pattern detection** - Analyzing historical data

### Task Configuration

Tasks are configured in `app/config/celery.py`:

- **Time limit**: 30 minutes
- **Soft time limit**: 25 minutes
- **Worker prefetch**: 1 (prevents task hoarding)
- **Max tasks per child**: 1000 (prevents memory leaks)

## API Performance

### Rate Limiting

Rate limiting prevents abuse and ensures fair resource usage:

- **Per minute**: 60 requests (configurable)
- **Per hour**: 1000 requests (configurable)

### Response Compression

Consider enabling gzip compression in nginx:

```nginx
gzip on;
gzip_types text/plain application/json application/javascript;
gzip_min_length 1000;
```

### HTTP/2

Enable HTTP/2 in nginx for better performance:

```nginx
listen 443 ssl http2;
```

## Monitoring Performance

### Key Metrics to Monitor

1. **Response Times**
   - Average response time
   - P95/P99 response times
   - Slowest endpoints

2. **Memory Usage** ⭐ *Enhanced Monitoring Available*
   - Process memory usage (RSS)
   - Memory deltas during operations
   - Peak memory tracking
   - System memory utilization
   - Automatic threshold warnings
   - See [MEMORY_MONITORING.md](MEMORY_MONITORING.md) for details

3. **Cache Hit Rate**
   - Monitor cache hit/miss ratio
   - Target: >80% hit rate

4. **Database Performance**
   - Query execution time
   - Connection pool usage
   - Slow queries

5. **Celery Task Performance**
   - Task execution time
   - Queue depth
   - Failed tasks
   - Memory usage per task (via monitoring checkpoints)

### Logging Performance

Performance metrics are logged automatically:

```python
logger.info(
    "API response",
    method=request.method,
    path=request.url.path,
    status_code=response.status_code,
    duration=duration,  # Response time in seconds
)
```

## Best Practices

### 1. Cache Frequently Accessed Data

- Risk scores
- Payer configurations
- Claim metadata
- User sessions (if implemented)

### 2. Don't Cache Frequently Changing Data

- Real-time notifications
- Task status (use Celery result backend)
- User-specific dynamic data

### 3. Use Appropriate TTLs

- Short TTL for frequently changing data
- Long TTL for stable configuration data
- Consider data freshness requirements

### 4. Monitor Cache Performance

- Track cache hit rates
- Monitor Redis memory usage
- Set up alerts for cache failures

### 5. Optimize Database Queries

- Use indexes
- Avoid N+1 queries
- Use pagination
- Limit result sets

### 6. Profile Before Optimizing

- Measure first, optimize second
- Use tools like `cProfile` or `py-spy`
- Identify actual bottlenecks

## Troubleshooting

### High Cache Miss Rate

**Symptoms**: Low cache hit rate, high database load

**Solutions**:
- Increase TTL for stable data
- Check cache invalidation logic
- Verify Redis is running
- Check cache key consistency

### Slow Database Queries

**Symptoms**: High query execution time

**Solutions**:
- Add missing indexes
- Optimize query structure
- Use eager loading
- Consider query result caching

### Redis Memory Issues

**Symptoms**: Redis out of memory errors

**Solutions**:
- Set Redis maxmemory policy
- Reduce TTL for cached data
- Implement cache eviction
- Monitor cache key patterns

### Application Memory Issues

**Symptoms**: Memory threshold warnings in logs, high process memory usage

**Solutions**:
- **Check memory monitoring logs**: Look for "Memory checkpoint" entries with `thresholds_exceeded`
- **Review memory checkpoints**: Identify operations with high `memory_delta_mb`
- **Adjust thresholds**: Configure `MEMORY_*_THRESHOLD_MB` in `.env` if needed
- **Optimize operations**: Reduce batch sizes, process files in chunks
- **Monitor system memory**: Check `system_memory_percent` in checkpoint logs
- See [MEMORY_MONITORING.md](MEMORY_MONITORING.md) for detailed troubleshooting

### Celery Task Backlog

**Symptoms**: Tasks queuing up, slow processing

**Solutions**:
- Increase worker concurrency
- Add more Celery workers
- Optimize task execution
- Check for stuck tasks

## Performance Testing

### Load Testing

Use tools like `locust` or `k6` to load test the API:

```bash
# Install locust
pip install locust

# Run load test
locust -f load_test.py --host=http://localhost:8000
```

### Benchmarking

Benchmark key endpoints:

```bash
# Using Apache Bench
ab -n 1000 -c 10 http://localhost:8000/api/v1/health

# Using wrk
wrk -t4 -c100 -d30s http://localhost:8000/api/v1/health
```

## Future Optimizations

Potential areas for further optimization:

1. **Database Query Result Caching** - Cache complex query results
2. **CDN Integration** - For static assets
3. **Database Read Replicas** - For read-heavy workloads
4. **Redis Cluster** - For high availability
5. **Connection Pooling Tuning** - Based on actual load
6. **Response Caching** - HTTP-level caching
7. **GraphQL** - For flexible data fetching

## Resources

- [FastAPI Performance](https://fastapi.tiangolo.com/advanced/performance/)
- [SQLAlchemy Performance](https://docs.sqlalchemy.org/en/14/faq/performance.html)
- [Redis Best Practices](https://redis.io/docs/manual/patterns/)
- [Celery Optimization](https://docs.celeryproject.org/en/stable/userguide/optimizing.html)

