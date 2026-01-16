"""Extract claim header data from CLM segment."""
from datetime import datetime
from typing import Dict, List

from app.services.edi.config import CLAIM_FREQUENCY_TYPE_MAP, FACILITY_TYPE_CODE_MAP, ParserConfig
from app.services.edi.validator import SegmentValidator
from app.utils.decimal_utils import parse_financial_amount, decimal_to_float
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ClaimExtractor:
    """Extract claim header information."""

    def __init__(self, config: ParserConfig):
        self.config = config
        self.validator = SegmentValidator(config)

    def extract(
        self, clm_segment: List[str], block: List[List[str]], warnings: List[str]
    ) -> Dict:
        """Extract claim data from CLM segment and related segments."""
        claim_data = {}

        # CLM segment (required)
        if len(clm_segment) < 2:
            warnings.append("CLM segment has insufficient elements")
            return claim_data

        # Patient control number (CLM01)
        claim_data["patient_control_number"] = self.validator.safe_get_element(clm_segment, 1)
        claim_data["claim_control_number"] = claim_data["patient_control_number"]  # Use as claim ID

        # Total claim charge amount (CLM02) - use decimal utilities for precision
        charge_amount_str = self.validator.safe_get_element(clm_segment, 2)
        if charge_amount_str:
            charge_decimal = parse_financial_amount(charge_amount_str)
            if charge_decimal is not None:
                claim_data["total_charge_amount"] = decimal_to_float(charge_decimal)
            else:
                warnings.append(f"Invalid charge amount: {charge_amount_str}")
                claim_data["total_charge_amount"] = None
        else:
            claim_data["total_charge_amount"] = None

        # Healthcare service location info (CLM05) - contains facility type, qualifier, frequency
        location_info = self.validator.safe_get_element(clm_segment, 5)
        if location_info:
            # Handle both ">" and ":" delimiters
            if ">" in location_info:
                parts = location_info.split(">")
            elif ":" in location_info:
                parts = location_info.split(":")
            else:
                parts = [location_info]

            if len(parts) >= 1:
                # Extract only first 2 characters for facility_type_code (database constraint)
                facility_code = parts[0][:2] if parts[0] else ""
                claim_data["facility_type_code"] = facility_code
                claim_data["facility_type_desc"] = FACILITY_TYPE_CODE_MAP.get(facility_code, "Unknown")
            if len(parts) >= 2:
                claim_data["facility_code_qualifier"] = parts[1]
            if len(parts) >= 3:
                freq_code = parts[2]
                claim_data["claim_frequency_type"] = freq_code
                claim_data["claim_frequency_desc"] = CLAIM_FREQUENCY_TYPE_MAP.get(freq_code, "Unknown")

        # Assignment/plan participation code (CLM07)
        claim_data["assignment_code"] = self.validator.safe_get_element(clm_segment, 7)

        # Extract dates from DTP segments in the block
        dtp_segments = self._find_segments_in_block(block, "DTP")
        dates = self._extract_dates(dtp_segments, warnings)
        claim_data.update(dates)

        return claim_data

    def _find_segments_in_block(self, block: List[List[str]], segment_id: str) -> List[List[str]]:
        """Find all segments of a type in block. Optimized with manual loop for better performance."""
        # Manual loop is faster than list comprehension for this case (early exit not needed)
        # Check seg[0] directly after verifying seg is non-empty
        result = []
        for seg in block:
            if seg and seg[0] == segment_id:
                result.append(seg)
        return result

    def _extract_dates(self, dtp_segments: List[List[str]], warnings: List[str]) -> Dict:
        """Extract dates from DTP segments."""
        dates = {}

        # Date qualifier mapping
        date_qualifier_map = {
            "434": "statement_date",
            "435": "admission_date",
            "096": "discharge_date",
            "472": "service_date",
        }

        for dtp in dtp_segments:
            if len(dtp) < 4:
                continue

            qualifier = self.validator.safe_get_element(dtp, 1)
            date_format = self.validator.safe_get_element(dtp, 2)
            date_value = self.validator.safe_get_element(dtp, 3)

            if qualifier in date_qualifier_map and date_value:
                try:
                    # Parse date based on format (D8 = CCYYMMDD)
                    # Optimize: use direct string slicing instead of strptime for better performance
                    if date_format == "D8" and len(date_value) == 8:
                        parsed_date = datetime(
                            int(date_value[0:4]), int(date_value[4:6]), int(date_value[6:8])
                        )
                        dates[date_qualifier_map[qualifier]] = parsed_date
                except (ValueError, TypeError) as e:
                    warnings.append(f"Failed to parse date {date_value}: {str(e)}")

        return dates

