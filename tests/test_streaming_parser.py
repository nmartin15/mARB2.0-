"""Tests for streaming EDI parser."""
from pathlib import Path

import pytest

from app.services.edi.parser import EDIParser
from app.services.edi.parser_streaming import StreamingEDIParser


@pytest.fixture
def sample_837_file_path() -> Path:
    """Path to sample 837 file."""
    return Path(__file__).parent.parent / "samples" / "sample_837.txt"


@pytest.fixture
def sample_837_content(sample_837_file_path: Path) -> str:
    """Read sample 837 file content."""
    with open(sample_837_file_path, "r") as f:
        return f.read()


@pytest.fixture
def sample_835_file_path() -> Path:
    """Path to sample 835 file."""
    return Path(__file__).parent.parent / "samples" / "sample_835.txt"


@pytest.fixture
def sample_835_content(sample_835_file_path: Path) -> str:
    """Read sample 835 file content."""
    with open(sample_835_file_path, "r") as f:
        return f.read()


@pytest.mark.unit
class TestStreamingParser837:
    """Test streaming parser for 837 files."""

    def test_streaming_parser_from_string(self, sample_837_content: str):
        """Test streaming parser with string content."""
        parser = StreamingEDIParser()
        result = parser.parse(file_content=sample_837_content, filename="test_837.txt")

        assert result["file_type"] == "837"
        assert "envelope" in result
        assert "claims" in result
        assert len(result["claims"]) > 0

    def test_streaming_parser_from_file(self, sample_837_file_path: Path):
        """Test streaming parser with file path."""
        parser = StreamingEDIParser()
        result = parser.parse(file_path=str(sample_837_file_path), filename="test_837.txt")

        assert result["file_type"] == "837"
        assert "envelope" in result
        assert "claims" in result
        assert len(result["claims"]) > 0

    def test_streaming_parser_matches_standard_parser(self, sample_837_content: str):
        """Test that streaming parser produces same results as standard parser."""
        streaming_parser = StreamingEDIParser()
        standard_parser = EDIParser()

        streaming_result = streaming_parser.parse(
            file_content=sample_837_content, filename="test_837.txt"
        )
        standard_result = standard_parser.parse(sample_837_content, "test_837.txt")

        # Compare key fields
        assert streaming_result["file_type"] == standard_result["file_type"]
        assert len(streaming_result["claims"]) == len(standard_result["claims"])

        # Compare envelope
        assert streaming_result["envelope"] == standard_result["envelope"]

        # Compare first claim
        if streaming_result["claims"] and standard_result["claims"]:
            streaming_claim = streaming_result["claims"][0]
            standard_claim = standard_result["claims"][0]
            assert (
                streaming_claim.get("claim_control_number")
                == standard_claim.get("claim_control_number")
            )


@pytest.mark.unit
class TestStreamingParser835:
    """Test streaming parser for 835 files."""

    def test_streaming_parser_from_string(self, sample_835_content: str):
        """Test streaming parser with string content."""
        parser = StreamingEDIParser()
        result = parser.parse(file_content=sample_835_content, filename="test_835.txt")

        assert result["file_type"] == "835"
        assert "envelope" in result
        assert "remittances" in result
        assert len(result["remittances"]) > 0

    def test_streaming_parser_from_file(self, sample_835_file_path: Path):
        """Test streaming parser with file path."""
        parser = StreamingEDIParser()
        result = parser.parse(file_path=str(sample_835_file_path), filename="test_835.txt")

        assert result["file_type"] == "835"
        assert "envelope" in result
        assert "remittances" in result
        assert len(result["remittances"]) > 0

    def test_streaming_parser_matches_standard_parser(self, sample_835_content: str):
        """Test that streaming parser produces same results as standard parser."""
        streaming_parser = StreamingEDIParser()
        standard_parser = EDIParser()

        streaming_result = streaming_parser.parse(
            file_content=sample_835_content, filename="test_835.txt"
        )
        standard_result = standard_parser.parse(sample_835_content, "test_835.txt")

        # Compare key fields
        assert streaming_result["file_type"] == standard_result["file_type"]
        assert len(streaming_result["remittances"]) == len(standard_result["remittances"])

        # Compare envelope
        assert streaming_result["envelope"] == standard_result["envelope"]

        # Compare first remittance
        if streaming_result["remittances"] and standard_result["remittances"]:
            streaming_remit = streaming_result["remittances"][0]
            standard_remit = standard_result["remittances"][0]
            assert (
                streaming_remit.get("claim_control_number")
                == standard_remit.get("claim_control_number")
            )


@pytest.mark.unit
class TestStreamingParserMemoryEfficiency:
    """Test memory efficiency of streaming parser."""

    def test_incremental_segment_processing(self):
        """Test that segments are processed incrementally."""
        # Create a simple EDI file with proper HL structure
        content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20240101*1200*CH~
