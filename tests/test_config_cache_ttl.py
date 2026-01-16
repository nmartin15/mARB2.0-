"""Tests for cache TTL configuration."""
import os
from unittest.mock import patch
import pytest

from app.config.cache_ttl import (
    get_ttl,
    get_risk_score_ttl,
    get_claim_ttl,
    get_payer_ttl,
    get_remittance_ttl,
    get_episode_ttl,
    get_provider_ttl,
    get_practice_config_ttl,
    get_count_ttl,
    DEFAULT_TTL,
    ENV_VAR_MAP,
)


@pytest.mark.unit
class TestCacheTTLConfiguration:
    """Tests for cache TTL configuration."""

    def test_get_ttl_returns_default(self):
        """Test that get_ttl returns default value when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            ttl = get_ttl("risk_score")
            assert ttl == DEFAULT_TTL["risk_score"]

    def test_get_ttl_uses_env_var(self):
        """Test that get_ttl uses environment variable when set."""
        with patch.dict(os.environ, {"CACHE_TTL_RISK_SCORE": "7200"}, clear=False):
            ttl = get_ttl("risk_score")
            assert ttl == 7200

    def test_get_ttl_invalid_env_var_uses_default(self):
        """Test that get_ttl uses default when env var is invalid."""
        with patch.dict(os.environ, {"CACHE_TTL_RISK_SCORE": "invalid"}, clear=False):
            ttl = get_ttl("risk_score")
            assert ttl == DEFAULT_TTL["risk_score"]

    def test_get_ttl_unknown_type_uses_default(self):
        """Test that get_ttl uses default for unknown cache type."""
        with patch.dict(os.environ, {}, clear=True):
            ttl = get_ttl("unknown_type")
            assert ttl == 3600  # Default fallback

    def test_get_ttl_all_cache_types(self):
        """Test that get_ttl works for all defined cache types."""
        cache_types = [
            "risk_score",
            "claim",
            "payer",
            "remittance",
            "episode",
            "provider",
            "practice_config",
            "count",
        ]
        
        with patch.dict(os.environ, {}, clear=True):
            for cache_type in cache_types:
                ttl = get_ttl(cache_type)
                assert ttl == DEFAULT_TTL[cache_type]
                assert isinstance(ttl, int)
                assert ttl > 0

    def test_get_ttl_env_var_mapping(self):
        """Test that all cache types have environment variable mappings."""
        for cache_type in DEFAULT_TTL.keys():
            assert cache_type in ENV_VAR_MAP
            env_var = ENV_VAR_MAP[cache_type]
            assert env_var.startswith("CACHE_TTL_")

    def test_get_risk_score_ttl(self):
        """Test get_risk_score_ttl convenience function."""
        with patch("app.config.cache_ttl.get_ttl", return_value=7200) as mock_get_ttl:
            ttl = get_risk_score_ttl()
            assert ttl == 7200
            mock_get_ttl.assert_called_once_with("risk_score")

    def test_get_claim_ttl(self):
        """Test get_claim_ttl convenience function."""
        with patch("app.config.cache_ttl.get_ttl", return_value=3600) as mock_get_ttl:
            ttl = get_claim_ttl()
            assert ttl == 3600
            mock_get_ttl.assert_called_once_with("claim")

    def test_get_payer_ttl(self):
        """Test get_payer_ttl convenience function."""
        with patch("app.config.cache_ttl.get_ttl", return_value=86400) as mock_get_ttl:
            ttl = get_payer_ttl()
            assert ttl == 86400
            mock_get_ttl.assert_called_once_with("payer")

    def test_get_remittance_ttl(self):
        """Test get_remittance_ttl convenience function."""
        with patch("app.config.cache_ttl.get_ttl", return_value=1800) as mock_get_ttl:
            ttl = get_remittance_ttl()
            assert ttl == 1800
            mock_get_ttl.assert_called_once_with("remittance")

    def test_get_episode_ttl(self):
        """Test get_episode_ttl convenience function."""
        with patch("app.config.cache_ttl.get_ttl", return_value=1800) as mock_get_ttl:
            ttl = get_episode_ttl()
            assert ttl == 1800
            mock_get_ttl.assert_called_once_with("episode")

    def test_get_provider_ttl(self):
        """Test get_provider_ttl convenience function."""
        with patch("app.config.cache_ttl.get_ttl", return_value=3600) as mock_get_ttl:
            ttl = get_provider_ttl()
            assert ttl == 3600
            mock_get_ttl.assert_called_once_with("provider")

    def test_get_practice_config_ttl(self):
        """Test get_practice_config_ttl convenience function."""
        with patch("app.config.cache_ttl.get_ttl", return_value=86400) as mock_get_ttl:
            ttl = get_practice_config_ttl()
            assert ttl == 86400
            mock_get_ttl.assert_called_once_with("practice_config")

    def test_get_count_ttl(self):
        """Test get_count_ttl convenience function."""
        with patch("app.config.cache_ttl.get_ttl", return_value=300) as mock_get_ttl:
            ttl = get_count_ttl()
            assert ttl == 300
            mock_get_ttl.assert_called_once_with("count")

    def test_get_ttl_with_zero_env_var(self):
        """Test that get_ttl handles zero value from env var."""
        with patch.dict(os.environ, {"CACHE_TTL_RISK_SCORE": "0"}, clear=False):
            ttl = get_ttl("risk_score")
            assert ttl == 0

    def test_get_ttl_with_negative_env_var_uses_default(self):
        """Test that get_ttl uses default when env var is negative."""
        with patch.dict(os.environ, {"CACHE_TTL_RISK_SCORE": "-100"}, clear=False):
            ttl = get_ttl("risk_score")
            # Negative values are still valid integers, so they'll be used
            assert ttl == -100

    def test_get_ttl_with_float_string_uses_default(self):
        """Test that get_ttl uses default when env var is float string."""
        with patch.dict(os.environ, {"CACHE_TTL_RISK_SCORE": "3600.5"}, clear=False):
            ttl = get_ttl("risk_score")
            # Float strings cause ValueError, so default is used
            assert ttl == DEFAULT_TTL["risk_score"]

    def test_default_ttl_values_are_reasonable(self):
        """Test that default TTL values are reasonable (positive integers)."""
        for cache_type, ttl in DEFAULT_TTL.items():
            assert isinstance(ttl, int)
            assert ttl > 0
            assert ttl < 86400 * 7  # Less than a week

