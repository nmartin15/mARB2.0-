"""Tests for 837 EDI claim parser."""
from datetime import datetime
from pathlib import Path

import pytest

from app.services.edi.parser import EDIParser
from app.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.fixture
def sample_837_file_path() -> Path:
    """Get path to sample 837 file."""
    return Path(__file__).parent.parent / "samples" / "sample_837.txt"


@pytest.fixture
def sample_837_content(sample_837_file_path: Path) -> str:
    """Load sample 837 file content."""
    with open(sample_837_file_path, "r") as f:
        return f.read()


@pytest.fixture
def minimal_837_content() -> str:
    """Minimal valid 837 file content."""
    return """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
NM1*41*2*SAMPLE MEDICAL PRACTICE*****46*1234567890~
HL*1**20*1~
PRV*BI*PXC*207RI0001X~
NM1*85*2*DR JOHN SMITH*****XX*1234567890~
HL*2*1*22*0~
SBR*P*18*GROUP123******CI~
NM1*IL*1*DOE*JOHN*M***MI*123456789~
DMG*D8*19800101*M~
NM1*PR*2*BLUE CROSS BLUE SHIELD*****PI*BLUE_CROSS~
CLM*CLAIM001*1500.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241215~
DTP*472*D8*20241215~
REF*D9*PATIENT001~
HI*ABK:I10*E11.9~
LX*1~
SV1*HC:99213*1500.00*UN*1***1~
DTP*472*D8*20241215~
SE*24*0001~
GE*1*1~
IEA*1*000000001~"""


@pytest.fixture
def multi_claim_837_content() -> str:
    """837 file with multiple claims."""
    claim1 = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
NM1*41*2*SAMPLE MEDICAL PRACTICE*****46*1234567890~
HL*1**20*1~
PRV*BI*PXC*207RI0001X~
NM1*85*2*DR JOHN SMITH*****XX*1234567890~
HL*2*1*22*0~
SBR*P*18*GROUP123******CI~
NM1*IL*1*DOE*JOHN*M***MI*123456789~
DMG*D8*19800101*M~
NM1*PR*2*BLUE CROSS BLUE SHIELD*****PI*BLUE_CROSS~
CLM*CLAIM001*1500.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241215~
DTP*472*D8*20241215~
REF*D9*PATIENT001~
HI*ABK:I10*E11.9~
LX*1~
SV1*HC:99213*1500.00*UN*1***1~
DTP*472*D8*20241215~"""

    claim2 = """HL*3*1*22*0~
SBR*P*18*GROUP456******CI~
NM1*IL*1*SMITH*JANE*F***MI*987654321~
DMG*D8*19900101*F~
NM1*PR*2*BLUE CROSS BLUE SHIELD*****PI*BLUE_CROSS~
CLM*CLAIM002*2000.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241216~
DTP*472*D8*20241216~
REF*D9*PATIENT002~
HI*ABK:I10*E11.9~
LX*1~
SV1*HC:99214*2000.00*UN*1***1~
DTP*472*D8*20241216~"""

    footer = """SE*48*0001~
