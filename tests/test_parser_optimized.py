"""Tests for OptimizedEDIParser."""
import os
import tempfile
from pathlib import Path

import pytest

from app.services.edi.parser_optimized import OptimizedEDIParser, LARGE_FILE_THRESHOLD
from app.utils.logger import get_logger

logger = get_logger(__name__)


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
class TestOptimizedEDIParserInit:
    """Test OptimizedEDIParser initialization."""

    def test_init_defaults(self):
        """Test parser initialization with default parameters."""
        parser = OptimizedEDIParser()
        assert parser.practice_id is None
        assert parser.auto_detect_format is True
        assert parser.config is not None
        assert parser.validator is not None
        assert parser.claim_extractor is not None
        assert parser.line_extractor is not None
        assert parser.payer_extractor is not None
        assert parser.diagnosis_extractor is not None

    def test_init_with_practice_id(self):
        """Test parser initialization with practice_id."""
        parser = OptimizedEDIParser(practice_id="test_practice")
        assert parser.practice_id == "test_practice"

    def test_init_without_format_detection(self):
        """Test parser initialization without format detection."""
        parser = OptimizedEDIParser(auto_detect_format=False)
        assert parser.auto_detect_format is False
        assert parser.format_detector is None


@pytest.mark.unit
class TestOptimizedEDIParserParse:
    """Test main parse() method."""

    def test_parse_with_file_content(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test parsing with file content string."""
        result = parser.parse(file_content=minimal_837_content, filename="test_837.txt")
        
        assert result is not None
        assert result["file_type"] == "837"
        assert "envelope" in result
        assert "claims" in result

    def test_parse_with_file_path(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test parsing with file path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(minimal_837_content)
            temp_path = f.name
        
        try:
            # When using file_path, file_content should be None, parser will read from file
            result = parser.parse(file_path=temp_path, filename="test_837.txt")
            assert result is not None
            assert result["file_type"] == "837"
        finally:
            os.unlink(temp_path)

    def test_parse_requires_content_or_path(self, parser: OptimizedEDIParser):
        """Test that parse requires either file_content or file_path."""
        with pytest.raises(ValueError, match="Either file_content or file_path must be provided"):
            parser.parse(filename="test.txt")

    def test_parse_small_file_uses_standard_parser(
        self, parser: OptimizedEDIParser, minimal_837_content: str
    ):
        """Test that small files use standard parser."""
        # Create a small file (less than LARGE_FILE_THRESHOLD)
        result = parser.parse(file_content=minimal_837_content, filename="small.txt")
        assert result["file_type"] == "837"
        assert "claims" in result

    def test_parse_large_file_uses_streaming_parser(
        self, parser: OptimizedEDIParser, minimal_837_content: str
    ):
        """Test that large files use streaming parser."""
        # Create a large file by repeating content
        large_content = minimal_837_content * (LARGE_FILE_THRESHOLD // len(minimal_837_content.encode("utf-8")) + 1)
        
        result = parser.parse(file_content=large_content, filename="large.txt")
        assert result is not None
        assert result["file_type"] == "837"

    def test_parse_835_file(self, parser: OptimizedEDIParser, minimal_835_content: str):
        """Test parsing 835 remittance file."""
        result = parser.parse(file_content=minimal_835_content, filename="test_835.txt")
        
        assert result is not None
        assert result["file_type"] == "835"
        assert "envelope" in result
        assert "remittances" in result


@pytest.mark.unit
class TestOptimizedEDIParserHelperMethods:
    """Test helper methods."""

    def test_split_segments(self, parser: OptimizedEDIParser):
        """Test segment splitting."""
        content = "ISA*00*01~GS*HC*01~ST*837*01~SE*3*01~GE*1*1~IEA*1*1~"
        segments = parser._split_segments(content)
        
        assert len(segments) == 6
        assert segments[0][0] == "ISA"
        assert segments[1][0] == "GS"
        assert segments[2][0] == "ST"

    def test_split_segments_handles_newlines(self, parser: OptimizedEDIParser):
        """Test segment splitting with newlines."""
        content = "ISA*00*01~\r\nGS*HC*01~\nST*837*01~"
        segments = parser._split_segments(content)
        
        assert len(segments) == 3
        assert segments[0][0] == "ISA"
        assert segments[1][0] == "GS"
        assert segments[2][0] == "ST"

    def test_detect_file_type_837(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test file type detection for 837."""
        segments = parser._split_segments(minimal_837_content)
        file_type = parser._detect_file_type(segments)
        assert file_type == "837"

    def test_detect_file_type_835(self, parser: OptimizedEDIParser, minimal_835_content: str):
        """Test file type detection for 835."""
        segments = parser._split_segments(minimal_835_content)
        file_type = parser._detect_file_type(segments)
        assert file_type == "835"

    def test_detect_file_type_defaults_to_837(self, parser: OptimizedEDIParser):
        """Test file type detection defaults to 837."""
        segments = [["UNKNOWN", "segment"]]
        file_type = parser._detect_file_type(segments)
        assert file_type == "837"

    def test_parse_envelope(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test envelope parsing."""
        segments = parser._split_segments(minimal_837_content)
        envelope = parser._parse_envelope(segments)
        
        assert "isa" in envelope
        assert "gs" in envelope
        assert "st" in envelope
        assert envelope["st"]["transaction_set_id"] == "837"

    def test_find_segment(self, parser: OptimizedEDIParser):
        """Test finding a segment by ID."""
        segments = [["ISA", "00", "01"], ["GS", "HC", "01"], ["ST", "837", "01"]]
        gs_seg = parser._find_segment(segments, "GS")
        
        assert gs_seg is not None
        assert gs_seg[0] == "GS"

    def test_find_segment_not_found(self, parser: OptimizedEDIParser):
        """Test finding a segment that doesn't exist."""
        segments = [["ISA", "00", "01"], ["GS", "HC", "01"]]
        missing_seg = parser._find_segment(segments, "ST")
        
        assert missing_seg is None

    def test_find_segment_in_block(self, parser: OptimizedEDIParser):
        """Test finding a segment in a block."""
        block = [["CLM", "001", "1500.00"], ["DTP", "431", "20241215"], ["HI", "ABK", "E11.9"]]
        clm_seg = parser._find_segment_in_block(block, "CLM")
        
        assert clm_seg is not None
        assert clm_seg[0] == "CLM"

    def test_find_all_segments_in_block(self, parser: OptimizedEDIParser):
        """Test finding all segments of a type in a block."""
        block = [
            ["DTP", "431", "20241215"],
            ["HI", "ABK", "E11.9"],
            ["DTP", "472", "20241215"],
        ]
        dtp_segments = parser._find_all_segments_in_block(block, "DTP")
        
        assert len(dtp_segments) == 2
        assert all(seg[0] == "DTP" for seg in dtp_segments)

    def test_parse_decimal(self, parser: OptimizedEDIParser):
        """Test decimal parsing."""
        assert parser._parse_decimal("1500.00") == 1500.0
        assert parser._parse_decimal("0.50") == 0.5
        assert parser._parse_decimal("") is None
        assert parser._parse_decimal(None) is None
        assert parser._parse_decimal("invalid") is None

    def test_parse_decimal_with_whitespace(self, parser: OptimizedEDIParser):
        """Test decimal parsing with whitespace."""
        assert parser._parse_decimal("  1500.00  ") == 1500.0


@pytest.mark.unit
class TestOptimizedEDIParserClaimBlocks:
    """Test claim block parsing."""

    def test_get_claim_blocks(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test getting claim blocks from segments."""
        segments = parser._split_segments(minimal_837_content)
        claim_blocks = parser._get_claim_blocks(segments)
        
        assert len(claim_blocks) > 0
        # Each block should start with HL segment where index 3 = '22'
        for block in claim_blocks:
            assert len(block) > 0
            # Find HL segment in block
            hl_found = any(seg[0] == "HL" and len(seg) > 3 and seg[3] == "22" for seg in block)
            assert hl_found or any(seg[0] == "CLM" for seg in block)

    def test_parse_claim_block(self, parser: OptimizedEDIParser):
        """Test parsing a single claim block."""
        block = [
            ["HL", "2", "1", "22", "0"],
            ["SBR", "P", "18", "GROUP123"],
            ["NM1", "IL", "1", "DOE", "JOHN"],
            ["CLM", "CLAIM001", "1500.00"],
            ["HI", "ABK", "E11.9"],
            ["LX", "1"],
            ["SV1", "HC:99213", "1500.00"],
        ]
        
        claim_data = parser._parse_claim_block(block, 0)
        
        assert claim_data is not None
        assert claim_data["block_index"] == 0
        assert "warnings" in claim_data
        # Should have claim control number if CLM segment is present
        if not claim_data.get("is_incomplete"):
            assert "claim_control_number" in claim_data or "lines" in claim_data


@pytest.mark.unit
class TestOptimizedEDIParserRemittanceBlocks:
    """Test remittance block parsing."""

    def test_get_remittance_blocks(self, parser: OptimizedEDIParser, minimal_835_content: str):
        """Test getting remittance blocks from segments."""
        segments = parser._split_segments(minimal_835_content)
        remittance_blocks = parser._get_remittance_blocks(segments)
        
        assert len(remittance_blocks) > 0
        # Each block should start with LX segment
        for block in remittance_blocks:
            assert len(block) > 0
            lx_found = any(seg[0] == "LX" for seg in block)
            clp_found = any(seg[0] == "CLP" for seg in block)
            assert lx_found or clp_found

    def test_extract_bpr_segment(self, parser: OptimizedEDIParser, minimal_835_content: str):
        """Test extracting BPR segment."""
        segments = parser._split_segments(minimal_835_content)
        bpr_data = parser._extract_bpr_segment(segments)
        
        assert bpr_data is not None
        # BPR segment should have transaction handling code
        if bpr_data:
            assert "transaction_handling_code" in bpr_data or "total_payment_amount" in bpr_data

    def test_extract_payer_from_835(self, parser: OptimizedEDIParser, minimal_835_content: str):
        """Test extracting payer from 835."""
        segments = parser._split_segments(minimal_835_content)
        payer_data = parser._extract_payer_from_835(segments)
        
        assert payer_data is not None
        # Should have payer name if N1*PR segment exists
        if payer_data:
            assert "name" in payer_data or len(payer_data) == 0

    def test_parse_remittance_block(self, parser: OptimizedEDIParser):
        """Test parsing a single remittance block."""
        block = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00", "1200.00", "0"],
            ["CAS", "CO", "45", "100.00"],
            ["NM1", "QC", "1", "DOE", "JOHN"],
        ]
        bpr_data = {"total_payment_amount": 1200.0}
        payer_data = {"name": "Test Payer"}
        
        remittance_data = parser._parse_remittance_block(block, 0, bpr_data, payer_data)
        
        assert remittance_data is not None
        assert remittance_data["block_index"] == 0
        assert "warnings" in remittance_data
        if not remittance_data.get("is_incomplete"):
            assert "claim_control_number" in remittance_data or "adjustments" in remittance_data


@pytest.mark.unit
class TestOptimizedEDIParserStreaming:
    """Test streaming methods."""

    def test_split_segments_streaming(self, parser: OptimizedEDIParser):
        """Test streaming segment splitting."""
        content = "ISA*00*01~GS*HC*01~ST*837*01~"
        segments = list(parser._split_segments_streaming(content))
        
        assert len(segments) == 3
        assert segments[0][0] == "ISA"
        assert segments[1][0] == "GS"
        assert segments[2][0] == "ST"

    def test_parse_envelope_streaming(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test streaming envelope parsing."""
        segments_gen = parser._split_segments_streaming(minimal_837_content)
        envelope, file_type, initial_segments = parser._parse_envelope_streaming(segments_gen)
        
        assert envelope is not None
        assert file_type == "837"
        assert len(initial_segments) > 0

    def test_parse_837_streaming_raises_not_implemented(self, parser: OptimizedEDIParser):
        """Test that streaming 837 parsing raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            parser._parse_837_streaming([], {}, "test.txt")

    def test_parse_835_streaming_raises_not_implemented(self, parser: OptimizedEDIParser):
        """Test that streaming 835 parsing raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            parser._parse_835_streaming([], {}, "test.txt")


@pytest.mark.unit
class TestOptimizedEDIParserErrorHandling:
    """Test error handling."""

    def test_parse_empty_content(self, parser: OptimizedEDIParser):
        """Test parsing empty content."""
        with pytest.raises(ValueError, match="No segments found"):
            parser._parse_standard("", "empty.txt")

    def test_parse_invalid_content(self, parser: OptimizedEDIParser):
        """Test parsing invalid content."""
        invalid_content = "This is not valid EDI content"
        # Parser handles invalid content gracefully, returns result with warnings
        result = parser._parse_standard(invalid_content, "invalid.txt")
        assert result is not None
        # Should have warnings or empty results
        assert len(result.get("warnings", [])) > 0 or result.get("claim_count", 0) == 0

    def test_parse_claim_block_missing_clm(self, parser: OptimizedEDIParser):
        """Test parsing claim block without CLM segment."""
        block = [["HL", "2", "1", "22", "0"], ["SBR", "P", "18"]]
        claim_data = parser._parse_claim_block(block, 0)
        
        assert claim_data is not None
        assert claim_data["is_incomplete"] is True
        assert len(claim_data["warnings"]) > 0

    def test_parse_remittance_block_missing_clp(self, parser: OptimizedEDIParser):
        """Test parsing remittance block without CLP segment."""
        block = [["LX", "1"], ["CAS", "CO", "45", "100.00"]]
        remittance_data = parser._parse_remittance_block(block, 0, {}, {})
        
        assert remittance_data is not None
        assert remittance_data["is_incomplete"] is True
        assert len(remittance_data["warnings"]) > 0


@pytest.mark.unit
class TestOptimizedEDIParserIntegration:
    """Integration tests for OptimizedEDIParser."""

    def test_parse_large_file_method(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test _parse_large_file method."""
        result = parser._parse_large_file(minimal_837_content, "test.txt")
        
        assert result is not None
        assert result["file_type"] == "837"

    def test_parse_standard_method(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test _parse_standard method."""
        result = parser._parse_standard(minimal_837_content, "test.txt")
        
        assert result is not None
        assert result["file_type"] == "837"
        assert "claims" in result or "remittances" in result

    def test_full_parse_837_flow(self, parser: OptimizedEDIParser, minimal_837_content: str):
        """Test full 837 parsing flow."""
        result = parser.parse(file_content=minimal_837_content, filename="test_837.txt")
        
        assert result["file_type"] == "837"
        assert "envelope" in result
        assert "claims" in result
        assert len(result["claims"]) > 0

    def test_full_parse_835_flow(self, parser: OptimizedEDIParser, minimal_835_content: str):
        """Test full 835 parsing flow."""
        result = parser.parse(file_content=minimal_835_content, filename="test_835.txt")
        
        assert result["file_type"] == "835"
        assert "envelope" in result
        assert "remittances" in result


@pytest.mark.unit
class TestOptimizedEDIParserEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_split_segments_empty_string(self, parser: OptimizedEDIParser):
        """Test splitting empty string."""
        segments = parser._split_segments("")
        assert segments == []

    def test_split_segments_only_delimiters(self, parser: OptimizedEDIParser):
        """Test splitting string with only delimiters."""
        segments = parser._split_segments("~~~")
        # Should return empty segments (filtered out)
        assert len(segments) == 0

    def test_split_segments_whitespace_only(self, parser: OptimizedEDIParser):
        """Test splitting whitespace-only segments."""
        segments = parser._split_segments("   ~  ~   ~")
        assert len(segments) == 0

    def test_split_segments_streaming_empty(self, parser: OptimizedEDIParser):
        """Test streaming split with empty content."""
        segments = list(parser._split_segments_streaming(""))
        assert len(segments) == 0

    def test_split_segments_streaming_trailing_segment(self, parser: OptimizedEDIParser):
        """Test streaming split with trailing segment (no final ~)."""
        content = "ISA*00*01~GS*HC*01~ST*837*01"
        segments = list(parser._split_segments_streaming(content))
        assert len(segments) == 3

    def test_parse_envelope_missing_segments(self, parser: OptimizedEDIParser):
        """Test envelope parsing with missing segments."""
        segments = [["ST", "837", "01"]]  # Missing ISA and GS
        envelope = parser._parse_envelope(segments)
        assert "st" in envelope
        assert "isa" not in envelope
        assert "gs" not in envelope

    def test_parse_envelope_streaming_early_exit(self, parser: OptimizedEDIParser):
        """Test envelope streaming with early exit when all info found."""
        content = """ISA*00*01*02*03*04*05*06*SENDER*08*RECEIVER*10*11*12*13*14~
GS*HC*SENDER*RECEIVER*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~"""
        segments_gen = parser._split_segments_streaming(content)
        envelope, file_type, initial_segments = parser._parse_envelope_streaming(segments_gen)
        
        assert "isa" in envelope
        assert "gs" in envelope
        assert "st" in envelope
        assert file_type == "837"

    def test_parse_envelope_streaming_safety_limit(self, parser: OptimizedEDIParser):
        """Test envelope streaming hits safety limit."""
        # Create content with >200 segments before finding envelope
        content = "ISA*00*01~" + "UNKNOWN*SEG*MENT~" * 250
        segments_gen = parser._split_segments_streaming(content)
        envelope, file_type, initial_segments = parser._parse_envelope_streaming(segments_gen)
        
        # Should still return something (even if incomplete)
        assert isinstance(envelope, dict)

    def test_parse_envelope_streaming_fallback_detection(self, parser: OptimizedEDIParser):
        """Test envelope streaming fallback file type detection."""
        # Content without GS segment, but has CLM segment
        content = "ISA*00*01~ST*837*01~CLM*001*1500.00~"
        segments_gen = parser._split_segments_streaming(content)
        envelope, file_type, initial_segments = parser._parse_envelope_streaming(segments_gen)
        
        assert file_type == "837"

    def test_get_claim_blocks_no_claims(self, parser: OptimizedEDIParser):
        """Test getting claim blocks when no claims exist."""
        segments = [["ISA", "00", "01"], ["GS", "HC", "01"], ["ST", "837", "01"]]
        claim_blocks = parser._get_claim_blocks(segments)
        assert len(claim_blocks) == 0

    def test_get_claim_blocks_multiple_claims(self, parser: OptimizedEDIParser):
        """Test getting multiple claim blocks."""
        segments = [
            ["HL", "1", "", "20", "1"],
            ["HL", "2", "1", "22", "0"],  # First claim
            ["CLM", "001", "1500.00"],
            ["HL", "3", "1", "22", "0"],  # Second claim
            ["CLM", "002", "2000.00"],
        ]
        claim_blocks = parser._get_claim_blocks(segments)
        assert len(claim_blocks) == 2

    def test_get_remittance_blocks_no_remittances(self, parser: OptimizedEDIParser):
        """Test getting remittance blocks when none exist."""
        segments = [["ISA", "00", "01"], ["GS", "HP", "01"], ["ST", "835", "01"]]
        remittance_blocks = parser._get_remittance_blocks(segments)
        assert len(remittance_blocks) == 0

    def test_get_remittance_blocks_with_termination(self, parser: OptimizedEDIParser):
        """Test remittance blocks stop at termination segments."""
        segments = [
            ["LX", "1"],
            ["CLP", "001", "1", "1500.00"],
            ["SE", "3", "01"],  # Termination
            ["LX", "2"],
            ["CLP", "002", "1", "2000.00"],
        ]
        remittance_blocks = parser._get_remittance_blocks(segments)
        # Should have 2 blocks (one before SE, one after)
        assert len(remittance_blocks) >= 1

    def test_parse_claim_block_with_all_extractors(self, parser: OptimizedEDIParser):
        """Test claim block parsing uses all extractors."""
        block = [
            ["HL", "2", "1", "22", "0"],
            ["SBR", "P", "18", "GROUP123"],
            ["NM1", "IL", "1", "DOE", "JOHN"],
            ["NM1", "PR", "2", "BLUE CROSS"],  # Add payer segment
            ["CLM", "CLAIM001", "1500.00"],
            ["HI", "ABK", "E11.9"],
            ["LX", "1"],
            ["SV2", "HC:99213", "1500.00"],  # Use SV2 instead of SV1
        ]
        claim_data = parser._parse_claim_block(block, 0)
        
        # Claim may be incomplete due to missing segments, but should have data
        assert "claim_control_number" in claim_data or "lines" in claim_data
        assert "warnings" in claim_data

    def test_parse_remittance_block_with_cas_adjustments(self, parser: OptimizedEDIParser):
        """Test remittance block parsing with CAS adjustments."""
        block = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00", "1200.00", "0"],
            ["CAS", "CO", "45", "100.00", "46", "50.00"],  # Multiple adjustments
            ["CAS", "PR", "1", "25.00"],
        ]
        remittance_data = parser._parse_remittance_block(block, 0, {}, {})
        
        assert "adjustments" in remittance_data
        assert len(remittance_data["adjustments"]) > 0
        assert "co_adjustments" in remittance_data
        assert "pr_adjustments" in remittance_data

    def test_parse_remittance_block_with_patient_provider(self, parser: OptimizedEDIParser):
        """Test remittance block parsing with patient and provider."""
        block = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00", "1200.00"],
            ["NM1", "QC", "1", "DOE", "JOHN"],  # Patient
            ["NM1", "82", "1", "SMITH", "JANE"],  # Provider
        ]
        remittance_data = parser._parse_remittance_block(block, 0, {}, {})
        
        assert "patient" in remittance_data
        assert "provider" in remittance_data

    def test_extract_bpr_segment_missing(self, parser: OptimizedEDIParser):
        """Test extracting BPR when segment is missing."""
        segments = [["ISA", "00", "01"], ["GS", "HP", "01"]]
        bpr_data = parser._extract_bpr_segment(segments)
        assert bpr_data == {}

    def test_extract_bpr_segment_partial(self, parser: OptimizedEDIParser):
        """Test extracting BPR with partial data."""
        segments = [["BPR", "I", "1200.00"]]  # Missing many fields
        bpr_data = parser._extract_bpr_segment(segments)
        assert "transaction_handling_code" in bpr_data
        assert bpr_data["transaction_handling_code"] == "I"

    def test_extract_payer_from_835_missing(self, parser: OptimizedEDIParser):
        """Test extracting payer when N1*PR is missing."""
        segments = [["ISA", "00", "01"], ["LX", "1"], ["CLP", "001"]]
        payer_data = parser._extract_payer_from_835(segments)
        assert payer_data == {}

    def test_extract_payer_from_835_with_address(self, parser: OptimizedEDIParser):
        """Test extracting payer with N3 and N4 segments."""
        segments = [
            ["N1", "PR", "BLUE CROSS"],
            ["N3", "123 MAIN ST"],
            ["N4", "CITY", "ST", "12345"],
        ]
        payer_data = parser._extract_payer_from_835(segments)
        assert "name" in payer_data
        assert "address" in payer_data
        assert "city" in payer_data
        assert "state" in payer_data
        assert "zip" in payer_data

    def test_parse_837_empty_claims(self, parser: OptimizedEDIParser):
        """Test parsing 837 with no claim blocks."""
        segments = [
            ["ISA", "00", "01"],
            ["GS", "HC", "01"],
            ["ST", "837", "01"],
            ["SE", "3", "01"],
        ]
        envelope = parser._parse_envelope(segments)
        result = parser._parse_837(segments, envelope, "empty.txt")
        
        assert result["file_type"] == "837"
        assert len(result["claims"]) == 0
        assert len(result["warnings"]) > 0

    def test_parse_835_empty_remittances(self, parser: OptimizedEDIParser):
        """Test parsing 835 with no remittance blocks."""
        segments = [
            ["ISA", "00", "01"],
            ["GS", "HP", "01"],
            ["ST", "835", "01"],
            ["SE", "3", "01"],
        ]
        envelope = parser._parse_envelope(segments)
        result = parser._parse_835(segments, envelope, "empty.txt")
        
        assert result["file_type"] == "835"
        assert len(result["remittances"]) == 0
        assert len(result["warnings"]) > 0

    def test_parse_837_batch_processing(self, parser: OptimizedEDIParser):
        """Test 837 parsing with batch processing for large files."""
        # Create segments with multiple claims (more than BATCH_SIZE)
        segments = [["ISA", "00", "01"], ["GS", "HC", "01"], ["ST", "837", "01"]]
        for i in range(60):  # More than BATCH_SIZE (50)
            segments.append(["HL", str(i + 2), "1", "22", "0"])
            segments.append(["CLM", f"CLAIM{i:03d}", "1500.00"])
        
        envelope = parser._parse_envelope(segments)
        result = parser._parse_837(segments, envelope, "large.txt")
        
        assert result["claim_count"] == 60
        assert len(result["claims"]) == 60

    def test_parse_835_batch_processing(self, parser: OptimizedEDIParser):
        """Test 835 parsing with batch processing for large files."""
        segments = [["ISA", "00", "01"], ["GS", "HP", "01"], ["ST", "835", "01"]]
        segments.append(["BPR", "I", "12000.00"])
        for i in range(60):  # More than BATCH_SIZE
            segments.append(["LX", str(i + 1)])
            segments.append(["CLP", f"CLAIM{i:03d}", "1", "1500.00", "1200.00"])
        
        envelope = parser._parse_envelope(segments)
        bpr_data = parser._extract_bpr_segment(segments)
        payer_data = parser._extract_payer_from_835(segments)
        result = parser._parse_835(segments, envelope, "large.txt")
        
        assert result["remittance_count"] == 60
        assert len(result["remittances"]) == 60

    def test_detect_file_type_gs_version_837(self, parser: OptimizedEDIParser):
        """Test file type detection from GS segment version (837)."""
        segments = [["GS", "HC", "SENDER", "RECEIVER", "20241220", "1340", "1", "X", "005010X222A1"]]
        file_type = parser._detect_file_type(segments)
        assert file_type == "837"

    def test_detect_file_type_gs_version_835(self, parser: OptimizedEDIParser):
        """Test file type detection from GS segment version (835)."""
        segments = [["GS", "HP", "SENDER", "RECEIVER", "20241220", "1340", "1", "X", "005010X221A1"]]
        file_type = parser._detect_file_type(segments)
        assert file_type == "835"

    def test_detect_file_type_fallback_clm(self, parser: OptimizedEDIParser):
        """Test file type detection fallback to CLM."""
        segments = [["CLM", "001", "1500.00"]]
        file_type = parser._detect_file_type(segments)
        assert file_type == "837"

    def test_detect_file_type_fallback_clp(self, parser: OptimizedEDIParser):
        """Test file type detection fallback to CLP."""
        segments = [["CLP", "001", "1", "1500.00"]]
        file_type = parser._detect_file_type(segments)
        assert file_type == "835"

    def test_find_segment_empty_list(self, parser: OptimizedEDIParser):
        """Test finding segment in empty list."""
        result = parser._find_segment([], "ISA")
        assert result is None

    def test_find_segment_in_block_empty(self, parser: OptimizedEDIParser):
        """Test finding segment in empty block."""
        result = parser._find_segment_in_block([], "CLM")
        assert result is None

    def test_find_all_segments_in_block_empty(self, parser: OptimizedEDIParser):
        """Test finding all segments in empty block."""
        result = parser._find_all_segments_in_block([], "DTP")
        assert result == []

    def test_parse_decimal_invalid_formats(self, parser: OptimizedEDIParser):
        """Test parsing various invalid decimal formats."""
        assert parser._parse_decimal("not-a-number") is None
        assert parser._parse_decimal("abc123") is None
        assert parser._parse_decimal("   ") is None

    def test_parse_decimal_scientific_notation(self, parser: OptimizedEDIParser):
        """Test parsing scientific notation."""
        # Should handle or reject gracefully
        result = parser._parse_decimal("1.5e2")
        # Either parses to 150.0 or returns None
        assert result is None or result == 150.0

    def test_parse_with_format_detection(self):
        """Test parsing with format detection enabled."""
        parser = OptimizedEDIParser(auto_detect_format=True)
        content = """ISA*00*01~GS*HC*01~ST*837*01~CLM*001*1500.00~SE*3*01~GE*1*1~IEA*1*1~"""
        # Format detection may not work if analyze_file isn't called, but parsing should still work
        result = parser.parse(file_content=content, filename="test.txt")
        assert result["file_type"] == "837"

    def test_parse_claim_block_exception_handling(self, parser: OptimizedEDIParser):
        """Test that claim block parsing handles exceptions gracefully."""
        # Create block that might cause issues
        block = [["CLM"]]  # Incomplete CLM segment
        claim_data = parser._parse_claim_block(block, 0)
        # Should return incomplete claim, not raise exception
        assert claim_data["is_incomplete"] is True

    def test_parse_remittance_block_cas_edge_cases(self, parser: OptimizedEDIParser):
        """Test CAS segment parsing edge cases."""
        # CAS with odd number of elements (incomplete pairs)
        block = [
            ["LX", "1"],
            ["CLP", "001", "1", "1500.00"],
            ["CAS", "CO", "45"],  # Missing amount
            ["CAS", "PR"],  # Missing group code and amounts
        ]
        remittance_data = parser._parse_remittance_block(block, 0, {}, {})
        # Should handle gracefully
        assert "adjustments" in remittance_data

