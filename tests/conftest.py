"""Pytest configuration and shared fixtures."""
import os
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables BEFORE any app imports
os.environ["TESTING"] = "true"
os.environ["ENVIRONMENT"] = "test"  # Set to test to avoid production validation
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", "sqlite:///./test.db"
)
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
# Override Redis settings for testing (unset password to avoid auth errors)
os.environ.pop("REDIS_PASSWORD", None)  # Remove password for local Redis without auth
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_DB", "0")
# Set security settings defaults for testing
# Use high-entropy keys that pass validation
# JWT secret: 32+ characters with high entropy
os.environ.setdefault("JWT_SECRET_KEY", "REMOVED_SECRET_FROM_HISTORY")
# Encryption key: exactly 32 characters with high entropy
os.environ.setdefault("ENCRYPTION_KEY", "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("REQUIRE_AUTH", "false")  # Disable auth for tests

# Mock Redis BEFORE importing app modules that use it
_mock_redis = MagicMock()
_mock_redis.get.return_value = None
_mock_redis.set.return_value = True
_mock_redis.setex.return_value = True
_mock_redis.delete.return_value = 1
_mock_redis.exists.return_value = False
_mock_redis.keys.return_value = []
_mock_redis.ping.return_value = True
# Mock pipeline for rate limiting middleware
_mock_pipeline = MagicMock()
_mock_pipeline.incr.return_value = _mock_pipeline
_mock_pipeline.expire.return_value = _mock_pipeline
_mock_pipeline.execute.return_value = [1, True, 1, True]  # [minute_count, expire_result, hour_count, expire_result]
_mock_redis.pipeline.return_value = _mock_pipeline

# Patch get_redis_client before any imports (patch both where it's defined and where it's used)
_redis_patcher_config = patch("app.config.redis.get_redis_client", return_value=_mock_redis)
_redis_patcher_config.start()
_redis_patcher_cache = patch("app.utils.cache.get_redis_client", return_value=_mock_redis)
_redis_patcher_cache.start()

# Now import after environment is set and Redis is mocked
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.config.database import Base, get_db
from app.main import app
from app.models.database import (
    Claim,
    ClaimLine,
    Payer,
    Provider,
)

# Import factories and configure them
from tests.factories import (
    ClaimEpisodeFactory,
    ClaimFactory,
    ClaimLineFactory,
    DenialPatternFactory,
    PayerFactory,
    PlanFactory,
    PracticeConfigFactory,
    ProviderFactory,
    RemittanceFactory,
    RiskScoreFactory,
)


# Cache clearing fixture
@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before and after each test to prevent test interference."""
    from app.utils.cache import cache
    # Clear cache before test
    cache.clear_namespace()
    yield
    # Clear cache after test
    cache.clear_namespace()


# Test database setup
@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """Create a test database session with transaction rollback."""
    # Use SQLite in-memory database for tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_db: Session) -> Generator[Session, None, None]:
    """Provide a database session for tests."""
    # Configure factories to use this session
    ProviderFactory._meta.sqlalchemy_session = test_db
    PayerFactory._meta.sqlalchemy_session = test_db
    PlanFactory._meta.sqlalchemy_session = test_db
    ClaimFactory._meta.sqlalchemy_session = test_db
    ClaimLineFactory._meta.sqlalchemy_session = test_db
    RemittanceFactory._meta.sqlalchemy_session = test_db
    ClaimEpisodeFactory._meta.sqlalchemy_session = test_db
    DenialPatternFactory._meta.sqlalchemy_session = test_db
    RiskScoreFactory._meta.sqlalchemy_session = test_db
    PracticeConfigFactory._meta.sqlalchemy_session = test_db

    yield test_db
    # Clean up after each test
    test_db.rollback()


@pytest.fixture(scope="function")
def override_get_db(db_session: Session):
    """Override the get_db dependency."""
    def _get_db():
        try:
            yield db_session
        finally:
            pass  # Don't close in tests

    return _get_db


@pytest.fixture(scope="function")
def client(override_get_db) -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    app.dependency_overrides[get_db] = override_get_db
    # Set raise_server_exceptions=False so that 500 errors return responses instead of raising
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def async_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# Mock fixtures
@pytest.fixture(scope="function")
def mock_celery_task(mocker):
    """Mock Celery task execution."""
    from unittest.mock import MagicMock

    mock_task = MagicMock()
    mock_task.delay = MagicMock(return_value=mock_task)
    mock_task.id = "test-task-id"
    mock_task.state = "PENDING"

    return mock_task


@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis connection."""
    return _mock_redis


@pytest.fixture(scope="function")
def mock_logger(mocker):
    """Mock logger to avoid noise in test output."""
    return mocker.patch("app.utils.logger.get_logger")


# Test data fixtures
@pytest.fixture
def sample_provider(db_session: Session) -> Provider:
    """Create a sample provider for testing."""
    provider = Provider(
        npi="1234567890",
        name="Test Provider",
        specialty="Internal Medicine",
        taxonomy_code="208D00000X",
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)
    return provider


@pytest.fixture
def sample_payer(db_session: Session) -> Payer:
    """Create a sample payer for testing."""
    payer = Payer(
        payer_id="PAYER001",
        name="Test Insurance Company",
        payer_type="Commercial",
        rules_config={"denial_threshold": 0.3},
    )
    db_session.add(payer)
    db_session.commit()
    db_session.refresh(payer)
    return payer


@pytest.fixture
def sample_claim(db_session: Session, sample_provider: Provider, sample_payer: Payer) -> Claim:
    """Create a sample claim for testing."""
    from app.models.database import ClaimStatus

    claim = Claim(
        claim_control_number="CLM001",
        patient_control_number="PAT001",
        provider_id=sample_provider.id,
        payer_id=sample_payer.id,
        total_charge_amount=1000.00,
        status=ClaimStatus.PENDING,
        is_incomplete=False,
        practice_id="PRACTICE001",
    )
    db_session.add(claim)
    db_session.commit()
    db_session.refresh(claim)
    return claim


@pytest.fixture
def sample_claim_with_lines(
    db_session: Session, sample_claim: Claim
) -> Claim:
    """Create a sample claim with claim lines."""
    from datetime import datetime

    line1 = ClaimLine(
        claim_id=sample_claim.id,
        line_number="1",
        procedure_code="99213",
        charge_amount=250.00,
        service_date=datetime.now(),
    )
    line2 = ClaimLine(
        claim_id=sample_claim.id,
        line_number="2",
        procedure_code="36415",
        charge_amount=50.00,
        service_date=datetime.now(),
    )

    db_session.add(line1)
    db_session.add(line2)
    db_session.commit()
    db_session.refresh(sample_claim)
    return sample_claim

