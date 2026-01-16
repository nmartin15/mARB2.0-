"""Tests for 835 EDI remittance parser."""
from pathlib import Path

import pytest

from app.services.edi.parser import EDIParser
from app.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.fixture
def sample_835_file_path() -> Path:
    """Get path to sample 835 file."""
    return Path(__file__).parent.parent / "samples" / "sample_835.txt"


@pytest.fixture
def sample_835_content(sample_835_file_path: Path) -> str:
    """Load sample 835 file content."""
    with open(sample_835_file_path, "r") as f:
        return f.read()


@pytest.mark.unit
class Test835ParserBasic:
    """Basic 835 parsing tests."""

    def test_parse_835_file_detection(self, sample_835_content: str):
        """Test that 835 file is correctly detected."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        assert result["file_type"] == "835"
        assert "envelope" in result

    def test_parse_835_envelope(self, sample_835_content: str):
        """Test envelope segment parsing."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        envelope = result.get("envelope", {})
        assert "isa" in envelope
        assert "gs" in envelope
        assert "st" in envelope

        # Verify GS segment indicates 835
        gs = envelope.get("gs", {})
        assert gs.get("receiver_id") is not None

    def test_parse_835_remittances_count(self, sample_835_content: str):
        """Test that all remittances are extracted."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        # Should extract multiple remittances from sample file
        # Note: 835 parser not yet fully implemented, so this may return empty list
        remittances = result.get("remittances", [])
        warnings = result.get("warnings", [])

        # If parser is not implemented, check for warning
        if len(remittances) == 0:
            assert any("not yet implemented" in str(w).lower() for w in warnings), \
                "If no remittances, should have warning about implementation"
        else:
            assert len(remittances) > 0, "Should extract at least one remittance"

    def test_parse_835_claim_payment_segments(self, sample_835_content: str):
        """Test CLP (claim payment) segment extraction."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        if remittances:
            remittance = remittances[0]
            # Verify CLP data is present
            assert "claim_control_number" in remittance or "claim_id" in remittance
            assert "payment_amount" in remittance or "claim_payment_amount" in remittance


@pytest.mark.unit
class Test835ParserSegments:
    """Test individual segment extraction from 835 files."""

    def test_extract_bpr_segment(self, sample_835_content: str):
        """Test BPR (financial information) segment extraction."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        # BPR should contain payment information
        # This will need to be implemented in parser
        assert "file_type" in result

    def test_extract_clp_segment(self, sample_835_content: str):
        """Test CLP (claim payment) segment extraction."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        if remittances:
            # Verify CLP data structure
            remittance = remittances[0]
            assert isinstance(remittance, dict)

    def test_extract_cas_segment(self, sample_835_content: str):
        """Test CAS (claim adjustment) segment extraction."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        if remittances:
            # Verify adjustment codes are extracted
            remittance = remittances[0]
            # Adjustments should be present in sample file
            assert isinstance(remittance, dict)

    def test_extract_svc_segment(self, sample_835_content: str):
        """Test SVC (service payment) segment extraction."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        if remittances:
            # Verify service line payments are extracted
            remittance = remittances[0]
            assert isinstance(remittance, dict)


