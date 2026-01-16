# Test Suite Documentation

This directory contains the comprehensive test suite for mARB 2.0 using industry best practices and modern testing frameworks.

## Test Framework Stack

- **pytest**: Primary testing framework
- **pytest-asyncio**: Async test support for FastAPI endpoints
- **pytest-cov**: Code coverage reporting
- **pytest-mock**: Enhanced mocking capabilities
- **pytest-xdist**: Parallel test execution
- **factory-boy**: Test data factories
- **faker**: Realistic fake data generation
- **httpx**: Async HTTP client for testing FastAPI

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures and configuration
├── factories.py         # Test data factories
├── test_utils.py        # Test utilities and helpers
├── test_claims_api.py   # Claims API endpoint tests
├── test_edi_parser.py   # EDI parser tests
├── test_risk_scoring.py # Risk scoring tests
└── test_episode_linking.py # Episode linking tests
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=app --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_claims_api.py
```

### Run specific test
```bash
pytest tests/test_claims_api.py::TestGetClaims::test_get_claims_empty
```

### Run tests in parallel
```bash
pytest -n auto
```

### Run tests by marker
```bash
pytest -m api          # Run only API tests
pytest -m unit         # Run only unit tests
pytest -m integration  # Run only integration tests
pytest -m "not slow"   # Skip slow tests
```

### Run with verbose output
```bash
pytest -v
```

### Run with extra verbose output
```bash
pytest -vv
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit`: Unit tests for individual functions/classes
- `@pytest.mark.integration`: Integration tests for component interactions
- `@pytest.mark.api`: API endpoint tests
- `@pytest.mark.async`: Async tests
- `@pytest.mark.slow`: Tests that take longer to run

## Fixtures

### Database Fixtures

- `test_db`: Creates an in-memory SQLite database for each test
- `db_session`: Provides a database session with automatic rollback
- `override_get_db`: Overrides the FastAPI dependency for database access

### Client Fixtures

- `client`: Synchronous test client (TestClient)
- `async_client`: Asynchronous test client (AsyncClient)

### Mock Fixtures

- `mock_celery_task`: Mocks Celery task execution
- `mock_redis`: Mocks Redis connection
- `mock_logger`: Mocks logger to reduce test output noise

### Data Fixtures

- `sample_provider`: Creates a test provider
- `sample_payer`: Creates a test payer
- `sample_claim`: Creates a test claim
- `sample_claim_with_lines`: Creates a claim with claim lines

## Using Factories

Factories make it easy to create test data:

```python
from tests.factories import ClaimFactory, ProviderFactory, PayerFactory

def test_something(db_session):
    provider = ProviderFactory()
    payer = PayerFactory()
    claim = ClaimFactory(provider=provider, payer=payer)
    
    # Use the created objects in your test
    assert claim.provider_id == provider.id
```

Factories automatically handle relationships and generate realistic data using Faker.

## Writing Tests

### API Endpoint Tests

```python
import pytest
from tests.factories import ClaimFactory

@pytest.mark.api
class TestGetClaims:
    def test_get_claims_empty(self, client, db_session):
        """Test getting claims when none exist."""
        response = client.get("/api/v1/claims")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
```

### Async Tests

```python
@pytest.mark.async
@pytest.mark.asyncio
async def test_async_endpoint(async_client, db_session):
    response = await async_client.get("/api/v1/claims")
    assert response.status_code == 200
```

### Mocking External Services

```python
def test_with_celery_mock(client, mock_celery_task):
    with patch("app.api.routes.claims.process_edi_file") as mock_task:
        mock_task.delay = MagicMock(return_value=mock_celery_task)
        # Your test code here
```

## Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Fixtures**: Use fixtures for setup/teardown instead of setUp/tearDown methods
3. **Factories**: Use factories for creating test data instead of manual object creation
4. **Markers**: Use markers to organize and filter tests
5. **Descriptive Names**: Use clear, descriptive test names that explain what is being tested
6. **AAA Pattern**: Arrange, Act, Assert - structure tests clearly
7. **Coverage**: Aim for high code coverage, especially for critical paths
8. **Mock External Dependencies**: Mock external services (Celery, Redis, etc.) in unit tests

## Coverage Goals

- Overall coverage target: 80%+
- Critical paths (API endpoints, business logic): 90%+
- Utility functions: 70%+

View coverage reports:
```bash
pytest --cov=app --cov-report=html
# Open htmlcov/index.html in your browser
```

## Continuous Integration

Tests should be run in CI/CD pipelines. The test suite is designed to:
- Run quickly (use in-memory database)
- Be deterministic (no external dependencies)
- Provide clear failure messages
- Generate coverage reports

## Troubleshooting

### Database Issues
If you see database-related errors, ensure:
- Test database is properly isolated (using fixtures)
- Transactions are rolled back after each test
- No global state is being modified

### Import Errors
If you see import errors:
- Ensure you're running tests from the project root
- Check that all dependencies are installed: `pip install -r requirements.txt`

### Async Test Issues
If async tests fail:
- Ensure `@pytest.mark.asyncio` decorator is present
- Use `async_client` fixture for async endpoints
- Check that `pytest-asyncio` is installed

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [factory-boy documentation](https://factoryboy.readthedocs.io/)
- [FastAPI testing guide](https://fastapi.tiangolo.com/tutorial/testing/)

