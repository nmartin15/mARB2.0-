# Performance Improvements - Cache & Database Optimization

This document summarizes the performance improvements implemented for mARB 2.0, including cache monitoring, TTL configuration, additional caching, database indexing, and load testing capabilities.

## Summary of Changes

### 1. Cache Statistics Tracking ✅

**Location**: `app/utils/cache.py`

Added comprehensive cache statistics tracking to monitor cache performance:
- **Hit/Miss Tracking**: Records cache hits and misses per key
- **Hit Rate Calculation**: Automatically calculates hit rates for individual keys and overall
- **Thread-Safe**: Uses locks to ensure thread-safe statistics collection
- **Statistics API**: Methods to retrieve and reset statistics

**Usage**:
```python
from app.utils.cache import cache

# Get overall statistics
stats = cache.get_stats()
# Returns: {
#   "overall": {"hits": 100, "misses": 20, "total": 120, "hit_rate": 83.33},
#   "by_key": {...}
# }

# Get statistics for specific key
stats = cache.get_stats(key="claim:123")

# Reset statistics
cache.reset_stats()  # Reset all
cache.reset_stats(key="claim:123")  # Reset specific key
```

### 2. Configurable TTL Values ✅

**Location**: `app/config/cache_ttl.py`

Created a centralized TTL configuration system:
- **Environment Variable Support**: All TTL values can be overridden via environment variables
- **Default Values**: Sensible defaults for each cache type
- **Easy Access**: Convenience functions for each cache type

**Default TTL Values**:
- Risk Score: 1 hour (3600s)
- Claim: 30 minutes (1800s)
- Payer: 24 hours (86400s)
- Remittance: 30 minutes (1800s)
- Episode: 30 minutes (1800s)
- Provider: 1 hour (3600s)
- Practice Config: 24 hours (86400s)

**Environment Variables**:
```bash
CACHE_TTL_RISK_SCORE=3600
CACHE_TTL_CLAIM=1800
CACHE_TTL_PAYER=86400
CACHE_TTL_REMITTANCE=1800
CACHE_TTL_EPISODE=1800
CACHE_TTL_PROVIDER=3600
CACHE_TTL_PRACTICE_CONFIG=86400
```

**Usage**:
```python
from app.config.cache_ttl import get_claim_ttl, get_risk_score_ttl

ttl = get_claim_ttl()  # Returns configured TTL for claims
cache.set(key, value, ttl_seconds=get_claim_ttl())
```

### 3. Additional Caching ✅

**Locations**: 
- `app/api/routes/remits.py` - Remittance caching
- `app/api/routes/episodes.py` - Episode caching

Added caching to frequently accessed endpoints:
- **Remittances**: `GET /api/v1/remits/{remit_id}` - Cached with 30-minute TTL
- **Episodes**: `GET /api/v1/episodes/{episode_id}` - Cached with 30-minute TTL

**Cache Invalidation**:
- Episodes: Cache invalidated when episode status is updated or marked complete
- Remittances: Cache invalidated via TTL (remittances are typically read-only after creation)

### 4. Cache Statistics API Endpoint ✅

**Location**: `app/api/routes/health.py`

Added monitoring endpoints for cache performance:
- **GET `/api/v1/cache/stats`**: Get cache statistics (overall or by key)
- **POST `/api/v1/cache/stats/reset`**: Reset cache statistics

**Example Response**:
```json
{
  "overall": {
    "hits": 1500,
    "misses": 200,
    "total": 1700,
    "hit_rate": 88.24
  },
  "by_key": {
    "claim:123": {
      "hits": 50,
      "misses": 5,
      "total": 55,
      "hit_rate": 90.91
    }
  }
}
```

### 5. Database Indexing ✅

**Location**: `alembic/versions/002_add_performance_indexes.py`

Created migration to add indexes on frequently queried columns:

**New Indexes**:
- `claims.payer_id` - For filtering claims by payer
- `claims.provider_id` - For filtering claims by provider
- `claims.practice_id` - For filtering claims by practice
- `claims.created_at` - For date-based queries and sorting
- `claims.payer_id + status` - Composite index for common query pattern
- `remittances.payer_id` - For filtering remittances by payer
- `remittances.created_at` - For date-based queries
- `claim_episodes.claim_id` - For finding episodes by claim
- `claim_episodes.remittance_id` - For finding episodes by remittance
- `claim_episodes.created_at` - For date-based queries
- `claim_lines.claim_id` - For finding claim lines
- `risk_scores.claim_id` - For finding risk scores
- `risk_scores.calculated_at` - For date-based queries
- `denial_patterns.payer_id` - For filtering patterns by payer

**To Apply Migration**:
```bash
source venv/bin/activate
alembic upgrade head
```

### 6. Load Testing Script ✅

