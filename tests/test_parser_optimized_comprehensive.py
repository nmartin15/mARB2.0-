"""Comprehensive tests for OptimizedEDIParser to improve coverage."""
import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

import pytest

from app.services.edi.parser_optimized import (
    OptimizedEDIParser,
    LARGE_FILE_THRESHOLD,
    STREAMING_FILE_THRESHOLD,
    BATCH_SIZE,
)


@pytest.fixture
def minimal_837_content() -> str:
    """Minimal valid 837 file content."""
    return """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
NM1*41*2*SAMPLE MEDICAL PRACTICE*****46*1234567890~
HL*1**20*1~
PRV*BI*PXC*207RI0001X~
NM1*85*2*DR JOHN SMITH*****XX*1234567890~
HL*2*1*22*0~
SBR*P*18*GROUP123******CI~
NM1*IL*1*DOE*JOHN*M***MI*123456789~
DMG*D8*19800101*M~
NM1*PR*2*BLUE CROSS BLUE SHIELD*****PI*BLUE_CROSS~
CLM*CLAIM001*1500.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241215~
DTP*472*D8*20241215~
REF*D9*PATIENT001~
HI*ABK:I10*E11.9~
LX*1~
SV1*HC:99213*1500.00*UN*1***1~
DTP*472*D8*20241215~
SE*24*0001~
GE*1*1~
IEA*1*000000001~"""


@pytest.fixture
def minimal_835_content() -> str:
    """Minimal valid 835 file content."""
    return """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HP*SENDERID*RECEIVERID*20241220*1340*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*1200.00*C*ACH*CCP*01*1234567890*DA*987654321*123456789*01*1234567890*DA*987654321*20241220~
TRN*1*1234567890*9876543210~
N1*PR*BLUE CROSS BLUE SHIELD~
N3*123 MAIN ST~
N4*CITY*ST*12345~
LX*1~
CLP*CLAIM001*1*1500.00*1200.00*0*MC*CLAIM001~
CAS*CO*45*100.00~
NM1*QC*1*DOE*JOHN*M***MI*123456789~
SE*24*0001~
GE*1*1~
IEA*1*000000001~"""


@pytest.fixture
def parser() -> OptimizedEDIParser:
    """Create OptimizedEDIParser instance."""
    return OptimizedEDIParser(practice_id=None, auto_detect_format=False)


