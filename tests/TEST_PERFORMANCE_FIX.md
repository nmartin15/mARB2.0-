# Test Performance Fix

## Problem Identified

Tests were taking extremely long to run due to several factors:

### Root Causes

1. **1,695 test functions** across 76 test files - massive test suite
2. **Coverage enabled by default** - Coverage collection adds significant overhead
3. **Performance/load tests running by default** - These tests:
   - Generate 100MB+ EDI files
   - Process large files
   - Monitor memory usage
   - Can take minutes per test
4. **No test filtering** - All tests run every time

### Impact

- Running `pytest --cov=app` could take 10+ minutes
- Development iteration was slow
- CI/CD pipelines would timeout

## Solution Applied

### 1. Updated pytest Configuration

**File:** `pyproject.toml`

**Changes:**
- **Removed coverage from default `addopts`** - Coverage is now opt-in
- **Added marker filtering** - Excludes slow/performance/load_test by default
- **Faster default test runs** - Only fast tests run by default

**Before:**
```toml
addopts = [
    "--cov=app",  # Coverage always enabled (slow)
    "--cov-report=term-missing",
    "--cov-report=html",
    # ... no test filtering
]
```

**After:**
```toml
addopts = [
    # Coverage NOT enabled by default
    "-m", "not slow and not performance and not load_test",  # Exclude slow tests
]
```

### 2. Created Coverage Commands Guide

**File:** `tests/COVERAGE_COMMANDS.md`

Provides clear commands for:
- Fast test runs (development)
- Coverage reports (when needed)
- Running slow tests separately

## Usage

### Fast Test Run (Default)
```bash
# Runs all tests except slow/performance/load tests
pytest

# Quiet mode (faster output)
pytest -q
```

### Full Coverage (When Needed)
```bash
# Full coverage with all tests
pytest --cov=app --cov-report=term-missing --cov-report=html

# Fast coverage (excludes slow tests)
pytest --cov=app --cov-report=term-missing -m "not slow and not performance and not load_test"
```

### Run Slow Tests Separately
```bash
# Only performance tests
pytest -m performance

# Only load tests
pytest -m load_test

# All tests including slow ones
pytest -m ""
```

## Expected Performance Improvement

### Before
- Default test run: **10+ minutes** (with coverage + slow tests)
- Coverage report: **15+ minutes**

### After
- Default test run: **~30-60 seconds** (no coverage, no slow tests)
- Coverage (fast): **~2-3 minutes** (no slow tests)
- Coverage (full): **~10-15 minutes** (all tests)

## Test Statistics

- **Total test files:** 76
- **Total test functions:** 1,695
- **Slow/performance/load tests:** ~50-100 tests
- **Fast tests:** ~1,600 tests

## Markers

Tests are organized with markers:
- `@pytest.mark.slow` - Slow running tests (excluded by default)
- `@pytest.mark.performance` - Performance tests (excluded by default)
- `@pytest.mark.load_test` - Load tests (excluded by default)
- `@pytest.mark.unit` - Unit tests (fast)
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.api` - API endpoint tests

## Next Steps

1. ✅ **Configuration updated** - Slow tests excluded by default
2. ✅ **Documentation created** - Coverage commands guide
3. ⏳ **Test the changes** - Verify faster test runs
4. ⏳ **Update CI/CD** - Adjust pipeline commands if needed

## Verification

To verify the fix works:

```bash
# Should run fast (30-60 seconds)
pytest -q

# Should show excluded tests
pytest -v | grep -i "excluded"

# Should run much faster than before
time pytest --cov=app -m "not slow and not performance and not load_test"
```

