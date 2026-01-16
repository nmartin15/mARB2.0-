"""Tests for payer extractor."""
import pytest

from app.services.edi.config import get_parser_config
from app.services.edi.extractors.payer_extractor import PayerExtractor


@pytest.fixture
def extractor():
    """Create a payer extractor instance."""
    config = get_parser_config()
    return PayerExtractor(config)


@pytest.fixture
def sample_block_with_payer():
    """Sample block with SBR and NM1 segments."""
    return [
        ["SBR", "P", "18", "GROUP123", "", "", "", "", "CI"],
        ["NM1", "PR", "2", "BLUE CROSS", "", "", "", "", "PI", "BLUE_CROSS"],
        ["NM1", "IL", "1", "DOE", "JOHN", "M", "", "", "MI", "123456789"],
    ]


@pytest.mark.unit
class TestPayerExtractor:
    """Tests for PayerExtractor."""

    def test_extract_primary_payer(self, extractor, sample_block_with_payer):
        """Test extracting primary payer information."""
        warnings = []

        result = extractor.extract(sample_block_with_payer, warnings)

        assert "payer_responsibility" in result
        assert result["payer_responsibility"] == "P"
        assert "payer_id" in result or "payer_name" in result
        assert len(warnings) == 0

    def test_extract_payer_missing_sbr(self, extractor):
        """Test extracting payer when SBR is missing."""
        block = [
            ["NM1", "PR", "2", "BLUE CROSS"],
        ]
        warnings = []

        result = extractor.extract(block, warnings)

        assert len(warnings) > 0
        assert any("Primary payer SBR segment not found" in w for w in warnings)

    def test_extract_payer_missing_nm1_pr(self, extractor):
        """Test extracting payer when NM1 PR is missing."""
        block = [
            ["SBR", "P", "18", "GROUP123"],
            ["NM1", "IL", "1", "DOE", "JOHN"],
        ]
        warnings = []

        result = extractor.extract(block, warnings)

        assert len(warnings) > 0
        assert any("NM1 PR segment not found" in w for w in warnings)

    def test_find_sbr_by_responsibility(self, extractor):
        """Test finding SBR by responsibility code."""
        block = [
            ["SBR", "S", "18", "GROUP123"],  # Secondary
            ["SBR", "P", "18", "GROUP456"],  # Primary
        ]

        primary = extractor._find_sbr_by_responsibility(block, "P")

        assert primary is not None
        assert primary[1] == "P"

    def test_find_sbr_not_found(self, extractor):
        """Test finding SBR when it doesn't exist."""
        block = [
            ["NM1", "PR", "2", "BLUE CROSS"],
        ]

        sbr = extractor._find_sbr_by_responsibility(block, "P")

        assert sbr is None

    def test_find_nm1_after_sbr(self, extractor):
        """Test finding NM1 segment after SBR."""
        block = [
            ["SBR", "P", "18", "GROUP123"],
            ["NM1", "PR", "2", "BLUE CROSS", "", "", "", "", "PI", "BLUE_CROSS"],
        ]

        sbr_seg = ["SBR", "P", "18", "GROUP123"]
        nm1 = extractor._find_nm1_after_sbr(block, sbr_seg, "PR")

        assert nm1 is not None
        assert nm1[2] == "2"  # Entity type code

    def test_extract_sbr_data(self, extractor):
        """Test extracting data from SBR segment."""
        sbr_segment = ["SBR", "P", "18", "GROUP123", "", "", "", "", "CI"]
        warnings = []

        result = extractor._extract_sbr_data(sbr_segment, warnings)

        assert result["payer_responsibility"] == "P"
        assert result.get("relationship_code") == "18"

    def test_extract_nm1_data(self, extractor):
        """Test extracting data from NM1 segment."""
        nm1_segment = ["NM1", "PR", "2", "BLUE CROSS", "", "", "", "", "PI", "BLUE_CROSS"]
        warnings = []

        result = extractor._extract_nm1_data(nm1_segment, warnings)

        assert result.get("payer_name") == "BLUE CROSS" or result.get("organization_name") == "BLUE CROSS"
        assert result.get("payer_id") == "BLUE_CROSS" or result.get("payer_identifier") == "BLUE_CROSS"

    def test_extract_nm1_individual(self, extractor):
        """Test extracting NM1 data for individual."""
        nm1_segment = ["NM1", "IL", "1", "DOE", "JOHN", "M", "", "", "MI", "123456789"]
        warnings = []

        result = extractor._extract_nm1_data(nm1_segment, warnings)

        # NM1 extractor only extracts payer_name, payer_id_qualifier, and payer_id
        # For individual (IL), it would extract as payer_name
        assert result.get("payer_name") == "DOE"  # First name field is used
        assert result.get("payer_id") == "123456789"

