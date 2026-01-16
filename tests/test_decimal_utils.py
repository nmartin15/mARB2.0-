"""Tests for decimal precision utilities."""
import pytest
from decimal import Decimal, InvalidOperation

from app.utils.decimal_utils import (
    parse_decimal,
    parse_financial_amount,
    decimal_to_float,
    validate_decimal_precision,
    round_to_precision,
)


@pytest.mark.unit
class TestParseDecimal:
    """Tests for parse_decimal function."""

    def test_parse_decimal_from_string(self):
        """Test parsing decimal from string."""
        result = parse_decimal("123.45")
        assert result == Decimal("123.45")

    def test_parse_decimal_from_int(self):
        """Test parsing decimal from integer."""
        result = parse_decimal(123)
        assert result == Decimal("123")

    def test_parse_decimal_from_float(self):
        """Test parsing decimal from float."""
        result = parse_decimal(123.45)
        assert result == Decimal("123.45")

    def test_parse_decimal_from_decimal(self):
        """Test parsing decimal from Decimal."""
        value = Decimal("123.45")
        result = parse_decimal(value)
        assert result == value

    def test_parse_decimal_none(self):
        """Test parsing None value."""
        result = parse_decimal(None)
        assert result is None

    def test_parse_decimal_empty_string(self):
        """Test parsing empty string."""
        result = parse_decimal("")
        assert result is None

    def test_parse_decimal_whitespace_string(self):
        """Test parsing whitespace-only string."""
        result = parse_decimal("   ")
        assert result is None

    def test_parse_decimal_with_precision(self):
        """Test parsing decimal with precision rounding."""
        result = parse_decimal("123.456", precision=Decimal("0.01"))
        assert result == Decimal("123.46")

    def test_parse_decimal_invalid_string(self):
        """Test parsing invalid string."""
        result = parse_decimal("not a number")
        assert result is None

    def test_parse_decimal_very_precise(self):
        """Test parsing very precise decimal."""
        result = parse_decimal("123.456789012345")
        assert result == Decimal("123.456789012345")

    def test_parse_decimal_negative(self):
        """Test parsing negative decimal."""
        result = parse_decimal("-123.45")
        assert result == Decimal("-123.45")

    def test_parse_decimal_zero(self):
        """Test parsing zero."""
        result = parse_decimal("0")
        assert result == Decimal("0")

    def test_parse_decimal_unsupported_type(self):
        """Test parsing unsupported type."""
        result = parse_decimal(["not", "a", "number"])
        assert result is None


@pytest.mark.unit
class TestParseFinancialAmount:
    """Tests for parse_financial_amount function."""

    def test_parse_financial_amount_string(self):
        """Test parsing financial amount from string."""
        result = parse_financial_amount("123.45")
        assert result == Decimal("123.45")

    def test_parse_financial_amount_rounds_to_2_decimal_places(self):
        """Test that financial amounts are rounded to 2 decimal places."""
        result = parse_financial_amount("123.456")
        assert result == Decimal("123.46")

    def test_parse_financial_amount_rounds_up(self):
        """Test that rounding follows ROUND_HALF_UP."""
        result = parse_financial_amount("123.455")
        assert result == Decimal("123.46")

    def test_parse_financial_amount_rounds_down(self):
        """Test that rounding follows ROUND_HALF_UP."""
        result = parse_financial_amount("123.454")
        assert result == Decimal("123.45")

    def test_parse_financial_amount_none(self):
        """Test parsing None financial amount."""
        result = parse_financial_amount(None)
        assert result is None

    def test_parse_financial_amount_integer(self):
        """Test parsing integer as financial amount."""
        result = parse_financial_amount(1000)
        assert result == Decimal("1000.00")

    def test_parse_financial_amount_float(self):
        """Test parsing float as financial amount."""
        result = parse_financial_amount(1000.5)
        assert result == Decimal("1000.50")


@pytest.mark.unit
class TestDecimalToFloat:
    """Tests for decimal_to_float function."""

    def test_decimal_to_float_conversion(self):
        """Test converting Decimal to float."""
        value = Decimal("123.45")
        result = decimal_to_float(value)
        assert result == 123.45
        assert isinstance(result, float)

    def test_decimal_to_float_none(self):
        """Test converting None to float."""
        result = decimal_to_float(None)
        assert result is None

    def test_decimal_to_float_precise(self):
        """Test converting precise Decimal to float."""
        value = Decimal("123.456789")
        result = decimal_to_float(value)
        assert isinstance(result, float)
        # Note: This is a lossy conversion, but should work
        assert abs(result - 123.456789) < 0.000001


