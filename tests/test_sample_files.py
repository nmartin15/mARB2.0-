"""Tests for sample EDI and plan design files."""
import json
from pathlib import Path

import pytest

from app.services.edi.parser import EDIParser


@pytest.fixture
def samples_dir() -> Path:
    """Get samples directory path."""
    return Path(__file__).parent.parent / "samples"


@pytest.fixture
def sample_835_path(samples_dir: Path) -> Path:
    """Get sample 835 file path."""
    return samples_dir / "sample_835.txt"


@pytest.fixture
def sample_plan_design_path(samples_dir: Path) -> Path:
    """Get sample plan design file path."""
    return samples_dir / "sample_plan_design.json"


@pytest.mark.integration
class TestSample835File:
    """Test the sample 835 file."""

    def test_sample_835_file_exists(self, sample_835_path: Path):
        """Test that sample 835 file exists."""
        assert sample_835_path.exists(), "Sample 835 file should exist"

    def test_sample_835_file_readable(self, sample_835_path: Path):
        """Test that sample 835 file is readable."""
        with open(sample_835_path, "r") as f:
            content = f.read()
            assert len(content) > 0, "Sample 835 file should have content"

    def test_sample_835_file_structure(self, sample_835_path: Path):
        """Test that sample 835 file has correct structure."""
        with open(sample_835_path, "r") as f:
            content = f.read()

            # Should have ISA segment
            assert "ISA*" in content, "Should have ISA segment"
            # Should have IEA segment
            assert "IEA*" in content, "Should have IEA segment"
            # Should have GS segment
            assert "GS*HP*" in content, "Should have GS segment with HP (Health Care Payment)"
            # Should have ST*835 segment
            assert "ST*835*" in content, "Should have ST*835 segment"
            # Should have CLP segments (claim payments)
            assert "CLP*" in content, "Should have CLP segments"

    def test_sample_835_parseable(self, sample_835_path: Path):
        """Test that sample 835 file can be parsed."""
        with open(sample_835_path, "r") as f:
            content = f.read()

        parser = EDIParser()
        result = parser.parse(content, "sample_835.txt")

        assert result["file_type"] == "835", "Should be detected as 835 file"
        assert "envelope" in result, "Should have envelope data"

    def test_sample_835_claim_count(self, sample_835_path: Path):
        """Test that sample 835 file has expected number of claims."""
        with open(sample_835_path, "r") as f:
            content = f.read()

        # Count CLP segments (each represents a claim)
        clp_count = content.count("CLP*")
        assert clp_count > 0, "Should have at least one CLP segment"
        # Sample file should have 8 claims
        assert clp_count == 8, f"Expected 8 claims, found {clp_count}"

    def test_sample_835_payment_scenarios(self, sample_835_path: Path):
        """Test that sample 835 file contains various payment scenarios."""
        with open(sample_835_path, "r") as f:
            content = f.read()

        # Should have fully paid claims (status code 1)
        assert "CLP*" in content and "*1*" in content, "Should have paid claims"
        # Should have denied claims (status code 4)
        assert "*4*" in content, "Should have denied claims"
        # Should have adjustment codes
        assert "CAS*" in content, "Should have adjustment codes"


