# Test Coverage Commands

## Quick Reference

### Fast Test Run (Default - Excludes Slow Tests)
```bash
# Run all tests except slow/performance/load tests
pytest

# Run with minimal output
pytest -q

# Run specific test file
pytest tests/test_claims_api.py
```

### Full Coverage Report (Includes All Tests)
```bash
# Full coverage with all tests (including slow/performance/load tests)
pytest --cov=app --cov-report=term-missing --cov-report=html --cov-report=json

# Coverage excluding slow tests (faster)
pytest --cov=app --cov-report=term-missing --cov-report=html -m "not slow and not performance and not load_test"

# Coverage for specific module
pytest --cov=app.services.edi --cov-report=term-missing tests/test_edi_parser.py
```

### Run Slow Tests Separately
```bash
# Run only performance tests
pytest -m performance

# Run only load tests
pytest -m load_test

# Run only slow tests
pytest -m slow

# Run all tests including slow ones
pytest -m ""
```

### Module-Specific Coverage
```bash
# Coverage for specific module
pytest --cov=app.services.risk --cov-report=term-missing tests/test_risk_scoring.py

# Coverage for multiple modules
pytest --cov=app.services --cov-report=term-missing tests/test_*.py
```

## Why Tests Are Slow

1. **1,695 test functions** across 76 test files
2. **Performance/load tests** generate 100MB+ files (very slow)
3. **Coverage collection** adds significant overhead
4. **Database setup/teardown** for each test

## Recommended Workflow

### Development (Fast Iteration)
```bash
# Run tests without coverage (fastest)
pytest -q

# Run specific test file
pytest tests/test_claims_api.py -v

# Run tests matching pattern
pytest -k "test_claim" -v
```

### Pre-Commit (Quick Check)
```bash
# Fast coverage check (excludes slow tests)
pytest --cov=app --cov-report=term-missing -m "not slow and not performance and not load_test"
```

### CI/CD (Full Coverage)
```bash
# Full coverage with all tests
pytest --cov=app --cov-report=term-missing --cov-report=html --cov-report=xml
```

### Coverage Analysis
```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Generate JSON for programmatic analysis
pytest --cov=app --cov-report=json
```

## Test Markers

- `@pytest.mark.unit` - Unit tests (fast)
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.slow` - Slow running tests (excluded by default)
- `@pytest.mark.performance` - Performance tests (excluded by default)
- `@pytest.mark.load_test` - Load tests (excluded by default)

## Performance Tips

1. **Use `-q` flag** for quieter output (faster)
2. **Run specific test files** instead of entire suite
3. **Use `-k` to filter** by test name pattern
4. **Run slow tests separately** when needed
5. **Use parallel execution** for faster runs: `pytest -n auto`

