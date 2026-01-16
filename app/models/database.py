"""
SQLAlchemy database models for mARB 2.0.

This module defines database models for claims, remittances, episodes, risk, and logging.
Core models (Provider, Payer, Plan, PracticeConfig) are in app.models.core.
Enums are in app.models.enums.

Models represent the core entities in the healthcare claim risk analysis system:

Claims & Remittances:
- Claim: 837 claim files (professional/institutional)
- ClaimLine: Individual line items within claims
- Remittance: 835 remittance files (payment/denial information)
- ClaimEpisode: Links claims to their remittance outcomes

Risk & Learning:
- DenialPattern: Learned patterns from historical denials
- RiskScore: Calculated risk scores for claims

Logging:
- ParserLog: Logs of parsing issues/warnings for resilience tracking
- AuditLog: HIPAA-compliant audit trail of API requests

All models inherit from Base and TimestampMixin, providing:
- Automatic created_at and updated_at timestamps
- Consistent primary key and indexing patterns

Database Indexes:
- Foreign keys are indexed for query performance
- Frequently queried columns (status, dates, control numbers) are indexed
- Composite indexes exist for common query patterns

Relationships:
- One-to-many: Provider -> Claims, Payer -> Claims/Plans
- Many-to-one: Claim -> Provider/Payer, ClaimLine -> Claim
- Many-to-many (via episodes): Claims <-> Remittances

**Note:** For backward compatibility, core models (Provider, Payer, Plan, PracticeConfig)
and enums are re-exported from this module. New code should import from app.models.core
and app.models.enums directly.
"""
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.config.database import Base, TimestampMixin
from app.models.enums import ClaimStatus, RemittanceStatus, EpisodeStatus, RiskLevel
from app.models.core import Provider, Payer, Plan, PracticeConfig


class Claim(Base, TimestampMixin):
    """
    837 Claim model - resilient to missing fields.
    
    Represents healthcare claims from EDI 837 files (both professional and institutional).
    The model is designed to handle incomplete or malformed EDI data gracefully,
    storing available information even when some segments are missing.
    
    Key Features:
    - Resilient parsing: Missing segments don't cause failures
    - Flexible date handling: Multiple date types supported
    - JSON storage: Diagnosis codes and parsed segments stored as JSON
    - Status tracking: Tracks processing status and completeness
    
    Attributes:
        claim_control_number: Unique claim control number (from CLM segment)
        patient_control_number: Patient control number
        provider_id: Foreign key to Provider model
        payer_id: Foreign key to Payer model
        total_charge_amount: Total charge amount for the claim
        diagnosis_codes: Array of diagnosis codes (stored as JSON)
        principal_diagnosis: Principal diagnosis code
        status: Claim processing status (pending, processed, incomplete, error)
        is_incomplete: Flag indicating if claim data is incomplete
    
    Relationships:
        provider: Many-to-one relationship with Provider model
        payer: Many-to-one relationship with Payer model
        claim_lines: One-to-many relationship with ClaimLine model
        episodes: One-to-many relationship with ClaimEpisode model
    """

    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    claim_control_number = Column(String(50), unique=True, nullable=False, index=True)
    patient_control_number = Column(String(50), index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), index=True)
    payer_id = Column(Integer, ForeignKey("payers.id"), index=True)
    
    # Claim header data (from CLM segment)
    total_charge_amount = Column(Float)
    facility_type_code = Column(String(2))
    claim_frequency_type = Column(String(1))
    assignment_code = Column(String(1))
    
    # Dates (from DTP segments)
    statement_date = Column(DateTime)
    admission_date = Column(DateTime)
    discharge_date = Column(DateTime)
    service_date = Column(DateTime)
    
    # Diagnosis codes (from HI segments) - stored as JSON for flexibility
    diagnosis_codes = Column(JSON)
    principal_diagnosis = Column(String(10))
    
    # Provider information
    attending_provider_npi = Column(String(10))
    operating_provider_npi = Column(String(10))
    referring_provider_npi = Column(String(10))
    
    # Raw EDI data for reference
    raw_edi_data = Column(Text)
    parsed_segments = Column(JSON)  # Store parsed segments for debugging
    
    # Status and metadata
    status = Column(SQLEnum(ClaimStatus), default=ClaimStatus.PENDING, index=True)
    is_incomplete = Column(Boolean, default=False)
    parsing_warnings = Column(JSON)  # Store parsing warnings/issues
    practice_id = Column(String(50), index=True)

    # Relationship: Many claims belong to one provider
    provider = relationship("Provider", back_populates="claims")
    # Relationship: Many claims belong to one payer
    payer = relationship("Payer", back_populates="claims")
    # Relationship: One claim can have many claim lines (cascade delete)
    claim_lines = relationship("ClaimLine", back_populates="claim", cascade="all, delete-orphan")
    # Relationship: One claim can have many episodes
    episodes = relationship("ClaimEpisode", back_populates="claim")
    # Relationship: One claim can have many risk scores
    risk_scores = relationship("RiskScore", back_populates="claim")