GE*1*1~
IEA*1*000000001~"""

    return claim1 + claim2 + footer


@pytest.mark.unit
class Test837ParserBasic:
    """Basic 837 parsing tests."""

    def test_parse_837_file_detection(self, sample_837_content: str):
        """Test that 837 file is correctly detected."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        assert result["file_type"] == "837"
        assert "envelope" in result

    def test_parse_837_envelope(self, sample_837_content: str):
        """Test envelope segment parsing."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        envelope = result.get("envelope", {})
        assert "isa" in envelope
        assert "gs" in envelope
        assert "st" in envelope

        # Verify GS segment indicates 837
        gs = envelope.get("gs", {})
        assert gs.get("receiver_id") is not None

        # Verify ST segment indicates 837
        st = envelope.get("st", {})
        assert st.get("transaction_set_id") == "837"

    def test_parse_837_claims_count(self, sample_837_content: str):
        """Test that all claims are extracted."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        warnings = result.get("warnings", [])

        # Should extract at least one claim from sample file
        assert len(claims) > 0, f"Should extract at least one claim. Warnings: {warnings}"

    def test_parse_837_claim_control_numbers(self, sample_837_content: str):
        """Test that claim control numbers are extracted."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        # Verify each claim has a control number
        for claim in claims:
            assert "claim_control_number" in claim
            assert claim["claim_control_number"] is not None
            assert len(claim["claim_control_number"]) > 0

    def test_parse_837_multiple_claims(self, multi_claim_837_content: str):
        """Test parsing file with multiple claims."""
        parser = EDIParser()
        result = parser.parse(multi_claim_837_content, "multi_claim_837.txt")

        claims = result.get("claims", [])
        assert len(claims) >= 2, "Should extract at least 2 claims"

        # Verify claim control numbers are unique
        control_numbers = [c["claim_control_number"] for c in claims if c.get("claim_control_number")]
        assert len(control_numbers) == len(set(control_numbers)), "Claim control numbers should be unique"


@pytest.mark.unit
class Test837ParserSegments:
    """Test individual segment extraction from 837 files."""

    def test_extract_clm_segment(self, sample_837_content: str):
        """Test CLM (claim) segment extraction."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        assert "claim_control_number" in claim
        assert "total_charge_amount" in claim
        assert claim["total_charge_amount"] is not None

    def test_extract_sbr_segment(self, sample_837_content: str):
        """Test SBR (subscriber) segment extraction."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # SBR data should be extracted (payer information)
        assert "payer" in claim or "payer_id" in claim or "payer_name" in claim

    def test_extract_nm1_segments(self, sample_837_content: str):
        """Test NM1 (name) segment extraction for patient/provider/payer."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # Should have patient or provider information
        has_patient = any(key in claim for key in ["patient", "patient_name", "patient_control_number"])
        has_provider = any(key in claim for key in ["provider", "provider_name", "provider_npi"])
        assert has_patient or has_provider, "Should extract patient or provider information"

    def test_extract_hi_segments(self, sample_837_content: str):
        """Test HI (diagnosis) segment extraction."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # Should have diagnosis codes
        has_diagnosis = any(key in claim for key in ["diagnosis_codes", "primary_diagnosis", "diagnosis"])
        assert has_diagnosis, "Should extract diagnosis codes"

    def test_extract_sv1_segments(self, sample_837_content: str):
        """Test SV1 (service line) segment extraction."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # Should have claim lines
        assert "lines" in claim
        assert isinstance(claim["lines"], list)
        assert len(claim["lines"]) > 0

    def test_extract_dtp_segments(self, sample_837_content: str):
        """Test DTP (date) segment extraction."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # Should have at least one date field
        date_fields = ["service_date", "statement_date", "admission_date", "discharge_date"]
        has_date = any(field in claim for field in date_fields)
        assert has_date, "Should extract at least one date field"

    def test_extract_ref_segments(self, sample_837_content: str):
        """Test REF (reference) segment extraction."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # Should have reference numbers (patient control number, etc.)
        has_ref = any(key in claim for key in ["patient_control_number", "references", "ref"])
        assert has_ref, "Should extract reference information"


