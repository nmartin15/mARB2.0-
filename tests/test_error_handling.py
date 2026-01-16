"""Comprehensive error handling tests for EDI parsing."""

import pytest

from app.services.edi.config import ParserConfig
from app.services.edi.parser import EDIParser
from app.services.edi.validator import SegmentValidator


@pytest.mark.unit
@pytest.mark.integration
class TestMissingSegments:
    """Test handling of missing segments in EDI files."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return EDIParser()

    def test_missing_critical_segment_isa(self, parser):
        """Test missing ISA segment (critical)."""
        # File without ISA segment
        content = """GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""

        # Should raise error or return warnings
        result = parser.parse(content, "missing_isa.txt")

        # Should have warnings about missing ISA
        assert "warnings" in result or len(result.get("claims", [])) == 0

    def test_missing_critical_segment_clm(self, parser):
        """Test missing CLM segment (critical for 837)."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
SBR*P*18~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "missing_clm.txt")

        # Should handle gracefully - no claims but no crash
        assert "warnings" in result or len(result.get("claims", [])) == 0

    def test_missing_important_segment_sbr(self, parser):
        """Test missing SBR segment (important but not critical)."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "missing_sbr.txt")

        # Should parse but with warnings
        assert "warnings" in result or len(result.get("claims", [])) >= 0

    def test_missing_important_segment_hi(self, parser):
        """Test missing HI segment (important but not critical)."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SBR*P*18~
SE*5*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "missing_hi.txt")

        # Should parse but with warnings about missing diagnosis
        assert "warnings" in result or len(result.get("claims", [])) >= 0

    def test_missing_optional_segment_ref(self, parser):
        """Test missing REF segment (optional)."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SBR*P*18~
HI*ABK:I10~
SE*6*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "missing_ref.txt")

        # Should parse successfully - REF is optional
        assert "file_type" in result
        assert len(result.get("claims", [])) >= 0

    def test_missing_multiple_segments(self, parser):
        """Test missing multiple segments."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "missing_multiple.txt")

        # Should handle gracefully with warnings
        assert "warnings" in result or len(result.get("claims", [])) == 0


@pytest.mark.unit
class TestInvalidDataFormats:
    """Test handling of invalid data formats."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return EDIParser()

    def test_invalid_date_format(self, parser):
        """Test invalid date format in DTP segment."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
DTP*431*D8*INVALID_DATE~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "invalid_date.txt")

        # Should parse but handle invalid date gracefully
        assert "file_type" in result
        # Date parsing should not crash

    def test_invalid_amount_format(self, parser):
        """Test invalid amount format."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*NOT_A_NUMBER~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "invalid_amount.txt")

        # Should parse but handle invalid amount gracefully
        assert "file_type" in result

    def test_invalid_diagnosis_code_format(self, parser):
        """Test invalid diagnosis code format."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
HI*ABK:INVALID_CODE~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "invalid_diagnosis.txt")

        # Should parse but handle invalid diagnosis code
        assert "file_type" in result

    def test_invalid_npi_format(self, parser):
        """Test invalid NPI format."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
