"""Tests for claim extractor."""
from datetime import datetime

import pytest

from app.services.edi.config import get_parser_config
from app.services.edi.extractors.claim_extractor import ClaimExtractor


@pytest.fixture
def extractor():
    """Create a claim extractor instance."""
    config = get_parser_config()
    return ClaimExtractor(config)


@pytest.fixture
def sample_clm_segment():
    """Sample CLM segment."""
    return [
        "CLM",
        "CLAIM001",
        "1500.00",
        "",
        "",
        "11:A:1",
        "",
        "Y",
        "",
        "",
        "",
        "Y",
        "A",
        "Y",
        "I",
    ]


@pytest.fixture
def sample_block_with_dates(sample_clm_segment):
    """Sample block with CLM and DTP segments."""
    return [
        sample_clm_segment,
        ["DTP", "434", "D8", "20241215"],  # Statement date (434, not 431)
        ["DTP", "472", "D8", "20241215"],  # Service date
        ["DTP", "435", "D8", "20241210"],  # Admission date
        ["DTP", "096", "D8", "20241220"],  # Discharge date
    ]


@pytest.mark.unit
class TestClaimExtractor:
    """Tests for ClaimExtractor."""

    def test_extract_basic_claim(self, extractor, sample_clm_segment):
        """Test extracting basic claim data."""
        warnings = []
        block = [sample_clm_segment]

        result = extractor.extract(sample_clm_segment, block, warnings)

        assert result["claim_control_number"] == "CLAIM001"
        assert result["patient_control_number"] == "CLAIM001"
        assert result["total_charge_amount"] == 1500.00
        assert len(warnings) == 0

    def test_extract_claim_with_facility_code(self, extractor):
        """Test extracting claim with facility type code."""
        clm_segment = ["CLM", "CLAIM002", "2000.00", "", "", "11:A:1", "", "Y"]
        warnings = []
        block = [clm_segment]

        result = extractor.extract(clm_segment, block, warnings)

        assert result["facility_type_code"] == "11"
        assert result["claim_frequency_type"] == "1"

    def test_extract_claim_with_colon_delimiter(self, extractor):
        """Test extracting claim with colon delimiter in location info."""
        clm_segment = ["CLM", "CLAIM003", "1000.00", "", "", "11:B:2", "", "Y"]
        warnings = []
        block = [clm_segment]

        result = extractor.extract(clm_segment, block, warnings)

        assert result["facility_type_code"] == "11"
        assert result["claim_frequency_type"] == "2"

    def test_extract_claim_with_dates(self, extractor, sample_block_with_dates):
        """Test extracting claim with date segments."""
        warnings = []
        clm_segment = sample_block_with_dates[0]

        result = extractor.extract(clm_segment, sample_block_with_dates, warnings)

        assert "statement_date" in result
        assert result["statement_date"] == datetime(2024, 12, 15)
        assert "service_date" in result
        assert result["service_date"] == datetime(2024, 12, 15)
        assert "admission_date" in result
        assert result["admission_date"] == datetime(2024, 12, 10)
        assert "discharge_date" in result
        assert result["discharge_date"] == datetime(2024, 12, 20)

    def test_extract_claim_invalid_amount(self, extractor):
        """Test extracting claim with invalid amount."""
        clm_segment = ["CLM", "CLAIM004", "INVALID", "", "", "11:A:1", "", "Y"]
        warnings = []
        block = [clm_segment]

        result = extractor.extract(clm_segment, block, warnings)

        assert result["total_charge_amount"] is None
        assert len(warnings) > 0
        assert any("Invalid charge amount" in w for w in warnings)

    def test_extract_claim_missing_amount(self, extractor):
        """Test extracting claim with missing amount."""
        clm_segment = ["CLM", "CLAIM005", "", "", "", "11:A:1", "", "Y"]
        warnings = []
        block = [clm_segment]

        result = extractor.extract(clm_segment, block, warnings)

        assert result["total_charge_amount"] is None

    def test_extract_claim_insufficient_elements(self, extractor):
        """Test extracting claim with insufficient CLM elements."""
        clm_segment = ["CLM"]
        warnings = []
        block = [clm_segment]

        result = extractor.extract(clm_segment, block, warnings)

        assert len(warnings) > 0
        assert any("insufficient elements" in w for w in warnings)

    def test_extract_claim_assignment_code(self, extractor, sample_clm_segment):
        """Test extracting assignment code."""
        warnings = []
        block = [sample_clm_segment]

        result = extractor.extract(sample_clm_segment, block, warnings)

        assert result["assignment_code"] == "Y"

    def test_extract_dates_invalid_format(self, extractor):
        """Test extracting dates with invalid format."""
        clm_segment = ["CLM", "CLAIM006", "1000.00"]
        block = [
            clm_segment,
            ["DTP", "431", "D6", "241215"],  # Invalid format (should be D8)
            ["DTP", "472", "INVALID", "BAD"],  # Invalid format
        ]
        warnings = []

        result = extractor.extract(clm_segment, block, warnings)

        # Should not have dates with invalid formats
        assert "statement_date" not in result or result.get("statement_date") is None

    def test_extract_dates_missing_qualifier(self, extractor):
        """Test extracting dates with missing qualifier."""
        clm_segment = ["CLM", "CLAIM007", "1000.00"]
        block = [
            clm_segment,
            ["DTP", "999", "D8", "20241215"],  # Unknown qualifier
        ]
        warnings = []

        result = extractor.extract(clm_segment, block, warnings)

        # Unknown qualifier should not create date field
        assert "statement_date" not in result

    def test_find_segments_in_block(self, extractor):
        """Test finding segments in block."""
        block = [
            ["CLM", "CLAIM001"],
            ["DTP", "431", "D8", "20241215"],
            ["DTP", "472", "D8", "20241215"],
            ["HI", "BK", "E11.9"],
        ]

        dtp_segments = extractor._find_segments_in_block(block, "DTP")

        assert len(dtp_segments) == 2
        assert all(seg[0] == "DTP" for seg in dtp_segments)

    def test_extract_dates_empty_segments(self, extractor):
        """Test extracting dates with empty DTP segments."""
        warnings = []
        dtp_segments = []

        dates = extractor._extract_dates(dtp_segments, warnings)

        assert len(dates) == 0
        assert len(warnings) == 0

    def test_extract_dates_insufficient_elements(self, extractor):
        """Test extracting dates with insufficient DTP elements."""
        warnings = []
        dtp_segments = [
            ["DTP"],  # Missing elements
            ["DTP", "431"],  # Missing format and date
        ]

        dates = extractor._extract_dates(dtp_segments, warnings)

        assert len(dates) == 0

