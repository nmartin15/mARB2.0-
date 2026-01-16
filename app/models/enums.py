"""
Status and type enumerations for database models.

This module contains all enum definitions used by database models.
Enums are defined as string enums for better JSON serialization and
database storage compatibility.
"""
import enum


class ClaimStatus(str, enum.Enum):
    """Claim status enumeration."""

    PENDING = "pending"
    PROCESSED = "processed"
    INCOMPLETE = "incomplete"
    ERROR = "error"


class RemittanceStatus(str, enum.Enum):
    """Remittance status enumeration."""

    PENDING = "pending"
    PROCESSED = "processed"
    ERROR = "error"


class EpisodeStatus(str, enum.Enum):
    """Episode status enumeration."""

    PENDING = "pending"
    LINKED = "linked"
    COMPLETE = "complete"


class RiskLevel(str, enum.Enum):
    """Risk level enumeration."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
