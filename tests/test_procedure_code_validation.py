"""Tests for procedure code validation."""
import pytest

from app.services.edi.extractors.line_extractor import LineExtractor
from app.services.edi.config import ParserConfig


@pytest.fixture
def extractor():
    """Create a LineExtractor instance."""
    config = ParserConfig()
    return LineExtractor(config)


@pytest.mark.unit
class TestProcedureCodeValidation:
    """Tests for procedure code validation."""

    def test_validate_cpt_code_valid(self, extractor):
        """Test validating valid CPT code."""
        assert extractor._validate_procedure_code("12345") is True
        assert extractor._validate_procedure_code("99213") is True
        assert extractor._validate_procedure_code("00001") is True

    def test_validate_hcpcs_code_valid(self, extractor):
        """Test validating valid HCPCS code."""
        assert extractor._validate_procedure_code("A1234") is True
        assert extractor._validate_procedure_code("G0123") is True
        assert extractor._validate_procedure_code("J1234") is True

    def test_validate_procedure_code_with_modifier(self, extractor):
        """Test validating procedure code with modifier (should strip modifier)."""
        assert extractor._validate_procedure_code("12345-26") is True
        assert extractor._validate_procedure_code("A1234-59") is True

    def test_validate_procedure_code_invalid_format(self, extractor):
        """Test validating invalid procedure code formats."""
        assert extractor._validate_procedure_code("") is False
        assert extractor._validate_procedure_code("1234") is False  # Too short
        assert extractor._validate_procedure_code("123456") is False  # Too long
        assert extractor._validate_procedure_code("ABCDE") is False  # All letters
        assert extractor._validate_procedure_code("12ABC") is False  # Mixed format
        assert extractor._validate_procedure_code("1234A") is False  # Wrong format

    def test_validate_procedure_code_none(self, extractor):
        """Test validating None procedure code."""
        assert extractor._validate_procedure_code(None) is False

    def test_validate_procedure_code_whitespace(self, extractor):
        """Test validating procedure code with whitespace."""
        # Whitespace should be stripped, so this should work
        assert extractor._validate_procedure_code(" 12345 ") is True

    def test_extract_line_with_valid_procedure_code(self, extractor):
        """Test extracting line with valid procedure code."""
        block = [
            ["LX", "1"],
            ["SV2", "0450", "HC>99213", "150.00", "UN", "1"],
        ]
        warnings = []
        
        result = extractor.extract(block, warnings)
        
        assert len(result) == 1
        line = result[0]
        assert line["procedure_code"] == "99213"
        assert line.get("procedure_code_valid") is True

    def test_extract_line_with_invalid_procedure_code(self, extractor):
        """Test extracting line with invalid procedure code."""
        block = [
            ["LX", "1"],
            ["SV2", "0450", "HC>INVALID", "150.00", "UN", "1"],
        ]
        warnings = []
        
        result = extractor.extract(block, warnings)
        
        assert len(result) == 1
        line = result[0]
        assert line["procedure_code"] == "INVALID"
        assert line.get("procedure_code_valid") is False

    def test_extract_line_with_decimal_precision(self, extractor):
        """Test extracting line with decimal precision handling."""
        block = [
            ["LX", "1"],
            ["SV2", "0450", "HC>99213", "123.456789", "UN", "1.5"],
        ]
        warnings = []
        
        result = extractor.extract(block, warnings)
        
        assert len(result) == 1
        line = result[0]
        # Charge amount should be rounded to 2 decimal places
        assert line["charge_amount"] == 123.46
        # Unit count should preserve decimal precision
        assert line["unit_count"] == 1.5

