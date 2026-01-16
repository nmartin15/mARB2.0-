"""Tests for Redis configuration."""
import os
from unittest.mock import MagicMock, patch
import pytest
import redis

# Import after setting up mocks
from app.config import redis as redis_config


@pytest.fixture(autouse=True)
def reset_redis_client_and_unpatch():
    """Reset Redis client and unpatch get_redis_client for these tests."""
    # Stop the conftest patcher so we can test the real function
    import tests.conftest
    if hasattr(tests.conftest, '_redis_patcher_config'):
        tests.conftest._redis_patcher_config.stop()
    
    # Store original
    original = redis_config._redis_client
    # Reset before test
    redis_config._redis_client = None
    yield
    # Restore after test
    redis_config._redis_client = original
    # Restart the conftest patcher
    if hasattr(tests.conftest, '_redis_patcher_config'):
        tests.conftest._redis_patcher_config.start()


@pytest.mark.unit
class TestRedisConfiguration:
    """Tests for Redis configuration."""

    def test_get_redis_client_creates_client(self):
        """Test that get_redis_client creates a Redis client."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis):
            with patch.dict(os.environ, {}, clear=True):
                client = redis_config.get_redis_client()

                assert client is not None
                mock_redis.ping.assert_called_once()

    def test_get_redis_client_uses_default_host(self):
        """Test that get_redis_client uses default host when not set."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis) as mock_redis_class:
            with patch.dict(os.environ, {}, clear=True):
                redis_config.get_redis_client()

                # Check that Redis was called with default host
                assert mock_redis_class.called
                call_kwargs = mock_redis_class.call_args[1]
                assert call_kwargs["host"] == "localhost"

    def test_get_redis_client_uses_env_host(self):
        """Test that get_redis_client uses REDIS_HOST from environment."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis) as mock_redis_class:
            with patch.dict(os.environ, {"REDIS_HOST": "redis.example.com"}, clear=False):
                redis_config.get_redis_client()

                assert mock_redis_class.called
                call_kwargs = mock_redis_class.call_args[1]
                assert call_kwargs["host"] == "redis.example.com"

    def test_get_redis_client_uses_default_port(self):
        """Test that get_redis_client uses default port when not set."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis) as mock_redis_class:
            with patch.dict(os.environ, {}, clear=True):
                redis_config.get_redis_client()

                assert mock_redis_class.called
                call_kwargs = mock_redis_class.call_args[1]
                assert call_kwargs["port"] == 6379

    def test_get_redis_client_uses_env_port(self):
        """Test that get_redis_client uses REDIS_PORT from environment."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis) as mock_redis_class:
            with patch.dict(os.environ, {"REDIS_PORT": "6380"}, clear=False):
                redis_config.get_redis_client()

                assert mock_redis_class.called
                call_kwargs = mock_redis_class.call_args[1]
                assert call_kwargs["port"] == 6380

    def test_get_redis_client_uses_env_password(self):
        """Test that get_redis_client uses REDIS_PASSWORD from environment."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis) as mock_redis_class:
            with patch.dict(os.environ, {"REDIS_PASSWORD": "secret123"}, clear=False):
                redis_config.get_redis_client()

                assert mock_redis_class.called
                call_kwargs = mock_redis_class.call_args[1]
                assert call_kwargs["password"] == "secret123"

    def test_get_redis_client_no_password_when_not_set(self):
        """Test that get_redis_client uses None for password when not set."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis) as mock_redis_class:
            with patch.dict(os.environ, {}, clear=True):
                redis_config.get_redis_client()

                assert mock_redis_class.called
                call_kwargs = mock_redis_class.call_args[1]
                assert call_kwargs["password"] is None

    def test_get_redis_client_uses_env_db(self):
        """Test that get_redis_client uses REDIS_DB from environment."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis) as mock_redis_class:
            with patch.dict(os.environ, {"REDIS_DB": "1"}, clear=False):
                redis_config.get_redis_client()

                assert mock_redis_class.called
                call_kwargs = mock_redis_class.call_args[1]
                assert call_kwargs["db"] == 1

    def test_get_redis_client_uses_default_db(self):
        """Test that get_redis_client uses default db when not set."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis) as mock_redis_class:
            with patch.dict(os.environ, {}, clear=True):
                redis_config.get_redis_client()

                assert mock_redis_class.called
                call_kwargs = mock_redis_class.call_args[1]
                assert call_kwargs["db"] == 0

    def test_get_redis_client_sets_decode_responses(self):
        """Test that get_redis_client sets decode_responses=True."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis) as mock_redis_class:
            with patch.dict(os.environ, {}, clear=True):
                redis_config.get_redis_client()

                assert mock_redis_class.called
                call_kwargs = mock_redis_class.call_args[1]
                assert call_kwargs["decode_responses"] is True

    def test_get_redis_client_sets_socket_connect_timeout(self):
        """Test that get_redis_client sets socket_connect_timeout."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis) as mock_redis_class:
            with patch.dict(os.environ, {}, clear=True):
                redis_config.get_redis_client()

                assert mock_redis_class.called
                call_kwargs = mock_redis_class.call_args[1]
                assert call_kwargs["socket_connect_timeout"] == 5

    def test_get_redis_client_connection_error(self):
        """Test that get_redis_client raises ConnectionError when Redis is unavailable."""
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = redis.ConnectionError("Connection refused")

        with patch("app.config.redis.redis.Redis", return_value=mock_redis):
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(redis.ConnectionError):
                    redis_config.get_redis_client()

    def test_get_redis_client_returns_singleton(self):
        """Test that get_redis_client returns the same client instance on subsequent calls."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis):
            with patch.dict(os.environ, {}, clear=True):
                client1 = redis_config.get_redis_client()
                client2 = redis_config.get_redis_client()

                assert client1 is client2
                # Should only create Redis client once
                assert mock_redis.ping.call_count == 1

    def test_get_redis_client_all_config_options(self):
        """Test that get_redis_client uses all configuration options together."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("app.config.redis.redis.Redis", return_value=mock_redis) as mock_redis_class:
            env_vars = {
                "REDIS_HOST": "redis.prod.com",
                "REDIS_PORT": "6380",
                "REDIS_PASSWORD": "super-secret",
                "REDIS_DB": "2",
            }
            with patch.dict(os.environ, env_vars, clear=False):
                redis_config.get_redis_client()

                assert mock_redis_class.called
                call_kwargs = mock_redis_class.call_args[1]
                assert call_kwargs["host"] == "redis.prod.com"
                assert call_kwargs["port"] == 6380
                assert call_kwargs["password"] == "super-secret"
                assert call_kwargs["db"] == 2
                assert call_kwargs["decode_responses"] is True
                assert call_kwargs["socket_connect_timeout"] == 5
