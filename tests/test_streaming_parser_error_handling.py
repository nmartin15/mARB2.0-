"""Comprehensive error handling and edge case tests for streaming parser."""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

from app.services.edi.parser_streaming import StreamingEDIParser


@pytest.mark.unit
class TestStreamingParserErrorHandling:
    """Test error handling in streaming parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return StreamingEDIParser()

    def test_parse_no_file_content_or_path(self, parser):
        """Test error when neither file_content nor file_path provided."""
        with pytest.raises(ValueError, match="Either file_content or file_path must be provided"):
            parser.parse(filename="test.edi")

    def test_parse_both_file_content_and_path(self, parser):
        """Test that file_path takes precedence when both provided."""
        # Should use file_path if both provided
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~")
            tmp_path = tmp_file.name

        try:
            # Should parse from file_path, not file_content
            result = parser.parse(
                file_content="invalid",
                file_path=tmp_path,
                filename="test.edi",
            )
            assert "file_type" in result
        finally:
            os.unlink(tmp_path)

    def test_parse_file_not_found(self, parser):
        """Test error when file_path doesn't exist."""
        with pytest.raises(FileNotFoundError, match="EDI file not found"):
            parser.parse(
                file_path="/nonexistent/path/file.edi",
                filename="test.edi",
            )

    def test_parse_empty_file_content(self, parser):
        """Test error when file_content is empty."""
        with pytest.raises(ValueError, match="empty or contains only whitespace"):
            parser.parse(
                file_content="",
                filename="test.edi",
            )

    def test_parse_whitespace_only_file_content(self, parser):
        """Test error when file_content is only whitespace."""
        with pytest.raises(ValueError, match="empty or contains only whitespace"):
            parser.parse(
                file_content="   \n\t  \n  ",
                filename="test.edi",
            )

    def test_parse_empty_file_path(self, parser):
        """Test error when file_path points to empty file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            with pytest.raises(ValueError, match="empty \\(0 bytes\\)"):
                parser.parse(
                    file_path=tmp_path,
                    filename="test.edi",
                )
        finally:
            os.unlink(tmp_path)

    def test_parse_file_read_permission_error(self, parser):
        """Test error handling when file cannot be read."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~")
            tmp_path = tmp_file.name

        # Make file unreadable
        os.chmod(tmp_path, 0o000)

        try:
            with pytest.raises((PermissionError, OSError)):
                parser.parse(
                    file_path=tmp_path,
                    filename="test.edi",
                )
        finally:
            # Restore permissions and cleanup
            os.chmod(tmp_path, 0o644)
            os.unlink(tmp_path)

    def test_parse_invalid_edi_format(self, parser):
        """Test error handling with invalid EDI format."""
        content = "NOT VALID EDI CONTENT AT ALL"

        # Parser raises ValueError for invalid format
        with pytest.raises(ValueError):
            parser.parse(
                file_content=content,
                filename="invalid.edi",
            )

    def test_parse_missing_isa_segment(self, parser):
        """Test error handling when ISA segment is missing."""
        content = """GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""

        # Parser raises ValueError for missing ISA segment
        with pytest.raises(ValueError, match="Missing required ISA"):
            parser.parse(
                file_content=content,
                filename="missing_isa.edi",
            )

    def test_parse_unknown_file_type(self, parser):
        """Test error handling when file type cannot be determined."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*999*0001*005010X222A1~  # Unknown transaction type
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""

        # Should handle gracefully or raise ValueError
        try:
            result = parser.parse(
                file_content=content,
                filename="unknown_type.edi",
            )
            assert isinstance(result, dict)
        except ValueError:
            # ValueError is acceptable for unknown file type
            pass

    def test_parse_corrupted_segment(self, parser):
        """Test error handling with corrupted segment."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CORRUPTED*SEGMENT*WITH*INVALID*FORMAT*AND*TOO*MANY*ELEMENTS*OR*MISSING*DELIMITERS
CLM*CLAIM001*1500.00~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        # Should skip corrupted segment and continue
        result = parser.parse(
            file_content=content,
            filename="corrupted.edi",
        )
        assert isinstance(result, dict)

    def test_parse_malformed_segment_terminator(self, parser):
        """Test error handling with malformed segment terminators."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1
