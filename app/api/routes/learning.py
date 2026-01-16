"""Pattern learning and detection endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.config.database import get_db
from app.services.learning.pattern_detector import PatternDetector
from app.models.database import Payer
from app.utils.errors import NotFoundError
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/patterns/detect/{payer_id}")
async def detect_patterns_for_payer(
    payer_id: int,
    days_back: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Detect denial patterns for a specific payer.
    
    Analyzes historical remittance data to identify recurring denial patterns
    for the specified payer. This helps predict and prevent future denials.
    
    **Parameters:**
    - `payer_id` (path): The ID of the payer to analyze
    - `days_back` (query): Number of days to look back for pattern analysis.
      Default: 90, Range: 1-365
    
    **Request Body:**
    None - all parameters are in the path and query string.
    
    **Returns:**
    - `payer_id`: The analyzed payer ID
    - `payer_name`: Name of the payer
    - `patterns_detected`: Number of patterns found
    - `patterns`: Array of detected patterns with:
      - `pattern_type`: Type of pattern (e.g., "denial_reason", "procedure_code")
      - `pattern_description`: Human-readable description
      - `denial_reason_code`: Associated denial reason code
      - `occurrence_count`: How many times this pattern occurred
      - `frequency`: Pattern frequency percentage
      - `confidence_score`: Confidence in pattern detection (0-1)
      - `conditions`: Conditions that trigger this pattern
      - `first_seen`: First occurrence date
      - `last_seen`: Most recent occurrence date
    
    **Errors:**
    - 404: Payer not found
    """
    payer = db.query(Payer).filter(Payer.id == payer_id).first()
    if not payer:
        raise NotFoundError("Payer", str(payer_id))

    detector = PatternDetector(db)
    patterns = detector.detect_patterns_for_payer(payer_id, days_back)

    db.commit()

    return {
        "payer_id": payer_id,
        "payer_name": payer.name,
        "patterns_detected": len(patterns),
        "patterns": [
            {
                "id": pattern.id,
                "pattern_type": pattern.pattern_type,
                "pattern_description": pattern.pattern_description,
                "denial_reason_code": pattern.denial_reason_code,
                "occurrence_count": pattern.occurrence_count,
                "frequency": pattern.frequency,
                "confidence_score": pattern.confidence_score,
                "conditions": pattern.conditions,
                "first_seen": pattern.first_seen.isoformat() if pattern.first_seen else None,
                "last_seen": pattern.last_seen.isoformat() if pattern.last_seen else None,
            }
            for pattern in patterns
        ],
    }


@router.post("/patterns/detect-all")
async def detect_patterns_for_all_payers(
    days_back: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Detect denial patterns for all payers."""
    detector = PatternDetector(db)
    all_patterns = detector.detect_all_patterns(days_back)

    return {
        "payers_processed": len(all_patterns),
        "total_patterns": sum(len(patterns) for patterns in all_patterns.values()),
        "patterns_by_payer": {
            payer_id: len(patterns) for payer_id, patterns in all_patterns.items()
        },
    }


@router.get("/patterns/payer/{payer_id}")
async def get_patterns_for_payer(
    payer_id: int,
    db: Session = Depends(get_db),
):
    """Get all learned denial patterns for a payer."""
    payer = db.query(Payer).filter(Payer.id == payer_id).first()
    if not payer:
        raise NotFoundError("Payer", str(payer_id))

    detector = PatternDetector(db)
    patterns = detector.get_patterns_for_payer(payer_id)

    return {
        "payer_id": payer_id,
        "payer_name": payer.name,
        "patterns": [
            {
                "id": pattern.id,
                "pattern_type": pattern.pattern_type,
                "pattern_description": pattern.pattern_description,
                "denial_reason_code": pattern.denial_reason_code,
                "occurrence_count": pattern.occurrence_count,
                "frequency": pattern.frequency,
                "confidence_score": pattern.confidence_score,
                "conditions": pattern.conditions,
                "first_seen": pattern.first_seen.isoformat() if pattern.first_seen else None,
                "last_seen": pattern.last_seen.isoformat() if pattern.last_seen else None,
            }
            for pattern in patterns
        ],
    }


@router.post("/patterns/analyze-claim/{claim_id}")
async def analyze_claim_for_patterns(
    claim_id: int,
    db: Session = Depends(get_db),
):
    """Analyze a claim against known denial patterns."""
    from app.models.database import Claim

    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise NotFoundError("Claim", str(claim_id))

    detector = PatternDetector(db)
    matching_patterns = detector.analyze_claim_for_patterns(claim_id)

    return {
        "claim_id": claim_id,
        "payer_id": claim.payer_id,
        "matching_patterns_count": len(matching_patterns),
        "matching_patterns": matching_patterns,
    }