**Location**: `scripts/load_test.py`

Created a comprehensive load testing script to test API performance under load.

**Features**:
- Concurrent request testing
- Multiple endpoint support
- Detailed statistics (mean, median, min, max, stddev)
- Status code distribution
- Error tracking
- Per-endpoint performance breakdown

**Usage**:
```bash
# Basic usage
python scripts/load_test.py --base-url http://localhost:8000 --concurrent 10 --requests 100

# Test specific endpoints
python scripts/load_test.py --endpoints /api/v1/health /api/v1/claims --concurrent 20 --requests 200

# High load test
python scripts/load_test.py --concurrent 50 --requests 1000
```

**Output Example**:
```
LOAD TEST SUMMARY
================================================================================
Total Requests: 500
Total Errors: 0
Success Rate: 100.0%

Overall Response Times (seconds):
  Mean:   0.045s
  Median: 0.042s
  Min:    0.012s
  Max:    0.234s
  StdDev: 0.023s

Status Code Distribution:
  200: 500

Performance by Endpoint:
  /api/v1/health:
    Requests: 100
    Mean:     0.012s
    ...
```

## Monitoring Cache Performance

### 1. Check Cache Statistics

```bash
# Get overall cache statistics
curl http://localhost:8000/api/v1/cache/stats

# Get statistics for specific key
curl "http://localhost:8000/api/v1/cache/stats?key=claim:123"
```

### 2. Monitor Hit Rates

Aim for hit rates above 70-80% for frequently accessed data:
- **Risk Scores**: Should have high hit rates (80%+) since they're expensive to calculate
- **Claims**: Moderate hit rates (60-80%) depending on access patterns
- **Payers**: Very high hit rates (90%+) since payer configs rarely change

### 3. Tune TTL Values

If hit rates are low, consider:
- **Increasing TTL** for stable data (payers, practice configs)
- **Decreasing TTL** for frequently changing data (claims, remittances)
- **Monitoring** access patterns to identify optimal TTL values

## Performance Recommendations

### Cache Tuning

1. **Monitor hit rates weekly** using the cache statistics endpoint
2. **Adjust TTL values** based on actual usage patterns
3. **Review cache keys** to ensure proper namespacing
4. **Monitor Redis memory** usage to prevent evictions

### Database Optimization

1. **Run EXPLAIN ANALYZE** on slow queries to verify index usage
2. **Monitor query performance** using database logs
3. **Consider composite indexes** for multi-column WHERE clauses
4. **Review index usage** periodically and remove unused indexes

### Load Testing

1. **Run load tests regularly** (weekly/monthly) to catch performance regressions
2. **Test with realistic data volumes** matching production
3. **Monitor during load tests**:
   - Response times
   - Error rates
   - Database connection pool usage
   - Redis memory and CPU usage
4. **Gradually increase load** to find breaking points

## Next Steps

1. **Monitor cache hit rates** in production for 1-2 weeks
2. **Tune TTL values** based on observed patterns
3. **Run load tests** regularly to ensure performance doesn't degrade
4. **Review database query logs** to identify additional indexing opportunities
5. **Consider caching** additional endpoints if they show high database load

## Environment Variables

Add these to your `.env` file to customize cache TTLs:

```bash
# Cache TTL Configuration (in seconds)
CACHE_TTL_RISK_SCORE=3600      # 1 hour
CACHE_TTL_CLAIM=1800           # 30 minutes
CACHE_TTL_PAYER=86400          # 24 hours
CACHE_TTL_REMITTANCE=1800      # 30 minutes
CACHE_TTL_EPISODE=1800         # 30 minutes
CACHE_TTL_PROVIDER=3600        # 1 hour
CACHE_TTL_PRACTICE_CONFIG=86400 # 24 hours
```

## Files Modified

- `app/utils/cache.py` - Added statistics tracking
- `app/config/cache_ttl.py` - New TTL configuration module
- `app/api/routes/health.py` - Added cache statistics endpoints
- `app/api/routes/claims.py` - Updated to use TTL config
- `app/api/routes/risk.py` - Updated to use TTL config
- `app/api/routes/remits.py` - Added caching
- `app/api/routes/episodes.py` - Added caching and invalidation
- `app/services/risk/rules/payer_rules.py` - Updated to use TTL config
- `alembic/versions/002_add_performance_indexes.py` - New migration
- `scripts/load_test.py` - New load testing script

## Testing

To verify the improvements:

1. **Apply database migration**:
   ```bash
   alembic upgrade head
   ```

2. **Test cache statistics**:
   ```bash
   curl http://localhost:8000/api/v1/cache/stats
   ```

3. **Run load test**:
   ```bash
   python scripts/load_test.py --concurrent 10 --requests 100
   ```

4. **Monitor cache performance** over time using the statistics endpoint

