"""Risk scoring endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.cache_ttl import get_risk_score_ttl
from app.services.risk.scorer import RiskScorer
from app.models.database import Claim
from app.utils.errors import NotFoundError
from app.utils.cache import cache, risk_score_cache_key

router = APIRouter()


@router.get("/risk/{claim_id}")
async def get_risk_score(claim_id: int, db: Session = Depends(get_db)):
    """Get risk score for a claim (cached). Optimized with eager loading."""
    # Try cache first
    cache_key = risk_score_cache_key(claim_id)
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # Optimize: Use eager loading and order by to get latest risk score efficiently
    from sqlalchemy.orm import joinedload
    
    claim = (
        db.query(Claim)
        .options(joinedload(Claim.risk_scores))
        .filter(Claim.id == claim_id)
        .first()
    )
    if not claim:
        raise NotFoundError("Claim", str(claim_id))
    
    # Get latest risk score (already sorted by calculated_at desc in query)
    if claim.risk_scores:
        latest_score = claim.risk_scores[0]  # First is latest due to ordering
        result = {
            "claim_id": claim_id,
            "overall_score": latest_score.overall_score,
            "risk_level": latest_score.risk_level.value,
            "component_scores": {
                "coding_risk": latest_score.coding_risk,
                "documentation_risk": latest_score.documentation_risk,
                "payer_risk": latest_score.payer_risk,
                "historical_risk": latest_score.historical_risk,
            },
            "risk_factors": latest_score.risk_factors,
            "recommendations": latest_score.recommendations,
            "calculated_at": latest_score.calculated_at.isoformat() if latest_score.calculated_at else None,
        }
    else:
        result = {
            "claim_id": claim_id,
            "message": "Risk score not yet calculated",
        }
    
    # Cache with configured TTL
    cache.set(cache_key, result, ttl_seconds=get_risk_score_ttl())
    return result


@router.post("/risk/{claim_id}/calculate")
async def calculate_risk_score(claim_id: int, db: Session = Depends(get_db)):
    """Calculate risk score for a claim. Optimized with eager loading."""
    # Optimize: Use eager loading to fetch claim with relationships
    from sqlalchemy.orm import joinedload
    
    claim = (
        db.query(Claim)
        .options(
            joinedload(Claim.claim_lines),
            joinedload(Claim.payer),
            joinedload(Claim.provider),
        )
        .filter(Claim.id == claim_id)
        .first()
    )
    if not claim:
        raise NotFoundError("Claim", str(claim_id))
    
    scorer = RiskScorer(db)
    risk_score = scorer.calculate_risk_score(claim_id)
    db.commit()
    
    # Cache is already updated in scorer.calculate_risk_score()
    result = {
        "claim_id": claim_id,
        "overall_score": risk_score.overall_score,
        "risk_level": risk_score.risk_level.value,
        "status": "calculated",
    }
    
    return result