HL*1**20*1~
PRV*BI*PXC*1234567890~
HL*2*1*22*0~
SBR*P*18*GROUP123******CI~
CLM*CLAIM001*1500.00~
SE*8*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = StreamingEDIParser()
        result = parser.parse(file_content=content, filename="test.txt")

        assert result["file_type"] == "837"
        assert len(result["claims"]) == 1

    def test_large_file_handling(self, tmp_path):
        """Test that streaming parser can handle large files efficiently."""
        # Create a large EDI file with many claims
        header = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~"""

        claim_template = """HL*{idx}**20*1~
PRV*BI*PXC*1234567890~
HL*{idx2}*{idx}*22*0~
SBR*P*18*GROUP123******CI~
CLM*CLAIM{idx:03d}*1500.00~"""

        footer = """SE*{count}*0001~
GE*1*1~
IEA*1*000000001~"""

        # Create file with 100 claims
        num_claims = 100
        content = header + "\n"
        for i in range(1, num_claims + 1):
            content += claim_template.format(idx=i, idx2=i*2) + "\n"
        content += footer.format(count=3 + num_claims * 5)

        # Write to temporary file
        test_file = tmp_path / "large_test.edi"
        test_file.write_text(content)

        # Parse using streaming parser
        parser = StreamingEDIParser()
        result = parser.parse(file_path=str(test_file), filename="large_test.edi")

        assert result["file_type"] == "837"
        assert len(result["claims"]) == num_claims


@pytest.mark.unit
class TestStreamingParserErrorHandling:
    """Test error handling in StreamingEDIParser."""

    def test_streaming_parser_empty_file_content(self):
        """Test streaming parser with empty file content."""
        parser = StreamingEDIParser()
        
        with pytest.raises(ValueError, match="empty or contains only whitespace"):
            parser.parse(file_content="", filename="empty.txt")

    def test_streaming_parser_whitespace_only_content(self):
        """Test streaming parser with whitespace-only content."""
        parser = StreamingEDIParser()
        
        with pytest.raises(ValueError, match="empty or contains only whitespace"):
            parser.parse(file_content="   \n\t  ", filename="whitespace.txt")

    def test_streaming_parser_file_not_found(self, tmp_path):
        """Test streaming parser with non-existent file path."""
        parser = StreamingEDIParser()
        non_existent_file = tmp_path / "does_not_exist.edi"
        
        with pytest.raises(FileNotFoundError, match="not found"):
            parser.parse(file_path=str(non_existent_file), filename="missing.edi")

    def test_streaming_parser_empty_file_path(self, tmp_path):
        """Test streaming parser with empty file."""
        parser = StreamingEDIParser()
        empty_file = tmp_path / "empty.edi"
        empty_file.write_text("")  # Create empty file
        
        with pytest.raises(ValueError, match="empty"):
            parser.parse(file_path=str(empty_file), filename="empty.edi")

    def test_streaming_parser_invalid_edi_format(self):
        """Test streaming parser with invalid EDI format (not EDI at all)."""
        parser = StreamingEDIParser()
        invalid_content = "This is not an EDI file at all. Just random text."
        
        # Streaming parser raises ValueError when ISA segment is missing
        with pytest.raises(ValueError, match="Missing required ISA"):
            parser.parse(file_content=invalid_content, filename="invalid.txt")

    def test_streaming_parser_missing_isa_segment(self):
        """Test streaming parser with content missing ISA segment."""
        parser = StreamingEDIParser()
        # Content without ISA segment (invalid EDI)
        invalid_content = "GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~"
        
        # Streaming parser raises ValueError when ISA segment is missing
        with pytest.raises(ValueError, match="Missing required ISA"):
            parser.parse(file_content=invalid_content, filename="no_isa.txt")

    def test_streaming_parser_malformed_segments(self):
        """Test streaming parser with malformed segments."""
        parser = StreamingEDIParser()
        # Content with malformed segments (missing delimiters)
        malformed_content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
INVALID_SEGMENT_WITHOUT_DELIMITERS
CLM*CLAIM001*1500.00~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""
        
        result = parser.parse(file_content=malformed_content, filename="malformed.txt")
        
        # Should handle gracefully - may parse what it can or return warnings
        assert isinstance(result, dict)
        assert "file_type" in result or "warnings" in result

    def test_streaming_parser_no_file_content_or_path(self):
        """Test streaming parser with neither file_content nor file_path."""
        parser = StreamingEDIParser()
        
        # Should raise ValueError when both are None
        with pytest.raises(ValueError, match="Either file_content or file_path must be provided"):
            parser.parse(filename="test.txt")


@pytest.mark.unit
class TestStreamingParserMethods:
    """Test individual methods of StreamingEDIParser."""

    def test_read_segments_from_string(self):
        """Test reading segments from string."""
        parser = StreamingEDIParser()
        content = "ISA*00*01~GS*HC*02~SE*03*04~"
        segments = list(parser._read_segments_from_string(content))
        assert len(segments) == 3
        assert segments[0] == ["ISA", "00", "01"]

    def test_read_segments_from_string_with_newlines(self):
        """Test reading segments from string with newlines."""
        parser = StreamingEDIParser()
        content = "ISA*00*01~\r\nGS*HC*02~\nSE*03*04~\r"
        segments = list(parser._read_segments_from_string(content))
        assert len(segments) == 3

    def test_read_segments_from_file(self, tmp_path):
        """Test reading segments from file."""
        parser = StreamingEDIParser()
        test_file = tmp_path / "test.edi"
        test_file.write_text("ISA*00*01~GS*HC*02~SE*03*04~")
        segments = list(parser._read_segments_from_file(str(test_file)))
        assert len(segments) == 3

    def test_parse_envelope_streaming(self):
        """Test parsing envelope from streaming segments."""
        parser = StreamingEDIParser()
        
        def segment_gen():
            yield ["ISA", "00", "", "", "", "", "SENDER", "", "RECEIVER", "20241220", "1340", "", "00501", "000000001", "0", "P", ":"]
            yield ["GS", "HC", "SENDER", "RECEIVER", "20241220", "1340", "1", "X", "005010X222A1"]
            yield ["ST", "837", "0001", "005010X222A1"]
        
        envelope, file_type, initial = parser._parse_envelope_streaming(segment_gen())
        assert "isa" in envelope
        assert "gs" in envelope
        assert file_type == "837"
        assert len(initial) == 3

    def test_parse_envelope_streaming_missing_segments(self):
        """Test parsing envelope with missing segments."""
        parser = StreamingEDIParser()
        
        def segment_gen():
            yield ["ST", "837", "0001"]
        
        # Streaming parser raises ValueError when ISA is missing
        with pytest.raises(ValueError, match="Missing required ISA"):
            parser._parse_envelope_streaming(segment_gen())

    def test_parse_decimal_valid(self):
        """Test parsing valid decimal."""
        parser = StreamingEDIParser()
        assert parser._parse_decimal("1500.00") == 1500.00
        assert parser._parse_decimal("123.45") == 123.45

    def test_parse_decimal_invalid(self):
        """Test parsing invalid decimal."""
        parser = StreamingEDIParser()
        assert parser._parse_decimal("invalid") is None
        assert parser._parse_decimal(None) is None
        assert parser._parse_decimal("") is None

    def test_find_segment_in_block(self):
        """Test finding segment in block."""
        parser = StreamingEDIParser()
        block = [["CLM", "CLAIM001"], ["DTP", "431", "D8", "20241215"]]
        result = parser._find_segment_in_block(block, "CLM")
        assert result == ["CLM", "CLAIM001"]

    def test_find_segment_in_block_not_found(self):
        """Test finding segment that doesn't exist."""
        parser = StreamingEDIParser()
        block = [["DTP", "431", "D8", "20241215"]]
        result = parser._find_segment_in_block(block, "CLM")
        assert result is None

    def test_find_all_segments_in_block(self):
        """Test finding all segments of a type."""
        parser = StreamingEDIParser()
        block = [["CAS", "PR", "1", "50.00"], ["CAS", "OA", "2", "25.00"], ["CLP", "CLAIM001"]]
        results = parser._find_all_segments_in_block(block, "CAS")
        assert len(results) == 2


