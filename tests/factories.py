"""Test data factories using factory-boy."""
from datetime import datetime

import factory

from app.models.database import (
    Claim,
    ClaimEpisode,
    ClaimLine,
    ClaimStatus,
    DenialPattern,
    EpisodeStatus,
    Payer,
    Plan,
    PracticeConfig,
    Provider,
    Remittance,
    RemittanceStatus,
    RiskLevel,
    RiskScore,
)


class ProviderFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for Provider model."""

    class Meta:
        model = Provider
        sqlalchemy_session_persistence = "commit"
        abstract = False

    npi = factory.Sequence(lambda n: f"{n:010d}")
    name = factory.Faker("company")
    specialty = factory.Faker("job")
    taxonomy_code = factory.Faker("numerify", text="######")


class PayerFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for Payer model."""

    class Meta:
        model = Payer
        sqlalchemy_session_persistence = "commit"
        abstract = False

    payer_id = factory.Sequence(lambda n: f"PAYER{n:03d}")
    name = factory.Faker("company")
    payer_type = factory.Iterator(["Medicare", "Medicaid", "Commercial", "Self-Pay"])
    rules_config = factory.LazyFunction(lambda: {"denial_threshold": 0.3})


class PlanFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for Plan model."""

    class Meta:
        model = Plan
        sqlalchemy_session_persistence = "commit"
        abstract = False

    payer = factory.SubFactory(PayerFactory)
    plan_name = factory.Faker("company")
    plan_type = factory.Iterator(["HMO", "PPO", "EPO", "POS"])
    benefit_rules = factory.LazyFunction(lambda: {"deductible": 1000, "copay": 25})


class ClaimFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for Claim model."""

    class Meta:
        model = Claim
        sqlalchemy_session_persistence = "commit"
        abstract = False

    claim_control_number = factory.Sequence(lambda n: f"CLM{n:06d}")
    patient_control_number = factory.Sequence(lambda n: f"PAT{n:06d}")
    provider = factory.SubFactory(ProviderFactory)
    payer = factory.SubFactory(PayerFactory)
    total_charge_amount = factory.Faker("pyfloat", left_digits=4, right_digits=2, positive=True)
    facility_type_code = factory.Iterator(["11", "12", "13", "21"])
    claim_frequency_type = factory.Iterator(["1", "2", "3"])
    assignment_code = factory.Iterator(["Y", "N"])
    statement_date = factory.LazyFunction(lambda: datetime.now())
    service_date = factory.LazyFunction(lambda: datetime.now())
    diagnosis_codes = factory.LazyFunction(lambda: ["E11.9", "I10"])
    principal_diagnosis = factory.Faker("numerify", text="E##.#")
    status = factory.Iterator([ClaimStatus.PENDING, ClaimStatus.PROCESSED])
    is_incomplete = False
    parsing_warnings = None
    practice_id = factory.Sequence(lambda n: f"PRACTICE{n:03d}")


class ClaimLineFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for ClaimLine model."""

    class Meta:
        model = ClaimLine
        sqlalchemy_session_persistence = "commit"
        abstract = False

    claim = factory.SubFactory(ClaimFactory)
    line_number = factory.Sequence(lambda n: str(n))
    procedure_code = factory.Iterator(["99213", "99214", "36415", "80053"])
    charge_amount = factory.Faker("pyfloat", left_digits=3, right_digits=2, positive=True)
    service_date = factory.LazyFunction(datetime.now)
    unit_count = factory.Faker("pyfloat", left_digits=1, right_digits=2, positive=True, min_value=1, max_value=10)
    unit_type = factory.Iterator(["UN", "DA", "WK"])


class RemittanceFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for Remittance model."""

    class Meta:
        model = Remittance
        sqlalchemy_session_persistence = "commit"
        abstract = False

    remittance_control_number = factory.Sequence(lambda n: f"REM{n:06d}")
    payer = factory.SubFactory(PayerFactory)
    payer_name = factory.Faker("company")
    payment_amount = factory.Faker("pyfloat", left_digits=4, right_digits=2, positive=True)
    payment_date = factory.LazyFunction(datetime.now)
    check_number = factory.Sequence(lambda n: f"CHK{n:06d}")
    claim_control_number = factory.Sequence(lambda n: f"CLM{n:06d}")
    denial_reasons = None
    adjustment_reasons = None
    status = factory.Iterator([RemittanceStatus.PENDING, RemittanceStatus.PROCESSED])


class ClaimEpisodeFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for ClaimEpisode model."""

    class Meta:
        model = ClaimEpisode
        sqlalchemy_session_persistence = "commit"
        abstract = False

    claim = factory.SubFactory(ClaimFactory)
    remittance = factory.SubFactory(RemittanceFactory)
    status = factory.Iterator([EpisodeStatus.PENDING, EpisodeStatus.LINKED, EpisodeStatus.COMPLETE])
    payment_amount = factory.Faker("pyfloat", left_digits=4, right_digits=2, positive=True)
    denial_count = factory.Faker("random_int", min=0, max=5)
    adjustment_count = factory.Faker("random_int", min=0, max=5)


class DenialPatternFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for DenialPattern model."""

    class Meta:
        model = DenialPattern
        sqlalchemy_session_persistence = "commit"
        abstract = False

    payer = factory.SubFactory(PayerFactory)
    pattern_type = factory.Iterator(["coding", "documentation", "eligibility", "authorization"])
    denial_reason_code = factory.Faker("numerify", text="CO##")
    frequency = factory.Faker("pyfloat", left_digits=1, right_digits=2, min_value=0, max_value=1)
    pattern_description = factory.Faker("sentence")
    occurrence_count = factory.Faker("random_int", min=1, max=100)
    confidence_score = factory.Faker("pyfloat", left_digits=1, right_digits=2, min_value=0, max_value=1)
    conditions = factory.LazyFunction(lambda: {"diagnosis_codes": ["E11.9"], "procedure_codes": ["99213"]})


class RiskScoreFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for RiskScore model."""

    class Meta:
        model = RiskScore
        sqlalchemy_session_persistence = "commit"
        abstract = False

    claim = factory.SubFactory(ClaimFactory)
    overall_score = factory.Faker("pyfloat", left_digits=2, right_digits=2, min_value=0, max_value=100)
    risk_level = factory.Iterator([RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL])
    coding_risk = factory.Faker("pyfloat", left_digits=2, right_digits=2, min_value=0, max_value=100)
    documentation_risk = factory.Faker("pyfloat", left_digits=2, right_digits=2, min_value=0, max_value=100)
    payer_risk = factory.Faker("pyfloat", left_digits=2, right_digits=2, min_value=0, max_value=100)
    historical_risk = factory.Faker("pyfloat", left_digits=2, right_digits=2, min_value=0, max_value=100)
    risk_factors = factory.LazyFunction(lambda: ["Missing documentation", "Coding mismatch"])
    recommendations = factory.LazyFunction(lambda: ["Add supporting documentation", "Review diagnosis codes"])
    model_version = "1.0.0"
    model_confidence = factory.Faker("pyfloat", left_digits=1, right_digits=2, min_value=0, max_value=1)


class PracticeConfigFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for PracticeConfig model."""

    class Meta:
        model = PracticeConfig
        sqlalchemy_session_persistence = "commit"
        abstract = False

    practice_id = factory.Sequence(lambda n: f"PRACTICE{n:03d}")
    config_key = factory.Iterator(["risk_threshold", "auto_submit", "notification_enabled"])
    config_value = factory.LazyFunction(lambda: {"value": True})

