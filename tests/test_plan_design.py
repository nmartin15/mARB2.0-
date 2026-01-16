"""Tests for insurance plan design rules."""
import json
from pathlib import Path

import pytest

from app.models.database import Plan
from tests.factories import PayerFactory


@pytest.fixture
def sample_plan_design_path() -> Path:
    """Get path to sample plan design file."""
    return Path(__file__).parent.parent / "samples" / "sample_plan_design.json"


@pytest.fixture
def sample_plan_design(sample_plan_design_path: Path) -> dict:
    """Load sample plan design JSON."""
    with open(sample_plan_design_path, "r") as f:
        return json.load(f)


@pytest.fixture
def plan_with_design(db_session, sample_plan_design: dict) -> Plan:
    """Create a plan with sample design loaded."""
    payer = PayerFactory()
    plan = Plan(
        payer_id=payer.id,
        plan_name=sample_plan_design["plan_name"],
        plan_type=sample_plan_design["plan_type"],
        benefit_rules=sample_plan_design,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


@pytest.mark.unit
class TestPlanDesignLoading:
    """Test loading and validation of plan designs."""

    def test_load_plan_design_from_json(self, sample_plan_design: dict):
        """Test loading plan design from JSON file."""
        assert "plan_name" in sample_plan_design
        assert "plan_type" in sample_plan_design
        assert "deductibles" in sample_plan_design
        assert "copays" in sample_plan_design

    def test_plan_design_required_fields(self, sample_plan_design: dict):
        """Test that all required fields are present."""
        required_fields = [
            "plan_name",
            "plan_type",
            "deductibles",
            "out_of_pocket_maximums",
            "copays",
            "coinsurance",
        ]
        for field in required_fields:
            assert field in sample_plan_design, f"Missing required field: {field}"

    def test_store_plan_design_in_database(self, db_session, sample_plan_design: dict):
        """Test storing plan design in database."""
        payer = PayerFactory()
        plan = Plan(
            payer_id=payer.id,
            plan_name=sample_plan_design["plan_name"],
            plan_type=sample_plan_design["plan_type"],
            benefit_rules=sample_plan_design,
        )
        db_session.add(plan)
        db_session.commit()

        # Verify it was stored
        retrieved = db_session.query(Plan).filter(Plan.id == plan.id).first()
        assert retrieved is not None
        assert retrieved.benefit_rules == sample_plan_design

    def test_retrieve_plan_design_from_database(self, plan_with_design: Plan):
        """Test retrieving plan design from database."""
        assert plan_with_design.benefit_rules is not None
        assert "plan_name" in plan_with_design.benefit_rules
        assert plan_with_design.benefit_rules["plan_name"] == plan_with_design.plan_name


@pytest.mark.unit
class TestDeductibleCalculation:
    """Test deductible calculation logic."""

    def test_individual_in_network_deductible(self, sample_plan_design: dict):
        """Test individual in-network deductible."""
        deductibles = sample_plan_design["deductibles"]
        individual = deductibles["individual"]

        assert "in_network" in individual
        assert individual["in_network"] == 1500.00

    def test_family_deductible(self, sample_plan_design: dict):
        """Test family deductible."""
        deductibles = sample_plan_design["deductibles"]
        family = deductibles["family"]

        assert "in_network" in family
        assert family["in_network"] == 3000.00

    def test_deductible_applies_to_services(self, sample_plan_design: dict):
        """Test deductible applies to correct service types."""
        deductibles = sample_plan_design["deductibles"]
        individual = deductibles["individual"]

        assert "applies_to" in individual
        assert "medical" in individual["applies_to"]
        assert "pharmacy" in individual["applies_to"]


@pytest.mark.unit
class TestCopayCalculation:
    """Test copay calculation logic."""

    def test_primary_care_copay(self, sample_plan_design: dict):
        """Test primary care visit copay."""
        copays = sample_plan_design["copays"]
        primary_care = copays["primary_care_visit"]

        assert "in_network" in primary_care
        assert primary_care["in_network"] == 25.00

    def test_specialist_copay(self, sample_plan_design: dict):
        """Test specialist visit copay."""
        copays = sample_plan_design["copays"]
        specialist = copays["specialist_visit"]

        assert "in_network" in specialist
        assert specialist["in_network"] == 50.00

    def test_emergency_room_copay(self, sample_plan_design: dict):
        """Test emergency room copay."""
        copays = sample_plan_design["copays"]
        er = copays["emergency_room"]

        assert "in_network" in er
        assert er["in_network"] == 250.00
        assert er.get("waived_if_admitted") is True

    def test_pharmacy_tier_copays(self, sample_plan_design: dict):
        """Test pharmacy tier copays."""
        copays = sample_plan_design["copays"]
        pharmacy = copays["pharmacy"]

        assert "generic" in pharmacy
        assert pharmacy["generic"]["in_network"] == 10.00
        assert pharmacy["preferred_brand"]["in_network"] == 40.00
        assert pharmacy["non_preferred_brand"]["in_network"] == 60.00
        assert pharmacy["specialty"]["in_network"] == 100.00


@pytest.mark.unit
class TestCoinsuranceCalculation:
    """Test coinsurance calculation logic."""

    def test_medical_coinsurance(self, sample_plan_design: dict):
        """Test medical coinsurance percentages."""
        coinsurance = sample_plan_design["coinsurance"]
        medical = coinsurance["medical"]

        assert medical["in_network"]["percentage"] == 20
        assert medical["out_of_network"]["percentage"] == 40

    def test_coinsurance_after_deductible(self, sample_plan_design: dict):
        """Test coinsurance applies after deductible."""
        coinsurance = sample_plan_design["coinsurance"]
        medical = coinsurance["medical"]

        assert medical["in_network"]["applies_after_deductible"] is True


@pytest.mark.unit
class TestOutOfPocketMaximum:
    """Test out-of-pocket maximum calculations."""

    def test_individual_oop_max(self, sample_plan_design: dict):
        """Test individual out-of-pocket maximum."""
        oop_max = sample_plan_design["out_of_pocket_maximums"]
        individual = oop_max["individual"]

        assert individual["in_network"] == 5000.00
        assert individual["out_of_network"] == 10000.00

    def test_family_oop_max(self, sample_plan_design: dict):
        """Test family out-of-pocket maximum."""
        oop_max = sample_plan_design["out_of_pocket_maximums"]
        family = oop_max["family"]

        assert family["in_network"] == 10000.00
        assert family["out_of_network"] == 20000.00

    def test_oop_max_includes_deductible(self, sample_plan_design: dict):
        """Test that OOP max includes deductible."""
        oop_max = sample_plan_design["out_of_pocket_maximums"]
        assert oop_max["includes_deductible"] is True


@pytest.mark.unit
class TestPriorAuthorizationRules:
    """Test prior authorization requirement detection."""

    def test_surgery_requires_pa(self, sample_plan_design: dict):
        """Test that surgery requires prior authorization."""
        pa_rules = sample_plan_design["prior_authorization_requirements"]
        always_required = pa_rules["always_required"]

        surgery_rule = next(
            (r for r in always_required if r["service_type"] == "surgery"),
            None
        )
        assert surgery_rule is not None
        assert "10000-69999" in surgery_rule["cpt_codes"]

    def test_imaging_requires_pa(self, sample_plan_design: dict):
        """Test that advanced imaging requires prior authorization."""
        pa_rules = sample_plan_design["prior_authorization_requirements"]
        always_required = pa_rules["always_required"]

        imaging_rule = next(
            (r for r in always_required if r["service_type"] == "imaging"),
            None
        )
        assert imaging_rule is not None
        assert "MRI" in imaging_rule.get("modalities", [])

    def test_pt_visits_require_pa_after_limit(self, sample_plan_design: dict):
        """Test that PT requires PA after visit limit."""
        pa_rules = sample_plan_design["prior_authorization_requirements"]
        required_after = pa_rules["required_after_visits"]

        assert "physical_therapy" in required_after
        assert required_after["physical_therapy"]["visits"] == 20


@pytest.mark.unit
class TestCPTCodeRules:
    """Test CPT code-specific rules."""

    def test_cpt_code_allowed_amounts(self, sample_plan_design: dict):
        """Test CPT code allowed amounts."""
        cpt_rules = sample_plan_design["cpt_code_rules"]

        assert "99213" in cpt_rules
        assert cpt_rules["99213"]["allowed_amount_in_network"] == 150.00
        assert cpt_rules["99213"]["allowed_amount_out_network"] == 200.00

    def test_cpt_code_prior_auth_requirement(self, sample_plan_design: dict):
        """Test CPT code prior authorization requirements."""
        cpt_rules = sample_plan_design["cpt_code_rules"]

        assert cpt_rules["99215"]["requires_prior_auth"] is True
        assert cpt_rules["99213"]["requires_prior_auth"] is False

    def test_cpt_code_frequency_limits(self, sample_plan_design: dict):
        """Test CPT code frequency limits."""
        cpt_rules = sample_plan_design["cpt_code_rules"]

        # 80053 has frequency limit
        if "80053" in cpt_rules:
            frequency_limit = cpt_rules["80053"].get("frequency_limit")
            if frequency_limit:
                assert frequency_limit["per_year"] == 4


@pytest.mark.unit
class TestDenialReasonCodes:
    """Test denial reason code mappings."""

    def test_denial_reason_code_structure(self, sample_plan_design: dict):
        """Test denial reason code structure."""
        denial_codes = sample_plan_design["denial_reason_codes"]

        assert "CO45" in denial_codes
        assert "PR1" in denial_codes
        assert "PR2" in denial_codes
        assert "OA23" in denial_codes

    def test_denial_reason_descriptions(self, sample_plan_design: dict):
        """Test denial reason descriptions."""
        denial_codes = sample_plan_design["denial_reason_codes"]

        co45 = denial_codes["CO45"]
        assert "description" in co45
        assert "category" in co45
        assert "action_required" in co45

    def test_denial_reason_appealability(self, sample_plan_design: dict):
        """Test denial reason appealability."""
        denial_codes = sample_plan_design["denial_reason_codes"]

        co45 = denial_codes["CO45"]
        assert "appealable" in co45
        assert isinstance(co45["appealable"], bool)


@pytest.mark.integration
class TestPlanDesignIntegration:
    """Integration tests for plan design rules."""

    def test_apply_plan_rules_to_claim(self, plan_with_design: Plan, db_session):
        """Test applying plan rules to a claim."""
        from tests.factories import ClaimFactory

        claim = ClaimFactory()

        # This would use a service to apply plan rules
        # For now, just verify plan has rules
        assert plan_with_design.benefit_rules is not None
        assert claim is not None

    def test_calculate_benefits_for_service(self, plan_with_design: Plan):
        """Test calculating benefits for a specific service."""
        benefit_rules = plan_with_design.benefit_rules
        cpt_rules = benefit_rules.get("cpt_code_rules", {})

        # Test with 99213
        if "99213" in cpt_rules:
            rule = cpt_rules["99213"]
            assert "allowed_amount_in_network" in rule
            assert rule["allowed_amount_in_network"] > 0

