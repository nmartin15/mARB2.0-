"""
Risk scoring orchestrator for claim risk analysis.

This module provides the RiskScorer class which orchestrates comprehensive risk scoring
for healthcare claims. It combines multiple risk assessment components:

- Payer-specific rules: Evaluates claim against payer-specific requirements
- Coding rules: Validates procedure and diagnosis code combinations
- Documentation rules: Assesses documentation completeness
- ML predictions: Uses machine learning models for risk prediction
- Pattern detection: Analyzes historical denial patterns

The scorer calculates an overall risk score (0-100) and risk level (low, medium, high, critical)
by combining weighted component scores. Risk scores are cached for performance.

Configuration:
- Risk weights can be configured via environment variables (see app/config/risk_weights.py)
- Component weights default to balanced distribution but can be customized per practice
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.database import Claim, RiskScore, RiskLevel
from app.services.risk.rules.payer_rules import PayerRulesEngine
from app.services.risk.rules.coding_rules import CodingRulesEngine
from app.services.risk.rules.doc_rules import DocumentationRulesEngine
from app.services.risk.ml_service import MLService
from app.services.learning.pattern_detector import PatternDetector
from app.utils.logger import get_logger
from app.utils.notifications import notify_risk_score_calculated
from app.utils.cache import cache, risk_score_cache_key
from app.config.cache_ttl import get_risk_score_ttl
from app.config.risk_weights import get_risk_weights, validate_weights

logger = get_logger(__name__)


class RiskScorer:
    """Orchestrates risk scoring for claims."""

    def __init__(self, db: Session, weights: Optional[Dict[str, float]] = None):
        """
        Initialize RiskScorer.
        
        Args:
            db: Database session
            weights: Optional dictionary of risk component weights. If not provided, 
                   uses weights from config (which can be overridden via environment variables).
        """
        self.db = db
        self.payer_rules = PayerRulesEngine(db)
        self.coding_rules = CodingRulesEngine(db)
        self.doc_rules = DocumentationRulesEngine(db)
        self.ml_service = MLService(db_session=db)
        self.pattern_detector = PatternDetector(db)
        
        # Use provided weights, or get from config (which reads from env vars or defaults)
        if weights is not None:
            self.weights = weights
        else:
            self.weights = get_risk_weights()
        
        # Validate weights sum to ~1.0
        if not validate_weights(self.weights):
            logger.warning(
                "Risk weights do not sum to 1.0",
                weights=self.weights,
                total=sum(self.weights.values()),
            )

    def calculate_risk_score(self, claim_id: int) -> RiskScore:
        """Calculate comprehensive risk score for a claim. Optimized with eager loading."""
        logger.info("Calculating risk score", claim_id=claim_id)
        
        # Optimize: Use eager loading to fetch related data in one query
        from sqlalchemy.orm import joinedload
        
        claim = (
            self.db.query(Claim)
            .options(
                joinedload(Claim.claim_lines),
                joinedload(Claim.payer),
                joinedload(Claim.provider),
            )
            .filter(Claim.id == claim_id)
            .first()
        )
        if not claim:
            raise ValueError(f"Claim {claim_id} not found")
        
        # Initialize risk factors and scores
        risk_factors = []
        component_scores = {}
        
        # 1. Payer-specific risk
        payer_risk, payer_factors = self.payer_rules.evaluate(claim)
        component_scores["payer_risk"] = payer_risk
        risk_factors.extend(payer_factors)
        
        # 2. Coding risk
        coding_risk, coding_factors = self.coding_rules.evaluate(claim)
        component_scores["coding_risk"] = coding_risk
        risk_factors.extend(coding_factors)
        
        # 3. Documentation risk
        doc_risk, doc_factors = self.doc_rules.evaluate(claim)
        component_scores["documentation_risk"] = doc_risk
        risk_factors.extend(doc_factors)
        
        # 4. Historical risk (from ML model)
        historical_risk = 0.0
        try:
            historical_risk = self.ml_service.predict_risk(claim)
            component_scores["historical_risk"] = historical_risk
        except Exception as e:
            logger.warning("ML prediction failed", error=str(e))
            component_scores["historical_risk"] = 0.0
        
        # 5. Pattern-based risk (from learned denial patterns)
        pattern_risk = 0.0
        pattern_factors = []
        try:
            matching_patterns = self.pattern_detector.analyze_claim_for_patterns(claim_id)
            if matching_patterns:
                # Calculate pattern risk based on matching patterns
                # Use the highest match score and confidence
                max_match = max(matching_patterns, key=lambda p: p.get("match_score", 0))
                pattern_risk = (
                    max_match.get("match_score", 0) * 100 * max_match.get("confidence_score", 0.5)
                )
                
                # Add pattern-based risk factors
                for pattern in matching_patterns[:3]:  # Top 3 patterns
                    pattern_factors.append({
                        "type": "pattern_match",
                        "severity": "high" if pattern.get("match_score", 0) > 0.7 else "medium",
                        "message": f"Matches denial pattern: {pattern.get('pattern_description', 'Unknown pattern')}",
                        "denial_reason_code": pattern.get("denial_reason_code"),
                        "confidence": pattern.get("confidence_score", 0),
                    })
                
                component_scores["pattern_risk"] = pattern_risk
                risk_factors.extend(pattern_factors)
        except Exception as e:
            logger.warning("Pattern analysis failed", error=str(e))
            component_scores["pattern_risk"] = 0.0
        
        # Calculate overall score (weighted average)
        # Weights are configurable via environment variables or config (see app.config.risk_weights)
        overall_score = (
            self.weights["payer_risk"] * payer_risk +
            self.weights["coding_risk"] * coding_risk +
            self.weights["doc_risk"] * doc_risk +
            self.weights["historical_risk"] * historical_risk +
            self.weights["pattern_risk"] * pattern_risk
        )
        
        # Determine risk level
        if overall_score >= 75:
            risk_level = RiskLevel.CRITICAL
        elif overall_score >= 50:
            risk_level = RiskLevel.HIGH
        elif overall_score >= 25:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        # Generate recommendations
        recommendations = self._generate_recommendations(risk_factors, component_scores)
        
        # Optimize: Query existing risk score with ordering to get latest
        risk_score = (
            self.db.query(RiskScore)
            .filter(RiskScore.claim_id == claim_id)
            .order_by(RiskScore.calculated_at.desc())
            .first()
        )
        
        # Store pattern_risk in component_scores dict (not as separate column)
        # Include pattern risk info in risk_factors for visibility
        
        if risk_score:
            # Update existing
            risk_score.overall_score = overall_score
            risk_score.risk_level = risk_level
            risk_score.coding_risk = coding_risk
            risk_score.documentation_risk = doc_risk
            risk_score.payer_risk = payer_risk
            risk_score.historical_risk = historical_risk
            risk_score.risk_factors = risk_factors
            risk_score.recommendations = recommendations
        else:
            # Create new
            risk_score = RiskScore(
                claim_id=claim_id,
                overall_score=overall_score,
                risk_level=risk_level,
                coding_risk=coding_risk,
                documentation_risk=doc_risk,
                payer_risk=payer_risk,
                historical_risk=historical_risk,
                risk_factors=risk_factors,
                recommendations=recommendations,
                model_version="1.0",
                model_confidence=0.8,
            )
            self.db.add(risk_score)
        
        self.db.flush()

        logger.info(
            "Risk score calculated",
            claim_id=claim_id,
            overall_score=overall_score,
            risk_level=risk_level.value,
        )

        # Optimize: Update cache with new risk score
        cache_key = risk_score_cache_key(claim_id)
        cache_result = {
            "claim_id": claim_id,
            "overall_score": overall_score,
            "risk_level": risk_level.value,
            "component_scores": {
                "coding_risk": coding_risk,
                "documentation_risk": doc_risk,
                "payer_risk": payer_risk,
                "historical_risk": historical_risk,
                "pattern_risk": pattern_risk,
            },
            "risk_factors": risk_factors,
            "recommendations": recommendations,
            "calculated_at": risk_score.calculated_at.isoformat() if risk_score.calculated_at else None,
        }
        cache.set(cache_key, cache_result, ttl_seconds=get_risk_score_ttl())

        # Send WebSocket notification
        try:
            notification_data = {
                "overall_score": overall_score,
                "risk_level": risk_level.value,
                "component_scores": {
                    "coding_risk": coding_risk,
                    "documentation_risk": doc_risk,
                    "payer_risk": payer_risk,
                    "historical_risk": historical_risk,
                    "pattern_risk": pattern_risk,
                },
            }
            notify_risk_score_calculated(claim_id, notification_data)
        except Exception as e:
            logger.warning("Failed to send risk score notification", error=str(e), claim_id=claim_id)
        
        return risk_score

    def _generate_recommendations(
        self, risk_factors: List[Dict], component_scores: Dict
    ) -> List[str]:
        """Generate actionable recommendations based on risk factors."""
        recommendations = []
        
        # High coding risk
        if component_scores.get("coding_risk", 0) > 50:
            recommendations.append("Review procedure codes and modifiers for accuracy")
            recommendations.append("Verify diagnosis codes match procedure codes")
        
        # High documentation risk
        if component_scores.get("documentation_risk", 0) > 50:
            recommendations.append("Ensure all required documentation is attached")
            recommendations.append("Verify provider signatures are present")
        
        # High payer risk
        if component_scores.get("payer_risk", 0) > 50:
            recommendations.append("Check payer-specific requirements before submission")
            recommendations.append("Verify patient eligibility and benefits")
        
        # Critical risk factors
        critical_factors = [f for f in risk_factors if f.get("severity") == "critical"]
        if critical_factors:
            recommendations.append("CRITICAL: Address high-priority issues before submission")
        
        return recommendations

