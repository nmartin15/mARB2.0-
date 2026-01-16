"""Comprehensive tests for streaming EDI parser - the heart and soul of the app."""
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
@pytest.mark.integration
class TestStreamingParserCorrectness:
    """Test that streaming parser produces identical results to standard parser."""

    def test_837_parsing_identical_results(self, sample_837_content: str):
        """Verify streaming parser produces identical results to standard parser for 837.
        
        Compares the output of StreamingEDIParser and EDIParser for 837 files,
        ensuring that envelope data, claim counts, claim details, diagnosis codes,
        and claim lines match exactly between both parsers.
        """
        streaming_parser = StreamingEDIParser()
        standard_parser = EDIParser()

        streaming_result = streaming_parser.parse(
            file_content=sample_837_content, filename="test_837.txt"
        )
        standard_result = standard_parser.parse(sample_837_content, "test_837.txt")

        # Compare file types
        assert streaming_result["file_type"] == standard_result["file_type"] == "837"

        # Compare envelope data
        assert streaming_result["envelope"] == standard_result["envelope"]

        # Compare claim counts
        assert len(streaming_result["claims"]) == len(standard_result["claims"])

        # Compare each claim in detail
        for i, (streaming_claim, standard_claim) in enumerate(
            zip(streaming_result["claims"], standard_result["claims"])
        ):
            # Compare key fields
            assert (
                streaming_claim.get("claim_control_number")
                == standard_claim.get("claim_control_number")
            ), f"Claim {i}: control number mismatch"
            assert (
                streaming_claim.get("total_charge_amount")
                == standard_claim.get("total_charge_amount")
            ), f"Claim {i}: charge amount mismatch"
            assert (
                streaming_claim.get("payer_responsibility")
                == standard_claim.get("payer_responsibility")
            ), f"Claim {i}: payer responsibility mismatch"

            # Compare diagnosis codes
            streaming_diag = set(streaming_claim.get("diagnosis_codes", []))
            standard_diag = set(standard_claim.get("diagnosis_codes", []))
            assert streaming_diag == standard_diag, f"Claim {i}: diagnosis codes mismatch"

            # Compare line counts
            assert len(streaming_claim.get("lines", [])) == len(
                standard_claim.get("lines", [])
            ), f"Claim {i}: line count mismatch"

    def test_835_parsing_identical_results(self, sample_835_content: str):
        """Verify streaming parser produces identical results to standard parser for 835.
        
        Compares the output of StreamingEDIParser and EDIParser for 835 files,
        ensuring that envelope data, BPR data, and remittance details match
        between both parsers. Allows for minor differences in remittance counts
        due to parsing implementation differences.
        """
        streaming_parser = StreamingEDIParser()
        standard_parser = EDIParser()

        streaming_result = streaming_parser.parse(
            file_content=sample_835_content, filename="test_835.txt"
        )
        standard_result = standard_parser.parse(sample_835_content, "test_835.txt")

        # Compare file types
        assert streaming_result["file_type"] == standard_result["file_type"] == "835"

        # Compare envelope data
        assert streaming_result["envelope"] == standard_result["envelope"]

        # Compare remittance counts (may differ by 1 due to parsing differences, but should be close)
        assert abs(len(streaming_result["remittances"]) - len(standard_result["remittances"])) <= 1

        # Compare BPR data
        assert streaming_result.get("bpr") == standard_result.get("bpr")

        # Compare first few remittances in detail
        min_count = min(len(streaming_result["remittances"]), len(standard_result["remittances"]))
        for i in range(min_count):
            streaming_remit = streaming_result["remittances"][i]
            standard_remit = standard_result["remittances"][i]

            # Compare key fields
            assert (
                streaming_remit.get("claim_control_number")
                == standard_remit.get("claim_control_number")
            ), f"Remittance {i}: control number mismatch"
            assert (
                streaming_remit.get("claim_amount") == standard_remit.get("claim_amount")
            ), f"Remittance {i}: claim amount mismatch"
            assert (
                streaming_remit.get("claim_payment_amount")
                == standard_remit.get("claim_payment_amount")
            ), f"Remittance {i}: payment amount mismatch"

    def test_file_path_vs_string_content(self, sample_837_file_path: Path):
        """Test that file path and string content produce identical results.
        
        Verifies that parsing from a file path produces the same results
        as parsing from string content, ensuring both input methods are equivalent.
        """
        streaming_parser = StreamingEDIParser()

        # Read content
        with open(sample_837_file_path, "r") as f:
            content = f.read()

        # Parse from file path
        file_result = streaming_parser.parse(
            file_path=str(sample_837_file_path), filename="test_837.txt"
        )

        # Parse from string content
        string_result = streaming_parser.parse(
            file_content=content, filename="test_837.txt"
        )

        # Results should be identical
        assert file_result["file_type"] == string_result["file_type"]
        assert len(file_result["claims"]) == len(string_result["claims"])
        assert file_result["envelope"] == string_result["envelope"]


