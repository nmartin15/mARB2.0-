"""Risk scoring weights configuration.

All risk component weights can be overridden via environment variables.
Weights should sum to 1.0 for proper weighted average calculation.
"""
import os
from typing import Dict

# Default risk component weights
DEFAULT_WEIGHTS = {
    "payer_risk": 0.20,
    "coding_risk": 0.25,
    "doc_risk": 0.20,
    "historical_risk": 0.15,
    "pattern_risk": 0.20,
}

# Environment variable mappings
ENV_VAR_MAP = {
    "payer_risk": "RISK_WEIGHT_PAYER",
    "coding_risk": "RISK_WEIGHT_CODING",
    "doc_risk": "RISK_WEIGHT_DOC",
    "historical_risk": "RISK_WEIGHT_HISTORICAL",
    "pattern_risk": "RISK_WEIGHT_PATTERN",
}


def get_risk_weights() -> Dict[str, float]:
    """
    Get risk component weights from environment variables or defaults.
    
    Returns:
        Dictionary of risk component weights
    """
    weights = {}
    
    for key, default_value in DEFAULT_WEIGHTS.items():
        env_var = ENV_VAR_MAP.get(key)
        if env_var:
            env_value = os.getenv(env_var)
            if env_value:
                try:
                    weights[key] = float(env_value)
                except ValueError:
                    weights[key] = default_value
            else:
                weights[key] = default_value
        else:
            weights[key] = default_value
    
    return weights


def validate_weights(weights: Dict[str, float]) -> bool:
    """
    Validate that weights sum to approximately 1.0.
    
    Args:
        weights: Dictionary of risk component weights
        
    Returns:
        True if weights are valid (sum to ~1.0), False otherwise
    """
    total = sum(weights.values())
    # Allow small floating point differences
    return abs(total - 1.0) < 0.01

