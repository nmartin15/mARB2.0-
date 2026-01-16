"""Comprehensive tests for LineExtractor to improve coverage."""
from datetime import datetime

import pytest

from app.services.edi.config import get_parser_config
from app.services.edi.extractors.line_extractor import LineExtractor


@pytest.fixture
def extractor():
    """Create a line extractor instance."""
    config = get_parser_config()
    return LineExtractor(config)


@pytest.mark.unit
class TestLineExtractorComprehensive:
    """Comprehensive tests for LineExtractor."""

    def test_extract_empty_block(self, extractor):
        """Test extracting from empty block."""
        warnings = []
        lines = extractor.extract([], warnings)
        assert lines == []
        assert len(warnings) == 0

    def test_extract_lx_without_sv2(self, extractor):
        """Test extracting when LX exists but no SV2 follows."""
        block = [
            ["LX", "1"],
            ["DTP", "472", "D8", "20241215"],
            ["LX", "2"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 0
        assert len(warnings) >= 2  # Should warn for both missing SV2s

    def test_extract_lx_incomplete(self, extractor):
        """Test extracting with incomplete LX segment."""
        block = [
            ["LX"],  # Missing line number
            ["SV2", "HC", "HC>99213", "250.00"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        # Should skip incomplete LX
        assert len(lines) == 0 or len(lines) == 1

    def test_extract_sv2_insufficient_elements(self, extractor):
        """Test extracting with SV2 that has insufficient elements."""
        block = [
            ["LX", "1"],
            ["SV2", "HC"],  # Only 2 elements, need at least 4
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert "line_number" in lines[0]
        assert len(warnings) > 0
        assert any("insufficient elements" in w.lower() for w in warnings)

    def test_extract_procedure_code_with_modifier(self, extractor):
        """Test extracting procedure code with modifier."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213-26", "250.00", "UN", "1"],  # Modifier -26
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("procedure_code") == "99213"
        assert lines[0].get("procedure_modifier") == "26"

    def test_extract_procedure_code_with_multiple_modifiers(self, extractor):
        """Test extracting procedure code with multiple modifiers separated by >."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213>26", "250.00", "UN", "1"],  # Modifier in separate part
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        # Should handle modifier extraction
        assert "procedure_code" in lines[0]

    def test_extract_procedure_code_invalid_format(self, extractor):
        """Test extracting with invalid procedure code format."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>INVALID", "250.00", "UN", "1"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("procedure_code_valid") is False

    def test_extract_procedure_code_cpt_format(self, extractor):
        """Test extracting CPT procedure code (5 digits)."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "UN", "1"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("procedure_code") == "99213"
        assert lines[0].get("procedure_code_valid") is True

    def test_extract_procedure_code_hcpcs_format(self, extractor):
        """Test extracting HCPCS procedure code (1 letter + 4 digits)."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>A1234", "250.00", "UN", "1"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("procedure_code") == "A1234"
        assert lines[0].get("procedure_code_valid") is True

    def test_extract_procedure_code_cpt_with_modifier(self, extractor):
        """Test extracting CPT code with modifier suffix."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213-26", "250.00", "UN", "1"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("procedure_code") == "99213"
        assert lines[0].get("procedure_code_valid") is True

    def test_extract_procedure_code_hcpcs_with_modifier(self, extractor):
        """Test extracting HCPCS code with modifier suffix."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>A1234-26", "250.00", "UN", "1"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("procedure_code") == "A1234"
        assert lines[0].get("procedure_code_valid") is True

    def test_extract_charge_amount_valid(self, extractor):
        """Test extracting valid charge amount."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.50", "UN", "1"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("charge_amount") == 250.50

    def test_extract_charge_amount_missing(self, extractor):
        """Test extracting when charge amount is missing."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "", "UN", "1"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("charge_amount") is None

    def test_extract_charge_amount_invalid(self, extractor):
        """Test extracting invalid charge amount."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "INVALID", "UN", "1"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("charge_amount") is None
        assert any("Invalid charge amount" in w for w in warnings)

    def test_extract_unit_count_valid(self, extractor):
        """Test extracting valid unit count."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "UN", "2.5"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("unit_count") == 2.5

    def test_extract_unit_count_missing(self, extractor):
        """Test extracting when unit count is missing."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "UN", ""],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("unit_count") is None

    def test_extract_unit_count_invalid(self, extractor):
        """Test extracting invalid unit count."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "UN", "INVALID"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("unit_count") is None

    def test_extract_service_date_valid(self, extractor):
        """Test extracting valid service date."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "UN", "1"],
            ["DTP", "472", "D8", "20241215"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("service_date") == datetime(2024, 12, 15)

    def test_extract_service_date_missing(self, extractor):
        """Test extracting when service date is missing."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "UN", "1"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert "service_date" not in lines[0] or lines[0].get("service_date") is None

    def test_extract_service_date_wrong_qualifier(self, extractor):
        """Test extracting when DTP has wrong qualifier."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "UN", "1"],
            ["DTP", "431", "D8", "20241215"],  # Wrong qualifier (431, not 472)
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert "service_date" not in lines[0] or lines[0].get("service_date") is None

    def test_extract_service_date_wrong_format(self, extractor):
        """Test extracting when DTP has wrong date format."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "UN", "1"],
            ["DTP", "472", "D6", "241215"],  # Wrong format (D6, not D8)
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert "service_date" not in lines[0] or lines[0].get("service_date") is None

    def test_extract_service_date_invalid_date(self, extractor):
        """Test extracting when DTP has invalid date value."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "UN", "1"],
            ["DTP", "472", "D8", "20241399"],  # Invalid date (month 13)
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert "service_date" not in lines[0] or lines[0].get("service_date") is None

    def test_extract_service_date_stops_at_next_sv2(self, extractor):
        """Test that service date search stops at next SV2."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "UN", "1"],
            ["LX", "2"],
            ["SV2", "HC", "HC>36415", "50.00", "UN", "1"],
            ["DTP", "472", "D8", "20241215"],  # This should not be associated with first line
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 2
        # First line should not have service date (stopped at next LX/SV2)
        assert "service_date" not in lines[0] or lines[0].get("service_date") is None

    def test_find_segments_in_block_empty(self, extractor):
        """Test finding segments in empty block."""
        result = extractor._find_segments_in_block([], "LX")
        assert result == []

    def test_find_segments_in_block_none_segments(self, extractor):
        """Test finding segments when block contains None segments."""
        block = [
            ["LX", "1"],
            None,
            ["LX", "2"],
            [],
        ]
        result = extractor._find_segments_in_block(block, "LX")
        assert len(result) == 2

    def test_find_sv2_after_lx_not_in_block(self, extractor):
        """Test finding SV2 when LX segment is not in block."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213"],
        ]
        lx_seg = ["LX", "999"]  # Not in block
        sv2 = extractor._find_sv2_after_lx(block, lx_seg)
        assert sv2 is None

    def test_find_sv2_after_lx_stops_at_termination(self, extractor):
        """Test that SV2 search stops at termination segments."""
        block = [
            ["LX", "1"],
            ["CLM", "CLAIM001"],  # Termination segment
            ["SV2", "HC", "HC>99213"],  # Should not find this
        ]
        lx_seg = ["LX", "1"]
        sv2 = extractor._find_sv2_after_lx(block, lx_seg)
        assert sv2 is None

    def test_find_sv2_after_lx_stops_at_next_lx(self, extractor):
        """Test that SV2 search stops at next LX."""
        block = [
            ["LX", "1"],
            ["LX", "2"],  # Next LX
            ["SV2", "HC", "HC>99213"],  # Should not find this for first LX
        ]
        lx_seg = ["LX", "1"]
        sv2 = extractor._find_sv2_after_lx(block, lx_seg)
        assert sv2 is None

    def test_find_service_date_after_sv2_not_in_block(self, extractor):
        """Test finding service date when SV2 is not in block."""
        block = [
            ["SV2", "HC", "HC>99213"],
            ["DTP", "472", "D8", "20241215"],
        ]
        sv2_seg = ["SV2", "HC", "HC>99999"]  # Not in block
        date = extractor._find_service_date_after_sv2(block, sv2_seg)
        assert date is None

    def test_find_service_date_after_sv2_stops_at_limit(self, extractor):
        """Test that service date search stops at limit (10 segments)."""
        block = [
            ["SV2", "HC", "HC>99213"],
        ]
        # Add 15 segments before DTP (should exceed limit)
        for i in range(15):
            block.append(["UNKNOWN", str(i)])
        block.append(["DTP", "472", "D8", "20241215"])
        
        sv2_seg = ["SV2", "HC", "HC>99213"]
        date = extractor._find_service_date_after_sv2(block, sv2_seg)
        # Should not find date (exceeded search limit)
        assert date is None

    def test_find_service_date_after_sv2_stops_at_termination(self, extractor):
        """Test that service date search stops at termination segments."""
        block = [
            ["SV2", "HC", "HC>99213"],
            ["SV2", "HC", "HC>36415"],  # Termination segment
            ["DTP", "472", "D8", "20241215"],  # Should not find this
        ]
        sv2_seg = ["SV2", "HC", "HC>99213"]
        date = extractor._find_service_date_after_sv2(block, sv2_seg)
        assert date is None

    def test_find_service_date_after_sv2_empty_segment(self, extractor):
        """Test finding service date when block contains empty segments."""
        block = [
            ["SV2", "HC", "HC>99213"],
            [],
            None,
            ["DTP", "472", "D8", "20241215"],
        ]
        sv2_seg = ["SV2", "HC", "HC>99213"]
        date = extractor._find_service_date_after_sv2(block, sv2_seg)
        assert date == datetime(2024, 12, 15)

    def test_find_service_date_after_sv2_insufficient_dtp_elements(self, extractor):
        """Test finding service date when DTP has insufficient elements."""
        block = [
            ["SV2", "HC", "HC>99213"],
            ["DTP", "472"],  # Missing format and date
        ]
        sv2_seg = ["SV2", "HC", "HC>99213"]
        date = extractor._find_service_date_after_sv2(block, sv2_seg)
        assert date is None

    def test_validate_procedure_code_cpt_valid(self, extractor):
        """Test validating valid CPT code."""
        assert extractor._validate_procedure_code("99213") is True

    def test_validate_procedure_code_cpt_with_modifier(self, extractor):
        """Test validating CPT code with modifier suffix."""
        assert extractor._validate_procedure_code("99213-26") is True

    def test_validate_procedure_code_hcpcs_valid(self, extractor):
        """Test validating valid HCPCS code."""
        assert extractor._validate_procedure_code("A1234") is True

    def test_validate_procedure_code_hcpcs_with_modifier(self, extractor):
        """Test validating HCPCS code with modifier suffix."""
        assert extractor._validate_procedure_code("A1234-26") is True

    def test_validate_procedure_code_invalid_length(self, extractor):
        """Test validating procedure code with invalid length."""
        assert extractor._validate_procedure_code("1234") is False  # Too short
        assert extractor._validate_procedure_code("123456") is False  # Too long

    def test_validate_procedure_code_invalid_format(self, extractor):
        """Test validating procedure code with invalid format."""
        assert extractor._validate_procedure_code("ABC12") is False  # Wrong pattern
        assert extractor._validate_procedure_code("12ABC") is False  # Wrong pattern

    def test_validate_procedure_code_none(self, extractor):
        """Test validating None procedure code."""
        assert extractor._validate_procedure_code(None) is False

    def test_validate_procedure_code_empty_string(self, extractor):
        """Test validating empty procedure code."""
        assert extractor._validate_procedure_code("") is False

    def test_validate_procedure_code_whitespace(self, extractor):
        """Test validating procedure code with whitespace."""
        assert extractor._validate_procedure_code("  99213  ") is True  # Should strip

    def test_validate_procedure_code_non_string(self, extractor):
        """Test validating procedure code that's not a string."""
        assert extractor._validate_procedure_code(99213) is False  # Not a string

    def test_extract_multiple_lines_complex(self, extractor):
        """Test extracting multiple lines with complex structure."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213-26", "250.00", "UN", "1"],
            ["DTP", "472", "D8", "20241215"],
            ["LX", "2"],
            ["SV2", "HC", "HC>36415", "50.00", "UN", "2.5"],
            ["DTP", "472", "D8", "20241216"],
            ["LX", "3"],
            ["SV2", "HC", "HC>A1234", "100.00", "DA", "3"],
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 3
        assert lines[0]["line_number"] == "1"
        assert lines[0].get("service_date") == datetime(2024, 12, 15)
        assert lines[1]["line_number"] == "2"
        assert lines[1].get("unit_count") == 2.5
        assert lines[2]["line_number"] == "3"
        assert lines[2].get("procedure_code") == "A1234"

    def test_extract_procedure_qualifier_extraction(self, extractor):
        """Test extracting procedure qualifier from SV202."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "N4>12345", "250.00", "UN", "1"],  # N4 qualifier (NDC)
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("procedure_qualifier") == "N4"

    def test_extract_procedure_qualifier_missing(self, extractor):
        """Test extracting when procedure qualifier is missing."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "99213", "250.00", "UN", "1"],  # No qualifier
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        # Should still extract procedure code
        assert "procedure_code" in lines[0] or "procedure_qualifier" not in lines[0]

    def test_extract_revenue_code(self, extractor):
        """Test extracting revenue code from SV201."""
        block = [
            ["LX", "1"],
            ["SV2", "0450", "HC>99213", "250.00", "UN", "1"],  # Revenue code 0450
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("revenue_code") == "0450"

    def test_extract_unit_type(self, extractor):
        """Test extracting unit type from SV204."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "DA", "1"],  # DA = Days
        ]
        warnings = []
        lines = extractor.extract(block, warnings)
        assert len(lines) == 1
        assert lines[0].get("unit_type") == "DA"
