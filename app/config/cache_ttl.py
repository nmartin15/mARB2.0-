"""Cache TTL (Time To Live) configuration.

All TTL values are in seconds and can be overridden via environment variables.
"""
import os

# Default TTL values (in seconds)
DEFAULT_TTL = {
    "risk_score": 3600,  # 1 hour
    "claim": 1800,  # 30 minutes
    "payer": 86400,  # 24 hours
    "remittance": 1800,  # 30 minutes
    "episode": 1800,  # 30 minutes
    "provider": 3600,  # 1 hour
    "practice_config": 86400,  # 24 hours
    "count": 300,  # 5 minutes - for count queries
}

# Environment variable mappings
ENV_VAR_MAP = {
    "risk_score": "CACHE_TTL_RISK_SCORE",
    "claim": "CACHE_TTL_CLAIM",
    "payer": "CACHE_TTL_PAYER",
    "remittance": "CACHE_TTL_REMITTANCE",
    "episode": "CACHE_TTL_EPISODE",
    "provider": "CACHE_TTL_PROVIDER",
    "practice_config": "CACHE_TTL_PRACTICE_CONFIG",
    "count": "CACHE_TTL_COUNT",
}


def get_ttl(cache_type: str) -> int:
    """
    Get TTL value for a cache type.
    
    Args:
        cache_type: Type of cache (e.g., "risk_score", "claim", "payer")
        
    Returns:
        TTL value in seconds
    """
    # Check environment variable first
    env_var = ENV_VAR_MAP.get(cache_type)
    if env_var:
        env_value = os.getenv(env_var)
        if env_value:
            try:
                return int(env_value)
            except ValueError:
                pass
    
    # Fall back to default
    return DEFAULT_TTL.get(cache_type, 3600)  # Default to 1 hour if not found


# Convenience functions for common cache types
def get_risk_score_ttl() -> int:
    """Get TTL for risk score cache."""
    return get_ttl("risk_score")


def get_claim_ttl() -> int:
    """Get TTL for claim cache."""
    return get_ttl("claim")


def get_payer_ttl() -> int:
    """Get TTL for payer cache."""
    return get_ttl("payer")


def get_remittance_ttl() -> int:
    """Get TTL for remittance cache."""
    return get_ttl("remittance")


def get_episode_ttl() -> int:
    """Get TTL for episode cache."""
    return get_ttl("episode")


def get_provider_ttl() -> int:
    """Get TTL for provider cache."""
    return get_ttl("provider")


def get_practice_config_ttl() -> int:
    """Get TTL for practice config cache."""
    return get_ttl("practice_config")


def get_count_ttl() -> int:
    """Get TTL for count query cache."""
    return get_ttl("count")