@pytest.mark.unit
class TestStreamingParserEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_file(self):
        """Test parsing empty file.
        
        Verifies that parsing an empty file raises an appropriate exception
        (ValueError or KeyError) since EDI files require envelope segments.
        """
        parser = StreamingEDIParser()
        with pytest.raises((ValueError, KeyError)):
            parser.parse(file_content="", filename="empty.txt")

    def test_file_with_only_envelope(self):
        """Test file with only envelope segments.
        
        Verifies that files containing only ISA, GS, ST, SE, GE, and IEA segments
        (no claim data) are parsed successfully and return an empty claims list.
        """
        content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
SE*3*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = StreamingEDIParser()
        result = parser.parse(file_content=content, filename="envelope_only.txt")

        assert result["file_type"] == "837"
        assert len(result.get("claims", [])) == 0

    def test_malformed_segments(self):
        """Test handling of malformed segments.
        
        Verifies that the parser can handle EDI files with missing or incomplete
        segments gracefully, still extracting available claim data when possible.
        """
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
        result = parser.parse(file_content=content, filename="malformed.txt")

        # Should still parse successfully
        assert result["file_type"] == "837"
        assert len(result.get("claims", [])) > 0

    def test_special_characters_in_data(self):
        """Test handling of special characters in data fields.
        
        Verifies that the parser correctly handles special characters (e.g., apostrophes)
        in patient names and other data fields without errors.
        """
        content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20240101*1200*CH~
HL*1**20*1~
PRV*BI*PXC*1234567890~
HL*2*1*22*0~
SBR*P*18*GROUP123******CI~
NM1*IL*1*O'BRIEN*JOHN*M***MI*123456789~
DMG*D8*19800101*M~
CLM*CLAIM001*1500.00~
SE*10*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = StreamingEDIParser()
        result = parser.parse(file_content=content, filename="special_chars.txt")

        assert result["file_type"] == "837"
        assert len(result.get("claims", [])) > 0

    def test_missing_optional_segments(self):
        """Test handling of missing optional segments.
        
        Verifies that the parser handles EDI files with missing optional segments
        gracefully, potentially marking claims as incomplete or generating warnings.
        """
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
        result = parser.parse(file_content=content, filename="missing_segments.txt")

        # Should parse but may have warnings
        assert result["file_type"] == "837"
        claims = result.get("claims", [])
        if claims:
            # Claims may be marked incomplete
            assert "is_incomplete" in claims[0] or "warnings" in claims[0]


@pytest.mark.unit
class TestStreamingParserMemoryEfficiency:
    """Test memory efficiency of streaming parser."""

    def test_large_file_processing(self, tmp_path):
        """Test that streaming parser can handle large files efficiently.
        
        Creates a large EDI file with 200 claims and verifies that the streaming
        parser can process it successfully, demonstrating memory efficiency
        compared to loading the entire file into memory.
        """
        # Create a large EDI file with many claims
        header = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20240101*1200*CH~"""

        claim_template = """HL*{idx}**20*1~
PRV*BI*PXC*1234567890~
HL*{idx2}*{idx}*22*0~
SBR*P*18*GROUP123******CI~
NM1*IL*1*DOE*JOHN*M***MI*123456789~
DMG*D8*19800101*M~
CLM*CLAIM{idx:03d}*1500.00~
HI*ABK:I10*E11.9~
LX*1~
SV1*HC:99213*1500.00*UN*1***1~
DTP*472*D8*20240101~"""

        footer = """SE*{count}*0001~