@pytest.mark.unit
class TestParserFilePathParsing:
    """Test parsing with file_path parameter."""

    def test_parse_with_file_path(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test parsing using file_path parameter."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".837", delete=False) as f:
            f.write(minimal_837_content)
            temp_path = f.name

        try:
            result = parser.parse(file_path=temp_path, filename="test.837")
            assert result["file_type"] == "837"
            assert "claims" in result
        finally:
            os.unlink(temp_path)

    def test_parse_with_file_path_and_content(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test parsing with both file_path and file_content (file_path takes precedence)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".837", delete=False) as f:
            f.write(minimal_837_content)
            temp_path = f.name

        try:
            # file_path should be used, not file_content
            result = parser.parse(file_path=temp_path, file_content="invalid", filename="test.837")
            assert result["file_type"] == "837"
        finally:
            os.unlink(temp_path)

    def test_parse_with_file_path_nonexistent(self, parser: OptimizedEDIParser):
        """Test parsing with nonexistent file path."""
        with pytest.raises((FileNotFoundError, OSError)):
            parser.parse(file_path="/nonexistent/file.837", filename="test.837")

    def test_parse_without_file_path_or_content(self, parser: OptimizedEDIParser):
        """Test parsing without file_path or file_content raises error."""
        with pytest.raises(ValueError, match="Either file_content or file_path must be provided"):
            parser.parse(filename="test.837")


@pytest.mark.unit
class TestParserLargeFileRouting:
    """Test routing to streaming parser for large files."""

    def test_parse_routes_to_streaming_for_large_file(self, parser: OptimizedEDIParser):
        """Test that large files (>10MB) route to streaming parser."""
        # Create content that exceeds LARGE_FILE_THRESHOLD
        large_content = "ISA*00*01~" + ("CLM*001*1500.00~" * 100000)  # Large file
        
        with patch("app.services.edi.parser_optimized.StreamingEDIParser") as mock_streaming_class:
            mock_streaming_parser = MagicMock()
            mock_streaming_parser.parse.return_value = {
                "file_type": "837",
                "claims": [],
                "warnings": [],
            }
            mock_streaming_class.return_value = mock_streaming_parser

            # Mock file size to be large
            with patch("os.path.getsize", return_value=LARGE_FILE_THRESHOLD + 1):
                with patch("builtins.open", mock_open(read_data=large_content)):
                    result = parser.parse(file_path="/large/file.837", filename="large.837")
                    
                    # Should have called streaming parser
                    mock_streaming_class.assert_called_once()
                    assert result["file_type"] == "837"

    def test_parse_uses_standard_for_small_file(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test that small files use standard parser."""
        with patch("app.services.edi.parser_optimized.StreamingEDIParser") as mock_streaming_class:
            # Should not call streaming parser for small files
            result = parser.parse(file_content=minimal_837_content, filename="small.837")
            
            # Should not have called streaming parser
            mock_streaming_class.assert_not_called()
            assert result["file_type"] == "837"


@pytest.mark.unit
class TestParserStreamingMethods:
    """Test streaming parsing methods."""

    def test_parse_837_streaming_not_implemented(self, parser: OptimizedEDIParser):
        """Test that _parse_837_streaming raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            parser._parse_837_streaming([], {}, "test.837")

    def test_parse_835_streaming_not_implemented(self, parser: OptimizedEDIParser):
        """Test that _parse_835_streaming raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            parser._parse_835_streaming([], {}, "test.835")


@pytest.mark.unit
class TestParserErrorHandling:
    """Test error handling in parser methods."""

    def test_parse_claim_block_exception_handling(self, parser: OptimizedEDIParser):
        """Test that claim block parsing handles exceptions gracefully."""
        # Create block that might cause issues
        block = [["CLM"]]  # Incomplete CLM segment
        claim_data = parser._parse_claim_block(block, 0)
        
        # Should return incomplete claim, not raise exception
        assert claim_data["is_incomplete"] is True
        assert len(claim_data["warnings"]) > 0

    def test_parse_remittance_block_exception_handling(self, parser: OptimizedEDIParser):
        """Test that remittance block parsing handles exceptions gracefully."""
        # Create block that might cause issues
        block = [["CLP"]]  # Incomplete CLP segment
        remittance_data = parser._parse_remittance_block(block, 0, {}, {})
        
        # Should handle gracefully
        assert "warnings" in remittance_data

    def test_parse_837_with_exception_in_block(self, parser: OptimizedEDIParser):
        """Test that _parse_837 handles exceptions in claim blocks."""
        segments = [
            ["ISA", "00", "01"],
            ["GS", "HC", "01"],
            ["ST", "837", "01"],
            ["HL", "2", "1", "22", "0"],
            ["CLM"],  # Incomplete - might cause issues
        ]
        envelope = parser._parse_envelope(segments)
        
        # Should handle gracefully and continue processing
        result = parser._parse_837(segments, envelope, "test.837")
        assert result["file_type"] == "837"
        assert "claims" in result

    def test_parse_835_with_exception_in_block(self, parser: OptimizedEDIParser):
        """Test that _parse_835 handles exceptions in remittance blocks."""
        segments = [
            ["ISA", "00", "01"],
            ["GS", "HP", "01"],
            ["ST", "835", "01"],
            ["BPR", "I", "1200.00"],
            ["LX", "1"],
            ["CLP"],  # Incomplete - might cause issues
        ]
        envelope = parser._parse_envelope(segments)
        
        # Should handle gracefully and continue processing
        result = parser._parse_835(segments, envelope, "test.835")
        assert result["file_type"] == "835"
        assert "remittances" in result


@pytest.mark.unit
class TestParserBatchProcessing:
    """Test batch processing for large files."""

    def test_parse_837_batch_processing_large_file(self, parser: OptimizedEDIParser):
        """Test 837 parsing with batch processing for large files (>500 blocks)."""
        segments = [["ISA", "00", "01"], ["GS", "HC", "01"], ["ST", "837", "01"]]
        # Create more than 500 claim blocks to trigger batch processing
        for i in range(600):
            segments.append(["HL", str(i + 2), "1", "22", "0"])
            segments.append(["CLM", f"CLAIM{i:03d}", "1500.00"])
        
        envelope = parser._parse_envelope(segments)
        result = parser._parse_837(segments, envelope, "large.txt")
        
        assert result["claim_count"] == 600
        assert len(result["claims"]) == 600

    def test_parse_835_batch_processing_large_file(self, parser: OptimizedEDIParser):
        """Test 835 parsing with batch processing for large files (>500 blocks)."""
        segments = [["ISA", "00", "01"], ["GS", "HP", "01"], ["ST", "835", "01"]]
        segments.append(["BPR", "I", "12000.00"])
        # Create more than 500 remittance blocks
        for i in range(600):
            segments.append(["LX", str(i + 1)])
            segments.append(["CLP", f"CLAIM{i:03d}", "1", "1500.00", "1200.00"])
        
        envelope = parser._parse_envelope(segments)
        bpr_data = parser._extract_bpr_segment(segments)
        payer_data = parser._extract_payer_from_835(segments)
        result = parser._parse_835(segments, envelope, "large.txt")
        
        assert result["remittance_count"] == 600
        assert len(result["remittances"]) == 600


@pytest.mark.unit
class TestParserHelperMethods:
    """Test helper methods with edge cases."""

    def test_find_segment_with_index_error(self, parser: OptimizedEDIParser):
        """Test _find_segment handles IndexError gracefully."""
        segments = [[]]  # Empty segment
        result = parser._find_segment(segments, "ISA")
        assert result is None

    def test_find_segment_in_block_with_index_error(self, parser: OptimizedEDIParser):
        """Test _find_segment_in_block handles IndexError gracefully."""
        block = [[]]  # Empty segment
        result = parser._find_segment_in_block(block, "CLM")
        assert result is None

    def test_parse_decimal_with_whitespace(self, parser: OptimizedEDIParser):
        """Test _parse_decimal handles whitespace correctly."""
        assert parser._parse_decimal("  1500.00  ") == 1500.0
        assert parser._parse_decimal("1500.00") == 1500.0
        assert parser._parse_decimal("  ") is None

    def test_parse_decimal_with_attribute_error(self, parser: OptimizedEDIParser):
        """Test _parse_decimal handles AttributeError (non-string input)."""
        assert parser._parse_decimal(None) is None
        # Should handle gracefully if passed non-string

    def test_parse_decimal_with_type_error(self, parser: OptimizedEDIParser):
        """Test _parse_decimal handles TypeError."""
        # Passing a dict or list should return None
        assert parser._parse_decimal({"amount": 1500}) is None

    def test_split_segments_with_newlines(self, parser: OptimizedEDIParser):
        """Test _split_segments handles newlines correctly."""
        content = "ISA*00*01~\r\nGS*HC*01~\nST*837*01~"
        segments = parser._split_segments(content)
        assert len(segments) == 3
        assert segments[0][0] == "ISA"
        assert segments[1][0] == "GS"
        assert segments[2][0] == "ST"

    def test_split_segments_with_whitespace_only(self, parser: OptimizedEDIParser):
        """Test _split_segments handles whitespace-only segments."""
        content = "ISA*00*01~   ~GS*HC*01~"
        segments = parser._split_segments(content)
        # Should filter out whitespace-only segments
        assert len(segments) >= 2

    def test_split_segments_streaming_with_newlines(self, parser: OptimizedEDIParser):
        """Test _split_segments_streaming handles newlines."""
        content = "ISA*00*01~\r\nGS*HC*01~\nST*837*01~"
        segments = list(parser._split_segments_streaming(content))
        assert len(segments) == 3

    def test_split_segments_streaming_trailing_segment(self, parser: OptimizedEDIParser):
        """Test _split_segments_streaming handles trailing segment without delimiter."""
        content = "ISA*00*01~GS*HC*01~ST*837*01"  # No final ~
        segments = list(parser._split_segments_streaming(content))
        assert len(segments) == 3


@pytest.mark.unit
class TestParserEnvelopeParsing:
    """Test envelope parsing edge cases."""

    def test_parse_envelope_streaming_with_missing_segments(self, parser: OptimizedEDIParser):
        """Test envelope streaming parsing with missing segments."""
        content = "ST*837*01~"  # Missing ISA and GS
        segments_gen = parser._split_segments_streaming(content)
        envelope, file_type, initial_segments = parser._parse_envelope_streaming(segments_gen)
        
        assert "st" in envelope
        assert file_type == "837"  # Fallback detection

    def test_parse_envelope_streaming_fallback_to_clm(self, parser: OptimizedEDIParser):
        """Test envelope streaming fallback to CLM for file type detection."""
        content = "ISA*00*01~ST*837*01~CLM*001*1500.00~"
        segments_gen = parser._split_segments_streaming(content)
        envelope, file_type, initial_segments = parser._parse_envelope_streaming(segments_gen)
        
        assert file_type == "837"

    def test_parse_envelope_streaming_fallback_to_clp(self, parser: OptimizedEDIParser):
        """Test envelope streaming fallback to CLP for file type detection."""
        content = "ISA*00*01~ST*835*01~CLP*001*1*1500.00~"
        segments_gen = parser._split_segments_streaming(content)
        envelope, file_type, initial_segments = parser._parse_envelope_streaming(segments_gen)
        
        assert file_type == "835"

    def test_parse_envelope_streaming_defaults_to_837(self, parser: OptimizedEDIParser):
        """Test envelope streaming defaults to 837 if type cannot be determined."""
        content = "ISA*00*01~ST*UNKNOWN*01~"
        segments_gen = parser._split_segments_streaming(content)
        envelope, file_type, initial_segments = parser._parse_envelope_streaming(segments_gen)
        
        assert file_type == "837"  # Default


@pytest.mark.unit
class TestParserRemittanceBlockParsing:
    """Test remittance block parsing edge cases."""

    def test_parse_remittance_block_with_multiple_cas_segments(self, parser: OptimizedEDIParser):
        """Test remittance block parsing with multiple CAS segments."""
        block = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00", "1200.00"],
            ["CAS", "CO", "45", "100.00", "46", "50.00"],
            ["CAS", "PR", "1", "25.00"],
        ]
        remittance_data = parser._parse_remittance_block(block, 0, {}, {})
        
        assert len(remittance_data["adjustments"]) > 0
        assert len(remittance_data["co_adjustments"]) > 0
        assert len(remittance_data["pr_adjustments"]) > 0

    def test_parse_remittance_block_with_incomplete_cas(self, parser: OptimizedEDIParser):
        """Test remittance block parsing with incomplete CAS segment."""
        block = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00"],
            ["CAS", "CO", "45"],  # Missing amount
        ]
        remittance_data = parser._parse_remittance_block(block, 0, {}, {})
        
        # Should handle gracefully
        assert "adjustments" in remittance_data

    def test_parse_remittance_block_with_bpr_data(self, parser: OptimizedEDIParser):
        """Test remittance block parsing includes BPR data."""
        block = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00", "1200.00"],
        ]
        bpr_data = {
            "transaction_handling_code": "I",
            "total_payment_amount": 1200.00,
        }
        remittance_data = parser._parse_remittance_block(block, 0, bpr_data, {})
        
        assert remittance_data["transaction_handling_code"] == "I"
        assert remittance_data["total_payment_amount"] == 1200.00

    def test_parse_remittance_block_with_payer_data(self, parser: OptimizedEDIParser):
        """Test remittance block parsing includes payer data."""
        block = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00", "1200.00"],
        ]
        payer_data = {
            "name": "BLUE CROSS",
            "address": "123 MAIN ST",
        }
        remittance_data = parser._parse_remittance_block(block, 0, {}, payer_data)
        
        assert remittance_data["payer"]["name"] == "BLUE CROSS"
        assert remittance_data["payer"]["address"] == "123 MAIN ST"


@pytest.mark.unit
class TestParserExtractMethods:
    """Test extraction methods with edge cases."""

    def test_extract_bpr_segment_with_partial_data(self, parser: OptimizedEDIParser):
        """Test BPR extraction with partial data."""
        segments = [["BPR", "I", "1200.00"]]  # Missing many fields
        bpr_data = parser._extract_bpr_segment(segments)
        
        assert "transaction_handling_code" in bpr_data
        assert bpr_data["transaction_handling_code"] == "I"

    def test_extract_payer_from_835_with_n3_n4(self, parser: OptimizedEDIParser):
        """Test payer extraction includes N3 and N4 segments."""
        segments = [
            ["N1", "PR", "BLUE CROSS"],
            ["N3", "123 MAIN ST"],
            ["N4", "CITY", "ST", "12345"],
        ]
        payer_data = parser._extract_payer_from_835(segments)
        
        assert payer_data["name"] == "BLUE CROSS"
        assert payer_data["address"] == "123 MAIN ST"
        assert payer_data["city"] == "CITY"
        assert payer_data["state"] == "ST"
        assert payer_data["zip"] == "12345"

    def test_extract_payer_from_835_stops_at_termination(self, parser: OptimizedEDIParser):
        """Test payer extraction stops at termination segments."""
        segments = [
            ["N1", "PR", "BLUE CROSS"],
            ["N3", "123 MAIN ST"],
            ["LX", "1"],  # Termination segment
            ["N4", "CITY", "ST", "12345"],  # Should be ignored
        ]
        payer_data = parser._extract_payer_from_835(segments)
        
        assert payer_data["name"] == "BLUE CROSS"
        assert "address" in payer_data
        assert "city" not in payer_data  # Should stop at LX


@pytest.mark.unit
class TestParserBlockExtraction:
    """Test block extraction methods."""

    def test_get_claim_blocks_with_nested_hl(self, parser: OptimizedEDIParser):
        """Test claim block extraction with nested HL segments."""
        segments = [
            ["HL", "1", "", "20", "1"],
            ["HL", "2", "1", "22", "0"],  # First claim
            ["CLM", "001", "1500.00"],
            ["HL", "3", "2", "23", "0"],  # Nested (line level)
            ["LX", "1"],
            ["SV1", "HC:99213", "1500.00"],
            ["HL", "4", "1", "22", "0"],  # Second claim
            ["CLM", "002", "2000.00"],
        ]
        claim_blocks = parser._get_claim_blocks(segments)
        
        assert len(claim_blocks) == 2

    def test_get_remittance_blocks_stops_at_se(self, parser: OptimizedEDIParser):
        """Test remittance blocks stop at SE segment."""
        segments = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00"],
            ["SE", "3", "01"],  # Termination
            ["LX", "2"],
            ["CLP", "CLAIM002", "1", "2000.00"],
        ]
        remittance_blocks = parser._get_remittance_blocks(segments)
        
        # Should have at least one block before SE
        assert len(remittance_blocks) >= 1

    def test_get_remittance_blocks_stops_at_ge(self, parser: OptimizedEDIParser):
        """Test remittance blocks stop at GE segment."""
        segments = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00"],
            ["GE", "1", "1"],  # Termination
        ]
        remittance_blocks = parser._get_remittance_blocks(segments)
        
        # Should have block before GE
        assert len(remittance_blocks) >= 1


@pytest.mark.unit
class TestParserFileTypeDetection:
    """Test file type detection edge cases."""

    def test_detect_file_type_from_gs_version_837(self, parser: OptimizedEDIParser):
        """Test file type detection from GS segment version (837)."""
        segments = [["GS", "HC", "SENDER", "RECEIVER", "20241220", "1340", "1", "X", "005010X222A1"]]
        file_type = parser._detect_file_type(segments)
        assert file_type == "837"

    def test_detect_file_type_from_gs_version_835(self, parser: OptimizedEDIParser):
        """Test file type detection from GS segment version (835)."""
        segments = [["GS", "HP", "SENDER", "RECEIVER", "20241220", "1340", "1", "X", "005010X221A1"]]
        file_type = parser._detect_file_type(segments)
        assert file_type == "835"

    def test_detect_file_type_fallback_to_clm(self, parser: OptimizedEDIParser):
        """Test file type detection fallback to CLM."""
        segments = [["CLM", "001", "1500.00"]]
        file_type = parser._detect_file_type(segments)
        assert file_type == "837"

    def test_detect_file_type_fallback_to_clp(self, parser: OptimizedEDIParser):
        """Test file type detection fallback to CLP."""
        segments = [["CLP", "001", "1", "1500.00"]]
        file_type = parser._detect_file_type(segments)
        assert file_type == "835"

    def test_detect_file_type_defaults_to_837(self, parser: OptimizedEDIParser):
        """Test file type detection defaults to 837 if uncertain."""
        segments = [["UNKNOWN", "SEGMENT"]]
        file_type = parser._detect_file_type(segments)
        assert file_type == "837"


@pytest.mark.unit
class TestParserMemoryOptimization:
    """Test memory optimization features."""

    def test_parse_837_memory_cleanup(self, parser: OptimizedEDIParser):
        """Test that _parse_837 performs memory cleanup for large files."""
        segments = [["ISA", "00", "01"], ["GS", "HC", "01"], ["ST", "837", "01"]]
        # Create large file (>500 blocks)
        for i in range(600):
            segments.append(["HL", str(i + 2), "1", "22", "0"])
            segments.append(["CLM", f"CLAIM{i:03d}", "1500.00"])
        
        envelope = parser._parse_envelope(segments)
        
        # Should complete without memory issues
        result = parser._parse_837(segments, envelope, "large.txt")
        assert result["claim_count"] == 600

    def test_parse_835_memory_cleanup(self, parser: OptimizedEDIParser):
        """Test that _parse_835 performs memory cleanup for large files."""
        segments = [["ISA", "00", "01"], ["GS", "HP", "01"], ["ST", "835", "01"]]
        segments.append(["BPR", "I", "12000.00"])
        # Create large file (>500 blocks)
        for i in range(600):
            segments.append(["LX", str(i + 1)])
            segments.append(["CLP", f"CLAIM{i:03d}", "1", "1500.00", "1200.00"])
        
        envelope = parser._parse_envelope(segments)
        bpr_data = parser._extract_bpr_segment(segments)
        payer_data = parser._extract_payer_from_835(segments)
        
        # Should complete without memory issues
        result = parser._parse_835(segments, envelope, "large.txt")
        assert result["remittance_count"] == 600