class ClaimLine(Base, TimestampMixin):
    """
    Claim line item model (from LX/SV2 segments).
    
    Represents individual service line items within a claim. Each claim can have
    multiple line items, each with its own procedure code, charge amount, and service date.
    
    Attributes:
        claim_id: Foreign key to Claim model
        line_number: Line number within the claim
        revenue_code: Revenue code (if applicable)
        procedure_code: CPT/HCPCS procedure code
        procedure_modifier: Procedure modifier codes
        charge_amount: Charge amount for this line item
        unit_count: Number of units
        service_date: Date of service for this line item
    
    Relationships:
        claim: Many-to-one relationship with Claim model
    """

    __tablename__ = "claim_lines"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    line_number = Column(String(10), nullable=False)
    
    # Service line data (from SV2 segment)
    revenue_code = Column(String(10))
    procedure_code = Column(String(10))
    procedure_modifier = Column(String(10))
    charge_amount = Column(Float)
    unit_count = Column(Float)
    unit_type = Column(String(2))
    
    # Service date
    service_date = Column(DateTime)
    
    # Raw data
    raw_segment_data = Column(JSON)

    # Relationship: Many claim lines belong to one claim
    claim = relationship("Claim", back_populates="claim_lines")


class Remittance(Base, TimestampMixin):
    """
    835 Remittance model.
    
    Represents remittance advice files (EDI 835) from payers containing payment
    and denial information. Remittances are linked to claims through episodes.
    
    Attributes:
        remittance_control_number: Unique remittance control number
        payer_id: Foreign key to Payer model
        payer_name: Payer name (denormalized for performance)
        payment_amount: Total payment amount
        payment_date: Date of payment
        check_number: Check or EFT reference number
        claim_control_number: Reference to the original claim
        denial_reasons: Array of denial reason codes (stored as JSON)
        adjustment_reasons: Array of adjustment reason codes (stored as JSON)
        status: Remittance processing status (pending, processed, error)
    
    Relationships:
        payer: Many-to-one relationship with Payer model
        episodes: One-to-many relationship with ClaimEpisode model
    """

    __tablename__ = "remittances"

    id = Column(Integer, primary_key=True, index=True)
    remittance_control_number = Column(String(50), unique=True, nullable=False, index=True)
    
    # Payer information
    payer_id = Column(Integer, ForeignKey("payers.id"), index=True)
    payer_name = Column(String(255))
    
    # Payment information
    payment_amount = Column(Float)
    payment_date = Column(DateTime)
    check_number = Column(String(50))
    
    # Claim reference
    claim_control_number = Column(String(50), index=True)
    
    # Denial information
    denial_reasons = Column(JSON)  # Array of denial reason codes
    adjustment_reasons = Column(JSON)  # Array of adjustment reason codes
    
    # Raw EDI data
    raw_edi_data = Column(Text)
    parsed_segments = Column(JSON)
    
    # Status
    status = Column(SQLEnum(RemittanceStatus), default=RemittanceStatus.PENDING, index=True)
    parsing_warnings = Column(JSON)

    # Relationship: Many remittances belong to one payer
    payer = relationship("Payer")
    # Relationship: One remittance can have many episodes
    episodes = relationship("ClaimEpisode", back_populates="remittance")