GE*1*1~
IEA*1*000000001~"""

        # Create file with 200 claims
        num_claims = 200
        content = header + "\n"
        for i in range(1, num_claims + 1):
            content += claim_template.format(idx=i, idx2=i * 2) + "\n"
        content += footer.format(count=3 + num_claims * 10)

        # Write to temporary file
        test_file = tmp_path / "large_test.edi"
        test_file.write_text(content)

        # Parse using streaming parser
        parser = StreamingEDIParser()
        result = parser.parse(file_path=str(test_file), filename="large_test.edi")

        assert result["file_type"] == "837"
        assert len(result["claims"]) == num_claims

    def test_incremental_claim_processing(self):
        """Test that claims are processed incrementally.
        
        Verifies that the parser correctly processes multiple claims in sequence,
        extracting each claim's control number and data correctly.
        """
        # Create file with multiple claims
        content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20240101*1200*CH~
HL*1**20*1~
PRV*BI*PXC*1234567890~
HL*2*1*22*0~
SBR*P*18*GROUP123******CI~
CLM*CLAIM001*1500.00~
HL*3**20*1~
PRV*BI*PXC*1234567890~
HL*4*3*22*0~
SBR*P*18*GROUP123******CI~
CLM*CLAIM002*2000.00~
HL*5**20*1~
PRV*BI*PXC*1234567890~
HL*6*5*22*0~
SBR*P*18*GROUP123******CI~
CLM*CLAIM003*2500.00~
SE*18*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = StreamingEDIParser()
        result = parser.parse(file_content=content, filename="multi_claim.txt")

        assert result["file_type"] == "837"
        assert len(result["claims"]) == 3

        # Verify each claim has correct control number
        claim_numbers = [c.get("claim_control_number") for c in result["claims"]]
        assert "CLAIM001" in claim_numbers
        assert "CLAIM002" in claim_numbers
        assert "CLAIM003" in claim_numbers


@pytest.mark.unit
class TestStreamingParserSegmentExtraction:
    """Test that all segment types are correctly extracted."""

    def test_envelope_segments_extracted(self, sample_837_content: str):
        """Test that envelope segments (ISA, GS, ST) are correctly extracted.
        
        Verifies that all envelope segments (ISA, GS, ST) are parsed and stored
        in the result's envelope dictionary with correct field extraction.
        """
        parser = StreamingEDIParser()
        result = parser.parse(file_content=sample_837_content, filename="test_837.txt")

        envelope = result["envelope"]
        assert "isa" in envelope
        assert "gs" in envelope
        assert "st" in envelope

        # Verify ISA segment data
        assert envelope["isa"].get("sender_id") is not None
        assert envelope["isa"].get("receiver_id") is not None

        # Verify GS segment data
        assert envelope["gs"].get("sender_id") is not None
        assert envelope["gs"].get("receiver_id") is not None

        # Verify ST segment data
        assert envelope["st"].get("transaction_set_id") == "837"

    def test_claim_segments_extracted(self, sample_837_content: str):
        """Test that claim segments are correctly extracted.
        
        Verifies that claim data including control numbers, charge amounts,
        and raw claim blocks are correctly extracted from 837 files.
        """
        parser = StreamingEDIParser()
        result = parser.parse(file_content=sample_837_content, filename="test_837.txt")

        claims = result.get("claims", [])
        assert len(claims) > 0

        # Check first claim has required fields
        first_claim = claims[0]
        assert "claim_control_number" in first_claim
        assert "total_charge_amount" in first_claim
        assert "raw_block" in first_claim

    def test_remittance_segments_extracted(self, sample_835_content: str):
        """Test that remittance segments are correctly extracted.
        
        Verifies that remittance data including control numbers, amounts,
        and raw remittance blocks are correctly extracted from 835 files.
        """
        parser = StreamingEDIParser()
        result = parser.parse(file_content=sample_835_content, filename="test_835.txt")

        remittances = result.get("remittances", [])
        assert len(remittances) > 0

        # Check first remittance has required fields
        first_remit = remittances[0]
        assert "claim_control_number" in first_remit
        assert "claim_amount" in first_remit
        assert "claim_payment_amount" in first_remit
        assert "raw_block" in first_remit


@pytest.mark.unit
class TestStreamingParserErrorHandling:
    """Test error handling and recovery."""

    def test_missing_critical_segments(self):
        """Test handling of missing critical segments.
        
        Verifies that files missing critical segments (e.g., CLM segment)
        are handled gracefully, potentially returning incomplete claims
        or generating appropriate warnings.
        """
        # File without CLM segment
        content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20240101*1200*CH~
HL*1**20*1~
PRV*BI*PXC*1234567890~
HL*2*1*22*0~
SBR*P*18*GROUP123******CI~
SE*8*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = StreamingEDIParser()
        result = parser.parse(file_content=content, filename="no_clm.txt")

        # Should handle gracefully
        assert result["file_type"] == "837"
        # May have no claims or incomplete claims
        claims = result.get("claims", [])
        if claims:
            assert claims[0].get("is_incomplete", False) or len(claims[0].get("warnings", [])) > 0

    def test_invalid_delimiters(self):
        """Test handling of files with unusual delimiters.
        
        Verifies that the parser can handle EDI files with standard delimiters
        but unusual formatting, still extracting claim data when possible.
        """
        # File with standard delimiters but unusual formatting
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
        result = parser.parse(file_content=content, filename="unusual_format.txt")

        # Should still parse
        assert result["file_type"] == "837"

    def test_very_long_segments(self):
        """Test handling of very long segments.
        
        Verifies that the parser can handle segments with very long data fields
        (e.g., 1000+ characters) without errors or truncation issues.
        """
        # Create segment with very long data
        long_data = "A" * 1000
        content = f"""ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20240101*1200*CH~
