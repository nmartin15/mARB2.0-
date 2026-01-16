"""Extract claim line data from LX/SV2 segments."""
import re
from datetime import datetime
from typing import Dict, List, Optional

from app.services.edi.config import ParserConfig
from app.services.edi.validator import SegmentValidator
from app.utils.decimal_utils import parse_decimal, parse_financial_amount, decimal_to_float
from app.utils.logger import get_logger

logger = get_logger(__name__)

# CPT code pattern: 5 digits, optionally followed by modifiers
# Format: 12345 or 12345-26 (with modifier)
CPT_CODE_PATTERN = re.compile(r"^\d{5}(-\d{2})?$")
# HCPCS code pattern: 1 letter followed by 4 digits, optionally with modifiers
HCPCS_CODE_PATTERN = re.compile(r"^[A-Z]\d{4}(-\d{2})?$")


class LineExtractor:
    """Extract claim line information."""

    def __init__(self, config: ParserConfig):
        self.config = config
        self.validator = SegmentValidator(config)

    def extract(self, block: List[List[str]], warnings: List[str]) -> List[Dict]:
        """Extract all claim lines from block."""
        lines = []

        # Find all LX segments (line number)
        lx_segments = self._find_segments_in_block(block, "LX")

        if not lx_segments:
            # No lines found - this might be okay for some claim types
            return lines

        for lx_seg in lx_segments:
            if len(lx_seg) < 2:
                continue

            line_number = self.validator.safe_get_element(lx_seg, 1)

            # Find SV2 segment that follows this LX
            sv2_seg = self._find_sv2_after_lx(block, lx_seg)

            if sv2_seg:
                line_data = self._extract_line_data(line_number, sv2_seg, block, warnings)
                lines.append(line_data)
            else:
                warnings.append(f"SV2 segment not found for line {line_number}")

        return lines

    def _find_segments_in_block(self, block: List[List[str]], segment_id: str) -> List[List[str]]:
        """Find all segments of a type in block. Optimized with manual loop for better performance."""
        # Manual loop is faster than list comprehension for this case
        # Check seg[0] directly after verifying seg is non-empty
        result = []
        for seg in block:
            if seg and seg[0] == segment_id:
                result.append(seg)
        return result

    def _find_sv2_after_lx(self, block: List[List[str]], lx_segment: List[str]) -> List[str]:
        """Find SV2 segment that follows an LX segment. Optimized with early exit."""
        lx_index = None
        block_len = len(block)
        for i in range(block_len):
            if block[i] == lx_segment:
                lx_index = i
                break

        if lx_index is None:
            return None

        # Look for SV2 after this LX
        # Cache termination segment IDs for faster lookup
        termination_segments = {"LX", "CLM"}
        for i in range(lx_index + 1, block_len):
            seg = block[i]
            if not seg:
                continue
            seg_id = seg[0]
            if seg_id == "SV2":
                return seg
            # Stop if we hit another LX or CLM
            if seg_id in termination_segments:
                break

        return None

    def _extract_line_data(
        self, line_number: str, sv2_seg: List[str], block: List[List[str]], warnings: List[str]
    ) -> Dict:
        """Extract data from SV2 segment."""
        line_data = {
            "line_number": line_number,
        }

        if len(sv2_seg) < 4:
            warnings.append(f"SV2 segment has insufficient elements for line {line_number}")
            return line_data

        # Revenue code (SV201)
        line_data["revenue_code"] = self.validator.safe_get_element(sv2_seg, 1)

        # Medical procedure identifier (SV202) - format: qualifier>code>modifier
        proc_id = self.validator.safe_get_element(sv2_seg, 2)
        if proc_id:
            parts = proc_id.split(">")
            if len(parts) >= 1:
                line_data["procedure_qualifier"] = parts[0]
            if len(parts) >= 2:
                # Procedure code might have modifiers separated by >
                proc_code = parts[1]
                if ">" in proc_code:
                    code_parts = proc_code.split(">")
                    proc_code = code_parts[0]
                    if len(code_parts) > 1:
                        line_data["procedure_modifier"] = code_parts[1]
                
                # Validate procedure code format
                if not self._validate_procedure_code(proc_code):
                    logger.warning(
                        "Invalid procedure code format",
                        code=proc_code,
                        line_number=line_number,
                    )
                    line_data["procedure_code"] = proc_code
                    line_data["procedure_code_valid"] = False
                else:
                    line_data["procedure_code"] = proc_code
                    line_data["procedure_code_valid"] = True

        # Line item charge amount (SV203) - use decimal utilities for precision
        charge_str = self.validator.safe_get_element(sv2_seg, 3)
        if charge_str:
            charge_decimal = parse_financial_amount(charge_str)
            if charge_decimal is not None:
                line_data["charge_amount"] = decimal_to_float(charge_decimal)
            else:
                warnings.append(f"Invalid charge amount for line {line_number}: {charge_str}")
                line_data["charge_amount"] = None
        else:
            line_data["charge_amount"] = None

        # Unit basis for measurement (SV204)
        line_data["unit_type"] = self.validator.safe_get_element(sv2_seg, 4)

        # Service unit count (SV205) - use decimal utilities for precision
        unit_count_str = self.validator.safe_get_element(sv2_seg, 5)
        if unit_count_str:
            # Unit count can have decimal places (e.g., 1.5 units)
            unit_decimal = parse_decimal(unit_count_str, precision=None)  # No rounding for unit counts
            if unit_decimal is not None:
                line_data["unit_count"] = decimal_to_float(unit_decimal)
            else:
                line_data["unit_count"] = None
        else:
            line_data["unit_count"] = None

        # Find service date from DTP segment after SV2
        service_date = self._find_service_date_after_sv2(block, sv2_seg)
        if service_date:
            line_data["service_date"] = service_date

        return line_data

    def _find_service_date_after_sv2(
        self, block: List[List[str]], sv2_segment: List[str]
    ) -> datetime:
        """Find service date from DTP segment after SV2. Optimized with early exit."""
        sv2_index = None
        block_len = len(block)
        for i in range(block_len):
            if block[i] == sv2_segment:
                sv2_index = i
                break

        if sv2_index is None:
            return None

        # Look for DTP with qualifier 472 (service date) after this SV2
        # Limit search window to next 10 segments (optimization)
        search_limit = min(sv2_index + 10, block_len)
        termination_segments = {"SV2", "LX"}

        for i in range(sv2_index + 1, search_limit):
            seg = block[i]
            if not seg:
                continue
            seg_id = seg[0]
            if seg_id == "DTP" and len(seg) >= 4:
                qualifier = self.validator.safe_get_element(seg, 1)
                if qualifier == "472":  # Service date
                    date_format = self.validator.safe_get_element(seg, 2)
                    date_value = self.validator.safe_get_element(seg, 3)
                    if date_format == "D8" and len(date_value) == 8:
                        try:
                            # Optimize: use direct string slicing instead of strptime for better performance
                            return datetime(
                                int(date_value[0:4]), int(date_value[4:6]), int(date_value[6:8])
                            )
                        except (ValueError, TypeError):
                            pass
            # Stop if we hit another SV2 or LX
            elif seg_id in termination_segments:
                break

        return None

    def _validate_procedure_code(self, code: str) -> bool:
        """
        Validate procedure code format (CPT or HCPCS).
        
        Args:
            code: Procedure code to validate
            
        Returns:
            True if code format is valid, False otherwise
        """
        if not code or not isinstance(code, str):
            return False

        code = code.strip()
        
        # Remove modifier suffix if present (e.g., "12345-26" -> "12345")
        if "-" in code:
            code = code.split("-")[0]
        
        # Check length (CPT codes are 5 digits, HCPCS are 1 letter + 4 digits)
        if len(code) < 5 or len(code) > 5:
            return False

        # Check for CPT code format (5 digits)
        if CPT_CODE_PATTERN.match(code):
            return True

        # Check for HCPCS code format (1 letter + 4 digits)
        if HCPCS_CODE_PATTERN.match(code):
            return True

        return False

