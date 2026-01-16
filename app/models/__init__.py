"""
Database models package.

This package provides all database models for the mARB 2.0 application.
Models are organized by domain but can be imported from this package
for backward compatibility.

**Backward Compatible Imports:**
    from app.models.database import Claim  # Still works
    from app.models import Claim  # Preferred new style

**Domain-Specific Imports:**
    from app.models.core import Provider, Payer
    from app.models.enums import ClaimStatus
"""

# Import enums
from app.models.enums import (
    ClaimStatus,
    RemittanceStatus,
    EpisodeStatus,
    RiskLevel,
)

# Import core models
from app.models.core import (
    Provider,
    Payer,
    Plan,
    PracticeConfig,
)

# Import remaining models from database.py (will be moved in future phases)
from app.models.database import (
    Claim,
    ClaimLine,
    Remittance,
    ClaimEpisode,
    DenialPattern,
    RiskScore,
    ParserLog,
    AuditLog,
)

__all__ = [
    # Enums
    "ClaimStatus",
    "RemittanceStatus",
    "EpisodeStatus",
    "RiskLevel",
    # Core models
    "Provider",
    "Payer",
    "Plan",
    "PracticeConfig",
    # Claims and remittances
    "Claim",
    "ClaimLine",
    "Remittance",
    "ClaimEpisode",
    # Risk and learning
    "DenialPattern",
    "RiskScore",
    # Logging
    "ParserLog",
    "AuditLog",
]