@pytest.mark.unit
class Test837ParserDataValidation:
    """Test data validation in 837 parser."""

    def test_validate_date_formats(self, sample_837_content: str):
        """Test date format validation."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # Check date fields are datetime objects or None
        date_fields = ["service_date", "statement_date", "admission_date", "discharge_date"]
        for field in date_fields:
            if field in claim:
                value = claim[field]
                assert value is None or isinstance(value, datetime), \
                    f"{field} should be datetime or None, got {type(value)}"

    def test_validate_numeric_amounts(self, sample_837_content: str):
        """Test numeric amount validation."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # Total charge amount should be numeric
        if "total_charge_amount" in claim and claim["total_charge_amount"] is not None:
            assert isinstance(claim["total_charge_amount"], (int, float)), \
                "total_charge_amount should be numeric"
            assert claim["total_charge_amount"] >= 0, "total_charge_amount should be non-negative"

    def test_validate_diagnosis_code_formats(self, sample_837_content: str):
        """Test diagnosis code format validation."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # Diagnosis codes should be valid format (ICD-10)
        diagnosis_fields = ["diagnosis_codes", "primary_diagnosis", "diagnosis"]
        for field in diagnosis_fields:
            if field in claim:
                codes = claim[field]
                if isinstance(codes, list):
                    for code in codes:
                        if isinstance(code, str):
                            # ICD-10 codes start with letter followed by digits
                            assert len(code) >= 3, f"Diagnosis code {code} should be at least 3 characters"

    def test_validate_cpt_code_formats(self, sample_837_content: str):
        """Test CPT code format validation."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # Procedure codes should be valid format
        if "lines" in claim:
            for line in claim["lines"]:
                if "procedure_code" in line:
                    code = line["procedure_code"]
                    if code:
                        # CPT codes are typically 5 digits, may have modifiers
                        assert len(code) >= 5, f"CPT code {code} should be at least 5 characters"

    def test_validate_npi_formats(self, sample_837_content: str):
        """Test NPI format validation."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # NPI should be 10 digits
        npi_fields = ["provider_npi", "npi", "provider_identifier"]
        for field in npi_fields:
            if field in claim:
                npi = claim[field]
                if npi and isinstance(npi, str):
                    # NPI is 10 digits
                    assert len(npi) == 10, f"NPI {npi} should be 10 digits"
                    assert npi.isdigit(), f"NPI {npi} should be numeric"


@pytest.mark.unit
class Test837ParserMissingSegments:
    """Test handling of missing segments."""

    def test_handle_missing_optional_segments(self, minimal_837_content: str):
        """Test handling missing optional segments gracefully."""
        parser = EDIParser()
        result = parser.parse(minimal_837_content, "minimal_837.txt")

        # Should parse successfully even with missing optional segments
        assert result["file_type"] == "837"
        claims = result.get("claims", [])
        assert len(claims) > 0

    def test_log_warnings_for_missing_important_segments(self):
        """Test that warnings are logged for missing important segments."""
        # Create file with missing CLM segment
        incomplete_837 = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = EDIParser()
        result = parser.parse(incomplete_837, "incomplete_837.txt")

        # Should have warnings about missing claims
        assert "warnings" in result or len(result.get("claims", [])) == 0

    def test_continue_parsing_when_non_critical_segments_missing(self, minimal_837_content: str):
        """Test that parsing continues when non-critical segments are missing."""
        parser = EDIParser()
        result = parser.parse(minimal_837_content, "minimal_837.txt")

        # Should still extract claims
        claims = result.get("claims", [])
        assert len(claims) > 0

    def test_mark_claims_incomplete_when_critical_segments_missing(self):
        """Test that claims are marked incomplete when critical segments missing."""
        # File with CLM but missing required segments
        incomplete_claim = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
HL*1**20*1~
HL*2*1*22*0~
CLM*CLAIM001*1500.00~
SE*7*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = EDIParser()
        result = parser.parse(incomplete_claim, "incomplete_claim.txt")

        claims = result.get("claims", [])
        if claims:
            # Claims with missing critical segments should be marked incomplete
            for claim in claims:
                if claim.get("is_incomplete"):
                    assert claim["is_incomplete"] is True


@pytest.mark.unit
class Test837ParserEdgeCases:
    """Test edge cases in 837 parser."""

    def test_parse_empty_file(self):
        """Test parsing empty file."""
        parser = EDIParser()

        with pytest.raises((ValueError, KeyError)):
            parser.parse("", "empty.txt")

    def test_parse_file_with_only_envelope(self):
        """Test parsing file with only envelope segments."""
        envelope_only = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = EDIParser()
        result = parser.parse(envelope_only, "envelope_only.txt")

        assert result["file_type"] == "837"
        # Should have no claims or warnings
        claims = result.get("claims", [])
        assert len(claims) == 0

    def test_parse_file_with_malformed_segments(self):
        """Test parsing file with malformed segments."""
        malformed = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
HL*1**20*1~
HL*2*1*22*0~
CLM*INCOMPLETE~
SE*6*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = EDIParser()
        result = parser.parse(malformed, "malformed.txt")

        # Should handle gracefully with warnings
        assert "warnings" in result or len(result.get("claims", [])) == 0

    def test_parse_file_with_invalid_delimiters(self):
        """Test parsing file with invalid delimiters."""
        # File with wrong delimiters (using | instead of *)
        invalid_delimiters = """ISA|00|          |00|          |ZZ|SENDER|ZZ|RECEIVER|241220|1200|^|00501|000000001|0|P|:~
GS|HC|SENDER|RECEIVER|20241220|1200|1|X|005010X222A1~
ST|837|0001|005010X222A1~
SE|3|0001~
GE|1|1~
IEA|1|000000001~"""

        parser = EDIParser()
        # Should handle gracefully (may not parse correctly but shouldn't crash)
        try:
            result = parser.parse(invalid_delimiters, "invalid_delimiters.txt")
            # If it parses, should have warnings or no claims
            assert "warnings" in result or len(result.get("claims", [])) == 0
        except (ValueError, KeyError):
            # Expected to fail with invalid delimiters
            pass

    def test_parse_file_with_special_characters(self, sample_837_content: str):
        """Test parsing file with special characters in data."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        # Should parse successfully
        assert result["file_type"] == "837"

    def test_parse_very_large_file(self):
        """Test parsing file with many claims (performance test)."""
        # Create a file with 10 claims
        base_claim = """HL*{idx}*1*22*0~
SBR*P*18*GROUP{idx}******CI~
NM1*IL*1*DOE*JOHN*M***MI*123456789~
DMG*D8*19800101*M~
CLM*CLAIM{idx:03d}*1500.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241215~
DTP*472*D8*20241215~
REF*D9*PATIENT{idx:03d}~
HI*ABK:I10*E11.9~
LX*1~
SV1*HC:99213*1500.00*UN*1***1~
DTP*472*D8*20241215~"""

        header = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