@pytest.mark.unit
class TestStreamingParserInit:
    """Test StreamingEDIParser initialization."""

    def test_init_default(self):
        """Test default initialization."""
        parser = StreamingEDIParser()
        assert parser.practice_id is None
        assert parser.auto_detect_format is True
        assert parser.format_detector is not None

    def test_init_with_practice_id(self):
        """Test initialization with practice_id."""
        parser = StreamingEDIParser(practice_id="practice-123")
        assert parser.practice_id == "practice-123"

    def test_init_without_auto_detect(self):
        """Test initialization without auto-detect."""
        parser = StreamingEDIParser(auto_detect_format=False)
        assert parser.auto_detect_format is False
        assert parser.format_detector is None


@pytest.mark.unit
class TestStreamingParser835Advanced:
    """Test advanced 835 parsing scenarios."""

    def test_parse_835_multiple_remittances(self):
        """Test parsing 835 with multiple remittances."""
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
        parser = StreamingEDIParser()
        result = parser.parse(file_content=content, filename="multi_835.edi")
        assert result["file_type"] == "835"
        assert len(result["remittances"]) == 2


@pytest.mark.unit
class TestStreamingParser837Advanced:
    """Test advanced 837 parsing scenarios."""

    def test_parse_837_large_file(self, tmp_path):
        """Test parsing large 837 file."""
        header = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~"""
        
        claim_template = """HL*{idx}**20*1~
HL*{idx2}*{idx}*22*0~
CLM*CLAIM{idx:03d}*1500.00~"""
        
        footer = """SE*{count}*0001~
GE*1*1~
IEA*1*000000001~"""
        
        num_claims = 200
        content = header
        for i in range(1, num_claims + 1):
            content += claim_template.format(idx=i, idx2=i*2)
        content += footer.format(count=3 + num_claims * 3)
        
        test_file = tmp_path / "large_837.edi"
        test_file.write_text(content)
        
        parser = StreamingEDIParser()
        result = parser.parse(file_path=str(test_file), filename="large_837.edi")
        assert result["file_type"] == "837"
        assert len(result["claims"]) == num_claims

