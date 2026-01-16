"""Stress tests for streaming parser - verify it handles extreme cases."""

import pytest

from app.services.edi.parser import EDIParser
from app.services.edi.parser_streaming import StreamingEDIParser


@pytest.mark.performance
class TestStreamingParserStress:
    """Stress tests for streaming parser."""

    def test_very_large_file_1000_claims(self, tmp_path):
        """Test streaming parser with 1000 claims.
        
        Verifies that the streaming parser can handle very large EDI files
        (1000+ claims) efficiently and correctly extract all claim data
        including control numbers.
        """
        # Create a very large EDI file
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
CLM*CLAIM{idx:04d}*1500.00~
HI*ABK:I10*E11.9~
LX*1~
SV1*HC:99213*1500.00*UN*1***1~
DTP*472*D8*20240101~"""

        footer = """SE*{count}*0001~
GE*1*1~
IEA*1*000000001~"""

        num_claims = 1000
        # Calculate segment count dynamically: header segments (3) + 
        # segments per claim (10) * num_claims
        segments_per_claim = 10
        header_segments = 3
        total_segments = header_segments + (num_claims * segments_per_claim)
        
        content = header + "\n"
        for i in range(1, num_claims + 1):
            content += claim_template.format(idx=i, idx2=i * 2) + "\n"
        content += footer.format(count=total_segments)

        test_file = tmp_path / "stress_test.edi"
        test_file.write_text(content)

        # Parse using streaming parser
        parser = StreamingEDIParser()
        result = parser.parse(file_path=str(test_file), filename="stress_test.edi")

        assert result["file_type"] == "837"
        assert len(result["claims"]) == num_claims

        # Verify all claims have correct control numbers
        for i, claim in enumerate(result["claims"]):
            expected_number = f"CLAIM{i+1:04d}"
            assert claim.get("claim_control_number") == expected_number

    def test_streaming_vs_standard_consistency_large_file(self, tmp_path):
        """Test that streaming and standard parser produce consistent results on large file.
        
        Verifies that both parsers produce identical results when processing
        large files (200+ claims), ensuring consistency between parsing approaches.
        """
        # Create file with 200 claims
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

        num_claims = 200
        # Calculate segment count dynamically: header segments (3) + 
        # segments per claim (10) * num_claims
        segments_per_claim = 10
        header_segments = 3
        total_segments = header_segments + (num_claims * segments_per_claim)
        
        content = header + "\n"
        for i in range(1, num_claims + 1):
            content += claim_template.format(idx=i, idx2=i * 2) + "\n"
        content += footer.format(count=total_segments)

        test_file = tmp_path / "consistency_test.edi"
        test_file.write_text(content)

        # Parse with both parsers
        streaming_parser = StreamingEDIParser()
        standard_parser = EDIParser()

        streaming_result = streaming_parser.parse(
            file_path=str(test_file), filename="consistency_test.edi"
        )
        standard_result = standard_parser.parse(content, "consistency_test.edi")

        # Compare results
        assert streaming_result["file_type"] == standard_result["file_type"]
        assert len(streaming_result["claims"]) == len(standard_result["claims"]) == num_claims

        # Compare first and last claims
        assert (
            streaming_result["claims"][0].get("claim_control_number")
            == standard_result["claims"][0].get("claim_control_number")
        )
        assert (
            streaming_result["claims"][-1].get("claim_control_number")
            == standard_result["claims"][-1].get("claim_control_number")
        )

    def test_file_with_many_segments_per_claim(self, tmp_path):
        """Test file where each claim has many segments.
        
        Verifies that the parser can handle claims with many service lines
        (20+ segments per claim) correctly, extracting all line items.
        """
        # Create claim with many service lines and segments
        header = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20240101*1200*CH~"""

        # Claim with 20 service lines
        claim_with_many_lines = """HL*1**20*1~
PRV*BI*PXC*1234567890~
HL*2*1*22*0~
SBR*P*18*GROUP123******CI~
NM1*IL*1*DOE*JOHN*M***MI*123456789~
DMG*D8*19800101*M~
CLM*CLAIM001*30000.00~
HI*ABK:I10*E11.9~"""

        # Add 20 service lines (using SV2 which the line extractor expects)
        num_service_lines = 20
        for i in range(1, num_service_lines + 1):
            claim_with_many_lines += f"""
LX*{i}~
SV2*HC:99213*1500.00*UN*1*1500.00~
DTP*472*D8*20240101~"""

        footer = """SE*{count}*0001~
GE*1*1~
IEA*1*000000001~"""

        # Calculate segment count: header (3) + claim base segments (7) + service lines (3 segments each)
        header_segments = 3
        claim_base_segments = 7
        segments_per_service_line = 3
        total_segments = header_segments + claim_base_segments + (num_service_lines * segments_per_service_line)
        
        content = header + claim_with_many_lines + footer.format(count=total_segments)

        test_file = tmp_path / "many_segments.edi"
        test_file.write_text(content)

        parser = StreamingEDIParser()
        result = parser.parse(file_path=str(test_file), filename="many_segments.edi")

        assert result["file_type"] == "837"
        assert len(result["claims"]) == 1
        claim = result["claims"][0]
        assert len(claim.get("lines", [])) == 20

    def test_consecutive_claim_blocks(self):
        """Test parsing multiple consecutive claim blocks.
        
        Verifies that the parser correctly handles multiple consecutive
        claim blocks in a single transaction set, extracting all claims
        with their correct control numbers.
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
        result = parser.parse(file_content=content, filename="consecutive_claims.txt")

        assert result["file_type"] == "837"
        assert len(result["claims"]) == 3

        # Verify claim numbers
        claim_numbers = [c.get("claim_control_number") for c in result["claims"]]
        assert "CLAIM001" in claim_numbers
        assert "CLAIM002" in claim_numbers
        assert "CLAIM003" in claim_numbers