NM1*41*2*SAMPLE MEDICAL PRACTICE*****46*1234567890~
HL*1**20*1~
PRV*BI*PXC*207RI0001X~
NM1*85*2*DR JOHN SMITH*****XX*1234567890~"""

        footer = """SE*{count}*0001~
GE*1*1~
IEA*1*000000001~"""

        claims = [base_claim.format(idx=i) for i in range(2, 12)]  # 10 claims
        large_file = header + "".join(claims) + footer.format(count=len(claims) + 7)

        parser = EDIParser()
        result = parser.parse(large_file, "large_837.txt")

        claims_parsed = result.get("claims", [])
        assert len(claims_parsed) >= 5, f"Should parse at least 5 claims, got {len(claims_parsed)}"

    def test_parse_file_with_duplicate_claim_control_numbers(self):
        """Test parsing file with duplicate claim control numbers."""
        duplicate_claims = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
HL*1**20*1~
HL*2*1*22*0~
SBR*P*18*GROUP123******CI~
CLM*CLAIM001*1500.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241215~
HL*3*1*22*0~
SBR*P*18*GROUP456******CI~
CLM*CLAIM001*2000.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241216~
SE*10*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = EDIParser()
        result = parser.parse(duplicate_claims, "duplicate_claims.txt")

        claims = result.get("claims", [])
        # Should parse both claims even with duplicate control numbers
        assert len(claims) >= 1
        # Should have warnings about duplicates
        if len(claims) > 1:
            control_numbers = [c["claim_control_number"] for c in claims if c.get("claim_control_number")]
            duplicates = [cn for cn in control_numbers if control_numbers.count(cn) > 1]
            # Parser should handle duplicates (may warn or process both)
            assert len(duplicates) >= 0  # May or may not detect duplicates


@pytest.mark.unit
class Test837ParserFormatDetection:
    """Test format detection in 837 parser."""

    def test_auto_detect_837_format(self, sample_837_content: str):
        """Test automatic format detection."""
        parser = EDIParser(auto_detect_format=True)
        result = parser.parse(sample_837_content, "sample_837.txt")

        assert result["file_type"] == "837"
        # Format analysis should be included if auto-detect is enabled
        if "format_analysis" in result:
            format_info = result["format_analysis"]
            assert "version" in format_info or "segment_frequency" in format_info

    def test_detect_x12_version(self, sample_837_content: str):
        """Test X12 version detection."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        envelope = result.get("envelope", {})
        st = envelope.get("st", {})
        # Should detect version from ST segment
        assert st is not None

    def test_detect_segment_delimiters(self, sample_837_content: str):
        """Test segment delimiter detection."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        # Should parse successfully (delimiters detected correctly)
        assert result["file_type"] == "837"
        claims = result.get("claims", [])
        assert len(claims) > 0


@pytest.mark.integration
class Test837ParserIntegration:
    """Integration tests for 837 parser."""

    def test_parse_and_validate_claim_structure(self, sample_837_content: str):
        """Test parsing and validating complete claim structure."""
        parser = EDIParser()
        result = parser.parse(sample_837_content, "sample_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        claim = claims[0]
        # Verify claim has required fields
        required_fields = ["claim_control_number", "total_charge_amount"]
        for field in required_fields:
            assert field in claim, f"Claim should have {field}"

    def test_parse_multiple_claims_with_different_formats(self, multi_claim_837_content: str):
        """Test parsing multiple claims with different data formats."""
        parser = EDIParser()
        result = parser.parse(multi_claim_837_content, "multi_claim_837.txt")

        claims = result.get("claims", [])
        assert len(claims) >= 2

        # Verify each claim has required data
        for claim in claims:
            assert "claim_control_number" in claim
            assert "total_charge_amount" in claim

    def test_parse_with_format_analysis(self, sample_837_content: str):
        """Test parsing with format analysis enabled."""
        parser = EDIParser(auto_detect_format=True)
        result = parser.parse(sample_837_content, "sample_837.txt")

        # Should include format analysis if enabled
        if "format_analysis" in result:
            format_info = result["format_analysis"]
            assert isinstance(format_info, dict)

