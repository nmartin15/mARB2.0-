"""Tests for diagnosis extractor."""
import pytest

from app.services.edi.config import get_parser_config
from app.services.edi.extractors.diagnosis_extractor import DiagnosisExtractor


@pytest.fixture
def extractor():
    """Create a diagnosis extractor instance."""
    config = get_parser_config()
    return DiagnosisExtractor(config)


@pytest.fixture
def sample_block_with_diagnosis():
    """Sample block with HI segments."""
    return [
        ["HI", "ABK>E11.9"],  # Principal diagnosis (format: qualifier>code)
        ["HI", "BF>I10"],  # Other diagnosis
        ["HI", "BF>E78.5"],  # Another diagnosis
    ]


@pytest.mark.unit
class TestDiagnosisExtractor:
    """Tests for DiagnosisExtractor."""

    def test_extract_diagnosis_codes(self, extractor, sample_block_with_diagnosis):
        """Test extracting diagnosis codes."""
        warnings = []

        result = extractor.extract(sample_block_with_diagnosis, warnings)

        assert "principal_diagnosis" in result
        assert result["principal_diagnosis"] == "E11.9"
        assert "diagnosis_codes" in result
        assert len(result["diagnosis_codes"]) >= 1

    def test_extract_multiple_diagnosis_codes(self, extractor, sample_block_with_diagnosis):
        """Test extracting multiple diagnosis codes."""
        warnings = []

        result = extractor.extract(sample_block_with_diagnosis, warnings)

        assert "diagnosis_codes" in result
        # Should have at least principal diagnosis
        assert len(result["diagnosis_codes"]) >= 1
        # Diagnosis codes are stored as dicts with 'code' key
        codes = [d.get("code") for d in result["diagnosis_codes"] if isinstance(d, dict)]
        assert "E11.9" in codes

    def test_extract_diagnosis_no_hi_segments(self, extractor):
        """Test extracting diagnosis when no HI segments exist."""
        block = [
            ["CLM", "CLAIM001", "1000.00"],
        ]
        warnings = []

        result = extractor.extract(block, warnings)

        # Should return empty or default values
        assert isinstance(result, dict)

    def test_extract_diagnosis_icd10_format(self, extractor):
        """Test extracting ICD-10 diagnosis codes."""
        block = [
            ["HI", "ABK>E11.9"],  # Principal diagnosis with ABK qualifier
        ]
        warnings = []

        result = extractor.extract(block, warnings)

        assert "principal_diagnosis" in result
        assert result["principal_diagnosis"] == "E11.9"

    def test_extract_diagnosis_abk_format(self, extractor):
        """Test extracting diagnosis with ABK qualifier."""
        block = [
            ["HI", "ABK>E11.9"],  # ABK format (qualifier>code)
        ]
        warnings = []

        result = extractor.extract(block, warnings)

        # Should handle ABK format and set as principal
        assert result["principal_diagnosis"] == "E11.9"
        assert len(result["diagnosis_codes"]) > 0

    def test_find_segments_in_block(self, extractor):
        """Test finding HI segments in block."""
        block = [
            ["HI", "ABK>E11.9"],
            ["HI", "BF>I10"],
            ["CLM", "CLAIM001"],
        ]

        hi_segments = extractor._find_segments_in_block(block, "HI")

        assert len(hi_segments) == 2
        assert all(seg[0] == "HI" for seg in hi_segments)