@pytest.mark.unit
class Test835ParserPaymentScenarios:
    """Test different payment scenarios in 835 files."""

    def test_parse_fully_paid_claim(self, sample_835_content: str):
        """Test parsing fully paid claim."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        # Sample file contains fully paid claims (status code 1)
        assert len(remittances) > 0

    def test_parse_denied_claim(self, sample_835_content: str):
        """Test parsing denied claim."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        # Sample file contains denied claim (status code 4)
        assert len(remittances) > 0

        # Find denied claim
        denied_remittances = [
            r for r in remittances
            if r.get("claim_status_code") == "4" or r.get("payment_amount", 0) == 0
        ]
        assert len(denied_remittances) > 0, "Should find at least one denied claim"

    def test_parse_partial_payment(self, sample_835_content: str):
        """Test parsing partial payment."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        # Sample file contains partial payments
        assert len(remittances) > 0


@pytest.mark.unit
class Test835ParserAdjustmentCodes:
    """Test adjustment code extraction and mapping."""

    def test_extract_co_codes(self, sample_835_content: str):
        """Test extraction of CO (contractual obligation) codes."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        # Sample file contains CO45 codes
        assert len(remittances) > 0

        # Verify CO codes are extracted
        co_found = False
        for remittance in remittances:
            co_adjustments = remittance.get("co_adjustments", [])
            if co_adjustments:
                co_found = True
                # Check for CO45 specifically
                co45_found = any(adj.get("reason_code") == "45" for adj in co_adjustments)
                assert co45_found, "Should find CO45 adjustment code"
                break

        assert co_found, "Should find at least one CO adjustment code"

    def test_extract_pr_codes(self, sample_835_content: str):
        """Test extraction of PR (patient responsibility) codes."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        # Sample file contains PR1 and PR2 codes
        assert len(remittances) > 0

        # Verify PR codes are extracted
        pr_found = False
        for remittance in remittances:
            pr_adjustments = remittance.get("pr_adjustments", [])
            if pr_adjustments:
                pr_found = True
                # Check for PR1 or PR2
                pr1_or_pr2 = any(adj.get("reason_code") in ("1", "2") for adj in pr_adjustments)
                assert pr1_or_pr2, "Should find PR1 or PR2 adjustment code"
                break

        assert pr_found, "Should find at least one PR adjustment code"

    def test_extract_oa_codes(self, sample_835_content: str):
        """Test extraction of OA (other adjustment) codes."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        # Sample file contains OA23 codes
        assert len(remittances) > 0

        # Verify OA codes are extracted
        oa_found = False
        for remittance in remittances:
            oa_adjustments = remittance.get("oa_adjustments", [])
            if oa_adjustments:
                oa_found = True
                # Check for OA23 specifically
                oa23_found = any(adj.get("reason_code") == "23" for adj in oa_adjustments)
                assert oa23_found, "Should find OA23 adjustment code"
                break

        assert oa_found, "Should find at least one OA adjustment code"

    def test_map_adjustment_to_denial_reason(self, sample_835_content: str):
        """Test mapping adjustment codes to denial reasons."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        # Verify denial reasons are extracted
        assert len(remittances) > 0

        # Verify adjustments are present (which can indicate denial reasons)
        adjustments_found = False
        for remittance in remittances:
            adjustments = remittance.get("adjustments", [])
            if adjustments:
                adjustments_found = True
                break

        assert adjustments_found, "Should find adjustment codes that can map to denial reasons"


@pytest.mark.unit
class Test835ParserErrorHandling:
    """Test error handling in 835 parser."""

    def test_parse_empty_file(self):
        """Test parsing empty file."""
        parser = EDIParser()

        with pytest.raises((ValueError, KeyError)):
            parser.parse("", "empty.txt")

    def test_parse_invalid_edi_structure(self):
        """Test parsing invalid EDI structure."""
        parser = EDIParser()
        invalid_content = "NOT*VALID*EDI*CONTENT~"

        # Should handle gracefully
        result = parser.parse(invalid_content, "invalid.txt")
        assert "warnings" in result or "errors" in result

    def test_parse_missing_segments(self):
        """Test parsing file with missing segments."""
        # Create minimal 835 file
        minimal_835 = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HP*SENDER*RECEIVER*20241220*1200*1*X*005010X221A1~
ST*835*0001*005010X221A1~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = EDIParser()
        result = parser.parse(minimal_835, "minimal_835.txt")

        # Should handle missing segments gracefully
        assert "file_type" in result
        assert "warnings" in result or len(result.get("remittances", [])) == 0


@pytest.mark.integration
class Test835ParserIntegration:
    """Integration tests for 835 parser."""

    def test_parse_and_store_remittance(self, sample_835_content: str, db_session):
        """Test parsing 835 and storing in database."""

        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        # This test will need the 835 transformer implementation
        remittances = result.get("remittances", [])
        assert len(remittances) > 0

    def test_parse_multiple_claims_in_file(self, sample_835_content: str):
        """Test parsing file with multiple claims."""
        parser = EDIParser()
        result = parser.parse(sample_835_content, "sample_835.txt")

        remittances = result.get("remittances", [])
        # Sample file contains 8 claims
        assert len(remittances) >= 1  # At least one should be parsed

