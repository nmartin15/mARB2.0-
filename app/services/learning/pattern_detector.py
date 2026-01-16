"""Denial pattern detection and learning."""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session, joinedload, selectinload
from datetime import datetime, timedelta
from collections import defaultdict

from app.models.database import (
    ClaimEpisode,
    DenialPattern,
    Remittance,
    Payer,
    EpisodeStatus,
)
from app.utils.logger import get_logger
from app.utils.cache import cache, cache_key
from app.config.cache_ttl import get_payer_ttl

logger = get_logger(__name__)


class PatternDetector:
    """Detect and learn denial patterns from historical data."""

    def __init__(self, db: Session):
        self.db = db

    def detect_patterns_for_payer(self, payer_id: int, days_back: int = 90) -> List[DenialPattern]:
        """Detect denial patterns for a specific payer."""
        logger.info("Detecting patterns for payer", payer_id=payer_id, days_back=days_back)
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Get episodes with denials for this payer - eager load remittance and claim to avoid N+1
        # Load both relationships even if not immediately used, to prevent lazy loading issues
        episodes = (
            self.db.query(ClaimEpisode)
            .join(Remittance)
            .options(
                joinedload(ClaimEpisode.remittance),
                joinedload(ClaimEpisode.claim)  # Load claim relationship to prevent N+1 if accessed
            )
            .filter(
                Remittance.payer_id == payer_id,
                ClaimEpisode.status == EpisodeStatus.COMPLETE,
                ClaimEpisode.denial_count > 0,
                Remittance.created_at >= cutoff_date,
            )
            .all()
        )
        
        if not episodes:
            logger.info("No denial episodes found for payer", payer_id=payer_id)
            return []
        
        # Analyze denial reasons
        denial_reasons = defaultdict(lambda: {"count": 0, "episodes": []})
        for episode in episodes:
            remittance = episode.remittance
            reasons = remittance.denial_reasons or []
            for reason in reasons:
                reason_code = reason.get("code") if isinstance(reason, dict) else str(reason)
                if reason_code:
                    denial_reasons[reason_code]["count"] += 1
                    denial_reasons[reason_code]["episodes"].append(episode.id)
        
        # Batch load all existing patterns for this payer to avoid N+1 queries
        existing_patterns = {
            pattern.denial_reason_code: pattern
            for pattern in (
                self.db.query(DenialPattern)
                .filter(DenialPattern.payer_id == payer_id)
                .all()
            )
        }
        
        # Create or update patterns
        patterns = []
        total_episodes = len(episodes)
        now = datetime.now()
        
        for reason_code, data in denial_reasons.items():
            frequency = data["count"] / total_episodes
            
            # Only create pattern if frequency is significant
            if frequency < 0.05:  # Less than 5% frequency
                continue
            
            # Check if pattern already exists (from batch-loaded patterns)
            pattern = existing_patterns.get(reason_code)
            
            if pattern:
                # Update existing pattern
                pattern.occurrence_count = data["count"]
                pattern.frequency = frequency
                pattern.last_seen = now
                pattern.confidence_score = min(frequency * 1.5, 1.0)  # Cap at 1.0
            else:
                # Create new pattern
                pattern = DenialPattern(
                    payer_id=payer_id,
                    pattern_type="denial_reason",
                    pattern_description=f"Denial reason code: {reason_code}",
                    denial_reason_code=reason_code,
                    occurrence_count=data["count"],
                    frequency=frequency,
                    confidence_score=min(frequency * 1.5, 1.0),
                    first_seen=now,
                    last_seen=now,
                )
                self.db.add(pattern)
            
            patterns.append(pattern)
        
        self.db.flush()
        
        # Invalidate cache for this payer's patterns
        cache_key_str = cache_key("pattern", "payer", payer_id)
        cache.delete(cache_key_str)
        
        logger.info(
            "Patterns detected for payer",
            payer_id=payer_id,
            pattern_count=len(patterns),
        )
        
        return patterns

    def get_patterns_for_payer(self, payer_id: int) -> List[DenialPattern]:
        """Get all denial patterns for a payer."""
        cache_key_str = cache_key("pattern", "payer", payer_id)
        ttl = get_payer_ttl()  # Use payer TTL since patterns are payer-specific
        
        # Try cache first
        cached_patterns = cache.get(cache_key_str)
        if cached_patterns is not None:
            logger.debug("Cache hit for patterns", payer_id=payer_id)
            # Validate cached data structure
            if not isinstance(cached_patterns, list) or not cached_patterns:
                logger.warning("Invalid cached patterns format", payer_id=payer_id)
                # Fall through to database query
            else:
                # Extract pattern ids efficiently from cached data (single pass)
                pattern_ids = [p.get("id") for p in cached_patterns if p.get("id") is not None]
                if pattern_ids:
                    # Batch load all patterns by IDs in a single query to avoid N+1 queries
                    patterns = (
                        self.db.query(DenialPattern)
                        .filter(DenialPattern.id.in_(pattern_ids))
                        .all()
                    )
                    # Create a dictionary for O(1) lookup of patterns by ID
                    pattern_dict = {p.id: p for p in patterns}
                    # Preserve original order from cache while filtering out missing patterns
                    patterns = [pattern_dict[pid] for pid in pattern_ids if pid in pattern_dict]
                    return patterns
                return []
        
        # Cache miss - query database
        logger.debug("Cache miss for patterns", payer_id=payer_id)
        patterns = (
            self.db.query(DenialPattern)
            .filter(DenialPattern.payer_id == payer_id)
            .order_by(DenialPattern.frequency.desc())
            .all()
        )
        
        # Cache the results (serialize to dict for caching)
        pattern_dicts = [
            {
                "id": p.id,
                "payer_id": p.payer_id,
                "pattern_type": p.pattern_type,
                "pattern_description": p.pattern_description,
                "denial_reason_code": p.denial_reason_code,
                "occurrence_count": p.occurrence_count,
                "frequency": p.frequency,
                "confidence_score": p.confidence_score,
                "conditions": p.conditions,
            }
            for p in patterns
        ]
        cache.set(cache_key_str, pattern_dicts, ttl_seconds=ttl)
        
        return patterns

    def analyze_claim_for_patterns(self, claim_id: int) -> List[Dict]:
        """
        Analyze a claim against known denial patterns.
        
        Returns a list of matching patterns with confidence scores.
        """
        from app.models.database import Claim

        # Check cache first
        cache_key_str = cache_key("pattern", "analysis", claim_id)
        cached_result = cache.get(cache_key_str)
        if cached_result is not None:
            logger.debug("Cache hit for claim pattern analysis", claim_id=claim_id)
            return cached_result

        # Eager load claim_lines to avoid N+1 queries
        claim = (
            self.db.query(Claim)
            .options(selectinload(Claim.claim_lines))
            .filter(Claim.id == claim_id)
            .first()
        )

        if not claim:
            logger.warning("Claim not found", claim_id=claim_id)
            return []

        if not claim.payer_id:
            logger.info("Claim has no payer ID, skipping pattern analysis", claim_id=claim_id)
            return []

        # Get all patterns for this payer (cached)
        patterns = self.get_patterns_for_payer(claim.payer_id)

        if not patterns:
            logger.info("No patterns found for payer", payer_id=claim.payer_id, claim_id=claim_id)
            return []

        matching_patterns = []

        for pattern in patterns:
            match_score = self._calculate_pattern_match(claim, pattern)
            if match_score > 0:
                matching_patterns.append(
                    {
                        "pattern_id": pattern.id,
                        "pattern_type": pattern.pattern_type,
                        "pattern_description": pattern.pattern_description,
                        "denial_reason_code": pattern.denial_reason_code,
                        "match_score": match_score,
                        "confidence_score": pattern.confidence_score,
                        "frequency": pattern.frequency,
                        "conditions": pattern.conditions,
                    }
                )

        # Sort by match score (highest first)
        matching_patterns.sort(key=lambda x: x["match_score"], reverse=True)

        # Cache the result (use claim TTL since it's claim-specific)
        from app.config.cache_ttl import get_claim_ttl
        cache.set(cache_key_str, matching_patterns, ttl_seconds=get_claim_ttl())

        logger.info(
            "Pattern analysis completed",
            claim_id=claim_id,
            total_patterns=len(patterns),
            matching_patterns=len(matching_patterns),
        )

        return matching_patterns

    def _calculate_pattern_match(self, claim, pattern: DenialPattern) -> float:
        """
        Calculate how well a claim matches a denial pattern.
        
        Args:
            claim: The claim to match against the pattern
            pattern: The denial pattern to match against
            
        Returns:
            Match score between 0.0 and 1.0, where:
            - 0.0 = no match
            - 1.0 = perfect match
            Score is weighted by pattern confidence and considers diagnosis codes,
            procedure codes, charge amounts, and facility types.
        """
        match_score = 0.0
        conditions = pattern.conditions or {}

        # If pattern has specific conditions, check them
        if conditions:
            # Check diagnosis code matches
            if "diagnosis_codes" in conditions:
                pattern_diagnosis = conditions.get("diagnosis_codes", [])
                claim_diagnosis = claim.diagnosis_codes or []
                if any(dx in claim_diagnosis for dx in pattern_diagnosis):
                    match_score += 0.3

            # Check principal diagnosis match
            if "principal_diagnosis" in conditions:
                if claim.principal_diagnosis == conditions["principal_diagnosis"]:
                    match_score += 0.4

            # Check procedure code matches
            if "procedure_codes" in conditions:
                pattern_procedures = conditions.get("procedure_codes", [])
                claim_procedures = [
                    line.procedure_code
                    for line in (claim.claim_lines or [])
                    if line.procedure_code
                ]
                if any(proc in claim_procedures for proc in pattern_procedures):
                    match_score += 0.2

            # Check charge amount range
            if "charge_amount_min" in conditions or "charge_amount_max" in conditions:
                min_amount = conditions.get("charge_amount_min")
                max_amount = conditions.get("charge_amount_max")
                claim_amount = claim.total_charge_amount or 0.0

                if min_amount and claim_amount < min_amount:
                    return 0.0  # Below minimum, no match
                if max_amount and claim_amount > max_amount:
                    return 0.0  # Above maximum, no match
                if min_amount or max_amount:
                    match_score += 0.1

            # Check facility type
            if "facility_type_code" in conditions:
                if claim.facility_type_code == conditions["facility_type_code"]:
                    match_score += 0.1

        else:
            # If no specific conditions, use pattern frequency as base match
            # This is a fallback for patterns without detailed conditions
            match_score = pattern.frequency or 0.0

        # Weight by pattern confidence
        final_score = match_score * (pattern.confidence_score or 0.5)

        return min(final_score, 1.0)

    def detect_all_patterns(self, days_back: int = 90) -> Dict[int, List[DenialPattern]]:
        """
        Detect patterns for all payers.
        
        Returns a dictionary mapping payer_id to list of patterns.
        """
        from app.models.database import Payer

        # Batch load all payers at once
        payers = self.db.query(Payer).all()
        all_patterns = {}

        # Process payers in batches to optimize memory usage
        batch_size = 50
        for i in range(0, len(payers), batch_size):
            payer_batch = payers[i : i + batch_size]
            for payer in payer_batch:
                patterns = self.detect_patterns_for_payer(payer.id, days_back)
                all_patterns[payer.id] = patterns
            
            # Flush after each batch to avoid memory buildup
            self.db.flush()

        self.db.commit()

        logger.info("Pattern detection completed for all payers", payer_count=len(payers))

        return all_patterns

