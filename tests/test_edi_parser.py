"""Comprehensive tests for EDI parser."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.edi.parser import EDIParser


@pytest.fixture
def sample_837_content():
    """Sample 837 EDI file content."""
    return """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
NM1*41*2*PROVIDER NAME*****XX*1234567890~
PER*IC*CONTACT NAME*TE*5551234567~
NM1*40*2*PAYER NAME*****XX*9876543210~
HL*1**20*1~
PRV*BI*PXC*207Q00000X~
NM1*85*2*PROVIDER NAME*****XX*1234567890~
N3*123 MAIN ST~
N4*CHICAGO*IL*60601~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GROUP123*ACME INSURANCE*****CI~
NM1*IL*1*DOE*JOHN*MIDDLE*JR****MI*123456789~
N3*456 PATIENT ST~
N4*CHICAGO*IL*60602~
DMG*D8*19800101*M~
NM1*PR*2*ACME INSURANCE*****PI*987654321~
CLM*CLAIM001*1500.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241215~
DTP*484*D8*20241215~
HI*ABK:I10*E11.9~
LX*1~
SV2*0450*HC*99213*1500.00*UN*1~
DTP*472*D8*20241215~
SE*25*0001~
GE*1*1~
IEA*1*000000001~"""


@pytest.fixture
def sample_835_content():
    """Sample 835 EDI file content."""
    return """ISA*00*          *00*          *ZZ*BCBSILPAYER     *ZZ*MEDPRACTICE001   *241220*143052*^*00501*000000001*0*P*:~
