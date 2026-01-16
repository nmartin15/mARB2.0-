"""Tests for format detector module."""
import pytest

from app.services.edi.format_detector import FormatDetector


@pytest.mark.unit
class TestFormatDetector:
    """Test FormatDetector class."""

    def test_init(self):
        """Test FormatDetector initialization."""
        detector = FormatDetector()
        assert detector.segment_patterns is not None
        assert detector.element_patterns is not None
        assert detector.date_formats is not None
        assert detector.diagnosis_qualifiers is not None
        assert detector.facility_codes is not None

    def test_analyze_file_basic_837(self):
        """Test analyzing a basic 837 file."""
        detector = FormatDetector()
        segments = [
            ["ISA", "00", "          ", "00", "          ", "ZZ", "PAYER001", "ZZ", "PROVIDER001", "241220", "143052", "*", "00501", "000000001", "0", "P", ":"],
            ["GS", "HC", "PAYER001", "PROVIDER001", "20241220", "143052", "1", "X", "005010X222A1"],
            ["ST", "837", "0001", "005010X222A1"],
            ["CLM", "CLAIM001", "1500.00", "", "", "11", "1234567890"],
            ["DTP", "431", "D8", "20241215"],
            ["HI", "BK", "E11.9>"],
            ["SBR", "P", "18", "GROUP001", "", "", "", "", "", "CI", "123456789"],
            ["NM1", "IL", "1", "DOE", "JOHN", "", "", "", "MI", "123456789"],
            ["SE", "8", "0001"],
            ["GE", "1", "1"],
            ["IEA", "1", "000000001"],
        ]

        profile = detector.analyze_file(segments)

        assert profile["file_type"] == "837"
        assert profile["version"] == "005010X222A1"
        assert "segment_frequency" in profile
        assert "CLM" in profile["segment_frequency"]
        assert profile["segment_frequency"]["CLM"] == 1
        assert "segment_order" in profile
        assert "CLM" in profile["segment_order"]
        assert "element_counts" in profile
        assert "date_formats" in profile

    def test_analyze_file_basic_835(self):
        """Test analyzing a basic 835 file."""
        detector = FormatDetector()
        segments = [
            ["ISA", "00", "          ", "00", "          ", "ZZ", "PAYER001", "ZZ", "PROVIDER001", "241220", "143052", "*", "00501", "000000001", "0", "P", ":"],
            ["GS", "HP", "PAYER001", "PROVIDER001", "20241220", "143052", "1", "X", "005010X221A1"],
            ["ST", "835", "0001", "005010X221A1"],
            ["CLP", "CLAIM001", "1", "1500.00", "1200.00", "0", "11", "1234567890"],
            ["CAS", "PR", "1", "50.00"],
            ["SE", "5", "0001"],
            ["GE", "1", "1"],
            ["IEA", "1", "000000001"],
        ]

        profile = detector.analyze_file(segments)

        assert profile["file_type"] == "835"
        assert profile["version"] == "005010X221A1"
        assert "CLP" in profile["segment_frequency"]
        assert profile["segment_frequency"]["CLP"] == 1

    def test_detect_version_from_gs(self):
        """Test version detection from GS segment."""
        detector = FormatDetector()
        segments = [
            ["GS", "HC", "PAYER001", "PROVIDER001", "20241220", "143052", "1", "X", "005010X222A1"],
        ]

        version = detector._detect_version(segments)
        assert version == "005010X222A1"

    def test_detect_version_no_gs(self):
        """Test version detection when GS segment is missing."""
        detector = FormatDetector()
        segments = [
            ["ST", "837", "0001"],
        ]

        version = detector._detect_version(segments)
        assert version is None

    def test_detect_version_gs_too_short(self):
        """Test version detection when GS segment is too short."""
        detector = FormatDetector()
        segments = [
            ["GS", "HC", "PAYER001"],
        ]

        version = detector._detect_version(segments)
        assert version is None

    def test_detect_file_type_837(self):
        """Test file type detection for 837."""
        detector = FormatDetector()
        segments = [
            ["CLM", "CLAIM001", "1500.00"],
        ]

        file_type = detector._detect_file_type(segments)
        assert file_type == "837"

    def test_detect_file_type_835(self):
        """Test file type detection for 835."""
        detector = FormatDetector()
        segments = [
            ["CLP", "CLAIM001", "1", "1500.00"],
        ]

        file_type = detector._detect_file_type(segments)
        assert file_type == "835"

    def test_detect_file_type_default(self):
        """Test file type detection defaults to 837."""
        detector = FormatDetector()
        segments = [
            ["ST", "837", "0001"],
        ]

        file_type = detector._detect_file_type(segments)
        assert file_type == "837"

    def test_get_segment_order(self):
        """Test getting segment order."""
        detector = FormatDetector()
        segments = [
            ["ISA"],
            ["GS"],
            ["ST"],
            ["CLM"],
            ["GS"],  # Duplicate
            ["SE"],
        ]

        order = detector._get_segment_order(segments)
        assert order == ["ISA", "GS", "ST", "CLM", "SE"]
        assert len(order) == 5

    def test_get_segment_order_empty(self):
        """Test getting segment order from empty segments."""
        detector = FormatDetector()
        segments = []

        order = detector._get_segment_order(segments)
        assert order == []

    def test_get_segment_order_with_empty_segments(self):
        """Test getting segment order with empty segment lists."""
        detector = FormatDetector()
        segments = [
            ["ISA"],
            [],  # Empty segment
            ["GS"],
            None,  # None segment
        ]

        order = detector._get_segment_order(segments)
        assert "ISA" in order
        assert "GS" in order

    def test_analyze_element_counts(self):
        """Test analyzing element counts per segment type."""
        detector = FormatDetector()
        segments = [
            ["CLM", "CLAIM001", "1500.00"],  # 3 elements
            ["CLM", "CLAIM002", "2000.00", "EXTRA"],  # 4 elements
            ["DTP", "431", "D8", "20241215"],  # 4 elements
        ]

        stats = detector._analyze_element_counts(segments)

        assert "CLM" in stats
        assert stats["CLM"]["min"] == 3
        assert stats["CLM"]["max"] == 4
        assert stats["CLM"]["avg"] == 3.5
        assert stats["CLM"]["most_common"] in [3, 4]

        assert "DTP" in stats
        assert stats["DTP"]["min"] == 4
        assert stats["DTP"]["max"] == 4

    def test_analyze_element_counts_empty(self):
        """Test analyzing element counts with empty segments."""
        detector = FormatDetector()
        segments = []

        stats = detector._analyze_element_counts(segments)
        assert stats == {}

    def test_analyze_date_formats(self):
        """Test analyzing date formats."""
        detector = FormatDetector()
        segments = [
            ["DTP", "431", "D8", "20241215"],
            ["DTP", "472", "D8", "20241215"],
            ["DTP", "431", "RD8", "20241215-20241220"],
            ["DTP", "431", "D8", "20241216"],
        ]

        date_formats = detector._analyze_date_formats(segments)

        assert "D8" in date_formats
        assert date_formats["D8"] == 3
        assert "RD8" in date_formats
        assert date_formats["RD8"] == 1

    def test_analyze_date_formats_no_dtp(self):
        """Test analyzing date formats with no DTP segments."""
        detector = FormatDetector()
        segments = [
            ["CLM", "CLAIM001", "1500.00"],
        ]

        date_formats = detector._analyze_date_formats(segments)
        assert date_formats == {}

    def test_analyze_date_formats_short_segment(self):
        """Test analyzing date formats with short DTP segment."""
        detector = FormatDetector()
        segments = [
            ["DTP", "431"],  # Too short
        ]

        date_formats = detector._analyze_date_formats(segments)
        assert date_formats == {}

    def test_analyze_diagnosis_qualifiers(self):
        """Test analyzing diagnosis qualifiers."""
        detector = FormatDetector()
        segments = [
            ["HI", "BK>E11.9", "ABK>E78.5"],
            ["HI", "BF>I10"],
        ]

        qualifiers = detector._analyze_diagnosis_qualifiers(segments)

        assert "BK" in qualifiers
        assert qualifiers["BK"] == 1
        assert "ABK" in qualifiers
        assert qualifiers["ABK"] == 1
        assert "BF" in qualifiers
        assert qualifiers["BF"] == 1

    def test_analyze_diagnosis_qualifiers_no_hi(self):
        """Test analyzing diagnosis qualifiers with no HI segments."""
        detector = FormatDetector()
        segments = [
            ["CLM", "CLAIM001", "1500.00"],
        ]

        qualifiers = detector._analyze_diagnosis_qualifiers(segments)
        assert qualifiers == {}

    def test_analyze_diagnosis_qualifiers_no_delimiter(self):
        """Test analyzing diagnosis qualifiers without delimiter."""
        detector = FormatDetector()
        segments = [
            ["HI", "E11.9"],  # No delimiter
        ]

        qualifiers = detector._analyze_diagnosis_qualifiers(segments)
        assert qualifiers == {}

    def test_analyze_facility_codes(self):
        """Test analyzing facility codes."""
        detector = FormatDetector()
        segments = [
            ["CLM", "CLAIM001", "1500.00", "", "", "11>HOSPITAL"],
            ["CLM", "CLAIM002", "2000.00", "", "", "21>CLINIC"],
            ["CLM", "CLAIM003", "3000.00", "", "", "11>HOSPITAL2"],
        ]

        facility_codes = detector._analyze_facility_codes(segments)

        assert "11" in facility_codes
        assert facility_codes["11"] == 2
        assert "21" in facility_codes
        assert facility_codes["21"] == 1

    def test_analyze_facility_codes_colon_delimiter(self):
        """Test analyzing facility codes with colon delimiter."""
        detector = FormatDetector()
        segments = [
            ["CLM", "CLAIM001", "1500.00", "", "", "11:HOSPITAL"],
        ]

        facility_codes = detector._analyze_facility_codes(segments)

        assert "11" in facility_codes
        assert facility_codes["11"] == 1

    def test_analyze_facility_codes_no_delimiter(self):
        """Test analyzing facility codes without delimiter."""
        detector = FormatDetector()
        segments = [
            ["CLM", "CLAIM001", "1500.00", "", "", "11HOSPITAL"],
        ]

        facility_codes = detector._analyze_facility_codes(segments)

        assert "11" in facility_codes
        assert facility_codes["11"] == 1

    def test_analyze_facility_codes_no_clm(self):
        """Test analyzing facility codes with no CLM segments."""
        detector = FormatDetector()
        segments = [
            ["DTP", "431", "D8", "20241215"],
        ]

        facility_codes = detector._analyze_facility_codes(segments)
        assert facility_codes == {}

    def test_analyze_facility_codes_short_segment(self):
        """Test analyzing facility codes with short CLM segment."""
        detector = FormatDetector()
        segments = [
            ["CLM", "CLAIM001"],  # Too short
        ]

        facility_codes = detector._analyze_facility_codes(segments)
        assert facility_codes == {}

    def test_compare_profiles(self):
        """Test comparing two format profiles."""
        detector = FormatDetector()

        profile1 = {
            "segment_frequency": {"CLM": 5, "DTP": 3, "HI": 2},
            "element_counts": {
                "CLM": {"most_common": 6},
                "DTP": {"most_common": 4},
            },
            "date_formats": {"D8": 3, "RD8": 1},
            "diagnosis_qualifiers": {"BK": 2, "BF": 1},
            "facility_codes": {"11": 3, "21": 2},
        }

        profile2 = {
            "segment_frequency": {"CLM": 3, "DTP": 5, "SBR": 2},
            "element_counts": {
                "CLM": {"most_common": 7},  # Different
                "DTP": {"most_common": 4},
            },
            "date_formats": {"D8": 5},
            "diagnosis_qualifiers": {"BK": 1, "ABK": 2},
            "facility_codes": {"11": 2, "22": 1},
        }

        differences = detector.compare_profiles(profile1, profile2)

        # Check segment differences
        assert "HI" in differences["segment_differences"]["only_in_1"]
        assert "SBR" in differences["segment_differences"]["only_in_2"]
        assert "CLM" in differences["segment_differences"]["common"]
        assert "DTP" in differences["segment_differences"]["common"]

        # Check element count differences
        assert "CLM" in differences["element_count_differences"]
        assert differences["element_count_differences"]["CLM"]["profile1"] == 6
        assert differences["element_count_differences"]["CLM"]["profile2"] == 7

        # Check date format differences
        assert "RD8" in differences["date_format_differences"]["only_in_1"]

        # Check diagnosis qualifier differences
        assert "BF" in differences["diagnosis_qualifier_differences"]["only_in_1"]
        assert "ABK" in differences["diagnosis_qualifier_differences"]["only_in_2"]

        # Check facility code differences
        assert "21" in differences["facility_code_differences"]["only_in_1"]
        assert "22" in differences["facility_code_differences"]["only_in_2"]

    def test_compare_profiles_empty(self):
        """Test comparing empty profiles."""
        detector = FormatDetector()

        profile1 = {}
        profile2 = {}

        differences = detector.compare_profiles(profile1, profile2)

        assert "segment_differences" in differences
        assert "element_count_differences" in differences
        assert "date_format_differences" in differences

    def test_analyze_file_comprehensive(self):
        """Test comprehensive file analysis with all features."""
        detector = FormatDetector()
        segments = [
            ["ISA", "00", "          ", "00", "          ", "ZZ", "PAYER001", "ZZ", "PROVIDER001", "241220", "143052", "*", "00501", "000000001", "0", "P", ":"],
            ["GS", "HC", "PAYER001", "PROVIDER001", "20241220", "143052", "1", "X", "005010X222A1"],
            ["ST", "837", "0001", "005010X222A1"],
            ["CLM", "CLAIM001", "1500.00", "", "", "11>HOSPITAL", "1234567890"],
            ["DTP", "431", "D8", "20241215"],
            ["DTP", "472", "RD8", "20241215-20241220"],
            ["HI", "BK>E11.9", "ABK>E78.5"],
            ["HI", "BF>I10"],
            ["SBR", "P", "18", "GROUP001"],
            ["NM1", "IL", "1", "DOE", "JOHN"],
            ["SE", "10", "0001"],
            ["GE", "1", "1"],
            ["IEA", "1", "000000001"],
        ]

        profile = detector.analyze_file(segments)

        # Verify all profile keys exist
        assert "segment_frequency" in profile
        assert "segment_order" in profile
        assert "element_counts" in profile
        assert "date_formats" in profile
        assert "diagnosis_qualifiers" in profile
        assert "facility_codes" in profile
        assert "version" in profile
        assert "file_type" in profile

        # Verify specific values
        assert profile["file_type"] == "837"
        assert profile["version"] == "005010X222A1"
        assert "D8" in profile["date_formats"]
        assert "RD8" in profile["date_formats"]
        assert "BK" in profile["diagnosis_qualifiers"]
        assert "11" in profile["facility_codes"]

