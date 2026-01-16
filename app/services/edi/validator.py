"""Segment validation with resilience."""
from typing import List, Optional
from app.services.edi.config import ParserConfig
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SegmentValidator:
    """Validates segments but doesn't fail on missing optional segments."""

    def __init__(self, config: ParserConfig):
        self.config = config

    def validate_segment(
        self, segment: Optional[List[str]], segment_id: str, min_length: int = 1
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a segment.
        
        Args:
            segment: The segment to validate (list of elements) or None
            segment_id: The segment identifier (e.g., "CLM", "HI")
            min_length: Minimum required number of elements in the segment
            
        Returns:
            Tuple of (is_valid, warning_message) where:
            - is_valid: True if segment is valid or optional, False if critical segment is missing/invalid
            - warning_message: Warning message if segment is missing or invalid, None otherwise
        """
        if segment is None:
            if self.config.is_critical_segment(segment_id):
                return False, f"Critical segment {segment_id} is missing"
            elif self.config.is_important_segment(segment_id):
                return True, f"Important segment {segment_id} is missing"
            else:
                return True, None  # Optional segment, no warning
        
        if len(segment) < min_length:
            return False, f"Segment {segment_id} has insufficient elements (expected at least {min_length})"
        
        return True, None

    def safe_get_element(self, segment: List[str], index: int, default: str = "") -> str:
        """
        Safely get element from segment with default value.
        
        Args:
            segment: The segment (list of elements) to access
            index: The index of the element to retrieve
            default: Default value to return if segment is None, too short, or element is empty
            
        Returns:
            The element at the specified index, or the default value if not available
        """
        if segment and len(segment) > index:
            return segment[index] or default
        return default

