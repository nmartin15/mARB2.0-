"""Dynamic format detection and analysis for 837 files."""
from collections import Counter, defaultdict
from typing import Dict, List, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)


class FormatDetector:
    """Detect and analyze 837 file format characteristics."""

    def __init__(self):
        self.segment_patterns = defaultdict(Counter)
        self.element_patterns = defaultdict(Counter)
        self.date_formats = Counter()
        self.diagnosis_qualifiers = Counter()
        self.facility_codes = Counter()

    def analyze_file(self, segments: List[List[str]]) -> Dict:
        """
        Analyze file structure and return format profile.

        Optimized to use single-pass analysis where possible.

        Returns:
            Dict with format characteristics and patterns
        """
        logger.info("Analyzing file format", segment_count=len(segments))

        profile = {
            "segment_frequency": {},
            "segment_order": [],
            "element_counts": {},
            "date_formats": {},
            "diagnosis_qualifiers": {},
            "facility_codes": {},
            "version": None,
            "file_type": None,
        }

        # Optimize: Single-pass analysis for multiple metrics
        segment_types = []
        segment_order_seen = set()
        segment_order = []
        element_counts = defaultdict(list)
        date_formats = Counter()
        diagnosis_qualifiers = Counter()
        facility_codes = Counter()
        version = None
        file_type = None

        # Single pass through segments
        for seg in segments:
            if not seg or len(seg) == 0:
                continue

            seg_type = seg[0]
            seg_len = len(seg)

            # Collect segment types for frequency
            segment_types.append(seg_type)

            # Track segment order (first occurrence only)
            if seg_type not in segment_order_seen:
                segment_order_seen.add(seg_type)
                segment_order.append(seg_type)

            # Collect element counts
            element_counts[seg_type].append(seg_len)

            # Detect version and file type (early exit if found)
            if version is None and seg_type == "GS" and seg_len > 8:
                version = seg[8]

            if file_type is None:
                if seg_type == "CLM":
                    file_type = "837"
                elif seg_type == "CLP":
                    file_type = "835"

            # Analyze date formats
            if seg_type == "DTP" and seg_len > 2:
                date_formats[seg[2]] += 1

            # Analyze diagnosis qualifiers
            if seg_type == "HI":
                for i in range(1, min(seg_len, 13)):  # HI01-HI12
                    code_info = seg[i] if i < seg_len else ""
                    if code_info and ">" in code_info:
                        qualifier = code_info.split(">", 1)[0]  # Split once only
                        diagnosis_qualifiers[qualifier] += 1

            # Analyze facility codes
            if seg_type == "CLM" and seg_len > 5:
                location_info = seg[5]  # CLM05
                if location_info:
                    # Extract facility code (first part before delimiter)
                    if ">" in location_info:
                        facility_code = location_info.split(">", 1)[0][:2]  # Split once only
                    elif ":" in location_info:
                        facility_code = location_info.split(":", 1)[0][:2]  # Split once only
                    else:
                        facility_code = location_info[:2]

                    if facility_code:
                        facility_codes[facility_code] += 1

        # Set profile values
        profile["version"] = version
        profile["file_type"] = file_type or "837"  # Default
        profile["segment_frequency"] = dict(Counter(segment_types))
        profile["segment_order"] = segment_order

        # Calculate element count statistics
        element_stats = {}
        for seg_type, counts in element_counts.items():
            if counts:
                element_stats[seg_type] = {
                    "min": min(counts),
                    "max": max(counts),
                    "avg": sum(counts) / len(counts),
                    "most_common": Counter(counts).most_common(1)[0][0] if counts else None,
                }
        profile["element_counts"] = element_stats

        profile["date_formats"] = dict(date_formats)
        profile["diagnosis_qualifiers"] = dict(diagnosis_qualifiers)
        profile["facility_codes"] = dict(facility_codes)

        logger.info("Format analysis complete", profile_keys=list(profile.keys()))
        return profile

    def _detect_version(self, segments: List[List[str]]) -> Optional[str]:
        """
        Detect EDI version from GS segment. Optimized with early exit.
        
        Args:
            segments: List of EDI segments to analyze
            
        Returns:
            EDI version string (e.g., "005010X222") or None if not found
        """
        for seg in segments:
            if seg and seg[0] == "GS" and len(seg) > 8:
                return seg[8]
        return None

    def _detect_file_type(self, segments: List[List[str]]) -> str:
        """
        Detect file type (837 vs 835). Optimized with early exit.
        
        Args:
            segments: List of EDI segments to analyze
            
        Returns:
            File type string ("837" for claims, "835" for remittances)
        """
        for seg in segments:
            if not seg:
                continue
            seg_type = seg[0]
            if seg_type == "CLM":
                return "837"
            elif seg_type == "CLP":
                return "835"
        return "837"  # Default

    def _get_segment_order(self, segments: List[List[str]]) -> List[str]:
        """
        Get ordered list of unique segment types. Optimized with set lookup.
        
        Args:
            segments: List of EDI segments to analyze
            
        Returns:
            Ordered list of unique segment type identifiers (e.g., ["ISA", "GS", "ST", "CLM"])
        """
        seen = set()
        order = []
        for seg in segments:
            if not seg:
                continue
            seg_type = seg[0]
            if seg_type not in seen:
                seen.add(seg_type)
                order.append(seg_type)
        return order

    def _analyze_element_counts(self, segments: List[List[str]]) -> Dict[str, Dict]:
        """
        Analyze element count patterns per segment type. Optimized.
        
        Args:
            segments: List of EDI segments to analyze
            
        Returns:
            Dictionary mapping segment types to statistics (min, max, avg, most_common element counts)
        """
        element_counts = defaultdict(list)

        for seg in segments:
            if not seg:
                continue
            seg_type = seg[0]
            element_counts[seg_type].append(len(seg))

        # Calculate statistics
        stats = {}
        for seg_type, counts in element_counts.items():
            if counts:
                stats[seg_type] = {
                    "min": min(counts),
                    "max": max(counts),
                    "avg": sum(counts) / len(counts),
                    "most_common": Counter(counts).most_common(1)[0][0] if counts else None,
                }

        return stats

    def _analyze_date_formats(self, segments: List[List[str]]) -> Dict:
        """
        Analyze date format qualifiers used. Optimized.
        
        Args:
            segments: List of EDI segments to analyze
            
        Returns:
            Dictionary mapping date format qualifiers to their frequency counts
        """
        date_formats = Counter()

        for seg in segments:
            if seg and seg[0] == "DTP" and len(seg) > 2:
                date_formats[seg[2]] += 1

        return dict(date_formats)

    def _analyze_diagnosis_qualifiers(self, segments: List[List[str]]) -> Dict:
        """
        Analyze diagnosis code qualifiers used. Optimized.
        
        Args:
            segments: List of EDI segments to analyze
            
        Returns:
            Dictionary mapping diagnosis qualifiers (e.g., "ABK", "ABJ") to their frequency counts
        """
        qualifiers = Counter()

        for seg in segments:
            if not seg or seg[0] != "HI":
                continue
            seg_len = len(seg)
            # HI segments contain diagnosis codes with qualifiers
            for i in range(1, min(seg_len, 13)):  # HI01-HI12
                code_info = seg[i] if i < seg_len else ""
                if code_info and ">" in code_info:
                    qualifier = code_info.split(">", 1)[0]  # Split once only
                    qualifiers[qualifier] += 1

        return dict(qualifiers)

    def _analyze_facility_codes(self, segments: List[List[str]]) -> Dict:
        """
        Analyze facility type codes used. Optimized.
        
        Args:
            segments: List of EDI segments to analyze
            
        Returns:
            Dictionary mapping facility type codes to their frequency counts
        """
        facility_codes = Counter()

        for seg in segments:
            if not seg or seg[0] != "CLM" or len(seg) <= 5:
                continue
            location_info = seg[5]  # CLM05
            if location_info:
                # Extract facility code (first part before delimiter)
                if ">" in location_info:
                    facility_code = location_info.split(">", 1)[0][:2]  # Split once only
                elif ":" in location_info:
                    facility_code = location_info.split(":", 1)[0][:2]  # Split once only
                else:
                    facility_code = location_info[:2]

                if facility_code:
                    facility_codes[facility_code] += 1

        return dict(facility_codes)

    def compare_profiles(self, profile1: Dict, profile2: Dict) -> Dict:
        """
        Compare two format profiles and identify differences.

        Returns:
            Dict with comparison results
        """
        differences = {
            "segment_differences": {},
            "element_count_differences": {},
            "date_format_differences": {},
            "diagnosis_qualifier_differences": {},
            "facility_code_differences": {},
        }

        # Compare segment frequencies
        segs1 = set(profile1.get("segment_frequency", {}).keys())
        segs2 = set(profile2.get("segment_frequency", {}).keys())
        differences["segment_differences"] = {
            "only_in_1": list(segs1 - segs2),
            "only_in_2": list(segs2 - segs1),
            "common": list(segs1 & segs2),
        }

        # Compare element counts
        elem1 = profile1.get("element_counts", {})
        elem2 = profile2.get("element_counts", {})
        common_segments = set(elem1.keys()) & set(elem2.keys())
        for seg in common_segments:
            if elem1[seg].get("most_common") != elem2[seg].get("most_common"):
                differences["element_count_differences"][seg] = {
                    "profile1": elem1[seg].get("most_common"),
                    "profile2": elem2[seg].get("most_common"),
                }

        # Compare date formats
        dates1 = set(profile1.get("date_formats", {}).keys())
        dates2 = set(profile2.get("date_formats", {}).keys())
        differences["date_format_differences"] = {
            "only_in_1": list(dates1 - dates2),
            "only_in_2": list(dates2 - dates1),
        }

        # Compare diagnosis qualifiers
        diag1 = set(profile1.get("diagnosis_qualifiers", {}).keys())
        diag2 = set(profile2.get("diagnosis_qualifiers", {}).keys())
        differences["diagnosis_qualifier_differences"] = {
            "only_in_1": list(diag1 - diag2),
            "only_in_2": list(diag2 - diag1),
        }

        # Compare facility codes
        fac1 = set(profile1.get("facility_codes", {}).keys())
        fac2 = set(profile2.get("facility_codes", {}).keys())
        differences["facility_code_differences"] = {
            "only_in_1": list(fac1 - fac2),
            "only_in_2": list(fac2 - fac1),
        }

        return differences

