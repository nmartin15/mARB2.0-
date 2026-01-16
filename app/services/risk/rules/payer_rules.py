"""Payer-specific rules engine."""
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session

from app.models.database import Claim, Payer
from app.utils.logger import get_logger
from app.config.cache_ttl import get_payer_ttl
from app.utils.cache import cache, payer_cache_key

logger = get_logger(__name__)


class PayerRulesEngine:
    """
    Evaluate payer-specific risk rules.
    
    This engine evaluates claims against payer-specific rules and configurations.
    It uses Redis caching to improve performance by caching payer data with a
    configurable TTL (time-to-live) based on the payer's update frequency.
    
    Cache Strategy:
    - Payer data is cached using the payer_cache_key() function
    - Cache TTL is configured via get_payer_ttl() from app.config.cache_ttl
    - Cache is automatically invalidated when payer data is updated
    - Cache keys follow the pattern: "marb:payer:{payer_id}"
    
    Configuration:
    - Payer-specific rules are stored in the Payer.rules_config JSON field
    - Rules can include: allowed_frequency_types, restricted_facility_types, etc.
    - Rules are evaluated in order and risk scores are cumulative
    """

    def __init__(self, db: Session):
        """
        Initialize payer rules engine.
        
        Args:
            db: Database session for querying payer data
        """
        self.db = db

    def evaluate(self, claim: Claim) -> Tuple[float, List[Dict]]:
        """
        Evaluate payer-specific rules.
        
        Returns:
            (risk_score, risk_factors)
        """
        risk_score = 0.0
        risk_factors = []
        
        if not claim.payer_id:
            risk_factors.append({
                "type": "payer",
                "severity": "medium",
                "message": "Payer information missing",
            })
            return 30.0, risk_factors
        
        # Try to get payer from cache
        payer_cache_key_str = payer_cache_key(claim.payer_id)
        cached_payer = cache.get(payer_cache_key_str)
        
        if cached_payer:
            payer_data = cached_payer
        else:
            # Query payer directly - more efficient than count() + first()
            payer = self.db.query(Payer).filter(Payer.id == claim.payer_id).first()
            if not payer:
                risk_factors.append({
                    "type": "payer",
                    "severity": "medium",
                    "message": "Payer not found in DB",
                })
                return 20.0, risk_factors
            
            # Cache payer data with configured TTL
            payer_data = {
                "id": payer.id,
                "name": payer.name,
                "rules_config": payer.rules_config or {},
            }
            cache.set(payer_cache_key_str, payer_data, ttl_seconds=get_payer_ttl())
        
        # Check payer-specific rules from configuration
        rules_config = payer_data.get("rules_config", {})
        
        # Example: Check if claim frequency type is allowed
        if claim.claim_frequency_type:
            allowed_frequencies = rules_config.get("allowed_frequency_types", [])
            if allowed_frequencies and claim.claim_frequency_type not in allowed_frequencies:
                risk_score += 25.0
                risk_factors.append({
                    "type": "payer",
                    "severity": "high",
                    "message": f"Claim frequency type {claim.claim_frequency_type} may not be accepted by payer",
                })
        
        # Example: Check facility type restrictions
        if claim.facility_type_code:
            restricted_facilities = rules_config.get("restricted_facility_types", [])
            if claim.facility_type_code in restricted_facilities:
                risk_score += 30.0
                risk_factors.append({
                    "type": "payer",
                    "severity": "high",
                    "message": f"Facility type {claim.facility_type_code} may be restricted by payer",
                })
        
        # Check historical denial patterns for this payer
        # TODO: Integrate with DenialPattern model
        
        return min(risk_score, 100.0), risk_factors

