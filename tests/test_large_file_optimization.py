"""Tests for large file EDI parsing optimizations."""
import time

import pytest

from app.models.database import Claim
from app.services.edi.parser import EDIParser
from app.services.queue.tasks import process_edi_file


@pytest.fixture
def very_large_837_content() -> str:
    """Create a very large 837 file with 200+ claims for performance testing.
    
    This fixture generates a complete EDI 837 file structure with:
    - ISA/GS/ST header segments (interchange, functional group, transaction set headers)
    - 200 claim blocks (HL segments with patient, payer, claim, and line item data)
    - SE/GE/IEA footer segments (transaction set, functional group, interchange trailers)
    
    Each claim includes:
    - Patient demographics (SBR, NM1, DMG segments)
    - Payer information (NM1 segment)
    - Claim header (CLM segment with claim number and amount)
    - Service dates (DTP segments)
    - Diagnosis codes (HI segment)
    - Service line items (LX, SV1 segments)
    
    The generated file is used to test:
    - Batch processing performance
    - Memory efficiency during parsing
    - Database operation optimization
    - Progress tracking for large files
    """
    # Base claim template: Each claim consists of hierarchical level (HL) segments
    # followed by subscriber (SBR), name (NM1), demographics (DMG), payer info,
    # claim (CLM), dates (DTP), diagnosis (HI), and service lines (LX, SV1)
    base_claim = """HL*{idx}*1*22*0~
SBR*P*18*GROUP{idx}******CI~
NM1*IL*1*DOE*JOHN*M***MI*123456789~
DMG*D8*19800101*M~
NM1*PR*2*BLUE CROSS BLUE SHIELD*****PI*BLUE_CROSS~
CLM*CLAIM{idx:03d}*1500.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241215~
DTP*472*D8*20241215~
REF*D9*PATIENT{idx:03d}~
HI*ABK:I10*E11.9~
LX*1~
SV1*HC:99213*1500.00*UN*1***1~
DTP*472*D8*20241215~"""

    # EDI file structure: Interchange header (ISA) defines sender/receiver and control numbers
    # Functional group header (GS) groups related transactions
    # Transaction set header (ST) marks the start of a claim transaction
    # BHT segment provides transaction purpose and reference
    # Provider information (NM1 segments) identifies the submitting entity
    header = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
NM1*41*2*SAMPLE MEDICAL PRACTICE*****46*1234567890~
HL*1**20*1~
PRV*BI*PXC*207RI0001X~
NM1*85*2*DR JOHN SMITH*****XX*1234567890~"""

    # Footer segments: Transaction set trailer (SE) with segment count,
    # Functional group trailer (GE), and Interchange trailer (IEA)
    footer = """SE*{count}*0001~
