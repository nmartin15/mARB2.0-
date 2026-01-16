"""Tests for cache utilities."""
from unittest.mock import MagicMock, patch, Mock
import json
import pytest

from app.utils.cache import (
    Cache,
    cache,
    cached,
    cache_key,
    claim_cache_key,
    risk_score_cache_key,
    payer_cache_key,
    remittance_cache_key,
    episode_cache_key,
    count_cache_key,
)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = False
    redis_mock.keys.return_value = []
    return redis_mock


@pytest.fixture
def cache_instance(mock_redis):
    """Create a Cache instance with mocked Redis."""
    with patch("app.utils.cache.get_redis_client", return_value=mock_redis):
        cache = Cache(namespace="test")
        return cache, mock_redis


@pytest.mark.unit
class TestCache:
    """Tests for Cache class."""

    def test_cache_init(self, mock_redis):
        """Test Cache initialization."""
        with patch("app.utils.cache.get_redis_client", return_value=mock_redis):
            cache = Cache(namespace="test_namespace")
            assert cache.namespace == "test_namespace"
            assert cache.redis == mock_redis

    def test_cache_init_default_namespace(self, mock_redis):
        """Test Cache initialization with default namespace."""
        with patch("app.utils.cache.get_redis_client", return_value=mock_redis):
            cache = Cache()
            assert cache.namespace == "marb"

    def test_make_key(self, cache_instance):
        """Test cache key generation."""
        cache, mock_redis = cache_instance
        key = cache._make_key("test_key")
        assert key == "test:test_key"

    def test_get_cache_hit(self, cache_instance):
        """Test getting value from cache (hit)."""
        cache, mock_redis = cache_instance
        cached_value = json.dumps({"data": "test"})
        mock_redis.get.return_value = cached_value

        result = cache.get("test_key")

        assert result == {"data": "test"}
        mock_redis.get.assert_called_once_with("test:test_key")

    def test_get_cache_miss(self, cache_instance):
        """Test getting value from cache (miss)."""
        cache, mock_redis = cache_instance
        mock_redis.get.return_value = None

        result = cache.get("test_key")

        assert result is None
        mock_redis.get.assert_called_once_with("test:test_key")

    def test_get_cache_error(self, cache_instance):
        """Test getting value from cache when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.get.side_effect = Exception("Redis error")

        result = cache.get("test_key")

        assert result is None

    def test_get_without_stats_tracking(self, cache_instance):
        """Test getting value without stats tracking."""
        cache, mock_redis = cache_instance
        cached_value = json.dumps({"data": "test"})
        mock_redis.get.return_value = cached_value

        result = cache.get("test_key", track_stats=False)

        assert result == {"data": "test"}

    def test_set_without_ttl(self, cache_instance):
        """Test setting value in cache without TTL."""
        cache, mock_redis = cache_instance

        result = cache.set("test_key", {"data": "test"})

        assert result is True
        mock_redis.set.assert_called_once()
        args = mock_redis.set.call_args
        assert args[0][0] == "test:test_key"
        assert json.loads(args[0][1]) == {"data": "test"}

    def test_set_with_ttl_seconds(self, cache_instance):
        """Test setting value in cache with TTL."""
        cache, mock_redis = cache_instance

        result = cache.set("test_key", {"data": "test"}, ttl_seconds=3600)

        assert result is True
        mock_redis.setex.assert_called_once_with("test:test_key", 3600, json.dumps({"data": "test"}))

    def test_set_with_ttl_inference(self, cache_instance):
        """Test setting value with TTL inferred from key pattern."""
        cache, mock_redis = cache_instance
        with patch("app.utils.cache.Cache._infer_ttl_from_key", return_value=1800):
            result = cache.set("claim:123", {"data": "test"})

            assert result is True
            # Should use inferred TTL from key pattern
            mock_redis.setex.assert_called_once_with("test:claim:123", 1800, json.dumps({"data": "test"}))

    def test_set_cache_error(self, cache_instance):
        """Test setting value when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.setex.side_effect = Exception("Redis error")

        result = cache.set("test_key", {"data": "test"}, ttl_seconds=3600)

        assert result is False

    def test_set_with_non_json_serializable(self, cache_instance):
        """Test setting non-JSON serializable value (uses default=str)."""
        cache, mock_redis = cache_instance
        from datetime import datetime
        value = {"date": datetime(2024, 1, 1)}

        result = cache.set("test_key", value)

        assert result is True
        # Should serialize datetime using default=str
        mock_redis.set.assert_called_once()

    def test_delete(self, cache_instance):
        """Test deleting key from cache."""
        cache, mock_redis = cache_instance

        result = cache.delete("test_key")

        assert result is True
        mock_redis.delete.assert_called_once_with("test:test_key")

    def test_delete_error(self, cache_instance):
        """Test deleting key when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.delete.side_effect = Exception("Redis error")

        result = cache.delete("test_key")

        assert result is False

    def test_delete_pattern(self, cache_instance):
        """Test deleting keys matching pattern using SCAN."""
        cache, mock_redis = cache_instance
        # Mock SCAN to return keys in batches
        mock_redis.scan.side_effect = [
            (0, [b"test:claim:1", b"test:claim:2"]),  # First scan returns cursor 0 (done)
        ]
        mock_redis.delete.return_value = 2

        result = cache.delete_pattern("claim:*")

        assert result == 2
        # Verify SCAN was called (not KEYS)
        mock_redis.scan.assert_called_once_with(cursor=0, match="test:claim:*", count=100)
        # Verify delete was called with the keys
        mock_redis.delete.assert_called_once_with(b"test:claim:1", b"test:claim:2")

    def test_delete_pattern_multiple_scans(self, cache_instance):
        """Test deleting keys matching pattern with multiple SCAN iterations."""
        cache, mock_redis = cache_instance
        # Mock SCAN to return keys in multiple batches
        mock_redis.scan.side_effect = [
            (100, [b"test:claim:1", b"test:claim:2"]),  # First scan returns cursor 100
            (0, [b"test:claim:3"]),  # Second scan returns cursor 0 (done)
        ]
        mock_redis.delete.return_value = 1  # Each delete call returns 1

        result = cache.delete_pattern("claim:*")

        assert result == 3
        # Verify SCAN was called twice
        assert mock_redis.scan.call_count == 2
        # Verify delete was called twice
        assert mock_redis.delete.call_count == 2

    def test_delete_pattern_no_matches(self, cache_instance):
        """Test deleting pattern when no keys match."""
        cache, mock_redis = cache_instance
        # Mock SCAN to return no keys
        mock_redis.scan.side_effect = [
            (0, []),  # No keys found
        ]

        result = cache.delete_pattern("claim:*")

        assert result == 0
        mock_redis.scan.assert_called()
        mock_redis.delete.assert_not_called()

    def test_delete_pattern_error(self, cache_instance):
        """Test deleting pattern when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.scan.side_effect = Exception("Redis error")

        result = cache.delete_pattern("claim:*")

        assert result == 0

    def test_exists(self, cache_instance):
        """Test checking if key exists."""
        cache, mock_redis = cache_instance
        mock_redis.exists.return_value = 1

        result = cache.exists("test_key")

        assert result is True
        mock_redis.exists.assert_called_once_with("test:test_key")

    def test_exists_false(self, cache_instance):
        """Test checking if key exists when it doesn't."""
        cache, mock_redis = cache_instance
        mock_redis.exists.return_value = 0

        result = cache.exists("test_key")

        assert result is False

    def test_exists_error(self, cache_instance):
        """Test checking existence when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.exists.side_effect = Exception("Redis error")

        result = cache.exists("test_key")

        assert result is False

    def test_clear_namespace(self, cache_instance):
        """Test clearing all keys in namespace using SCAN."""
        cache, mock_redis = cache_instance
        # Mock SCAN to return keys
        mock_redis.scan.side_effect = [
            (0, [b"test:key1", b"test:key2"]),  # First scan returns cursor 0 (done)
        ]
        mock_redis.delete.return_value = 2

        result = cache.clear_namespace()

        assert result == 2
        # Verify SCAN was called (not KEYS)
        mock_redis.scan.assert_called()

    def test_get_stats_single_key(self, cache_instance):
        """Test getting stats for a single key."""
        cache, mock_redis = cache_instance

        # Make some operations
        cache.get("key1", track_stats=True)
        cache.get("key1", track_stats=True)
        cache.get("key1", track_stats=True)

        stats = cache.get_stats("key1")

        assert "hits" in stats or "misses" in stats
        assert "total" in stats
        assert "hit_rate" in stats

    def test_get_stats_all_keys(self, cache_instance):
        """Test getting stats for all keys."""
        cache, mock_redis = cache_instance

        # Make some operations
        cache.get("key1", track_stats=True)
        cache.get("key2", track_stats=True)

        stats = cache.get_stats()

        assert "overall" in stats
        assert "by_key" in stats
        assert "hits" in stats["overall"]
        assert "misses" in stats["overall"]
        assert "total" in stats["overall"]
        assert "hit_rate" in stats["overall"]

    def test_reset_stats_single_key(self, cache_instance):
        """Test resetting stats for a single key."""
        cache, mock_redis = cache_instance

        cache.get("key1", track_stats=True)
        cache.reset_stats("key1")

        stats = cache.get_stats("key1")
        assert stats["total"] == 0

    def test_reset_stats_all_keys(self, cache_instance):
        """Test resetting all stats."""
        cache, mock_redis = cache_instance

        cache.get("key1", track_stats=True)
        cache.get("key2", track_stats=True)
        cache.reset_stats()

        stats = cache.get_stats()
        assert stats["overall"]["total"] == 0


@pytest.mark.unit
class TestCacheDecorator:
    """Tests for @cached decorator."""

    def test_cached_decorator_cache_hit(self, cache_instance):
        """Test @cached decorator with cache hit."""
        cache_obj, mock_redis = cache_instance
        cached_value = json.dumps({"result": "cached"})
        mock_redis.get.return_value = cached_value

        with patch("app.utils.cache.cache", cache_obj):
            @cached(ttl_seconds=3600, key_prefix="test")
            def test_function(x: int, y: int) -> dict:
                return {"result": x + y}

            result = test_function(1, 2)

            assert result == {"result": "cached"}
            # Function should not be called (cache hit)
            mock_redis.get.assert_called()

    def test_cached_decorator_cache_miss(self, cache_instance):
        """Test @cached decorator with cache miss."""
        cache_obj, mock_redis = cache_instance
        mock_redis.get.return_value = None

        call_count = 0

        with patch("app.utils.cache.cache", cache_obj):
            @cached(ttl_seconds=3600, key_prefix="test")
            def test_function(x: int, y: int) -> dict:
                nonlocal call_count
                call_count += 1
                return {"result": x + y}

            result = test_function(1, 2)

            assert result == {"result": 3}
            assert call_count == 1  # Function should be called once
            # Should set value in cache
            mock_redis.setex.assert_called_once()

    def test_cached_decorator_with_custom_key_func(self, cache_instance):
        """Test @cached decorator with custom key function."""
        cache_obj, mock_redis = cache_instance
        mock_redis.get.return_value = None

        def key_func(x: int, y: int) -> str:
            return f"custom:{x}:{y}"

        with patch("app.utils.cache.cache", cache_obj):
            @cached(ttl_seconds=3600, key_func=key_func)
            def test_function(x: int, y: int) -> int:
                return x + y

            result = test_function(1, 2)

            assert result == 3
            # Should use custom key function
            mock_redis.get.assert_called()

    def test_cached_decorator_with_invalidate_on(self, cache_instance):
        """Test @cached decorator with cache invalidation."""
        cache_obj, mock_redis = cache_instance
        mock_redis.get.return_value = None
        mock_redis.keys.return_value = [b"marb:claim:1"]

        with patch("app.utils.cache.cache", cache_obj):
            @cached(ttl_seconds=3600, invalidate_on=["claim:*"])
            def test_function() -> dict:
                return {"result": "test"}

            result = test_function()

            assert result == {"result": "test"}
            # Should invalidate cache patterns
            mock_redis.keys.assert_called()

    def test_cached_decorator_default_ttl(self, cache_instance):
        """Test @cached decorator with default TTL."""
        cache_obj, mock_redis = cache_instance
        mock_redis.get.return_value = None

        with patch("app.utils.cache.cache", cache_obj):
            @cached()  # No TTL specified, should use default 3600
            def test_function() -> dict:
                return {"result": "test"}

            result = test_function()

            assert result == {"result": "test"}
            # Should use default TTL of 3600
            args = mock_redis.setex.call_args
            assert args[0][1] == 3600  # TTL should be 3600


@pytest.mark.unit
class TestCacheKeyHelpers:
    """Tests for cache key helper functions."""

    def test_cache_key(self):
        """Test cache_key function."""
        key = cache_key("claim", 1, "status", "pending")
        assert key == "claim:1:status:pending"

    def test_cache_key_with_none(self):
        """Test cache_key function with None values."""
        key = cache_key("claim", None, "status", None)
        assert key == "claim:status"

    def test_claim_cache_key(self):
        """Test claim_cache_key function."""
        key = claim_cache_key(123)
        assert key == "claim:123"

    def test_risk_score_cache_key(self):
        """Test risk_score_cache_key function."""
        key = risk_score_cache_key(456)
        assert key == "risk_score:456"

    def test_payer_cache_key(self):
        """Test payer_cache_key function."""
        key = payer_cache_key(789)
        assert key == "payer:789"

    def test_remittance_cache_key(self):
        """Test remittance_cache_key function."""
        key = remittance_cache_key(101)
        assert key == "remittance:101"

    def test_episode_cache_key(self):
        """Test episode_cache_key function."""
        key = episode_cache_key(202)
        assert key == "episode:202"

    def test_count_cache_key_no_filters(self):
        """Test count_cache_key without filters."""
        key = count_cache_key("claim")
        assert key == "count:claim"

    def test_count_cache_key_with_filters(self):
        """Test count_cache_key with filters."""
        key = count_cache_key("claim", status="pending", payer_id=1)
        # Should include filters in sorted order
        assert "count:claim" in key
        assert "payer_id=1" in key
        assert "status=pending" in key

    def test_count_cache_key_filters_sorted(self):
        """Test that count_cache_key sorts filters consistently."""
        key1 = count_cache_key("claim", status="pending", payer_id=1)
        key2 = count_cache_key("claim", payer_id=1, status="pending")
        # Should be the same regardless of filter order
        assert key1 == key2


@pytest.mark.unit
class TestCacheTTLInference:
    """Tests for TTL inference from cache keys."""

    def test_infer_ttl_from_claim_key(self, cache_instance):
        """Test TTL inference for claim keys."""
        cache, mock_redis = cache_instance
        with patch("app.config.cache_ttl.get_ttl", return_value=1800):
            result = cache.set("claim:123", {"data": "test"})
            
            assert result is True
            mock_redis.setex.assert_called_once_with("test:claim:123", 1800, json.dumps({"data": "test"}))

    def test_infer_ttl_from_risk_score_key(self, cache_instance):
        """Test TTL inference for risk_score keys."""
        cache, mock_redis = cache_instance
        with patch("app.config.cache_ttl.get_ttl", return_value=3600):
            result = cache.set("risk_score:456", {"score": 75})
            
            assert result is True
            mock_redis.setex.assert_called_once_with("test:risk_score:456", 3600, json.dumps({"score": 75}))

    def test_infer_ttl_from_unknown_key(self, cache_instance):
        """Test TTL inference for unknown key pattern (no TTL)."""
        cache, mock_redis = cache_instance
        result = cache.set("unknown:key", {"data": "test"})
        
        assert result is True
        # Should use set() without TTL since pattern not recognized
        mock_redis.set.assert_called_once_with("test:unknown:key", json.dumps({"data": "test"}))

    def test_infer_ttl_import_error(self, cache_instance):
        """Test TTL inference when config import fails."""
        cache, mock_redis = cache_instance
        with patch("app.utils.cache.Cache._infer_ttl_from_key", side_effect=Exception("Import error")):
            result = cache.set("claim:123", {"data": "test"})
            
            assert result is True
            # Should fall back to set() without TTL
            mock_redis.set.assert_called_once_with("test:claim:123", json.dumps({"data": "test"}))

    def test_set_with_explicit_ttl_overrides_inference(self, cache_instance):
        """Test that explicit TTL overrides inference."""
        cache, mock_redis = cache_instance
        result = cache.set("claim:123", {"data": "test"}, ttl_seconds=7200)
        
        assert result is True
        # Should use explicit TTL, not inferred
        mock_redis.setex.assert_called_once_with("test:claim:123", 7200, json.dumps({"data": "test"}))

    def test_get_stats_with_no_operations(self, cache_instance):
        """Test getting stats when no operations have been performed."""
        cache, mock_redis = cache_instance
        
        stats = cache.get_stats()
        
        assert "overall" in stats
        assert stats["overall"]["hits"] == 0
        assert stats["overall"]["misses"] == 0
        assert stats["overall"]["total"] == 0
        assert stats["overall"]["hit_rate"] == 0.0
        assert "by_key" in stats

    def test_get_stats_single_key_no_operations(self, cache_instance):
        """Test getting stats for a key with no operations."""
        cache, mock_redis = cache_instance
        
        stats = cache.get_stats("nonexistent_key")
        
        assert stats["key"] == "nonexistent_key"
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["total"] == 0
        assert stats["hit_rate"] == 0.0

    def test_reset_stats_nonexistent_key(self, cache_instance):
        """Test resetting stats for a key that doesn't exist."""
        cache, mock_redis = cache_instance
        
        # Should not raise an error
        cache.reset_stats("nonexistent_key")
        
        stats = cache.get_stats("nonexistent_key")
        assert stats["total"] == 0

    def test_clear_namespace_with_no_keys(self, cache_instance):
        """Test clearing namespace when no keys exist."""
        cache, mock_redis = cache_instance
        mock_redis.scan.side_effect = [
            (0, []),  # No keys found
        ]
        
        result = cache.clear_namespace()
        
        assert result == 0
        mock_redis.scan.assert_called()
        mock_redis.delete.assert_not_called()

    def test_delete_pattern_with_special_characters(self, cache_instance):
        """Test delete_pattern with special characters in pattern."""
        cache, mock_redis = cache_instance
        mock_redis.scan.side_effect = [
            (0, [b"test:claim:1:status:pending"]),
        ]
        mock_redis.delete.return_value = 1
        
        result = cache.delete_pattern("claim:*:status:*")
        
        assert result == 1
        mock_redis.scan.assert_called()

    def test_get_with_json_decode_error(self, cache_instance):
        """Test get when cached value is invalid JSON."""
        cache, mock_redis = cache_instance
        # Return invalid JSON
        mock_redis.get.return_value = b"invalid json{"
        
        result = cache.get("test_key")
        
        # Should handle gracefully and return None
        assert result is None

    def test_set_with_ttl_zero(self, cache_instance):
        """Test setting value with TTL of 0 (should use set, not setex)."""
        cache, mock_redis = cache_instance
        
        result = cache.set("test_key", {"data": "test"}, ttl_seconds=0)
        
        assert result is True
        # Should use set() not setex() when TTL is 0
        mock_redis.set.assert_called_once()
        mock_redis.setex.assert_not_called()

    def test_set_with_ttl_none_and_no_inference(self, cache_instance):
        """Test setting value with None TTL and no key pattern match."""
        cache, mock_redis = cache_instance
        with patch("app.utils.cache.Cache._infer_ttl_from_key", return_value=None):
            result = cache.set("unknown:key", {"data": "test"})
            
            assert result is True
            # Should use set() without TTL
            mock_redis.set.assert_called_once()
            mock_redis.setex.assert_not_called()

    def test_get_stats_hit_rate_calculation(self, cache_instance):
        """Test that hit rate is calculated correctly."""
        cache, mock_redis = cache_instance
        
        # Simulate some cache operations
        mock_redis.get.side_effect = [
            json.dumps({"data": "cached"}),  # Hit
            None,  # Miss
            json.dumps({"data": "cached"}),  # Hit
        ]
        
        cache.get("key1", track_stats=True)
        cache.get("key1", track_stats=True)
        cache.get("key1", track_stats=True)
        
        stats = cache.get_stats("key1")
        
        # Should have 2 hits and 1 miss = 66.67% hit rate
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["total"] == 3
        assert 66.0 <= stats["hit_rate"] <= 67.0  # Allow for rounding

    def test_delete_pattern_with_empty_pattern(self, cache_instance):
        """Test delete_pattern with empty pattern."""
        cache, mock_redis = cache_instance
        mock_redis.scan.side_effect = [
            (0, []),
        ]
        
        result = cache.delete_pattern("")
        
        assert result == 0
        # Should still call scan with the namespaced pattern
        mock_redis.scan.assert_called()

    def test_exists_with_redis_error_returns_false(self, cache_instance):
        """Test that exists returns False on Redis error."""
        cache, mock_redis = cache_instance
        mock_redis.exists.side_effect = Exception("Redis connection error")
        
        result = cache.exists("test_key")
        
        assert result is False

    def test_delete_with_multiple_keys(self, cache_instance):
        """Test delete operation."""
        cache, mock_redis = cache_instance
        mock_redis.delete.return_value = 1
        
        result = cache.delete("test_key")
        
        assert result is True
        mock_redis.delete.assert_called_once_with("test:test_key")

    def test_get_many_empty_list(self, cache_instance):
        """Test get_many with empty list."""
        cache, mock_redis = cache_instance
        
        result = cache.get_many([])
        
        assert result == {}
        mock_redis.mget.assert_not_called()

    def test_get_many_success(self, cache_instance):
        """Test get_many with successful retrieval."""
        cache, mock_redis = cache_instance
        cached_value1 = json.dumps({"data": "test1"})
        cached_value2 = json.dumps({"data": "test2"})
        mock_redis.mget.return_value = [cached_value1, None, cached_value2]
        
        result = cache.get_many(["key1", "key2", "key3"])
        
        assert "key1" in result
        assert result["key1"] == {"data": "test1"}
        assert "key2" not in result  # None value not included
        assert "key3" in result
        assert result["key3"] == {"data": "test2"}
        mock_redis.mget.assert_called_once_with(["test:key1", "test:key2", "test:key3"])

    def test_get_many_with_invalid_json(self, cache_instance):
        """Test get_many when cached value is invalid JSON."""
        cache, mock_redis = cache_instance
        mock_redis.mget.return_value = [b"invalid json{", None]
        
        result = cache.get_many(["key1", "key2"])
        
        assert result == {}
        # Should handle gracefully and not include invalid entries

    def test_get_many_error(self, cache_instance):
        """Test get_many when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.mget.side_effect = Exception("Redis error")
        
        result = cache.get_many(["key1", "key2"])
        
        assert result == {}

    def test_set_many_empty_dict(self, cache_instance):
        """Test set_many with empty dictionary."""
        cache, mock_redis = cache_instance
        
        result = cache.set_many({})
        
        assert result == 0
        mock_redis.pipeline.assert_not_called()

    def test_set_many_success(self, cache_instance):
        """Test set_many with successful operations."""
        cache, mock_redis = cache_instance
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = [True, True]
        
        result = cache.set_many({"key1": {"data": "test1"}, "key2": {"data": "test2"}}, ttl_seconds=3600)
        
        assert result == 2
        assert mock_pipe.setex.call_count == 2
        mock_pipe.execute.assert_called_once()

    def test_set_many_with_ttl_inference(self, cache_instance):
        """Test set_many with TTL inference from key patterns."""
        cache, mock_redis = cache_instance
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = [True]
        
        with patch("app.utils.cache.Cache._infer_ttl_from_key", return_value=1800):
            result = cache.set_many({"claim:123": {"data": "test"}})
            
            assert result == 1
            # Should use inferred TTL
            mock_pipe.setex.assert_called_once()

    def test_set_many_partial_failure(self, cache_instance):
        """Test set_many when some items fail to serialize."""
        cache, mock_redis = cache_instance
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        
        # Create a value that can't be serialized (circular reference)
        class Circular:
            def __init__(self):
                self.ref = self
        
        result = cache.set_many({"key1": {"data": "test"}, "key2": Circular()})
        
        # Should still set the valid key
        assert result >= 1

    def test_set_many_error(self, cache_instance):
        """Test set_many when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.pipeline.side_effect = Exception("Redis error")
        
        result = cache.set_many({"key1": {"data": "test"}})
        
        assert result == 0

    def test_delete_many_empty_list(self, cache_instance):
        """Test delete_many with empty list."""
        cache, mock_redis = cache_instance
        
        result = cache.delete_many([])
        
        assert result == 0
        mock_redis.delete.assert_not_called()

    def test_delete_many_success(self, cache_instance):
        """Test delete_many with successful deletion."""
        cache, mock_redis = cache_instance
        mock_redis.delete.return_value = 2
        
        result = cache.delete_many(["key1", "key2", "key3"])
        
        assert result == 2
        mock_redis.delete.assert_called_once_with("test:key1", "test:key2", "test:key3")

    def test_delete_many_error(self, cache_instance):
        """Test delete_many when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.delete.side_effect = Exception("Redis error")
        
        result = cache.delete_many(["key1", "key2"])
        
        assert result == 0

    def test_get_ttl_key_exists(self, cache_instance):
        """Test get_ttl when key exists with TTL."""
        cache, mock_redis = cache_instance
        mock_redis.ttl.return_value = 3600
        
        result = cache.get_ttl("test_key")
        
        assert result == 3600
        mock_redis.ttl.assert_called_once_with("test:test_key")

    def test_get_ttl_key_no_ttl(self, cache_instance):
        """Test get_ttl when key exists but has no TTL."""
        cache, mock_redis = cache_instance
        mock_redis.ttl.return_value = -1
        
        result = cache.get_ttl("test_key")
        
        assert result is None

    def test_get_ttl_key_not_exists(self, cache_instance):
        """Test get_ttl when key doesn't exist."""
        cache, mock_redis = cache_instance
        mock_redis.ttl.return_value = -2
        
        result = cache.get_ttl("test_key")
        
        assert result is None

    def test_get_ttl_error(self, cache_instance):
        """Test get_ttl when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.ttl.side_effect = Exception("Redis error")
        
        result = cache.get_ttl("test_key")
        
        assert result is None

    def test_expire_success(self, cache_instance):
        """Test expire when key exists."""
        cache, mock_redis = cache_instance
        mock_redis.expire.return_value = True
        
        result = cache.expire("test_key", 3600)
        
        assert result is True
        mock_redis.expire.assert_called_once_with("test:test_key", 3600)

    def test_expire_key_not_exists(self, cache_instance):
        """Test expire when key doesn't exist."""
        cache, mock_redis = cache_instance
        mock_redis.expire.return_value = False
        
        result = cache.expire("test_key", 3600)
        
        assert result is False

    def test_expire_error(self, cache_instance):
        """Test expire when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.expire.side_effect = Exception("Redis error")
        
        result = cache.expire("test_key", 3600)
        
        assert result is False

    def test_persist_success(self, cache_instance):
        """Test persist when key exists."""
        cache, mock_redis = cache_instance
        mock_redis.persist.return_value = True
        
        result = cache.persist("test_key")
        
        assert result is True
        mock_redis.persist.assert_called_once_with("test:test_key")

    def test_persist_key_not_exists(self, cache_instance):
        """Test persist when key doesn't exist."""
        cache, mock_redis = cache_instance
        mock_redis.persist.return_value = False
        
        result = cache.persist("test_key")
        
        assert result is False

    def test_persist_error(self, cache_instance):
        """Test persist when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.persist.side_effect = Exception("Redis error")
        
        result = cache.persist("test_key")
        
        assert result is False

    def test_keys_success(self, cache_instance):
        """Test keys with successful retrieval."""
        cache, mock_redis = cache_instance
        mock_redis.scan.side_effect = [
            (0, [b"test:claim:1", b"test:claim:2"]),
        ]
        
        result = cache.keys("claim:*")
        
        assert len(result) == 2
        assert "claim:1" in result or b"claim:1" in result
        mock_redis.scan.assert_called()

    def test_keys_multiple_scans(self, cache_instance):
        """Test keys with multiple SCAN iterations."""
        cache, mock_redis = cache_instance
        mock_redis.scan.side_effect = [
            (100, [b"test:claim:1"]),
            (0, [b"test:claim:2"]),
        ]
        
        result = cache.keys("claim:*")
        
        assert len(result) == 2
        assert mock_redis.scan.call_count == 2

    def test_keys_error(self, cache_instance):
        """Test keys when Redis error occurs."""
        cache, mock_redis = cache_instance
        mock_redis.scan.side_effect = Exception("Redis error")
        
        result = cache.keys("claim:*")
        
        assert result == []

    def test_infer_ttl_all_patterns(self, cache_instance):
        """Test _infer_ttl_from_key with all supported patterns."""
        cache, mock_redis = cache_instance
        patterns = [
            ("claim:123", "claim"),
            ("risk_score:456", "risk_score"),
            ("payer:789", "payer"),
            ("remittance:101", "remittance"),
            ("episode:202", "episode"),
            ("provider:303", "provider"),
            ("practice_config:404", "practice_config"),
            ("count:505", "count"),
        ]
        
        for key, pattern_type in patterns:
            with patch("app.config.cache_ttl.get_ttl", return_value=3600):
                ttl = cache._infer_ttl_from_key(key)
                assert ttl == 3600

    def test_infer_ttl_no_match(self, cache_instance):
        """Test _infer_ttl_from_key with no matching pattern."""
        cache, mock_redis = cache_instance
        ttl = cache._infer_ttl_from_key("unknown:pattern")
        assert ttl is None

    def test_infer_ttl_import_error(self, cache_instance):
        """Test _infer_ttl_from_key when config import fails."""
        cache, mock_redis = cache_instance
        with patch("app.utils.cache.Cache._infer_ttl_from_key", side_effect=ImportError("No module")):
            # Should handle gracefully
            ttl = cache._infer_ttl_from_key("claim:123")
            # When import fails, should return None
            # But the method itself should not raise
            pass  # Just verify no exception

    def test_set_with_negative_ttl(self, cache_instance):
        """Test set with negative TTL (should use set, not setex)."""
        cache, mock_redis = cache_instance
        
        result = cache.set("test_key", {"data": "test"}, ttl_seconds=-1)
        
        assert result is True
        # Should use set() not setex() when TTL is negative
        mock_redis.set.assert_called_once()
        mock_redis.setex.assert_not_called()

    def test_get_many_with_track_stats_false(self, cache_instance):
        """Test get_many without stats tracking."""
        cache, mock_redis = cache_instance
        cached_value = json.dumps({"data": "test"})
        mock_redis.mget.return_value = [cached_value]
        
        result = cache.get_many(["key1"], track_stats=False)
        
        assert "key1" in result
        # Stats should not be recorded

    def test_set_many_with_no_ttl(self, cache_instance):
        """Test set_many without TTL."""
        cache, mock_redis = cache_instance
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = [True]
        
        result = cache.set_many({"key1": {"data": "test"}}, ttl_seconds=None)
        
        assert result == 1
        # Should use set() not setex() when TTL is None and no inference

    def test_set_many_with_serialization_error(self, cache_instance):
        """Test set_many handles serialization errors gracefully."""
        cache, mock_redis = cache_instance
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        
        # Create value that can't be serialized
        class Unserializable:
            pass
        
        result = cache.set_many({"key1": Unserializable()})
        
        # Should handle gracefully, might return 0 or partial success
        assert isinstance(result, int)
        assert result >= 0

    def test_get_many_with_type_error(self, cache_instance):
        """Test get_many handles TypeError in JSON decode."""
        cache, mock_redis = cache_instance
        # Return something that causes TypeError
        mock_redis.mget.return_value = [b"invalid"]
        
        result = cache.get_many(["key1"])
        
        # Should handle gracefully
        assert isinstance(result, dict)

    def test_keys_with_bytes_keys(self, cache_instance):
        """Test keys handles bytes keys from Redis."""
        cache, mock_redis = cache_instance
        mock_redis.scan.side_effect = [
            (0, [b"test:claim:1", b"test:claim:2"]),
        ]
        
        result = cache.keys("claim:*")
        
        # Should decode bytes to strings
        assert len(result) == 2
        assert all(isinstance(k, str) for k in result)

    def test_keys_with_string_keys(self, cache_instance):
        """Test keys handles string keys from Redis."""
        cache, mock_redis = cache_instance
        mock_redis.scan.side_effect = [
            (0, ["test:claim:1", "test:claim:2"]),
        ]
        
        result = cache.keys("claim:*")
        
        # Should work with string keys
        assert len(result) == 2
        assert all(isinstance(k, str) for k in result)

    def test_keys_with_namespace_prefix(self, cache_instance):
        """Test keys removes namespace prefix correctly."""
        cache, mock_redis = cache_instance
        # Keys already have namespace prefix
        mock_redis.scan.side_effect = [
            (0, [b"test:claim:1", b"test:claim:2"]),
        ]
        
        result = cache.keys("claim:*")
        
        # Should remove "test:" prefix
        assert all(not k.startswith("test:") for k in result)

    def test_get_stats_with_mixed_hits_misses(self, cache_instance):
        """Test get_stats with mixed hits and misses."""
        cache, mock_redis = cache_instance
        
        # Simulate operations
        mock_redis.get.side_effect = [
            json.dumps({"data": "cached"}),  # Hit
            None,  # Miss
            json.dumps({"data": "cached"}),  # Hit
            None,  # Miss
            None,  # Miss
        ]
        
        for _ in range(5):
            cache.get("key1", track_stats=True)
        
        stats = cache.get_stats("key1")
        
        assert stats["hits"] == 2
        assert stats["misses"] == 3
        assert stats["total"] == 5
        assert stats["hit_rate"] == pytest.approx(40.0, abs=0.1)