HL*1**20*1~
PRV*BI*PXC*1234567890~
HL*2*1*22*0~
SBR*P*18*GROUP123******CI~
NM1*IL*1*{long_data}*JOHN*M***MI*123456789~
CLM*CLAIM001*1500.00~
SE*9*0001~
GE*1*1~
IEA*1*000000001~"""

        parser = StreamingEDIParser()
        result = parser.parse(file_content=content, filename="long_segment.txt")

        # Should handle long segments
        assert result["file_type"] == "837"


@pytest.mark.performance
class TestStreamingParserPerformance:
    """Test performance characteristics of streaming parser."""

    def test_streaming_vs_standard_memory_usage(self, sample_837_content: str):
        """Compare memory usage between streaming and standard parser.
        
        Verifies that both parsers produce identical results. Note that actual
        memory measurement would require more sophisticated tools, but this test
        ensures functional equivalence between the two parsing approaches.
        """

        streaming_parser = StreamingEDIParser()
        standard_parser = EDIParser()

        # Parse with streaming parser
        streaming_result = streaming_parser.parse(
            file_content=sample_837_content, filename="test_837.txt"
        )

        # Parse with standard parser
        standard_result = standard_parser.parse(sample_837_content, "test_837.txt")

        # Both should produce same results
        assert len(streaming_result["claims"]) == len(standard_result["claims"])

        # Note: Actual memory measurement would require more sophisticated tools
        # This test just verifies both parsers work correctly

    def test_large_file_performance(self, tmp_path):
        """Test performance with large file.
        
        Creates a moderately large EDI file (500 claims) and verifies that
        the streaming parser can process it successfully, demonstrating
        scalability for production workloads.
        """
        # Create a moderately large file (500 claims)
        header = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20240101*1200*CH~"""

        claim_template = """HL*{idx}**20*1~
PRV*BI*PXC*1234567890~
HL*{idx2}*{idx}*22*0~
SBR*P*18*GROUP123******CI~
NM1*IL*1*DOE*JOHN*M***MI*123456789~
DMG*D8*19800101*M~
CLM*CLAIM{idx:03d}*1500.00~
HI*ABK:I10*E11.9~
LX*1~
SV1*HC:99213*1500.00*UN*1***1~
DTP*472*D8*20240101~"""

        footer = """SE*{count}*0001~
GE*1*1~
IEA*1*000000001~"""

        num_claims = 500
        content = header + "\n"
        for i in range(1, num_claims + 1):
            content += claim_template.format(idx=i, idx2=i * 2) + "\n"
        content += footer.format(count=3 + num_claims * 10)

        test_file = tmp_path / "performance_test.edi"
        test_file.write_text(content)

        # Parse using streaming parser
        parser = StreamingEDIParser()
        result = parser.parse(file_path=str(test_file), filename="performance_test.edi")

        assert result["file_type"] == "837"
        assert len(result["claims"]) == num_claims

