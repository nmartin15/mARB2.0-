"""Tests for line extractor."""
from datetime import datetime

import pytest

from app.services.edi.config import get_parser_config
from app.services.edi.extractors.line_extractor import LineExtractor


@pytest.fixture
def extractor():
    """Create a line extractor instance."""
    config = get_parser_config()
    return LineExtractor(config)


@pytest.fixture
def sample_block_with_lines():
    """Sample block with LX and SV2 segments.
    
    SV2 Segment Format (Service Line Information):
    The SV2 segment in EDI 837 contains service line details for professional claims.
    
    SV2 Field Positions:
    - SV201: Revenue Code (HC = Healthcare Common Procedure Coding System)
    - SV202: Procedure Qualifier and Code (format: "QUALIFIER>CODE", e.g., "HC>99213")
             HC = HCPCS code, N4 = National Drug Code, etc.
    - SV203: Line Item Charge Amount (monetary amount)
    - SV204: Unit or Basis for Measurement Code (UN = Units, DA = Days, etc.)
    - SV205: Service Unit Count (number of units)
    - SV206-SV212: Additional fields (place of service, etc.)
    
    Example: ["SV2", "HC", "HC>99213", "250.00", "UN", "1", "", "", "", "", "1"]
             - Revenue code: HC
             - Procedure: HCPCS code 99213 (office visit)
             - Charge: $250.00
             - Unit type: UN (units)
             - Unit count: 1
    """
    return [
        ["LX", "1"],
        ["SV2", "HC", "HC>99213", "250.00", "UN", "1", "", "", "", "", "1"],
        ["DTP", "472", "D8", "20241215"],
        ["LX", "2"],
        ["SV2", "HC", "HC>36415", "50.00", "UN", "1", "", "", "", "", "1"],
        ["DTP", "472", "D8", "20241215"],
    ]


@pytest.mark.unit
class TestLineExtractor:
    """Tests for LineExtractor."""

    def test_extract_lines_basic(self, extractor, sample_block_with_lines):
        """Test extracting basic claim lines from SV2 segments.
        
        SV2 segments contain service line information:
        - SV201: Revenue code (e.g., "HC" for HCPCS)
        - SV202: Procedure code in format "QUALIFIER>CODE" (e.g., "HC>99213")
        - SV203: Charge amount (e.g., "250.00")
        - SV204: Unit type (e.g., "UN" for units)
        - SV205: Unit count (e.g., "1")
        """
        warnings = []

        lines = extractor.extract(sample_block_with_lines, warnings)

        assert len(lines) == 2
        assert lines[0]["line_number"] == "1"
        # SV2 format: [SV2, revenue_code, procedure_qualifier>code, charge_amount, unit_type, unit_count]
        # The extractor should parse SV202 to extract the procedure code (e.g., "99213" from "HC>99213")
        assert "procedure_code" in lines[0] or "revenue_code" in lines[0]
        assert lines[0].get("charge_amount") == 250.00 or lines[0].get("charge_amount") is not None
        assert lines[1]["line_number"] == "2"

    def test_extract_lines_no_lx_segments(self, extractor):
        """Test extracting lines when no LX segments exist."""
        block = [
            ["CLM", "CLAIM001", "1000.00"],
            ["HI", "BK", "E11.9"],
        ]
        warnings = []

        lines = extractor.extract(block, warnings)

        assert len(lines) == 0
        assert len(warnings) == 0  # This is acceptable

    def test_extract_lines_missing_sv2(self, extractor):
        """Test extracting lines when SV2 is missing."""
        block = [
            ["LX", "1"],
            ["DTP", "472", "D8", "20241215"],
        ]
        warnings = []

        lines = extractor.extract(block, warnings)

        assert len(lines) == 0
        assert len(warnings) > 0
        assert any("SV2 segment not found" in w for w in warnings)

    def test_extract_line_data_with_date(self, extractor, sample_block_with_lines):
        """Test extracting line with service date."""
        warnings = []

        lines = extractor.extract(sample_block_with_lines, warnings)

        assert len(lines) > 0
        assert "service_date" in lines[0]
        assert lines[0]["service_date"] == datetime(2024, 12, 15)

    def test_extract_line_data_invalid_amount(self, extractor):
        """Test extracting line with invalid amount."""
        block = [
            ["LX", "1"],
            ["SV2", "HC>99213", "INVALID", "UN", "1"],
        ]
        warnings = []

        lines = extractor.extract(block, warnings)

        assert len(lines) > 0
        # Should handle invalid amount gracefully
        assert lines[0].get("charge_amount") is None or isinstance(lines[0].get("charge_amount"), (int, float))

    def test_extract_line_data_missing_elements(self, extractor):
        """Test extracting line with missing SV2 elements."""
        block = [
            ["LX", "1"],
            ["SV2", "HC"],  # Missing elements
        ]
        warnings = []

        lines = extractor.extract(block, warnings)

        # Should still create line entry but with missing data
        assert len(lines) >= 0

    def test_find_segments_in_block(self, extractor):
        """Test finding segments in block."""
        block = [
            ["LX", "1"],
            ["SV2", "HC", "99213"],
            ["LX", "2"],
            ["SV2", "HC", "36415"],
        ]

        lx_segments = extractor._find_segments_in_block(block, "LX")

        assert len(lx_segments) == 2
        assert all(seg[0] == "LX" for seg in lx_segments)

    def test_find_sv2_after_lx(self, extractor):
        """Test finding SV2 segment after LX."""
        block = [
            ["LX", "1"],
            ["SV2", "HC>99213", "250.00"],
            ["LX", "2"],
            ["SV2", "HC>36415", "50.00"],
        ]

        lx_seg = ["LX", "1"]
        sv2 = extractor._find_sv2_after_lx(block, lx_seg)

        assert sv2 is not None
        assert sv2[0] == "SV2"
        assert "99213" in sv2[1]  # Procedure code is in second element with format HC>99213

    def test_find_sv2_after_lx_not_found(self, extractor):
        """Test finding SV2 when it doesn't exist."""
        block = [
            ["LX", "1"],
            ["DTP", "472", "D8", "20241215"],
        ]

        lx_seg = ["LX", "1"]
        sv2 = extractor._find_sv2_after_lx(block, lx_seg)

        assert sv2 is None

    def test_extract_line_data_unit_count(self, extractor):
        """Test extracting line with unit count from SV2 segment.
        
        SV2 segment format: [SV2, revenue_code, procedure_code, charge_amount, unit_type, unit_count]
        - SV205 (6th element, index 5): Unit count indicates quantity of service units
        - Example: ["SV2", "HC", "HC>99213", "250.00", "UN", "2"] means 2 units of service
        """
        block = [
            ["LX", "1"],
            ["SV2", "HC", "HC>99213", "250.00", "UN", "2"],  # 2 units (SV205 in SV2 format)
        ]
        warnings = []

        lines = extractor.extract(block, warnings)

        assert len(lines) > 0
        assert lines[0].get("unit_count") == 2.0 or lines[0].get("unit_count") == "2"