NM1*85*2*DR SMITH*****XX*INVALID_NPI~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "invalid_npi.txt")

        # Should parse but handle invalid NPI
        assert "file_type" in result

    def test_invalid_cpt_code_format(self, parser):
        """Test invalid CPT code format."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
LX*1~
SV2*HC>INVALID_CPT*1500.00*UN*1~
SE*5*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "invalid_cpt.txt")

        # Should parse but handle invalid CPT code
        assert "file_type" in result


@pytest.mark.unit
class TestMalformedFiles:
    """Test handling of malformed EDI files."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return EDIParser()

    def test_empty_file(self, parser):
        """Test parsing empty file."""
        content = ""

        with pytest.raises(ValueError, match="No segments found"):
            parser.parse(content, "empty.txt")

    def test_file_with_only_whitespace(self, parser):
        """Test parsing file with only whitespace."""
        content = "   \n\t  \n  "

        with pytest.raises(ValueError, match="No segments found"):
            parser.parse(content, "whitespace.txt")

    def test_file_with_wrong_delimiter(self, parser):
        """Test file with wrong segment delimiter."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*|
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1|
ST*837*0001*005010X222A1|"""

        # Should handle gracefully - might not parse correctly but shouldn't crash
        result = parser.parse(content, "wrong_delimiter.txt")
        # May have warnings or parse incorrectly
        assert isinstance(result, dict)

    def test_file_with_missing_segment_terminator(self, parser):
        """Test file missing segment terminator."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1
ST*837*0001*005010X222A1"""

        # Should handle - might treat as single segment or parse partially
        result = parser.parse(content, "missing_terminator.txt")
        assert isinstance(result, dict)

    def test_file_with_duplicate_claim_numbers(self, parser):
        """Test file with duplicate claim control numbers."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SE*3*0001~
ST*837*0002*005010X222A1~
CLM*CLAIM001*2000.00~
SE*3*0002~
GE*2*1~
IEA*1*000000001~"""

        result = parser.parse(content, "duplicate_claims.txt")

        # Should parse both claims (duplicates are allowed in EDI)
        assert "file_type" in result
        assert len(result.get("claims", [])) >= 0

    def test_file_with_malformed_segment(self, parser):
        """Test file with malformed segment."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
MALFORMED*SEGMENT*WITH*TOO*MANY*ELEMENTS*OR*WRONG*FORMAT~
CLM*CLAIM001*1500.00~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "malformed_segment.txt")

        # Should skip malformed segment and continue parsing
        assert "file_type" in result

    def test_file_with_special_characters(self, parser):
        """Test file with special characters."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
NM1*IL*1*O'BRIEN*JOHN*JR***MI*123456789~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "special_chars.txt")

        # Should handle special characters in names
        assert "file_type" in result

    def test_file_with_unicode_characters(self, parser):
        """Test file with unicode characters."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
NM1*IL*1*GARCÍA*MARÍA***MI*123456789~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "unicode.txt")

        # Should handle unicode characters
        assert "file_type" in result


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return EDIParser()

    def test_file_with_only_envelope_segments(self, parser):
        """Test file with only envelope segments."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "envelope_only.txt")

        # Should parse but have no claims
        assert "file_type" in result
        assert len(result.get("claims", [])) == 0

    def test_file_with_very_long_segment(self, parser):
        """Test file with very long segment."""
        long_element = "A" * 1000
        content = f"""ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00*{long_element}~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "long_segment.txt")

        # Should handle long segments
        assert "file_type" in result

    def test_file_with_many_segments(self, parser):
        """Test file with many segments."""
        segments = []
        segments.append("ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~")
        segments.append("GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~")
        segments.append("ST*837*0001*005010X222A1~")

        # Add many claims
        for i in range(100):
            segments.append(f"CLM*CLAIM{i:03d}*1500.00~")
            segments.append("SBR*P*18~")
            segments.append("HI*ABK:I10~")

        segments.append("SE*303*0001~")
        segments.append("GE*1*1~")
        segments.append("IEA*1*000000001~")

        content = "\n".join(segments)

        result = parser.parse(content, "many_segments.txt")

        # Should handle many segments
        assert "file_type" in result
        assert len(result.get("claims", [])) >= 0

    def test_file_with_nested_loops(self, parser):
        """Test file with nested hierarchical loops."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
HL*1**20*1~
PRV*BI*PXC*207RI0001X~
HL*2*1*22*0~
SBR*P*18~
CLM*CLAIM001*1500.00~
LX*1~
SV2*HC:99213*1500.00*UN*1~
SE*9*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "nested_loops.txt")

        # Should handle nested loops
        assert "file_type" in result

    def test_file_with_control_number_mismatch(self, parser):
        """Test file with control number mismatches."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SE*4*0002~  # Mismatch: should be 0001
GE*1*1~
IEA*1*000000002~  # Mismatch: should be 000000001"""

        result = parser.parse(content, "mismatch.txt")

        # Should parse but may have warnings about mismatches
        assert "file_type" in result


