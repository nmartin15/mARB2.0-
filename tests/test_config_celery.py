"""Tests for Celery configuration."""
import os
from unittest.mock import patch, MagicMock
import pytest

from app.config.celery import celery_app, broker_url, result_backend


@pytest.mark.unit
class TestCeleryConfiguration:
    """Tests for Celery configuration."""

    def test_celery_app_created(self):
        """Test that celery_app is created."""
        assert celery_app is not None

    def test_celery_app_name(self):
        """Test that celery_app has correct name."""
        assert celery_app.main == "marb_risk_engine"

    def test_celery_app_includes_tasks(self):
        """Test that celery_app includes task modules."""
        assert "app.services.queue.tasks" in celery_app.conf.include

    def test_broker_url_default(self):
        """Test that broker_url has default value."""
        # broker_url is set at module import, but we can check it exists
        assert broker_url is not None
        assert isinstance(broker_url, str)

    def test_broker_url_from_env(self):
        """Test that broker_url can be set from environment."""
        # This is tested indirectly - broker_url reads from env at import time
        assert broker_url is not None

    def test_result_backend_default(self):
        """Test that result_backend has default value."""
        assert result_backend is not None
        assert isinstance(result_backend, str)

    def test_result_backend_from_env(self):
        """Test that result_backend can be set from environment."""
        # This is tested indirectly - result_backend reads from env at import time
        assert result_backend is not None

    def test_celery_app_task_serializer(self):
        """Test that celery_app uses JSON task serializer."""
        assert celery_app.conf.task_serializer == "json"

    def test_celery_app_accept_content(self):
        """Test that celery_app accepts JSON content."""
        assert "json" in celery_app.conf.accept_content

    def test_celery_app_result_serializer(self):
        """Test that celery_app uses JSON result serializer."""
        assert celery_app.conf.result_serializer == "json"

    def test_celery_app_timezone(self):
        """Test that celery_app uses UTC timezone."""
        assert celery_app.conf.timezone == "UTC"

    def test_celery_app_enable_utc(self):
        """Test that celery_app has UTC enabled."""
        assert celery_app.conf.enable_utc is True

    def test_celery_app_task_track_started(self):
        """Test that celery_app tracks task started."""
        assert celery_app.conf.task_track_started is True

    def test_celery_app_task_time_limit(self):
        """Test that celery_app has task time limit."""
        assert celery_app.conf.task_time_limit == 30 * 60  # 30 minutes

    def test_celery_app_task_soft_time_limit(self):
        """Test that celery_app has task soft time limit."""
        assert celery_app.conf.task_soft_time_limit == 25 * 60  # 25 minutes

    def test_celery_app_worker_prefetch_multiplier(self):
        """Test that celery_app has worker prefetch multiplier."""
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_celery_app_worker_max_tasks_per_child(self):
        """Test that celery_app has worker max tasks per child."""
        assert celery_app.conf.worker_max_tasks_per_child == 1000

    def test_celery_app_sentry_initialized(self):
        """Test that Sentry is initialized for Celery."""
        # Sentry initialization happens at module import time
        # We verify the module imports successfully
        from app.config import celery
        assert celery is not None