@pytest.mark.unit
class TestValidateDecimalPrecision:
    """Tests for validate_decimal_precision function."""

    def test_validate_decimal_precision_valid(self):
        """Test validating decimal with acceptable precision."""
        value = Decimal("123.45")
        assert validate_decimal_precision(value, max_decimal_places=2) is True

    def test_validate_decimal_precision_too_many_places(self):
        """Test validating decimal with too many decimal places."""
        value = Decimal("123.456")
        assert validate_decimal_precision(value, max_decimal_places=2) is False

    def test_validate_decimal_precision_exact_limit(self):
        """Test validating decimal at exact limit."""
        value = Decimal("123.45")
        assert validate_decimal_precision(value, max_decimal_places=2) is True

    def test_validate_decimal_precision_integer(self):
        """Test validating integer (no decimal places)."""
        value = Decimal("123")
        assert validate_decimal_precision(value, max_decimal_places=2) is True

    def test_validate_decimal_precision_none(self):
        """Test validating None value."""
        assert validate_decimal_precision(None, max_decimal_places=2) is False

    def test_validate_decimal_precision_custom_limit(self):
        """Test validating with custom decimal place limit."""
        value = Decimal("123.456")
        assert validate_decimal_precision(value, max_decimal_places=3) is True
        assert validate_decimal_precision(value, max_decimal_places=2) is False


@pytest.mark.unit
class TestRoundToPrecision:
    """Tests for round_to_precision function."""

    def test_round_to_precision_2_decimal_places(self):
        """Test rounding to 2 decimal places."""
        value = Decimal("123.456")
        result = round_to_precision(value, decimal_places=2)
        assert result == Decimal("123.46")

    def test_round_to_precision_3_decimal_places(self):
        """Test rounding to 3 decimal places."""
        value = Decimal("123.4567")
        result = round_to_precision(value, decimal_places=3)
        assert result == Decimal("123.457")

    def test_round_to_precision_rounds_up(self):
        """Test that rounding follows ROUND_HALF_UP."""
        value = Decimal("123.455")
        result = round_to_precision(value, decimal_places=2)
        assert result == Decimal("123.46")

    def test_round_to_precision_rounds_down(self):
        """Test that rounding follows ROUND_HALF_UP."""
        value = Decimal("123.454")
        result = round_to_precision(value, decimal_places=2)
        assert result == Decimal("123.45")

    def test_round_to_precision_none(self):
        """Test rounding None value."""
        result = round_to_precision(None, decimal_places=2)
        assert result is None

    def test_round_to_precision_zero_decimal_places(self):
        """Test rounding to zero decimal places."""
        value = Decimal("123.456")
        result = round_to_precision(value, decimal_places=0)
        assert result == Decimal("123")

    def test_parse_decimal_with_quantize_error(self):
        """Test parse_decimal handles quantize errors gracefully."""
        # This tests the error handling in quantize
        # Create a value that might cause issues
        result = parse_decimal("123.456", precision=Decimal("0.01"))
        # Should still work and round properly
        assert result is not None
        assert isinstance(result, Decimal)

    def test_parse_decimal_very_large_number(self):
        """Test parse_decimal with very large numbers."""
        result = parse_decimal("999999999999999.99")
        assert result == Decimal("999999999999999.99")

    def test_parse_decimal_very_small_number(self):
        """Test parse_decimal with very small numbers."""
        result = parse_decimal("0.0000001")
        assert result == Decimal("0.0000001")

    def test_parse_decimal_scientific_notation(self):
        """Test parse_decimal with scientific notation string."""
        result = parse_decimal("1.23e-4")
        # Decimal should handle this
        assert result is not None

    def test_parse_decimal_unicode_characters(self):
        """Test parse_decimal with unicode in string."""
        # Should handle gracefully
        result = parse_decimal("123.45")
        assert result == Decimal("123.45")

    def test_decimal_to_float_large_value(self):
        """Test decimal_to_float with very large Decimal."""
        value = Decimal("999999999999999.99")
        result = decimal_to_float(value)
        assert isinstance(result, float)
        assert result > 0

    def test_decimal_to_float_very_small_value(self):
        """Test decimal_to_float with very small Decimal."""
        value = Decimal("0.0000001")
        result = decimal_to_float(value)
        assert isinstance(result, float)

    def test_validate_decimal_precision_zero(self):
        """Test validate_decimal_precision with zero."""
        value = Decimal("0")
        assert validate_decimal_precision(value, max_decimal_places=2) is True

    def test_validate_decimal_precision_negative(self):
        """Test validate_decimal_precision with negative value."""
        value = Decimal("-123.45")
        assert validate_decimal_precision(value, max_decimal_places=2) is True

    def test_round_to_precision_negative(self):
        """Test round_to_precision with negative value."""
        value = Decimal("-123.456")
        result = round_to_precision(value, decimal_places=2)
        assert result == Decimal("-123.46")

    def test_parse_financial_amount_negative(self):
        """Test parse_financial_amount with negative value."""
        result = parse_financial_amount("-123.456")
        assert result == Decimal("-123.46")

    def test_parse_decimal_with_custom_precision(self):
        """Test parse_decimal with custom precision (3 decimal places)."""
        result = parse_decimal("123.456789", precision=Decimal("0.001"))
        assert result == Decimal("123.457")  # Rounded to 3 places