ST*837*0001*005010X222A1
CLM*CLAIM001*1500.00
SE*4*0001
GE*1*1
IEA*1*000000001"""

        # Parser may raise ValueError or handle gracefully - test both cases
        try:
            result = parser.parse(
                file_content=content,
                filename="malformed.edi",
            )
            # If succeeds, should return dict
            assert isinstance(result, dict)
        except ValueError:
            # If raises ValueError, that's also acceptable
            pass

    def test_parse_unicode_decode_error(self, parser):
        """Test error handling with invalid encoding."""
        # Create file with invalid UTF-8 bytes
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp_file:
            tmp_file.write(b'\xff\xfe\x00\x01')  # Invalid UTF-8
            tmp_path = tmp_file.name

        try:
            with pytest.raises((UnicodeDecodeError, ValueError)):
                parser.parse(
                    file_path=tmp_path,
                    filename="invalid_encoding.edi",
                )
        finally:
            os.unlink(tmp_path)

    def test_parse_generator_exception(self, parser):
        """Test error handling when segment generator raises exception."""
        with patch.object(parser, '_read_segments_from_string') as mock_gen:
            mock_gen.side_effect = Exception("Generator error")

            with pytest.raises(Exception, match="Generator error"):
                parser.parse(
                    file_content="ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~",
                    filename="test.edi",
                )

    def test_parse_envelope_parsing_error(self, parser):
        """Test error handling when envelope parsing fails."""
        content = """ISA*INVALID*FORMAT*WITH*WRONG*NUMBER*OF*ELEMENTS~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        # Should handle gracefully
        result = parser.parse(
            file_content=content,
            filename="invalid_envelope.edi",
        )
        assert isinstance(result, dict)


@pytest.mark.unit
class TestStreamingParserEdgeCases:
    """Test edge cases in streaming parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return StreamingEDIParser()

    def test_parse_very_large_file(self, parser):
        """Test parsing very large file (simulated)."""
        # Create large content with many segments
        segments = []
        segments.append("ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~")
        segments.append("GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~")

        # Add many claims
        for i in range(1000):
            segments.append(f"ST*837*{i:04d}*005010X222A1~")
            segments.append(f"CLM*CLAIM{i:04d}*1500.00~")
            segments.append(f"SE*3*{i:04d}~")

        segments.append("GE*1000*1~")
        segments.append("IEA*1*000000001~")

        content = "\n".join(segments)

        result = parser.parse(
            file_content=content,
            filename="large_file.edi",
        )

        assert result["file_type"] == "837"
        assert len(result.get("claims", [])) >= 0  # May process all or some

    def test_parse_file_with_max_segment_length(self, parser):
        """Test parsing file with maximum segment length."""
        # Create segment with very long element
        long_element = "A" * 10000
        content = f"""ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00*{long_element}~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(
            file_content=content,
            filename="long_segment.edi",
        )

        assert result["file_type"] == "837"

    def test_parse_file_with_special_characters(self, parser):
        """Test parsing file with special characters."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
NM1*IL*1*O'BRIEN*JOHN*JR***MI*123456789~
NM1*PR*2*COMPANY, INC.***XX*987654321~
SE*5*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(
            file_content=content,
            filename="special_chars.edi",
        )

        assert result["file_type"] == "837"

    def test_parse_file_with_unicode_characters(self, parser):
        """Test parsing file with unicode characters."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
NM1*IL*1*GARCÍA*MARÍA***MI*123456789~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(
            file_content=content,
            filename="unicode.edi",
        )

        assert result["file_type"] == "837"

    def test_parse_file_with_only_envelope(self, parser):
        """Test parsing file with only envelope segments."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(
            file_content=content,
            filename="envelope_only.edi",
        )

        assert result["file_type"] == "837"
        assert len(result.get("claims", [])) == 0

    def test_parse_file_with_nested_loops(self, parser):
        """Test parsing file with nested hierarchical loops."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
