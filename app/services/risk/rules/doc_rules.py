"""Documentation validation rules engine."""
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session

from app.models.database import Claim
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DocumentationRulesEngine:
    """Evaluate documentation-related risk rules."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate(self, claim: Claim) -> Tuple[float, List[Dict]]:
        """
        Evaluate documentation rules.
        
        Returns:
            (risk_score, risk_factors)
        """
        risk_score = 0.0
        risk_factors = []
        
        # Check if claim is marked as incomplete
        if claim.is_incomplete:
            risk_score += 30.0
            risk_factors.append({
                "type": "documentation",
                "severity": "high",
                "message": "Claim parsing indicates incomplete data",
            })
        
        # Check for parsing warnings
        parsing_warnings = claim.parsing_warnings or []
        if len(parsing_warnings) > 5:
            risk_score += 25.0
            risk_factors.append({
                "type": "documentation",
                "severity": "medium",
                "message": f"Multiple parsing warnings ({len(parsing_warnings)}) indicate data quality issues",
            })
        
        # Check for required provider information
        if not claim.attending_provider_npi:
            risk_score += 20.0
            risk_factors.append({
                "type": "documentation",
                "severity": "medium",
                "message": "Attending provider NPI is missing",
            })
        
        # Check for dates
        if not claim.service_date and not claim.statement_date:
            risk_score += 15.0
            risk_factors.append({
                "type": "documentation",
                "severity": "medium",
                "message": "Service or statement date is missing",
            })
        
        # Check for assignment code
        if not claim.assignment_code:
            risk_score += 10.0
            risk_factors.append({
                "type": "documentation",
                "severity": "low",
                "message": "Assignment code is missing",
            })
        
        return min(risk_score, 100.0), risk_factors

