"""Practice/payer-specific EDI parsing configurations."""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.database import PracticeConfig
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Default segment expectations
DEFAULT_SEGMENT_EXPECTATIONS = {
    "critical": ["ISA", "GS", "ST", "CLM"],
    "important": ["SBR", "NM1", "DTP", "HI"],
    "optional": ["PRV", "REF", "N4", "LX", "SV2"],
}

# Code mapping dictionaries (from your prototype)
FACILITY_TYPE_CODE_MAP = {
    "11": "Office Physicians office",
    "12": "Home Services provided at the patients home",
    "13": "Critical Access Hospital",  # Most common in rural hospitals
    "14": "Skilled Nursing Facility",
    "18": "Other",  # Additional facility type
    "21": "Inpatient Hospital Services",
    "22": "Outpatient Hospital",
    "23": "Emergency Room Services",
    "24": "Ambulatory Surgical Center Outpatient",
    "85": "Other",  # Additional facility type code
}

PAYER_RESPONSIBILITY_SEQ_MAP = {
    "P": "Primary",
    "S": "Secondary",
    "T": "Tertiary",
}

CLAIM_FREQUENCY_TYPE_MAP = {
    "1": "Original Claim",
    "7": "Corrected Claim",
    "8": "Void Claim",
}

DIAGNOSIS_CODE_QUALIFIER_MAP = {
    "ABK": "Principal Diagnosis",
    "ABJ": "Principal Diagnosis",
    "APR": "Other Diagnoses",  # Additional/Other diagnosis codes
    "ABF": "Other Diagnoses",
    "ABN": "Advance Beneficiary Notice",
    "BBR": "Admitting Diagnosis",
    "BBQ": "Discharge Diagnosis",
}


class ParserConfig:
    """Parser configuration for a practice/payer."""

    def __init__(
        self,
        practice_id: Optional[str] = None,
        payer_id: Optional[str] = None,
        segment_expectations: Optional[Dict] = None,
    ):
        self.practice_id = practice_id
        self.payer_id = payer_id
        self.segment_expectations = segment_expectations or DEFAULT_SEGMENT_EXPECTATIONS.copy()

    def is_critical_segment(self, segment_id: str) -> bool:
        """Check if segment is critical."""
        return segment_id in self.segment_expectations.get("critical", [])

    def is_important_segment(self, segment_id: str) -> bool:
        """Check if segment is important."""
        return segment_id in self.segment_expectations.get("important", [])

    def is_optional_segment(self, segment_id: str) -> bool:
        """Check if segment is optional."""
        return segment_id in self.segment_expectations.get("optional", [])


def get_parser_config(
    practice_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> ParserConfig:
    """
    Get parser configuration for a practice.
    
    Loads configuration from database if practice_id and db session are provided.
    Falls back to default configuration if not found or if database is not available.
    
    Args:
        practice_id: Optional practice ID to load configuration for
        db: Optional database session. If provided, will attempt to load from database.
        
    Returns:
        ParserConfig instance with practice-specific or default configuration
    """
    # If we have both practice_id and db session, try to load from database
    if practice_id and db:
        try:
            practice_config = (
                db.query(PracticeConfig)
                .filter(PracticeConfig.practice_id == practice_id)
                .first()
            )
            
            if practice_config and practice_config.segment_expectations:
                # Use database configuration
                segment_expectations = practice_config.segment_expectations
                
                # Ensure it has the expected structure
                if isinstance(segment_expectations, dict):
                    # Merge with defaults to ensure all required keys exist
                    merged_expectations = DEFAULT_SEGMENT_EXPECTATIONS.copy()
                    merged_expectations.update(segment_expectations)
                    
                    logger.info(
                        "Loaded parser config from database",
                        practice_id=practice_id,
                    )
                    return ParserConfig(
                        practice_id=practice_id,
                        segment_expectations=merged_expectations,
                    )
                else:
                    logger.warning(
                        "Invalid segment_expectations format in database",
                        practice_id=practice_id,
                    )
            elif practice_config:
                logger.info(
                    "Practice config found but no segment_expectations, using defaults",
                    practice_id=practice_id,
                )
        except Exception as e:
            logger.warning(
                "Failed to load parser config from database, using defaults",
                practice_id=practice_id,
                error=str(e),
            )
    
    # Fall back to default configuration
    return ParserConfig(practice_id=practice_id)