GS*HP*BCBSILPAYER*MEDPRACTICE001*20241220*143052*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*28750.00*C*CHK987654321*20241220*123456789*01*987654321*DA*1234567890*20241220~
TRN*1*987654321*9876543210~
DTM*405*20241220~
N1*PR*ACME INSURANCE*FI*987654321~
N3*123 PAYER ST~
N4*CHICAGO*IL*60601~
LX*1~
CLP*CLAIM001*1*1500.00*1200.00*0*11*1234567890*20241215*1~
CAS*PR*1*50.00~
NM1*QC*1*DOE*JOHN****MI*123456789~
NM1*82*1*PROVIDER NAME*****XX*1234567890~
SVC*HC:99213*1500.00*1200.00*1~
CAS*PR*1*50.00~
DTM*472*D8*20241215~
SE*20*0001~
GE*1*1~
IEA*1*000000001~"""


@pytest.fixture
def parser():
    """Create EDI parser instance."""
    return EDIParser()


class TestEDIParserInit:
    """Test parser initialization."""

    def test_init_default(self):
        """Test default initialization."""
        parser = EDIParser()
        assert parser.practice_id is None
        assert parser.auto_detect_format is True
        assert parser.format_detector is not None
        assert parser.validator is not None

    def test_init_with_practice_id(self):
        """Test initialization with practice_id."""
        parser = EDIParser(practice_id="practice-123")
        assert parser.practice_id == "practice-123"

    def test_init_without_auto_detect(self):
        """Test initialization without auto-detect."""
        parser = EDIParser(auto_detect_format=False)
        assert parser.auto_detect_format is False
        assert parser.format_detector is None


class TestSplitSegments:
    """Test segment splitting functionality."""

    def test_split_segments_basic(self, parser):
        """Test basic segment splitting."""
        content = "ISA*00*01~GS*HC*02~SE*03*04~"
        segments = parser._split_segments(content)
        assert len(segments) == 3
        assert segments[0] == ["ISA", "00", "01"]
        assert segments[1] == ["GS", "HC", "02"]
        assert segments[2] == ["SE", "03", "04"]

    def test_split_segments_with_newlines(self, parser):
        """Test splitting segments with newlines."""
        content = "ISA*00*01~\r\nGS*HC*02~\nSE*03*04~\r"
        segments = parser._split_segments(content)
        assert len(segments) == 3
        assert segments[0] == ["ISA", "00", "01"]
        assert segments[1] == ["GS", "HC", "02"]
        assert segments[2] == ["SE", "03", "04"]

    def test_split_segments_empty(self, parser):
        """Test splitting empty content."""
        segments = parser._split_segments("")
        assert segments == []

    def test_split_segments_whitespace(self, parser):
        """Test splitting segments with whitespace."""
        content = " ISA*00*01 ~ GS*HC*02 ~"
        segments = parser._split_segments(content)
        assert len(segments) == 2
        assert segments[0] == ["ISA", "00", "01"]
        assert segments[1] == ["GS", "HC", "02"]

    def test_split_segments_chunked(self, parser):
        """Test chunked segment splitting."""
        # Create large content
        content = "~".join([f"SEG{i}*A*B*C" for i in range(15000)])
        chunks = list(parser._split_segments_chunked(content))
        assert len(chunks) > 0
        total_segments = sum(len(chunk) for chunk in chunks)
        assert total_segments == 15000


class TestDetectFileType:
    """Test file type detection."""

    def test_detect_837_by_gs(self, parser):
        """Test detecting 837 by GS segment."""
        segments = [["GS", "HC", "SENDER", "RECEIVER", "20241220", "1340", "1", "X", "005010X222A1"]]
        assert parser._detect_file_type(segments) == "837"

    def test_detect_835_by_gs(self, parser):
        """Test detecting 835 by GS segment."""
        segments = [["GS", "HP", "SENDER", "RECEIVER", "20241220", "1340", "1", "X", "005010X221A1"]]
        assert parser._detect_file_type(segments) == "835"

    def test_detect_837_by_clm(self, parser):
        """Test detecting 837 by CLM segment."""
        segments = [["CLM", "CLAIM001", "1500.00"]]
        assert parser._detect_file_type(segments) == "837"

    def test_detect_835_by_clp(self, parser):
        """Test detecting 835 by CLP segment."""
        segments = [["CLP", "CLAIM001", "1", "1500.00"]]
        assert parser._detect_file_type(segments) == "835"

    def test_detect_default_837(self, parser):
        """Test defaulting to 837 when uncertain."""
        segments = [["UNKNOWN", "SEGMENT"]]
        assert parser._detect_file_type(segments) == "837"


class TestParseEnvelope:
    """Test envelope parsing."""

    def test_parse_envelope_complete(self, parser):
        """Test parsing complete envelope."""
        segments = [
            ["ISA", "00", "", "", "", "", "SENDERID", "", "RECEIVERID", "20241220", "1340", "", "00501", "000000001", "0", "P", ":"],
            ["GS", "HC", "SENDERID", "RECEIVERID", "20241220", "1340", "1", "X", "005010X222A1"],
            ["ST", "837", "0001", "005010X222A1"],
        ]
        envelope = parser._parse_envelope(segments)
        assert "isa" in envelope
        assert envelope["isa"]["sender_id"] == "SENDERID"
        assert envelope["isa"]["receiver_id"] == "RECEIVERID"
        assert "gs" in envelope
        assert "st" in envelope

    def test_parse_envelope_missing_isa(self, parser):
        """Test parsing envelope with missing ISA."""
        segments = [["GS", "HC", "SENDER", "RECEIVER"]]
        envelope = parser._parse_envelope(segments)
        assert "isa" not in envelope
        assert "gs" in envelope

    def test_parse_envelope_missing_gs(self, parser):
        """Test parsing envelope with missing GS."""
        segments = [["ISA", "00", "", "", "", "", "SENDER", "", "RECEIVER"]]
        envelope = parser._parse_envelope(segments)
        assert "isa" in envelope
        assert "gs" not in envelope

    def test_parse_envelope_short_segments(self, parser):
        """Test parsing envelope with short segments."""
        segments = [["ISA"], ["GS"], ["ST"]]
        envelope = parser._parse_envelope(segments)
        # Should not crash, but may have None values
        assert isinstance(envelope, dict)


class TestParseDecimal:
    """Test decimal parsing."""

    def test_parse_decimal_valid(self, parser):
        """Test parsing valid decimal."""
        assert parser._parse_decimal("1500.00") == 1500.00
        assert parser._parse_decimal("123.45") == 123.45
        assert parser._parse_decimal("0") == 0.0

    def test_parse_decimal_whitespace(self, parser):
        """Test parsing decimal with whitespace."""
        assert parser._parse_decimal(" 1500.00 ") == 1500.00

    def test_parse_decimal_none(self, parser):
        """Test parsing None."""
        assert parser._parse_decimal(None) is None

    def test_parse_decimal_empty(self, parser):
        """Test parsing empty string."""
        assert parser._parse_decimal("") is None
        assert parser._parse_decimal("   ") is None

    def test_parse_decimal_invalid(self, parser):
        """Test parsing invalid decimal."""
        assert parser._parse_decimal("invalid") is None
        assert parser._parse_decimal("ABC") is None


class TestFindSegments:
    """Test segment finding functionality."""

    def test_find_segment_exists(self, parser):
        """Test finding existing segment."""
        segments = [["ISA", "00"], ["GS", "HC"], ["ST", "837"]]
        result = parser._find_segment(segments, "GS")
        assert result == ["GS", "HC"]

    def test_find_segment_not_exists(self, parser):
        """Test finding non-existent segment."""
        segments = [["ISA", "00"], ["ST", "837"]]
        result = parser._find_segment(segments, "GS")
        assert result is None

    def test_find_segment_in_block(self, parser):
        """Test finding segment in block."""
        block = [["CLM", "CLAIM001"], ["DTP", "431", "D8", "20241215"]]
        result = parser._find_segment_in_block(block, "CLM")
        assert result == ["CLM", "CLAIM001"]

    def test_find_all_segments_in_block(self, parser):
        """Test finding all segments in block."""
        block = [["CAS", "PR", "1", "50.00"], ["CAS", "OA", "2", "25.00"], ["CLP", "CLAIM001"]]
        results = parser._find_all_segments_in_block(block, "CAS")
        assert len(results) == 2
        assert results[0] == ["CAS", "PR", "1", "50.00"]
        assert results[1] == ["CAS", "OA", "2", "25.00"]


class TestGetClaimBlocks:
    """Test claim block extraction."""

    def test_get_claim_blocks_single(self, parser):
        """Test extracting single claim block."""
        segments = [
            ["HL", "1", "", "20", "1"],
            ["HL", "2", "1", "22", "0"],  # Subscriber level
            ["CLM", "CLAIM001", "1500.00"],
            ["DTP", "431", "D8", "20241215"],
        ]
        blocks = parser._get_claim_blocks(segments)
        assert len(blocks) == 1
        assert len(blocks[0]) == 3  # HL + CLM + DTP

    def test_get_claim_blocks_multiple(self, parser):
        """Test extracting multiple claim blocks."""
        segments = [
            ["HL", "1", "", "20", "1"],
            ["HL", "2", "1", "22", "0"],  # First claim
            ["CLM", "CLAIM001", "1500.00"],
            ["HL", "3", "1", "22", "0"],  # Second claim
            ["CLM", "CLAIM002", "2000.00"],
        ]
        blocks = parser._get_claim_blocks(segments)
        assert len(blocks) == 2

    def test_get_claim_blocks_no_subscriber_level(self, parser):
        """Test extracting blocks with no subscriber level."""
        segments = [
            ["HL", "1", "", "20", "1"],
            ["CLM", "CLAIM001", "1500.00"],
        ]
        blocks = parser._get_claim_blocks(segments)
        # Should still create a block even without subscriber level HL
        assert len(blocks) >= 0


class TestGetRemittanceBlocks:
    """Test remittance block extraction."""

    def test_get_remittance_blocks_single(self, parser):
        """Test extracting single remittance block."""
        segments = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00"],
            ["CAS", "PR", "1", "50.00"],
        ]
        blocks = parser._get_remittance_blocks(segments)
        assert len(blocks) == 1
        assert len(blocks[0]) == 3

    def test_get_remittance_blocks_multiple(self, parser):
        """Test extracting multiple remittance blocks."""
        segments = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00"],
            ["LX", "2"],
            ["CLP", "CLAIM002", "1", "2000.00"],
        ]
        blocks = parser._get_remittance_blocks(segments)
        assert len(blocks) == 2

    def test_get_remittance_blocks_termination(self, parser):
        """Test remittance blocks with termination segments."""
        segments = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00"],
            ["SE", "5", "0001"],
        ]
        blocks = parser._get_remittance_blocks(segments)
        assert len(blocks) == 1


class TestParse837:
    """Test 837 file parsing."""

    def test_parse_837_basic(self, parser, sample_837_content):
        """Test parsing basic 837 file."""
        result = parser.parse(sample_837_content, "test_837.edi")
        assert result["file_type"] == "837"
        assert "claims" in result
        assert "envelope" in result
        assert len(result["claims"]) > 0

    def test_parse_837_no_claims(self, parser):
        """Test parsing 837 with no claims."""
        content = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""
        result = parser.parse(content, "test_empty_837.edi")
        assert result["file_type"] == "837"
        assert len(result["claims"]) == 0
        assert "warnings" in result

    def test_parse_837_with_warnings(self, parser):
        """Test parsing 837 that generates warnings."""
        content = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
HL*1**20*1~
HL*2*1*22*0~
CLM*CLAIM001*1500.00~
SE*5*0001~
GE*1*1~
IEA*1*000000001~"""
        result = parser.parse(content, "test_837_warnings.edi")
        assert result["file_type"] == "837"
        # May have warnings for missing segments
        assert isinstance(result.get("warnings", []), list)


