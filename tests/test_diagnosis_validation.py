"""Tests for diagnosis code validation."""
import pytest

from app.services.edi.extractors.diagnosis_extractor import DiagnosisExtractor
from app.services.edi.config import ParserConfig
from app.services.edi.validator import SegmentValidator


@pytest.fixture
def extractor():
    """Create a DiagnosisExtractor instance."""
    config = ParserConfig()
    return DiagnosisExtractor(config)


@pytest.mark.unit
class TestDiagnosisCodeValidation:
    """Tests for diagnosis code validation."""

    def test_validate_icd10_code_valid(self, extractor):
        """Test validating valid ICD-10 code."""
        assert extractor._validate_diagnosis_code("E11.9") is True
        assert extractor._validate_diagnosis_code("I10") is True
        assert extractor._validate_diagnosis_code("A00.00") is True

    def test_validate_icd9_code_valid(self, extractor):
        """Test validating valid ICD-9 code."""
        assert extractor._validate_diagnosis_code("001") is True
        assert extractor._validate_diagnosis_code("001.0") is True
        assert extractor._validate_diagnosis_code("12345") is True

    def test_validate_diagnosis_code_invalid_format(self, extractor):
        """Test validating invalid diagnosis code formats."""
        assert extractor._validate_diagnosis_code("") is False
        assert extractor._validate_diagnosis_code("AB") is False  # Too short
        assert extractor._validate_diagnosis_code("12345678901") is False  # Too long
        assert extractor._validate_diagnosis_code("E11.999") is False  # Too many decimal places
        assert extractor._validate_diagnosis_code("11E.9") is False  # Wrong format
        assert extractor._validate_diagnosis_code("E") is False  # Too short
        assert extractor._validate_diagnosis_code("E1") is False  # Too short

    def test_validate_diagnosis_code_none(self, extractor):
        """Test validating None diagnosis code."""
        assert extractor._validate_diagnosis_code(None) is False

    def test_validate_diagnosis_code_whitespace(self, extractor):
        """Test validating diagnosis code with whitespace."""
        # Whitespace should be stripped, so this should work
        assert extractor._validate_diagnosis_code(" E11.9 ") is True

    def test_parse_code_info_valid_icd10(self, extractor):
        """Test parsing valid ICD-10 code info."""
        result = extractor._parse_code_info("ABK>E11.9")
        
        assert result is not None
        assert result["code"] == "E11.9"
        assert result["qualifier"] == "ABK"
        assert result.get("is_valid") is True

    def test_parse_code_info_valid_icd9(self, extractor):
        """Test parsing valid ICD-9 code info."""
        result = extractor._parse_code_info("ABK>001.0")
        
        assert result is not None
        assert result["code"] == "001.0"
        assert result["qualifier"] == "ABK"
        assert result.get("is_valid") is True

    def test_parse_code_info_invalid_format(self, extractor):
        """Test parsing invalid diagnosis code format."""
        result = extractor._parse_code_info("ABK>INVALID")
        
        assert result is not None
        assert result["code"] == "INVALID"
        assert result.get("is_valid") is False
        assert "validation_warning" in result

    def test_parse_code_info_missing_separator(self, extractor):
        """Test parsing code info without separator."""
        result = extractor._parse_code_info("ABKE11.9")
        assert result is None

    def test_parse_code_info_empty_code(self, extractor):
        """Test parsing code info with empty code."""
        result = extractor._parse_code_info("ABK>")
        assert result is None

    def test_parse_code_info_empty_qualifier(self, extractor):
        """Test parsing code info with empty qualifier."""
        result = extractor._parse_code_info(">E11.9")
        # Should still parse but qualifier will be empty
        assert result is not None

    def test_extract_with_invalid_diagnosis_codes(self, extractor):
        """Test extracting diagnosis codes with invalid formats."""
        block = [
            ["HI", "ABK>E11.9"],  # Valid
            ["HI", "ABK>INVALID"],  # Invalid
            ["HI", "ABK>AB"],  # Too short
        ]
        warnings = []
        
        result = extractor.extract(block, warnings)
        
        assert "diagnosis_codes" in result
        assert len(result["diagnosis_codes"]) == 3  # All codes should be extracted
        # Check that invalid codes are marked
        invalid_codes = [c for c in result["diagnosis_codes"] if not c.get("is_valid", True)]
        assert len(invalid_codes) >= 1

    def test_extract_with_edge_case_codes(self, extractor):
        """Test extracting diagnosis codes with edge cases."""
        block = [
            ["HI", "ABK>E11"],  # Valid ICD-10 without decimal
            ["HI", "ABK>001"],  # Valid ICD-9 without decimal
            ["HI", "ABK>E11.99"],  # Valid ICD-10 with 2 decimal places
        ]
        warnings = []
        
        result = extractor.extract(block, warnings)
        
        assert "diagnosis_codes" in result
        assert len(result["diagnosis_codes"]) == 3
        # All should be valid
        for code_data in result["diagnosis_codes"]:
            assert code_data.get("is_valid") is True

