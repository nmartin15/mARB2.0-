# Test Suite Quick Start

## Installation

Install all testing dependencies:
```bash
pip install -r requirements.txt
```

## Quick Commands

```bash
# Run all tests
pytest

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_claims_api.py

# Run specific test
pytest tests/test_claims_api.py::TestGetClaims::test_get_claims_empty

# Run in parallel (faster)
pytest -n auto

# Run only API tests
pytest -m api

# Run with verbose output
pytest -vv
```

## Writing Your First Test

```python
import pytest
from tests.factories import ClaimFactory, ProviderFactory, PayerFactory

@pytest.mark.api
def test_get_claim(client, db_session):
    """Test getting a claim by ID."""
    # Arrange: Create test data
    provider = ProviderFactory()
    payer = PayerFactory()
    claim = ClaimFactory(provider=provider, payer=payer)
    
    # Act: Make API call
    response = client.get(f"/api/v1/claims/{claim.id}")
    
    # Assert: Verify results
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == claim.id
```

## Common Patterns

### Testing API Endpoints
```python
@pytest.mark.api
def test_endpoint(client, db_session):
    response = client.get("/api/v1/endpoint")
    assert response.status_code == 200
```

### Testing with Mocks
```python
def test_with_mock(client, mock_celery_task):
    with patch("app.api.routes.claims.process_edi_file") as mock:
        mock.delay = MagicMock(return_value=mock_celery_task)
        # Your test code
```

### Testing Async Endpoints
```python
@pytest.mark.async
@pytest.mark.asyncio
async def test_async(async_client, db_session):
    response = await async_client.get("/api/v1/endpoint")
    assert response.status_code == 200
```

### Using Factories
```python
from tests.factories import ClaimFactory

def test_something(db_session):
    claim = ClaimFactory()  # Creates claim with all required fields
    # Or customize:
    claim = ClaimFactory(total_charge_amount=5000.00)
```

## Available Fixtures

- `client`: FastAPI test client (synchronous)
- `async_client`: FastAPI async test client
- `db_session`: Database session (auto-rollback)
- `mock_celery_task`: Mock Celery task
- `sample_provider`, `sample_payer`, `sample_claim`: Pre-created test data

## Test Markers

Use markers to organize tests:
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.slow` - Slow tests

## Coverage

View coverage report:
```bash
make test-cov
# Then open htmlcov/index.html
```

Target: 80%+ overall coverage

