"""
Core database models for healthcare entities.

This module contains the core entity models:
- Provider: Healthcare providers (identified by NPI)
- Payer: Insurance payers (Medicare, Medicaid, Commercial, etc.)
- Plan: Insurance plans with benefit rules
- PracticeConfig: Practice-specific EDI parsing configuration

All models inherit from Base and TimestampMixin, providing automatic
created_at and updated_at timestamps.
"""
from sqlalchemy import Column, String, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.config.database import Base, TimestampMixin


class Provider(Base, TimestampMixin):
    """
    Healthcare provider model.
    
    Represents healthcare providers identified by National Provider Identifier (NPI).
    Providers submit claims and are linked to claims through the provider_id foreign key.
    
    Attributes:
        npi: National Provider Identifier (10 digits, unique)
        name: Provider name
        specialty: Provider specialty
        taxonomy_code: Healthcare provider taxonomy code
    
    Relationships:
        claims: One-to-many relationship with Claim model
    """

    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True)
    npi = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    specialty = Column(String(100))
    taxonomy_code = Column(String(10))

    # Relationship: One provider can have many claims
    claims = relationship("Claim", back_populates="provider")


class Payer(Base, TimestampMixin):
    """
    Insurance payer model.
    
    Represents insurance payers (Medicare, Medicaid, Commercial insurers, etc.)
    that process claims and issue remittances. Payers have configurable rules
    and can have multiple insurance plans.
    
    Attributes:
        payer_id: Unique payer identifier (string, not to be confused with database id)
        name: Payer name (e.g., "Blue Cross Blue Shield")
        payer_type: Type of payer (Medicare, Medicaid, Commercial, etc.)
        rules_config: JSON configuration for payer-specific rules
    
    Relationships:
        claims: One-to-many relationship with Claim model
        plans: One-to-many relationship with Plan model
    """

    __tablename__ = "payers"

    id = Column(Integer, primary_key=True, index=True)
    payer_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    payer_type = Column(String(50))  # Medicare, Medicaid, Commercial, etc.
    rules_config = Column(JSON)  # Payer-specific rules configuration

    # Relationship: One payer can have many claims
    claims = relationship("Claim", back_populates="payer")
    # Relationship: One payer can have many plans
    plans = relationship("Plan", back_populates="payer")


class Plan(Base, TimestampMixin):
    """
    Insurance plan model.
    
    Represents specific insurance plans offered by payers. Each plan can have
    unique benefit rules and coverage configurations.
    
    Attributes:
        payer_id: Foreign key to Payer model
        plan_name: Name of the insurance plan
        plan_type: Type of plan (HMO, PPO, etc.)
        benefit_rules: JSON configuration for plan-specific benefit rules
    
    Relationships:
        payer: Many-to-one relationship with Payer model
    """

    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    payer_id = Column(Integer, ForeignKey("payers.id"), nullable=False, index=True)
    plan_name = Column(String(255))
    plan_type = Column(String(50))  # HMO, PPO, etc.
    benefit_rules = Column(JSON)  # Plan-specific benefit rules

    # Relationship: Many plans belong to one payer
    payer = relationship("Payer", back_populates="plans")


class PracticeConfig(Base, TimestampMixin):
    """
    Practice-specific EDI parsing configuration.
    
    Stores practice-specific settings for EDI file parsing, including expected
    segments and payer-specific parsing rules. Allows customization of parsing
    behavior per practice.
    
    Attributes:
        practice_id: Unique practice identifier
        practice_name: Name of the practice
        segment_expectations: JSON configuration for expected segments per practice
        payer_specific_rules: JSON configuration for payer-specific parsing rules
    """

    __tablename__ = "practice_configs"

    id = Column(Integer, primary_key=True, index=True)
    practice_id = Column(String(50), unique=True, nullable=False, index=True)
    practice_name = Column(String(255), nullable=False)
    segment_expectations = Column(JSON)  # Expected segments per practice
    payer_specific_rules = Column(JSON)  # Payer-specific parsing rules
