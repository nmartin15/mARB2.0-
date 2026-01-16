"""Tests for segment validator module."""
import pytest

from app.services.edi.config import ParserConfig
from app.services.edi.validator import SegmentValidator


@pytest.mark.unit
class TestSegmentValidator:
    """Test SegmentValidator class."""

    def test_init(self):
        """Test SegmentValidator initialization."""
        config = ParserConfig()
        validator = SegmentValidator(config)
        assert validator.config == config

    def test_validate_segment_critical_present(self):
        """Test validating a critical segment that is present."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM", "CLAIM001", "1500.00"]
        is_valid, warning = validator.validate_segment(segment, "CLM", min_length=2)

        assert is_valid is True
        assert warning is None

    def test_validate_segment_critical_missing(self):
        """Test validating a critical segment that is missing."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        is_valid, warning = validator.validate_segment(None, "CLM", min_length=2)

        assert is_valid is False
        assert "Critical segment CLM is missing" in warning

    def test_validate_segment_important_present(self):
        """Test validating an important segment that is present."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["SBR", "P", "18"]
        is_valid, warning = validator.validate_segment(segment, "SBR", min_length=2)

        assert is_valid is True
        assert warning is None

    def test_validate_segment_important_missing(self):
        """Test validating an important segment that is missing."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        is_valid, warning = validator.validate_segment(None, "SBR", min_length=2)

        assert is_valid is True
        assert "Important segment SBR is missing" in warning

    def test_validate_segment_optional_missing(self):
        """Test validating an optional segment that is missing."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        is_valid, warning = validator.validate_segment(None, "PRV", min_length=2)

        assert is_valid is True
        assert warning is None  # Optional segments don't generate warnings

    def test_validate_segment_insufficient_length(self):
        """Test validating a segment with insufficient length."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM"]  # Only 1 element, needs at least 2
        is_valid, warning = validator.validate_segment(segment, "CLM", min_length=2)

        assert is_valid is False
        assert "insufficient elements" in warning
        assert "expected at least 2" in warning

    def test_validate_segment_exact_min_length(self):
        """Test validating a segment with exact minimum length."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM", "CLAIM001"]  # Exactly 2 elements
        is_valid, warning = validator.validate_segment(segment, "CLM", min_length=2)

        assert is_valid is True
        assert warning is None

    def test_validate_segment_exceeds_min_length(self):
        """Test validating a segment that exceeds minimum length."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM", "CLAIM001", "1500.00", "EXTRA"]
        is_valid, warning = validator.validate_segment(segment, "CLM", min_length=2)

        assert is_valid is True
        assert warning is None

    def test_validate_segment_min_length_one(self):
        """Test validating a segment with min_length=1."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["ISA"]
        is_valid, warning = validator.validate_segment(segment, "ISA", min_length=1)

        assert is_valid is True
        assert warning is None

    def test_validate_segment_empty_list(self):
        """Test validating an empty segment list."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = []
        is_valid, warning = validator.validate_segment(segment, "CLM", min_length=1)

        assert is_valid is False
        assert "insufficient elements" in warning

    def test_validate_segment_custom_config_critical(self):
        """Test validating with custom config that defines critical segments."""
        custom_expectations = {
            "critical": ["CUSTOM"],
            "important": ["SBR"],
            "optional": ["PRV"],
        }
        config = ParserConfig(segment_expectations=custom_expectations)
        validator = SegmentValidator(config)

        # Test custom critical segment
        is_valid, warning = validator.validate_segment(None, "CUSTOM", min_length=1)
        assert is_valid is False
        assert "Critical segment CUSTOM is missing" in warning

        # Test custom important segment
        is_valid, warning = validator.validate_segment(None, "SBR", min_length=1)
        assert is_valid is True
        assert "Important segment SBR is missing" in warning

        # Test custom optional segment
        is_valid, warning = validator.validate_segment(None, "PRV", min_length=1)
        assert is_valid is True
        assert warning is None

    def test_validate_segment_unknown_segment(self):
        """Test validating an unknown segment (not in config)."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        # Unknown segment should be treated as optional
        is_valid, warning = validator.validate_segment(None, "UNKNOWN", min_length=1)

        assert is_valid is True
        assert warning is None

    def test_safe_get_element_valid_index(self):
        """Test safely getting element with valid index."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM", "CLAIM001", "1500.00"]
        element = validator.safe_get_element(segment, 1)

        assert element == "CLAIM001"

    def test_safe_get_element_index_zero(self):
        """Test safely getting element at index 0."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM", "CLAIM001"]
        element = validator.safe_get_element(segment, 0)

        assert element == "CLM"

    def test_safe_get_element_index_out_of_range(self):
        """Test safely getting element with index out of range."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM", "CLAIM001"]
        element = validator.safe_get_element(segment, 5)

        assert element == ""  # Default value

    def test_safe_get_element_index_out_of_range_custom_default(self):
        """Test safely getting element with custom default."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM", "CLAIM001"]
        element = validator.safe_get_element(segment, 5, default="N/A")

        assert element == "N/A"

    def test_safe_get_element_empty_segment(self):
        """Test safely getting element from empty segment."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = []
        element = validator.safe_get_element(segment, 0)

        assert element == ""

    def test_safe_get_element_none_segment(self):
        """Test safely getting element from None segment."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = None
        element = validator.safe_get_element(segment, 0)

        assert element == ""

    def test_safe_get_element_none_value(self):
        """Test safely getting element that is None."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM", None, "1500.00"]
        element = validator.safe_get_element(segment, 1)

        assert element == ""  # None values return default

    def test_safe_get_element_empty_string(self):
        """Test safely getting element that is empty string."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM", "", "1500.00"]
        element = validator.safe_get_element(segment, 1)

        assert element == ""  # Empty string returns as-is

    def test_safe_get_element_last_index(self):
        """Test safely getting last element."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM", "CLAIM001", "1500.00"]
        element = validator.safe_get_element(segment, 2)

        assert element == "1500.00"

    def test_validate_segment_with_none_elements(self):
        """Test validating segment that contains None elements."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        segment = ["CLM", None, "1500.00"]
        is_valid, warning = validator.validate_segment(segment, "CLM", min_length=2)

        # Should still be valid (length is 3, even if one element is None)
        assert is_valid is True
        assert warning is None

    def test_validate_segment_multiple_critical_segments(self):
        """Test validating multiple critical segments."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        # ISA is critical
        is_valid, warning = validator.validate_segment(None, "ISA", min_length=1)
        assert is_valid is False

        # GS is critical
        is_valid, warning = validator.validate_segment(None, "GS", min_length=1)
        assert is_valid is False

        # ST is critical
        is_valid, warning = validator.validate_segment(None, "ST", min_length=1)
        assert is_valid is False

        # CLM is critical
        is_valid, warning = validator.validate_segment(None, "CLM", min_length=1)
        assert is_valid is False

    def test_validate_segment_multiple_important_segments(self):
        """Test validating multiple important segments."""
        config = ParserConfig()
        validator = SegmentValidator(config)

        # SBR is important
        is_valid, warning = validator.validate_segment(None, "SBR", min_length=1)
        assert is_valid is True
        assert "Important segment SBR is missing" in warning

        # NM1 is important
        is_valid, warning = validator.validate_segment(None, "NM1", min_length=1)
        assert is_valid is True
        assert "Important segment NM1 is missing" in warning

        # DTP is important
        is_valid, warning = validator.validate_segment(None, "DTP", min_length=1)
        assert is_valid is True
        assert "Important segment DTP is missing" in warning

        # HI is important
        is_valid, warning = validator.validate_segment(None, "HI", min_length=1)
        assert is_valid is True
        assert "Important segment HI is missing" in warning