class ClaimEpisode(Base, TimestampMixin):
    """
    Links claims to remittances, creating a complete claim lifecycle.
    
    Episodes connect claims (837) with their remittance outcomes (835), providing
    a complete picture of the claim from submission to payment/denial. Episodes
    can be automatically linked by control numbers or manually created.
    
    Attributes:
        claim_id: Foreign key to Claim model
        remittance_id: Foreign key to Remittance model (optional, can be pending)
        status: Episode status (pending, linked, complete, denied)
        linked_at: Timestamp when episode was linked
        payment_amount: Payment amount for this episode
        denial_count: Number of denials in the remittance
        adjustment_count: Number of adjustments in the remittance
    
    Relationships:
        claim: Many-to-one relationship with Claim model
        remittance: Many-to-one relationship with Remittance model
    """

    __tablename__ = "claim_episodes"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    remittance_id = Column(Integer, ForeignKey("remittances.id"), index=True)
    
    # Episode metadata
    status = Column(SQLEnum(EpisodeStatus), default=EpisodeStatus.PENDING, index=True)
    linked_at = Column(DateTime)
    
    # Outcome information
    payment_amount = Column(Float)
    denial_count = Column(Integer, default=0)
    adjustment_count = Column(Integer, default=0)

    # Relationship: Many episodes belong to one claim
    claim = relationship("Claim", back_populates="episodes")
    # Relationship: Many episodes belong to one remittance
    remittance = relationship("Remittance", back_populates="episodes")


class DenialPattern(Base, TimestampMixin):
    """
    Learned denial patterns from historical remittance data.
    
    Stores patterns detected by the pattern learning system. These patterns
    help predict potential denials before claims are submitted by analyzing
    historical denial data and identifying recurring patterns.
    
    Attributes:
        payer_id: Foreign key to Payer model (patterns are payer-specific)
        pattern_type: Type of pattern (coding, documentation, eligibility, etc.)
        pattern_description: Human-readable description of the pattern
        denial_reason_code: Associated denial reason code (e.g., CO45, PR1)
        occurrence_count: Number of times this pattern has occurred
        frequency: Frequency of this pattern (0.0 to 1.0)
        confidence_score: ML confidence score for pattern detection (0.0 to 1.0)
        conditions: JSON object containing conditions that trigger this pattern
        first_seen: Date when pattern was first detected
        last_seen: Date when pattern was most recently seen
    
    Relationships:
        payer: Many-to-one relationship with Payer model
    """

    __tablename__ = "denial_patterns"

    id = Column(Integer, primary_key=True, index=True)
    payer_id = Column(Integer, ForeignKey("payers.id"), index=True)
    
    # Pattern information
    pattern_type = Column(String(50))  # coding, documentation, eligibility, etc.
    pattern_description = Column(Text)
    denial_reason_code = Column(String(10))
    
    # Pattern metrics
    occurrence_count = Column(Integer, default=0)
    frequency = Column(Float)  # Frequency of this pattern
    confidence_score = Column(Float)  # ML confidence score
    
    # Pattern conditions (stored as JSON for flexibility)
    conditions = Column(JSON)  # Conditions that trigger this pattern
    
    # Metadata
    first_seen = Column(DateTime)
    last_seen = Column(DateTime)

    # Relationship: Many denial patterns belong to one payer
    payer = relationship("Payer")


class RiskScore(Base, TimestampMixin):
    """
    Risk score for claims.
    
    Stores calculated risk scores for claims, including overall score, risk level,
    and component scores from different risk assessment engines. Risk scores are
    cached for performance and can be recalculated when needed.
    
    Attributes:
        claim_id: Foreign key to Claim model
        overall_score: Overall risk score (0-100, where higher is riskier)
        risk_level: Risk level classification (low, medium, high, critical)
        coding_risk: Risk score from coding rules engine
        documentation_risk: Risk score from documentation rules engine
        payer_risk: Risk score from payer-specific rules engine
        historical_risk: Risk score from historical pattern analysis
        risk_factors: Array of identified risk factors (stored as JSON)
        recommendations: Array of recommendations to reduce risk (stored as JSON)
    
    Relationships:
        claim: Many-to-one relationship with Claim model
    """

    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    
    # Risk score
    overall_score = Column(Float, nullable=False)  # 0-100
    risk_level = Column(SQLEnum(RiskLevel), nullable=False, index=True)
    
    # Component scores
    coding_risk = Column(Float)
    documentation_risk = Column(Float)
    payer_risk = Column(Float)
    historical_risk = Column(Float)
    
    # Risk factors
    risk_factors = Column(JSON)  # Array of identified risk factors
    recommendations = Column(JSON)  # Array of recommendations
    
    # ML model information
    model_version = Column(String(50))
    model_confidence = Column(Float)
    
    # Metadata
    calculated_at = Column(DateTime, default=func.now())

    # Relationship: Many risk scores belong to one claim
    claim = relationship("Claim", back_populates="risk_scores")


