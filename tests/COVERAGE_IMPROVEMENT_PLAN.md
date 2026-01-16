# Test Coverage Improvement Plan

## Overview

This document outlines the plan to improve test coverage for modules identified as having low coverage in the `coverage.xml` report.

## Current Status

Based on `coverage.xml` analysis, the overall coverage is **34.83%** (1481 lines covered out of 4252 total lines).

## Priority Modules for Testing

### Critical Priority (<30% coverage)

1. **`services/queue/tasks.py`** - 7.9% coverage
   - Status: ✅ Has existing tests (`test_tasks.py`)
   - Action: Expand tests to cover more edge cases and error paths

2. **`services/episodes/linker.py`** - 13.2% coverage
   - Status: ✅ Has existing tests (`test_episode_linker.py`)
   - Action: Verify tests are comprehensive

3. **`services/learning/pattern_detector.py`** - 11.2% coverage
   - Status: ⚠️ Needs tests
   - Action: Create comprehensive tests

4. **`services/edi/transformer.py`** - 11.0% coverage
   - Status: ✅ Has existing tests (`test_transformer.py`)
   - Action: Expand tests to cover more edge cases

5. **`services/risk/scorer.py`** - 16.0% coverage
   - Status: ✅ Has existing tests (`test_risk_scorer_expanded.py`)
   - Action: Verify tests are comprehensive

6. **`api/middleware/rate_limit.py`** - 21.3% coverage
   - Status: ✅ **NEW** - Created `test_rate_limit.py`
   - Action: Tests created, ready for execution

7. **`utils/cache.py`** - 29.3% coverage
   - Status: ✅ **NEW** - Created `test_cache.py`
   - Action: Tests created, ready for execution

8. **`config/sentry.py`** - 28.5% coverage
   - Status: ✅ **NEW** - Created `test_sentry.py`
   - Action: Tests created, ready for execution

### High Priority (30-50% coverage)

1. **`api/routes/claims.py`** - 28.6% coverage
   - Status: ✅ Has existing tests (`test_claims_api.py`)
   - Action: Expand tests to cover more edge cases and error paths

2. **`api/routes/episodes.py`** - 29.5% coverage
   - Status: ✅ Has existing tests (`test_episodes_api.py`)
   - Action: Expand tests to cover more edge cases

3. **`api/routes/remits.py`** - 27.5% coverage
   - Status: ✅ Has existing tests (`test_remits_api.py`)
   - Action: Expand tests to cover more edge cases

4. **`api/routes/health.py`** - 34.3% coverage
   - Status: ✅ Has existing tests (`test_health_api.py`)
   - Action: Expand tests

5. **`api/routes/risk.py`** - 36.1% coverage
   - Status: ✅ Has existing tests (`test_risk_api.py`)
   - Action: Expand tests

6. **`api/routes/websocket.py`** - 41.2% coverage
   - Status: ✅ Has existing tests (`test_websocket_api.py`)
   - Action: Expand tests

7. **`api/routes/learning.py`** - 43.9% coverage
   - Status: ⚠️ Needs tests
   - Action: Create tests

8. **`api/middleware/auth.py`** - 41.9% coverage
   - Status: ⚠️ Needs tests
   - Action: Create tests

9. **`api/middleware/auth_middleware.py`** - 47.4% coverage
   - Status: ⚠️ Needs tests
   - Action: Create tests

10. **`api/middleware/audit.py`** - 52.6% coverage
    - Status: ⚠️ Needs tests
    - Action: Create tests

11. **`utils/memory_monitor.py`** - 25.8% coverage
    - Status: ✅ Has existing tests (`test_memory_monitor.py`)
    - Action: Expand tests

12. **`utils/notifications.py`** - 31.8% coverage
    - Status: ⚠️ Needs tests
    - Action: Create tests

## New Test Files Created

### 1. `test_rate_limit.py` ✅
- **Coverage Target**: Rate limiting middleware
- **Tests**: 15+ tests covering:
  - Rate limit enforcement (per minute and per hour)
  - Health endpoint exclusion
  - IP tracking (X-Forwarded-For, X-Real-IP, client.host)
  - Rate limit headers
  - Test mode disabling
  - Error message formatting
  - Multiple IP tracking

### 2. `test_cache.py` ✅
- **Coverage Target**: Cache utilities
- **Tests**: 40+ tests covering:
  - Cache get/set/delete operations
  - TTL handling
  - Cache statistics
  - Error handling
  - Pattern deletion
  - Namespace clearing
  - @cached decorator
  - Cache key helpers

### 3. `test_sentry.py` ✅
- **Coverage Target**: Sentry configuration
- **Tests**: 25+ tests covering:
  - SentrySettings configuration
  - init_sentry function
  - filter_sensitive_data function
  - capture_exception function
  - capture_message function
  - set_user_context function
  - clear_user_context function
  - add_breadcrumb function
  - Error handling and edge cases

## Next Steps

### Immediate Actions

1. **Run new tests** to verify they work correctly:
   ```bash
   pytest tests/test_rate_limit.py -v
   pytest tests/test_cache.py -v
   pytest tests/test_sentry.py -v
   ```

2. **Generate updated coverage report**:
   ```bash
   pytest tests/ --cov=app --cov-report=xml --cov-report=html
   ```

3. **Review coverage improvements** and identify remaining gaps

### Short-term Actions

1. **Create tests for remaining high-priority modules**:
   - `api/routes/learning.py`
   - `api/middleware/auth.py`
   - `api/middleware/auth_middleware.py`
   - `api/middleware/audit.py`
   - `utils/notifications.py`
   - `services/learning/pattern_detector.py`

2. **Expand existing tests** for modules with partial coverage:
   - Add more edge case tests
   - Add error handling tests
   - Add integration tests

### Long-term Actions

1. **Maintain 80%+ coverage** for all critical modules
2. **Set up coverage gates** in CI/CD pipeline
3. **Regular coverage reviews** as part of code review process

## Expected Coverage Improvements

After implementing the new tests:

- **Rate Limit Middleware**: 21.3% → 80%+ (estimated)
- **Cache Utilities**: 29.3% → 80%+ (estimated)
- **Sentry Config**: 28.5% → 80%+ (estimated)
- **Overall Coverage**: 34.83% → 45%+ (estimated)

## Test Execution

### Run all new tests
```bash
pytest tests/test_rate_limit.py tests/test_cache.py tests/test_sentry.py -v
```

### Run with coverage
```bash
pytest tests/test_rate_limit.py tests/test_cache.py tests/test_sentry.py --cov=app.api.middleware.rate_limit --cov=app.utils.cache --cov=app.config.sentry --cov-report=term-missing
```

### Run all tests
```bash
pytest tests/ -v --cov=app --cov-report=html
```

## Notes

- Some modules show discrepancies between `coverage.xml` and `FINAL_COVERAGE_REPORT.md`
- The `coverage.xml` may be outdated - regenerate after running new tests
- Focus on critical business logic and error handling paths
- Use mocking to isolate units and avoid external dependencies