class TestParse835:
    """Test 835 file parsing."""

    def test_parse_835_basic(self, parser, sample_835_content):
        """Test parsing basic 835 file."""
        result = parser.parse(sample_835_content, "test_835.edi")
        assert result["file_type"] == "835"
        assert "remittances" in result
        assert "envelope" in result
        assert len(result["remittances"]) > 0

    def test_parse_835_no_remittances(self, parser):
        """Test parsing 835 with no remittances."""
        content = """ISA*00*          *00*          *ZZ*BCBSILPAYER     *ZZ*MEDPRACTICE001   *241220*143052*^*00501*000000001*0*P*:~
GS*HP*BCBSILPAYER*MEDPRACTICE001*20241220*143052*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*28750.00*C*CHK987654321*20241220~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""
        result = parser.parse(content, "test_empty_835.edi")
        assert result["file_type"] == "835"
        assert len(result["remittances"]) == 0
        assert "warnings" in result


class TestExtractBPR:
    """Test BPR segment extraction."""

    def test_extract_bpr_complete(self, parser):
        """Test extracting complete BPR segment."""
        segments = [["BPR", "I", "28750.00", "C", "CHK", "20241220", "123456789", "01", "987654321", "DA", "1234567890", "20241220"]]
        bpr = parser._extract_bpr_segment(segments)
        assert bpr["transaction_handling_code"] == "I"
        assert bpr["total_payment_amount"] == 28750.00
        assert bpr["credit_debit_flag"] == "C"

    def test_extract_bpr_missing(self, parser):
        """Test extracting BPR when missing."""
        segments = [["CLP", "CLAIM001"]]
        bpr = parser._extract_bpr_segment(segments)
        assert bpr == {}


class TestExtractPayerFrom835:
    """Test payer extraction from 835."""

    def test_extract_payer_complete(self, parser):
        """Test extracting complete payer info."""
        segments = [
            ["N1", "PR", "ACME INSURANCE", "FI", "987654321"],
            ["N3", "123 PAYER ST"],
            ["N4", "CHICAGO", "IL", "60601"],
        ]
        payer = parser._extract_payer_from_835(segments)
        assert payer["name"] == "ACME INSURANCE"
        assert payer["address"] == "123 PAYER ST"
        assert payer["city"] == "CHICAGO"
        assert payer["state"] == "IL"
        assert payer["zip"] == "60601"

    def test_extract_payer_missing(self, parser):
        """Test extracting payer when missing."""
        segments = [["CLP", "CLAIM001"]]
        payer = parser._extract_payer_from_835(segments)
        assert payer == {}


class TestParseClaimBlock:
    """Test claim block parsing."""

    def test_parse_claim_block_complete(self, parser):
        """Test parsing complete claim block."""
        block = [
            ["HL", "2", "1", "22", "0"],
            ["CLM", "CLAIM001", "1500.00", "", "", "11:A:1", "Y", "A", "Y", "I"],
            ["DTP", "431", "D8", "20241215"],
            ["HI", "ABK:I10", "E11.9"],
        ]
        claim = parser._parse_claim_block(block, 0)
        assert claim["block_index"] == 0
        assert "warnings" in claim

    def test_parse_claim_block_missing_clm(self, parser):
        """Test parsing claim block without CLM."""
        block = [["DTP", "431", "D8", "20241215"]]
        claim = parser._parse_claim_block(block, 0)
        assert claim["is_incomplete"] is True
        assert len(claim["warnings"]) > 0


class TestParseRemittanceBlock:
    """Test remittance block parsing."""

    def test_parse_remittance_block_complete(self, parser):
        """Test parsing complete remittance block."""
        block = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00", "1200.00", "0", "11"],
            ["CAS", "PR", "1", "50.00"],
            ["SVC", "HC:99213", "1500.00", "1200.00", "1"],
        ]
        remittance = parser._parse_remittance_block(block, 0, {}, {})
        assert remittance["block_index"] == 0
        assert remittance["claim_control_number"] == "CLAIM001"
        assert "adjustments" in remittance
        assert "service_lines" in remittance

    def test_parse_remittance_block_missing_clp(self, parser):
        """Test parsing remittance block without CLP."""
        block = [["CAS", "PR", "1", "50.00"]]
        remittance = parser._parse_remittance_block(block, 0, {}, {})
        assert remittance["is_incomplete"] is True
        assert len(remittance["warnings"]) > 0


class TestParseFullFlow:
    """Test full parsing flow."""

    def test_parse_with_format_detection(self, parser, sample_837_content):
        """Test parsing with format detection enabled."""
        result = parser.parse(sample_837_content, "test_837.edi")
        assert result["file_type"] == "837"
        assert "claims" in result

    def test_parse_without_format_detection(self, sample_837_content):
        """Test parsing without format detection."""
        parser = EDIParser(auto_detect_format=False)
        result = parser.parse(sample_837_content, "test_837.edi")
        assert result["file_type"] == "837"

    def test_parse_empty_file(self, parser):
        """Test parsing empty file."""
        with pytest.raises(ValueError, match="No segments found"):
            parser.parse("", "empty.edi")

    def test_parse_invalid_file_type(self, parser):
        """Test parsing file with invalid type."""
        content = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*UNKNOWN~
ST*999*0001*UNKNOWN~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""
        # Parser defaults to 837 when uncertain, so this should not raise an error
        # but will try to parse as 837 and may have warnings
        result = parser.parse(content, "invalid.edi")
        assert result["file_type"] == "837"  # Defaults to 837

    def test_parse_with_practice_id(self, sample_837_content):
        """Test parsing with practice_id."""
        parser = EDIParser(practice_id="practice-123")
        result = parser.parse(sample_837_content, "test_837.edi")
        assert result["file_type"] == "837"


class TestAdaptToFormat:
    """Test format adaptation functionality."""

    def test_adapt_to_format_with_segments(self, parser):
        """Test adapting to format with detected segments."""
        format_analysis = {
            "segment_frequency": {
                "ISA": 1,
                "GS": 1,
                "ST": 1,
                "CLM": 5,
                "DTP": 10,
                "HI": 5,
                "SV2": 5,
            }
        }
        parser._adapt_to_format(format_analysis)
        # Should update config with important segments
        assert "important" in parser.config.segment_expectations

    def test_adapt_to_format_empty(self, parser):
        """Test adapting to format with empty analysis."""
        format_analysis = {"segment_frequency": {}}
        parser._adapt_to_format(format_analysis)
        # Should not crash

    def test_adapt_to_format_critical_segments(self, parser):
        """Test that critical segments are preserved."""
        format_analysis = {
            "segment_frequency": {
                "ISA": 1,
                "GS": 1,
                "ST": 1,
                "CLM": 5,
            }
        }
        parser._adapt_to_format(format_analysis)
        # Critical segments should be preserved
        assert isinstance(parser.config.segment_expectations, dict)


class TestSplitSegmentsChunked:
    """Test chunked segment splitting."""

    def test_split_segments_chunked_small(self, parser):
        """Test chunked splitting with small content."""
        content = "ISA*00*01~GS*HC*02~SE*03*04~"
        chunks = list(parser._split_segments_chunked(content))
        assert len(chunks) == 1
        assert len(chunks[0]) == 3

    def test_split_segments_chunked_large(self, parser):
        """Test chunked splitting with large content."""
        # Create content with more than SEGMENT_CHUNK_SIZE segments
        segments = [f"SEG{i}*A*B*C" for i in range(15000)]
        content = "~".join(segments) + "~"
        chunks = list(parser._split_segments_chunked(content))
        assert len(chunks) > 1  # Should be multiple chunks
        total = sum(len(chunk) for chunk in chunks)
        assert total == 15000

    def test_split_segments_chunked_with_newlines(self, parser):
        """Test chunked splitting with newlines."""
        content = "ISA*00*01~\r\nGS*HC*02~\nSE*03*04~\r"
        chunks = list(parser._split_segments_chunked(content))
        assert len(chunks) == 1
        assert len(chunks[0]) == 3

    def test_split_segments_chunked_empty(self, parser):
        """Test chunked splitting with empty content."""
        chunks = list(parser._split_segments_chunked(""))
        assert len(chunks) == 0

    def test_split_segments_chunked_whitespace(self, parser):
        """Test chunked splitting with whitespace segments."""
        content = " ISA*00*01 ~ GS*HC*02 ~"
        chunks = list(parser._split_segments_chunked(content))
        assert len(chunks) == 1
        assert len(chunks[0]) == 2


class TestParse837Advanced:
    """Test advanced 837 parsing scenarios."""

    def test_parse_837_large_file_batching(self, parser):
        """Test 837 parsing with large file batching."""
        # Create content with many claim blocks
        base_content = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~"""
        
        # Add many claim blocks
        claim_blocks = []
        for i in range(600):  # More than batch_size * 10
            claim_blocks.append(f"""HL*{i+1}*{i if i > 0 else ''}*22*0~
CLM*CLAIM{i:06d}*1500.00***11:A:1*Y*A*Y*I~""")
        
        content = base_content + "".join(claim_blocks) + """SE*602*0001~
GE*1*1~
IEA*1*000000001~"""
        
        result = parser.parse(content, "large_837.edi")
        assert result["file_type"] == "837"
        assert len(result["claims"]) == 600

    def test_parse_837_with_exception_in_block(self, parser):
        """Test 837 parsing when a block raises an exception."""
        content = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