class ParserLog(Base, TimestampMixin):
    """
    Logs of parsing issues/warnings for resilience tracking.
    
    Tracks parsing issues, warnings, and errors encountered during EDI file processing.
    This helps identify common parsing problems and improve parser resilience over time.
    
    Attributes:
        file_name: Name of the EDI file being parsed
        file_type: Type of EDI file (837 or 835)
        log_level: Severity level (warning, error, info)
        segment_type: EDI segment type where issue occurred (CLM, SBR, etc.)
        issue_type: Type of issue (missing_segment, invalid_format, etc.)
        message: Human-readable error message
        details: Additional context and details (stored as JSON)
        claim_control_number: Associated claim control number (if applicable)
        practice_id: Practice ID for the file
        created_at: Timestamp when log entry was created (indexed for queries)
    """

    __tablename__ = "parser_logs"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(10))  # 837 or 835
    
    # Log information
    log_level = Column(String(20))  # warning, error, info
    segment_type = Column(String(10))  # CLM, SBR, etc.
    issue_type = Column(String(50))  # missing_segment, invalid_format, etc.
    message = Column(Text, nullable=False)
    details = Column(JSON)  # Additional details
    
    # Context
    claim_control_number = Column(String(50))
    practice_id = Column(String(50))
    
    # Override created_at from TimestampMixin to add index
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)


class AuditLog(Base, TimestampMixin):
    """
    HIPAA-compliant audit log for API requests and responses.
    
    Stores comprehensive audit trail of all API requests for HIPAA compliance.
    All PHI (Protected Health Information) is hashed before storage. This model
    is automatically populated by the AuditMiddleware for all API requests.
    
    Key Features:
    - PHI Protection: All identifiers are hashed (no plaintext PHI)
    - Comprehensive Tracking: Method, path, status, duration, user, IP
    - Queryable: Indexed fields enable efficient compliance reporting
    - Immutable: Logs are never modified after creation
    
    Attributes:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: API endpoint path
        status_code: HTTP status code
        duration: Request processing duration in seconds
        user_id: Authenticated user ID (if available)
        client_ip: Client IP address
        request_identifier: Hashed identifier for request PHI
        response_identifier: Hashed identifier for response PHI
        created_at: Timestamp when request was processed
    
    Note: All PHI is hashed using SHA-256 before storage. Only hashed identifiers
    are stored and returned in API responses.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Request information
    method = Column(String(10), nullable=False, index=True)  # GET, POST, PUT, etc.
    path = Column(String(500), nullable=False, index=True)
    status_code = Column(Integer, nullable=False, index=True)
    duration = Column(Float)  # Request duration in seconds
    
    # User and client information
    user_id = Column(String(100), index=True)  # User ID if authenticated
    client_ip = Column(String(45))  # IPv4 or IPv6 address
    
    # Hashed identifiers (HIPAA-compliant - no PHI stored)
    request_identifier = Column(String(64))  # Hashed identifier for request body
    response_identifier = Column(String(64))  # Hashed identifier for response body
    
    # Detailed hashed PHI identifiers (JSON format)
    request_hashed_identifiers = Column(JSON)  # Hashed PHI identifiers from request
    response_hashed_identifiers = Column(JSON)  # Hashed PHI identifiers from response
    
    # Override created_at from TimestampMixin to add index for querying
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)


# Re-export core models and enums for backward compatibility
# New code should import from app.models.core and app.models.enums directly
__all__ = [
    # Core models (re-exported from app.models.core)
    "Provider",
    "Payer",
    "Plan",
    "PracticeConfig",
    # Enums (re-exported from app.models.enums)
    "ClaimStatus",
    "RemittanceStatus",
    "EpisodeStatus",
    "RiskLevel",
    # Models defined in this module
    "Claim",
    "ClaimLine",
    "Remittance",
    "ClaimEpisode",
    "DenialPattern",
    "RiskScore",
    "ParserLog",
    "AuditLog",
]

