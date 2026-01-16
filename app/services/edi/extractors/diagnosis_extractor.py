"""Extract diagnosis codes from HI segments."""
import re
from typing import Dict, List, Optional

from app.services.edi.config import DIAGNOSIS_CODE_QUALIFIER_MAP, ParserConfig
from app.services.edi.validator import SegmentValidator
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ICD-10 code pattern: Letter followed by digits, optionally with decimal point
# Format: A00.00 (letter, 2 digits, optional decimal, 0-2 digits)
ICD10_PATTERN = re.compile(r"^[A-Z]\d{2}(\.\d{0,2})?$")

# ICD-9 code pattern: 3-5 digits, optionally with decimal point
# Format: 001.00 (3-5 digits, optional decimal, 0-2 digits)
ICD9_PATTERN = re.compile(r"^\d{3,5}(\.\d{0,2})?$")

# Minimum and maximum diagnosis code length
MIN_DIAGNOSIS_CODE_LENGTH = 3
MAX_DIAGNOSIS_CODE_LENGTH = 10


class DiagnosisExtractor:
    """Extract diagnosis information."""

    def __init__(self, config: ParserConfig):
        self.config = config
        self.validator = SegmentValidator(config)

    def extract(self, block: List[List[str]], warnings: List[str]) -> Dict:
        """Extract diagnosis codes from HI segments."""
        diagnosis_data = {
            "diagnosis_codes": [],
            "principal_diagnosis": None,
        }

        # Find all HI segments
        hi_segments = self._find_segments_in_block(block, "HI")

        if not hi_segments:
            warnings.append("No HI segments found")
            return diagnosis_data

        for hi_seg in hi_segments:
            if len(hi_seg) < 2:
                continue

            # HI01 - Health care code information
            code_info = self.validator.safe_get_element(hi_seg, 1)
            if code_info:
                code_data = self._parse_code_info(code_info)
                if code_data:
                    diagnosis_data["diagnosis_codes"].append(code_data)

                    # Check if this is principal diagnosis
                    if code_data.get("qualifier") in ["ABK", "ABJ"]:
                        diagnosis_data["principal_diagnosis"] = code_data.get("code")

            # HI02 - Additional health care code information (optional)
            if len(hi_seg) > 2:
                code_info2 = self.validator.safe_get_element(hi_seg, 2)
                if code_info2:
                    code_data2 = self._parse_code_info(code_info2)
                    if code_data2:
                        diagnosis_data["diagnosis_codes"].append(code_data2)

        return diagnosis_data

    def _find_segments_in_block(self, block: List[List[str]], segment_id: str) -> List[List[str]]:
        """
        Find all segments of a type in block. Optimized with list comprehension.
        
        Args:
            block: List of segments (each segment is a list of strings)
            segment_id: The segment identifier to search for (e.g., "HI")
            
        Returns:
            List of segments matching the segment_id
            
        Note:
            Length check ensures seg[0] access is safe and prevents IndexError.
        """
        # List comprehension is faster than manual loop for filtering
        # Check seg is non-empty and has at least one element before accessing seg[0]
        return [seg for seg in block if seg and len(seg) > 0 and seg[0] == segment_id]

    def _parse_code_info(self, code_info: str) -> Optional[Dict]:
        """
        Parse health care code information (format: qualifier>code).
        
        Args:
            code_info: Code information string in format "qualifier>code"
            
        Returns:
            Dictionary with code data, or None if invalid
        """
        if not code_info or ">" not in code_info:
            return None

        parts = code_info.split(">", 1)
        if len(parts) < 2:
            return None

        qualifier = parts[0].strip()
        code = parts[1].strip()

        # Validate code format
        if not self._validate_diagnosis_code(code):
            logger.warning(
                "Invalid diagnosis code format",
                code=code,
                qualifier=qualifier,
                code_info=code_info,
            )
            # Still return the code but mark it as potentially invalid
            return {
                "qualifier": qualifier,
                "qualifier_desc": DIAGNOSIS_CODE_QUALIFIER_MAP.get(qualifier, "Unknown"),
                "code": code,
                "is_valid": False,
                "validation_warning": "Code format may be invalid",
            }

        return {
            "qualifier": qualifier,
            "qualifier_desc": DIAGNOSIS_CODE_QUALIFIER_MAP.get(qualifier, "Unknown"),
            "code": code,
            "is_valid": True,
        }

    def _validate_diagnosis_code(self, code: str) -> bool:
        """
        Validate diagnosis code format (ICD-10 or ICD-9).
        
        Args:
            code: Diagnosis code to validate
            
        Returns:
            True if code format is valid, False otherwise
        """
        if not code or not isinstance(code, str):
            return False

        code = code.strip()
        
        # Check length constraints
        if len(code) < MIN_DIAGNOSIS_CODE_LENGTH or len(code) > MAX_DIAGNOSIS_CODE_LENGTH:
            return False

        # Check for ICD-10 format (letter followed by digits)
        if ICD10_PATTERN.match(code):
            return True

        # Check for ICD-9 format (digits only)
        if ICD9_PATTERN.match(code):
            return True

        # If neither pattern matches, code is invalid
        return False