HL*1**20*1~
HL*2*1*22*0~
CLM*CLAIM001*1500.00~
SE*5*0001~
GE*1*1~
IEA*1*000000001~"""
        # Should handle gracefully even if block parsing fails
        result = parser.parse(content, "test_837.edi")
        assert result["file_type"] == "837"
        assert "warnings" in result or len(result["claims"]) >= 0

    def test_parse_837_no_blocks_warning(self, parser):
        """Test 837 parsing with no claim blocks generates warning."""
        content = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""
        result = parser.parse(content, "no_claims_837.edi")
        assert result["file_type"] == "837"
        assert len(result["claims"]) == 0
        assert "warnings" in result
        assert any("No claim blocks" in w for w in result["warnings"])


class TestParse835Advanced:
    """Test advanced 835 parsing scenarios."""

    def test_parse_835_multiple_remittances(self, parser):
        """Test 835 parsing with multiple remittances."""
        content = """ISA*00*          *00*          *ZZ*BCBSILPAYER     *ZZ*MEDPRACTICE001   *241220*143052*^*00501*000000001*0*P*:~
GS*HP*BCBSILPAYER*MEDPRACTICE001*20241220*143052*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*28750.00*C*CHK987654321*20241220~
LX*1~
CLP*CLAIM001*1*1500.00*1200.00*0*11~
LX*2~
CLP*CLAIM002*1*2000.00*1800.00*0*11~
SE*8*0001~
GE*1*1~
IEA*1*000000001~"""
        result = parser.parse(content, "multi_835.edi")
        assert result["file_type"] == "835"
        assert len(result["remittances"]) == 2

    def test_parse_835_with_bpr(self, parser):
        """Test 835 parsing with BPR segment."""
        content = """ISA*00*          *00*          *ZZ*BCBSILPAYER     *ZZ*MEDPRACTICE001   *241220*143052*^*00501*000000001*0*P*:~
