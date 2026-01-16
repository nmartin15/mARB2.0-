"""Decimal precision utilities for financial calculations."""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional, Union

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Standard precision for financial amounts (2 decimal places)
FINANCIAL_PRECISION = Decimal("0.01")


def parse_decimal(value: Optional[Union[str, int, float, Decimal]], precision: Optional[Decimal] = None) -> Optional[Decimal]:
    """
    Parse a value to Decimal with proper precision handling.
    
    Args:
        value: Value to parse (string, int, float, or Decimal)
        precision: Optional precision to round to (default: FINANCIAL_PRECISION for 2 decimal places)
        
    Returns:
        Decimal value or None if parsing fails
        
    Example:
        >>> parse_decimal("123.456")
        Decimal('123.46')
        >>> parse_decimal("123.456", precision=Decimal("0.001"))
        Decimal('123.456')
    """
    if value is None:
        return None
    
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, float)):
        try:
            result = Decimal(str(value))
        except (ValueError, InvalidOperation) as e:
            logger.warning("Failed to convert numeric value to Decimal", value=value, error=str(e))
            return None
    elif isinstance(value, str):
        # Strip whitespace
        value = value.strip()
        if not value:
            return None
        try:
            result = Decimal(value)
        except (ValueError, InvalidOperation) as e:
            logger.warning("Failed to parse decimal string", value=value, error=str(e))
            return None
    else:
        logger.warning("Unsupported type for decimal parsing", value=value, type=type(value).__name__)
        return None
    
    # Round to precision if specified
    if precision is not None:
        try:
            result = result.quantize(precision, rounding=ROUND_HALF_UP)
        except (ValueError, InvalidOperation) as e:
            logger.warning("Failed to quantize decimal", value=result, precision=precision, error=str(e))
            return None
    
    return result


def parse_financial_amount(value: Optional[Union[str, int, float, Decimal]]) -> Optional[Decimal]:
    """
    Parse a financial amount with 2 decimal place precision.
    
    Args:
        value: Value to parse
        
    Returns:
        Decimal value rounded to 2 decimal places, or None if parsing fails
        
    Example:
        >>> parse_financial_amount("123.456")
        Decimal('123.46')
        >>> parse_financial_amount("1000.00")
        Decimal('1000.00')
    """
    return parse_decimal(value, precision=FINANCIAL_PRECISION)


def decimal_to_float(value: Optional[Decimal]) -> Optional[float]:
    """
    Convert Decimal to float for database storage (Float columns).
    Preserves precision as much as possible.
    
    Args:
        value: Decimal value to convert
        
    Returns:
        Float value or None
        
    Note:
        This is a lossy conversion. Use Decimal columns when possible for financial data.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError) as e:
        logger.warning("Failed to convert Decimal to float", value=value, error=str(e))
        return None


def validate_decimal_precision(value: Decimal, max_decimal_places: int = 2) -> bool:
    """
    Validate that a Decimal value has acceptable precision.
    
    Args:
        value: Decimal value to validate
        max_decimal_places: Maximum number of decimal places allowed
        
    Returns:
        True if value has acceptable precision, False otherwise
        
    Example:
        >>> validate_decimal_precision(Decimal("123.45"), max_decimal_places=2)
        True
        >>> validate_decimal_precision(Decimal("123.456"), max_decimal_places=2)
        False
    """
    if value is None:
        return False
    
    # Get the number of decimal places
    decimal_places = abs(value.as_tuple().exponent)
    return decimal_places <= max_decimal_places


def round_to_precision(value: Decimal, decimal_places: int = 2) -> Decimal:
    """
    Round a Decimal value to a specific number of decimal places.
    
    Args:
        value: Decimal value to round
        decimal_places: Number of decimal places to round to
        
    Returns:
        Rounded Decimal value
        
    Example:
        >>> round_to_precision(Decimal("123.456"), decimal_places=2)
        Decimal('123.46')
    """
    if value is None:
        return value
    
    precision = Decimal("0.1") ** decimal_places
    return value.quantize(precision, rounding=ROUND_HALF_UP)