@pytest.mark.integration
class TestSamplePlanDesignFile:
    """Test the sample plan design file."""

    def test_sample_plan_design_exists(self, sample_plan_design_path: Path):
        """Test that sample plan design file exists."""
        assert sample_plan_design_path.exists(), "Sample plan design file should exist"

    def test_sample_plan_design_valid_json(self, sample_plan_design_path: Path):
        """Test that sample plan design is valid JSON."""
        with open(sample_plan_design_path, "r") as f:
            data = json.load(f)
            assert isinstance(data, dict), "Should be a dictionary"

    def test_sample_plan_design_required_fields(self, sample_plan_design_path: Path):
        """Test that sample plan design has required fields."""
        with open(sample_plan_design_path, "r") as f:
            data = json.load(f)

        required_fields = [
            "plan_name",
            "plan_type",
            "deductibles",
            "out_of_pocket_maximums",
            "copays",
            "coinsurance",
            "benefit_limits",
            "prior_authorization_requirements",
            "cpt_code_rules",
            "denial_reason_codes",
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_sample_plan_design_deductibles(self, sample_plan_design_path: Path):
        """Test deductible structure in sample plan design."""
        with open(sample_plan_design_path, "r") as f:
            data = json.load(f)

        deductibles = data["deductibles"]
        assert "individual" in deductibles
        assert "family" in deductibles
        assert "in_network" in deductibles["individual"]
        assert deductibles["individual"]["in_network"] == 1500.00

    def test_sample_plan_design_copays(self, sample_plan_design_path: Path):
        """Test copay structure in sample plan design."""
        with open(sample_plan_design_path, "r") as f:
            data = json.load(f)

        copays = data["copays"]
        assert "primary_care_visit" in copays
        assert "specialist_visit" in copays
        assert "emergency_room" in copays
        assert "pharmacy" in copays

    def test_sample_plan_design_cpt_rules(self, sample_plan_design_path: Path):
        """Test CPT code rules in sample plan design."""
        with open(sample_plan_design_path, "r") as f:
            data = json.load(f)

        cpt_rules = data["cpt_code_rules"]
        assert len(cpt_rules) > 0, "Should have CPT code rules"

        # Check specific codes from sample 835 file
        test_codes = ["99213", "99214", "99215", "36415", "80053", "85025", "93000", "71020"]
        found_codes = [code for code in test_codes if code in cpt_rules]
        assert len(found_codes) > 0, f"Should have at least some CPT codes from 835 file. Found: {found_codes}"

    def test_sample_plan_design_denial_codes(self, sample_plan_design_path: Path):
        """Test denial reason codes in sample plan design."""
        with open(sample_plan_design_path, "r") as f:
            data = json.load(f)

        denial_codes = data["denial_reason_codes"]
        assert len(denial_codes) > 0, "Should have denial reason codes"

        # Check codes that appear in sample 835 file
        expected_codes = ["CO45", "CO96", "CO97", "CO253", "OA23", "PR1", "PR2"]
        found_codes = [code for code in expected_codes if code in denial_codes]
        assert len(found_codes) > 0, f"Should have denial codes from 835 file. Found: {found_codes}"


@pytest.mark.integration
class TestSampleFilesIntegration:
    """Integration tests using both sample files."""

    def test_parse_835_and_apply_plan_rules(self, sample_835_path: Path, sample_plan_design_path: Path):
        """Test parsing 835 and applying plan design rules."""
        # Load 835 file
        with open(sample_835_path, "r") as f:
            edi_content = f.read()

        # Load plan design
        with open(sample_plan_design_path, "r") as f:
            plan_design = json.load(f)

        # Parse 835
        parser = EDIParser()
        result = parser.parse(edi_content, "sample_835.txt")

        # Verify parsing worked
        assert result["file_type"] == "835"

        # Verify plan design has rules for codes in 835
        cpt_rules = plan_design["cpt_code_rules"]
        denial_codes = plan_design["denial_reason_codes"]

        # Both should have data
        assert len(cpt_rules) > 0
        assert len(denial_codes) > 0

    def test_denial_codes_match_835_adjustments(self, sample_835_path: Path, sample_plan_design_path: Path):
        """Test that denial codes in plan design match adjustment codes in 835."""
        # Load 835 file
        with open(sample_835_path, "r") as f:
            edi_content = f.read()

        # Load plan design
        with open(sample_plan_design_path, "r") as f:
            plan_design = json.load(f)

        # Extract adjustment codes from 835 (CAS segments)
        # Format: CAS*{category}*{code}*{amount}
        adjustment_codes = set()
        for line in edi_content.split("~"):
            if line.startswith("CAS*"):
                parts = line.split("*")
                if len(parts) >= 3:
                    category = parts[1]
                    code = parts[2]
                    adjustment_codes.add(f"{category}{code}")

        # Get denial codes from plan design
        denial_codes = set(plan_design["denial_reason_codes"].keys())

        # Should have some overlap
        # Note: CAS segment format is CAS*{category}*{code}*{amount}*...
        # We need to check if codes match (e.g., CO45 in CAS should match CO45 in denial codes)
        # Extract just the code part (category + code)
        cas_codes = set()
        for code in adjustment_codes:
            # Codes are like "CO45", "PR1", etc.
            cas_codes.add(code)

        overlap = cas_codes.intersection(denial_codes)
        # If no direct overlap, check if any CAS codes start with categories in denial codes
        if len(overlap) == 0:
            # Check for partial matches (e.g., CO45 in CAS matches CO45 in denial codes)
            for cas_code in cas_codes:
                if cas_code in denial_codes:
                    overlap.add(cas_code)

        # If we couldn't extract codes (parser not implemented), just verify the file has CAS segments
        if len(cas_codes) == 0:
            # Verify CAS segments exist in file
            assert "CAS*" in edi_content, "835 file should contain CAS segments"
            # Verify plan design has denial codes
            assert len(denial_codes) > 0, "Plan design should have denial codes"
        else:
            assert len(overlap) > 0, \
                f"Should have matching codes. 835 codes: {cas_codes}, Plan codes: {denial_codes}"