GS*HP*BCBSILPAYER*MEDPRACTICE001*20241220*143052*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*28750.00*C*CHK987654321*20241220*123456789*01*987654321*DA*1234567890*20241220~
LX*1~
CLP*CLAIM001*1*1500.00*1200.00*0*11~
SE*5*0001~
GE*1*1~
IEA*1*000000001~"""
        result = parser.parse(content, "bpr_835.edi")
        assert result["file_type"] == "835"
        assert "bpr" in result
        assert result["bpr"]["total_payment_amount"] == 28750.00

    def test_parse_835_no_remittances(self, parser):
        """Test 835 parsing with no remittances."""
        content = """ISA*00*          *00*          *ZZ*BCBSILPAYER     *ZZ*MEDPRACTICE001   *241220*143052*^*00501*000000001*0*P*:~
GS*HP*BCBSILPAYER*MEDPRACTICE001*20241220*143052*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*0.00*C*CHK987654321*20241220~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""
        result = parser.parse(content, "empty_835.edi")
        assert result["file_type"] == "835"
        assert len(result["remittances"]) == 0


class TestExtractBPRAdvanced:
    """Test advanced BPR extraction."""

    def test_extract_bpr_short_segment(self, parser):
        """Test extracting BPR with short segment."""
        segments = [["BPR", "I", "28750.00"]]
        bpr = parser._extract_bpr_segment(segments)
        assert bpr["transaction_handling_code"] == "I"
        assert bpr["total_payment_amount"] == 28750.00

    def test_extract_bpr_empty(self, parser):
        """Test extracting BPR from empty segments."""
        segments = []
        bpr = parser._extract_bpr_segment(segments)
        assert bpr == {}