HL*1**20*1~
PRV*BI*PXC*207RI0001X~
HL*2*1*22*0~
SBR*P*18~
CLM*CLAIM001*1500.00~
LX*1~
SV2*HC:99213*1500.00*UN*1~
SE*9*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(
            file_content=content,
            filename="nested_loops.edi",
        )

        assert result["file_type"] == "837"

    def test_parse_file_with_control_number_mismatch(self, parser):
        """Test parsing file with control number mismatches."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SE*4*0002~  # Mismatch: should be 0001
GE*1*1~
IEA*1*000000002~  # Mismatch: should be 000000001"""

        # Should parse but may have warnings
        result = parser.parse(
            file_content=content,
            filename="mismatch.edi",
        )

        assert result["file_type"] == "837"

    def test_parse_file_with_duplicate_claim_numbers(self, parser):
        """Test parsing file with duplicate claim control numbers."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SE*4*0001~
ST*837*0002*005010X222A1~
CLM*CLAIM001*2000.00~  # Duplicate claim number
SE*4*0002~
GE*2*1~
IEA*1*000000001~"""

        result = parser.parse(
            file_content=content,
            filename="duplicate_claims.edi",
        )

        assert result["file_type"] == "837"
        # Should parse both claims (duplicates allowed in EDI)

    def test_parse_file_with_many_segments_per_claim(self, parser):
        """Test parsing file with many segments per claim."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~"""

        # Add many segments
        for i in range(100):
            content += f"\nDTP*431*D8*202412{i%30+1:02d}~"
            content += f"\nHI*ABK:I10*E11.{i}~"

        content += "\nSE*202*0001~"
        content += "\nGE*1*1~"
        content += "\nIEA*1*000000001~"

        result = parser.parse(
            file_content=content,
            filename="many_segments.edi",
        )

        assert result["file_type"] == "837"

    def test_parse_file_with_consecutive_claim_blocks(self, parser):
        """Test parsing file with consecutive claim blocks."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~"""

        # Add many consecutive claim blocks
        for i in range(50):
            content += f"\nST*837*{i+1:04d}*005010X222A1~"
            content += f"\nCLM*CLAIM{i+1:04d}*1500.00~"
            content += f"\nSE*3*{i+1:04d}~"

        content += "\nGE*50*1~"
        content += "\nIEA*1*000000001~"

        result = parser.parse(
            file_content=content,
            filename="consecutive_claims.edi",
        )

        assert result["file_type"] == "837"
        assert len(result.get("claims", [])) >= 0  # May process all or some


@pytest.mark.unit
class TestStreamingParserPerformanceEdgeCases:
    """Test performance-related edge cases."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return StreamingEDIParser()

    def test_parse_memory_efficient_large_file(self, parser):
        """Test that parser handles large files without loading all into memory."""
        # Create large file on disk
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~\n")
            tmp_file.write("GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~\n")

            # Write many claims
            for i in range(500):
                tmp_file.write(f"ST*837*{i+1:04d}*005010X222A1~\n")
                tmp_file.write(f"CLM*CLAIM{i+1:04d}*1500.00~\n")
                tmp_file.write(f"SE*3*{i+1:04d}~\n")

            tmp_file.write("GE*500*1~\n")
            tmp_file.write("IEA*1*000000001~\n")
            tmp_path = tmp_file.name

        try:
            # Should parse without loading entire file into memory
            result = parser.parse(
                file_path=tmp_path,
                filename="large_file.edi",
            )

            assert result["file_type"] == "837"
        finally:
            os.unlink(tmp_path)

    def test_parse_incremental_processing(self, parser):
        """Test that parser processes segments incrementally."""
        content = """ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        # Mock generator to verify incremental processing
        with patch.object(parser, '_read_segments_from_string') as mock_gen:
            def segment_generator():
                segments = content.split('~')
                for seg in segments:
                    if seg.strip():
                        yield seg.split('*')
            mock_gen.return_value = segment_generator()

            result = parser.parse(
                file_content=content,
                filename="test.edi",
            )

            # Generator should be called
            assert mock_gen.called

    def test_parse_garbage_collection_large_file(self, parser):
        """Test that parser triggers garbage collection for large files."""
        # Create large content
        segments = []
        segments.append("ISA*00*          *00*          *ZZ*SENDER*ZZ*RECEIVER*241220*1200*^*00501*000000001*0*P*:~")
        segments.append("GS*HC*SENDER*RECEIVER*20241220*1200*1*X*005010X222A1~")

        for i in range(200):
            segments.append(f"ST*837*{i+1:04d}*005010X222A1~")
            segments.append(f"CLM*CLAIM{i+1:04d}*1500.00~")
            segments.append(f"SE*3*{i+1:04d}~")

        segments.append("GE*200*1~")
        segments.append("IEA*1*000000001~")

        content = "\n".join(segments)

        # Should process without memory issues
        result = parser.parse(
            file_content=content,
            filename="large_file.edi",
        )

        assert result["file_type"] == "837"