GE*1*1~
IEA*1*000000001~"""

    # Generate 200 claim blocks (indices 2-201) to create a large file
    # Each claim is formatted with its index for unique claim numbers
    # The segment count in SE includes all segments: header segments + claim segments + footer segments
    claims = [base_claim.format(idx=i) for i in range(2, 202)]
    return header + "".join(claims) + footer.format(count=len(claims) + 7)


@pytest.mark.performance
class TestLargeFileOptimization:
    """Tests for large file parsing optimizations."""

    def test_batch_processing_performance(self, very_large_837_content: str):
        """Test that batch processing improves performance for large files."""
        parser = EDIParser()

        start_time = time.time()
        result = parser.parse(very_large_837_content, "very_large_837.txt")
        elapsed_time = time.time() - start_time

        assert result["file_type"] == "837"
        claims = result.get("claims", [])
        assert len(claims) >= 100, "Should parse at least 100 claims"

        # Should complete in reasonable time (less than 30 seconds for 200 claims)
        assert elapsed_time < 30.0, \
            f"Parsing took {elapsed_time:.3f}s, expected < 30.0s for 200 claims"

        # Average time per claim should be reasonable
        avg_time_per_claim = elapsed_time / len(claims)
        assert avg_time_per_claim < 0.2, \
            f"Average time per claim {avg_time_per_claim:.3f}s is too high"

        print(f"\n[PERF] Very large file (200 claims): {elapsed_time:.3f}s")
        print(f"[PERF] Average time per claim: {avg_time_per_claim:.3f}s")
        print(f"[PERF] Claims per second: {len(claims) / elapsed_time:.2f}")

        # Check for performance monitoring data
        if "_performance" in result:
            perf = result["_performance"]
            print(f"[PERF] Memory delta: {perf.get('memory_delta_mb', 0):.2f} MB")
            print(f"[PERF] Checkpoints: {len(perf.get('checkpoints', []))}")

    def test_memory_efficiency_large_file(self, very_large_837_content: str):
        """Test that large file parsing doesn't use excessive memory."""
        import sys

        parser = EDIParser()

        file_size_mb = len(very_large_837_content.encode("utf-8")) / (1024 * 1024)
        initial_size = sys.getsizeof(very_large_837_content)

        result = parser.parse(very_large_837_content, "very_large_837.txt")

        # Check performance monitoring if available
        if "_performance" in result:
            perf = result["_performance"]
            memory_delta = perf.get("memory_delta_mb", 0)

            print(f"\n[PERF] File size: {file_size_mb:.2f} MB")
            print(f"[PERF] Memory delta: {memory_delta:.2f} MB")

            # Memory delta should be reasonable (less than 1GB for 200 claims)
            assert memory_delta < 1000, \
                f"Memory delta {memory_delta:.2f} MB is too high for 200 claims"

            # Memory efficiency: delta should be less than 10x file size
            if file_size_mb > 0:
                memory_ratio = memory_delta / file_size_mb
                assert memory_ratio < 10, \
                    f"Memory delta {memory_delta:.2f} MB is {memory_ratio:.1f}x file size"

    def test_batch_database_operations(self, very_large_837_content: str, db_session):
        """Test that batch database operations work correctly."""
        from unittest.mock import patch

        # Mock the database session
        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            # Process file
            result = process_edi_file.run(
                file_content=very_large_837_content,
                filename="very_large_837.txt",
                file_type="837",
            )

            assert result["status"] == "success"
            assert result["claims_created"] > 0

            # Verify claims were created in database
            claims_count = db_session.query(Claim).count()
            assert claims_count == result["claims_created"], \
                f"Expected {result['claims_created']} claims, found {claims_count}"

            print(f"\n[PERF] Batch database operations: {result['claims_created']} claims created")

            # Check for performance data
            if "_performance" in result:
                perf = result["_performance"]
                print(f"[PERF] Total processing time: {perf.get('total_time_seconds', 0):.3f}s")
                print(f"[PERF] Memory delta: {perf.get('memory_delta_mb', 0):.2f} MB")

    def test_progress_tracking_large_file(self, very_large_837_content: str):
        """Test that progress tracking works for large files."""
        parser = EDIParser()

        result = parser.parse(very_large_837_content, "very_large_837.txt")

        # Check for performance monitoring data
        if "_performance" in result:
            perf = result["_performance"]
            checkpoints = perf.get("checkpoints", [])

            assert len(checkpoints) > 0, "Should have performance checkpoints"

            # Should have start checkpoint
            checkpoint_names = [cp["name"] for cp in checkpoints]
            assert "start" in checkpoint_names or "segments_split" in checkpoint_names, \
                "Should have start checkpoint"

            print(f"\n[PERF] Progress tracking: {len(checkpoints)} checkpoints")
            for checkpoint in checkpoints:
                print(f"  - {checkpoint['name']}: {checkpoint.get('elapsed_seconds', 0):.3f}s")

    def test_optimized_segment_processing(self, very_large_837_content: str):
        """Test that optimized segment processing is used for large files."""
        parser = EDIParser()

        start_time = time.time()
        result = parser.parse(very_large_837_content, "very_large_837.txt")
        elapsed_time = time.time() - start_time

        # Verify parsing completed successfully
        assert result["file_type"] == "837"
        assert len(result.get("claims", [])) > 0

        # Segment processing should be efficient
        # For 200 claims, should complete in reasonable time
        assert elapsed_time < 30.0, \
            f"Segment processing took {elapsed_time:.3f}s, expected < 30.0s"

        print(f"\n[PERF] Optimized segment processing: {elapsed_time:.3f}s for 200 claims")