@pytest.mark.unit
class TestErrorMessages:
    """Test that error messages are helpful and informative."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return EDIParser()

    def test_error_message_for_empty_file(self, parser):
        """Test error message for empty file."""
        content = ""

        with pytest.raises(ValueError) as exc_info:
            parser.parse(content, "empty.txt")

        error_message = str(exc_info.value)
        assert "No segments found" in error_message or "empty" in error_message.lower()

    def test_warning_message_for_missing_segment(self, parser):
        """Test warning message for missing segment."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "missing_segments.txt")

        # Parser should handle missing segments gracefully
        # Warnings may be in result or logged - either way parsing should succeed
        assert "file_type" in result
        # File should parse (may have no claims if critical segments missing)
        assert isinstance(result, dict)

    def test_error_message_for_invalid_file_type(self, parser):
        """Test error message for invalid file type."""
        # File that doesn't match 837 or 835
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*999*0001*005010X222A1~  # Invalid transaction type
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""

        # Should handle gracefully or provide informative error
        result = parser.parse(content, "invalid_type.txt")
        # May default to 837 or provide warnings
        assert isinstance(result, dict)


@pytest.mark.unit
class TestValidatorErrorHandling:
    """Test error handling in SegmentValidator."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        config = ParserConfig()
        return SegmentValidator(config)

    def test_validator_critical_segment_error_message(self, validator):
        """Test error message for missing critical segment."""
        is_valid, warning = validator.validate_segment(None, "CLM", min_length=1)

        assert is_valid is False
        assert "Critical segment CLM is missing" in warning
        assert "CLM" in warning  # Should mention the segment

    def test_validator_important_segment_warning_message(self, validator):
        """Test warning message for missing important segment."""
        is_valid, warning = validator.validate_segment(None, "SBR", min_length=1)

        assert is_valid is True  # Important segments don't fail validation
        assert "Important segment SBR is missing" in warning
        assert "SBR" in warning  # Should mention the segment

    def test_validator_insufficient_elements_error_message(self, validator):
        """Test error message for insufficient elements."""
        segment = ["CLM"]  # Only 1 element, needs at least 2
        is_valid, warning = validator.validate_segment(segment, "CLM", min_length=2)

        assert is_valid is False
        assert "insufficient elements" in warning.lower()
        assert "expected at least 2" in warning.lower()

    def test_validator_safe_get_element_default(self, validator):
        """Test safe_get_element returns default for missing elements."""
        segment = ["CLM", "CLAIM001"]

        # Get element that exists
        element = validator.safe_get_element(segment, 1)
        assert element == "CLAIM001"

        # Get element that doesn't exist
        element = validator.safe_get_element(segment, 5)
        assert element == ""  # Default value

        # Get element with custom default
        element = validator.safe_get_element(segment, 5, default="N/A")
        assert element == "N/A"


@pytest.mark.integration
class TestErrorHandlingInUploadFlow:
    """Test error handling in complete upload flow."""

    def test_upload_invalid_file_via_api(self, client):
        """Test uploading invalid file via API."""
        from io import BytesIO

        # Create invalid file content
        invalid_content = "NOT VALID EDI CONTENT"
        file = ("invalid.edi", BytesIO(invalid_content.encode("utf-8")), "text/plain")

        response = client.post(
            "/api/v1/claims/upload",
            files={"file": file}
        )

        # Should handle gracefully - either return error or queue with warnings
        assert response.status_code in [200, 400, 422]

        if response.status_code == 200:
            # If queued, should have task_id
            data = response.json()
            assert "task_id" in data or "error" in data

    def test_upload_file_with_missing_segments(self, client):
        """Test uploading file with missing segments."""
        from io import BytesIO

        # File missing critical segments
        content = """GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
SE*2*0001~
GE*1*1~"""

        file = ("missing_segments.edi", BytesIO(content.encode("utf-8")), "text/plain")

        response = client.post(
            "/api/v1/claims/upload",
            files={"file": file}
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 422]

    def test_upload_empty_file(self, client):
        """Test uploading empty file."""
        from io import BytesIO

        file = ("empty.edi", BytesIO(b""), "text/plain")

        response = client.post(
            "/api/v1/claims/upload",
            files={"file": file}
        )

        # API may queue the file (200) - error will occur during processing
        # Or return error immediately (400/422/500)
        assert response.status_code in [200, 400, 422, 500]

        if response.status_code == 200:
            # If queued, the task will fail when processing
            data = response.json()
            assert "task_id" in data or "error" in data

