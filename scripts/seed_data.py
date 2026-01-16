#!/usr/bin/env python3
"""Seed initial data for development and testing."""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.config.database import SessionLocal, engine, Base
from app.models.database import Payer, PracticeConfig, Provider
from app.utils.logger import get_logger

logger = get_logger(__name__)


def seed_payers(db: Session) -> None:
    """
    Seed initial payers into the database.
    
    Args:
        db: SQLAlchemy database session
        
    Returns:
        None
        
    Raises:
        SQLAlchemyError: If database operation fails
    """
    payers = [
        {
            "payer_id": "MEDICARE",
            "name": "Medicare",
            "payer_type": "Medicare",
            "rules_config": {
                "denial_threshold": 0.25,
                "requires_prior_auth": True,
                "common_denial_codes": ["CO-16", "CO-18", "CO-50"],
            },
        },
        {
            "payer_id": "MEDICAID",
            "name": "Medicaid",
            "payer_type": "Medicaid",
            "rules_config": {
                "denial_threshold": 0.30,
                "requires_prior_auth": True,
                "common_denial_codes": ["CO-16", "CO-18", "CO-97"],
            },
        },
        {
            "payer_id": "BLUE_CROSS",
            "name": "Blue Cross Blue Shield",
            "payer_type": "Commercial",
            "rules_config": {
                "denial_threshold": 0.20,
                "requires_prior_auth": False,
                "common_denial_codes": ["CO-16", "CO-50", "CO-97"],
            },
        },
        {
            "payer_id": "AETNA",
            "name": "Aetna",
            "payer_type": "Commercial",
            "rules_config": {
                "denial_threshold": 0.22,
                "requires_prior_auth": True,
                "common_denial_codes": ["CO-16", "CO-18", "CO-50"],
            },
        },
    ]

    for payer_data in payers:
        existing = db.query(Payer).filter(Payer.payer_id == payer_data["payer_id"]).first()
        if existing:
            logger.info(f"Payer {payer_data['payer_id']} already exists, skipping")
            continue

        payer = Payer(**payer_data)
        db.add(payer)
        logger.info(f"Created payer: {payer_data['name']} ({payer_data['payer_id']})")

    db.commit()


def seed_practice_configs(db: Session) -> None:
    """
    Seed initial practice configurations into the database.
    
    Args:
        db: SQLAlchemy database session
        
    Returns:
        None
        
    Raises:
        SQLAlchemyError: If database operation fails
    """
    configs = [
        {
            "practice_id": "PRACTICE001",
            "practice_name": "Sample Medical Practice",
            "segment_expectations": {
                "required": ["ISA", "GS", "ST", "BHT", "NM1", "CLM", "HI", "LX", "SV1"],
                "optional": ["REF", "N3", "N4", "DMG", "PRV"],
            },
            "payer_specific_rules": {
                "MEDICARE": {
                    "require_icd10": True,
                    "require_modifiers": False,
                },
                "MEDICAID": {
                    "require_icd10": True,
                    "require_modifiers": True,
                },
            },
        },
    ]

    for config_data in configs:
        existing = (
            db.query(PracticeConfig)
            .filter(PracticeConfig.practice_id == config_data["practice_id"])
            .first()
        )
        if existing:
            logger.info(f"Practice config {config_data['practice_id']} already exists, skipping")
            continue

        config = PracticeConfig(**config_data)
        db.add(config)
        logger.info(f"Created practice config: {config_data['practice_name']} ({config_data['practice_id']})")

    db.commit()


def seed_providers(db: Session) -> None:
    """
    Seed initial providers into the database.
    
    Args:
        db: SQLAlchemy database session
        
    Returns:
        None
        
    Raises:
        SQLAlchemyError: If database operation fails
    """
    providers = [
        {
            "npi": "1234567890",
            "name": "Dr. John Smith",
            "specialty": "Internal Medicine",
            "taxonomy_code": "207RI0001X",
        },
        {
            "npi": "0987654321",
            "name": "Dr. Jane Doe",
            "specialty": "Cardiology",
            "taxonomy_code": "207RC0000X",
        },
    ]

    for provider_data in providers:
        existing = db.query(Provider).filter(Provider.npi == provider_data["npi"]).first()
        if existing:
            logger.info(f"Provider {provider_data['npi']} already exists, skipping")
            continue

        provider = Provider(**provider_data)
        db.add(provider)
        logger.info(f"Created provider: {provider_data['name']} (NPI: {provider_data['npi']})")

    db.commit()


def main() -> None:
    """Main seeding function."""
    logger.info("Starting data seeding...")

    # Create database session
    db = SessionLocal()

    try:
        seed_payers(db)
        seed_practice_configs(db)
        seed_providers(db)
        logger.info("Data seeding completed successfully!")
    except IntegrityError as e:
        logger.error(
            "Database integrity error during seeding",
            error=str(e),
            exc_info=True
        )
        db.rollback()
        raise  # Re-raise to preserve original exception and traceback
    except SQLAlchemyError as e:
        logger.error(
            "Database error during seeding",
            error=str(e),
            exc_info=True
        )
        db.rollback()
        raise  # Re-raise to preserve original exception and traceback
    except Exception as e:
        logger.error(
            "Unexpected error during seeding",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        db.rollback()
        raise  # Re-raise to preserve original exception and traceback
    finally:
        db.close()


if __name__ == "__main__":
    main()