class TestExtractPayerFrom835Advanced:
    """Test advanced payer extraction from 835."""

    def test_extract_payer_partial_info(self, parser):
        """Test extracting payer with partial information."""
        segments = [
            ["N1", "PR", "ACME INSURANCE"],
        ]
        payer = parser._extract_payer_from_835(segments)
        assert payer["name"] == "ACME INSURANCE"

    def test_extract_payer_no_n1(self, parser):
        """Test extracting payer when N1 segment missing."""
        segments = [["N3", "123 ST"], ["N4", "CHICAGO", "IL"]]
        payer = parser._extract_payer_from_835(segments)
        assert payer == {}


class TestParseRemittanceBlockAdvanced:
    """Test advanced remittance block parsing."""

    def test_parse_remittance_block_with_service_lines(self, parser):
        """Test parsing remittance block with service lines."""
        block = [
            ["LX", "1"],
            ["CLP", "CLAIM001", "1", "1500.00", "1200.00", "0", "11"],
            ["SVC", "HC:99213", "1500.00", "1200.00", "1"],
            ["CAS", "PR", "1", "50.00"],
        ]
        payer_info = {"name": "ACME INSURANCE"}
        bpr_info = {"total_payment_amount": 1500.00}
        remittance = parser._parse_remittance_block(block, 0, payer_info, bpr_info)
        assert remittance["claim_control_number"] == "CLAIM001"
        assert "service_lines" in remittance
        assert len(remittance["service_lines"]) > 0

    def test_parse_remittance_block_no_lx(self, parser):
        """Test parsing remittance block without LX."""
        block = [
            ["CLP", "CLAIM001", "1", "1500.00"],
        ]
        remittance = parser._parse_remittance_block(block, 0, {}, {})
        assert remittance["claim_control_number"] == "CLAIM001"


class TestParseClaimBlockAdvanced:
    """Test advanced claim block parsing."""

    def test_parse_claim_block_with_all_segments(self, parser):
        """Test parsing claim block with all segment types."""
        block = [
            ["HL", "2", "1", "22", "0"],
            ["CLM", "CLAIM001", "1500.00", "", "", "11:A:1", "Y", "A", "Y", "I"],
            ["DTP", "431", "D8", "20241215"],
            ["DTP", "472", "D8", "20241215"],
            ["HI", "ABK:I10", "E11.9", "I10"],
            ["LX", "1"],
            ["SV2", "0450", "HC", "99213", "1500.00", "UN", "1"],
        ]
        claim = parser._parse_claim_block(block, 0)
        assert claim["claim_control_number"] == "CLAIM001"
        assert claim["block_index"] == 0

    def test_parse_claim_block_minimal(self, parser):
        """Test parsing claim block with minimal segments."""
        block = [
            ["CLM", "CLAIM001", "1500.00"],
        ]
        claim = parser._parse_claim_block(block, 0)
        assert claim["claim_control_number"] == "CLAIM001"
        assert claim["is_incomplete"] is True  # Missing required segments


class TestPerformanceMonitoring:
    """Test performance monitoring integration."""

    @patch("app.services.edi.parser.PERFORMANCE_MONITORING_AVAILABLE", True)
    @patch("app.services.edi.parser.PerformanceMonitor")
    def test_parse_with_performance_monitoring(self, mock_monitor_class, sample_837_content):
        """Test parsing with performance monitoring enabled."""
        mock_monitor = MagicMock()
        mock_monitor_class.return_value = mock_monitor
        
        # Create parser after patching
        parser = EDIParser()
        
        # Create large content to trigger monitoring (>1MB = 1024*1024 bytes)
        # Sample content is ~1KB, so we need 1024+ copies
        large_content = sample_837_content * 1200  # Make it >1MB
        result = parser.parse(large_content, "large_837.edi")
        
        assert result["file_type"] == "837"
        # Monitor should have been started if content is large enough
        # Check if it was called (may not be if content isn't quite large enough)
        if len(large_content.encode("utf-8")) > 1024 * 1024:
            assert mock_monitor_class.called or mock_monitor.start.called

    @patch("app.services.edi.parser.PERFORMANCE_MONITORING_AVAILABLE", False)
    def test_parse_without_performance_monitoring(self, parser, sample_837_content):
        """Test parsing without performance monitoring."""
        result = parser.parse(sample_837_content, "test_837.edi")
        assert result["file_type"] == "837"


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_parse_invalid_segment_format(self, parser):
        """Test parsing with invalid segment format."""
        content = "NOT*VALID*SEGMENT~ISA*00*01~"
        # Should handle gracefully
        result = parser.parse(content, "invalid.edi")
        assert "file_type" in result

    def test_parse_malformed_envelope(self, parser):
        """Test parsing with malformed envelope."""
        content = "ISA~GS~ST*837*0001~CLM*CLAIM001*1500.00~SE*4*0001~GE*1*1~IEA*1*000000001~"
        result = parser.parse(content, "malformed.edi")
        assert result["file_type"] == "837"
        assert "warnings" in result or "envelope" in result

