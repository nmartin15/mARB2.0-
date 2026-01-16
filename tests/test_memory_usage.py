"""Tests for memory usage during EDI file processing."""
import gc
import sys
from unittest.mock import patch

import pytest

from app.services.edi.parser import EDIParser
from app.services.edi.parser_optimized import OptimizedEDIParser
from app.services.queue.tasks import process_edi_file


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        # Fallback to sys.getsizeof for basic estimation
        return sys.getsizeof(gc.get_objects()) / (1024 * 1024)


@pytest.fixture
def very_large_837_content() -> str:
    """Generate a very large 837 file with 2000 claims for memory testing."""
    import time

    from scripts.generate_large_edi_files import (
        generate_837_claim,
        generate_837_footer,
        generate_837_header,
    )

    # Use timestamp to ensure unique claim numbers
    timestamp = int(time.time() * 1000) % 1000000

    header = generate_837_header()
    header_segments = len(header.split("~")) - 1

    claims = []
    for i in range(2, 2002):  # 2000 claims
        claim = generate_837_claim(i, i % 1000, i % 30)
        # Replace claim number with unique one
        claim = claim.replace(f"CLAIM{i:06d}", f"MEM{timestamp}{i:06d}")
        claims.append(claim)

    claims_content = "".join(claims)
    claim_segments = 2000 * 12
    total_segments = header_segments + claim_segments + 3

    footer = generate_837_footer(total_segments)

    return header + claims_content + footer


@pytest.fixture
def very_large_835_content() -> str:
    """Generate a very large 835 file with 2000 remittances for memory testing."""
    import time

    from scripts.generate_large_edi_files import (
        generate_835_footer,
        generate_835_header,
        generate_835_remittance,
    )

    # Use timestamp to ensure unique claim numbers
    timestamp = int(time.time() * 1000) % 1000000

    header = generate_835_header()
    header_segments = len(header.split("~")) - 1

    remittances = []
    for i in range(1, 2001):  # 2000 remittances
        claim_num = f"MEM{timestamp}{i:06d}"
        patient_num = f"PATIENT{i % 1000:06d}"
        remittance = generate_835_remittance(i, claim_num, patient_num, i % 30)
        remittances.append(remittance)

    remittances_content = "".join(remittances)
    remit_segments = 2000 * 15
    total_segments = header_segments + remit_segments + 3

    footer = generate_835_footer(total_segments)

    return header + remittances_content + footer


@pytest.mark.performance
class TestMemoryUsage:
    """Tests for memory usage during EDI file processing."""

    def test_memory_usage_standard_parser(self, very_large_837_content: str):
        """Test memory usage with standard parser."""
        parser = EDIParser()

        # Measure initial memory
        gc.collect()
        initial_memory = get_memory_usage_mb()

        # Parse file
        result = parser.parse(very_large_837_content, "very_large_837.edi")

        # Measure memory after parsing
        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        # Verify parsing succeeded
        assert result["file_type"] == "837"
        assert len(result.get("claims", [])) > 0

        file_size_mb = len(very_large_837_content.encode("utf-8")) / (1024 * 1024)

        print("\n[MEMORY] Standard Parser:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Memory delta: {memory_delta:.2f} MB")
        print(f"  Memory ratio: {memory_delta / file_size_mb:.2f}x file size")

        # Memory delta should be reasonable (less than 1GB for 2000 claims)
        assert memory_delta < 1000, \
            f"Memory delta {memory_delta:.2f} MB is too high for 2000 claims"

        # Memory efficiency: delta should be less than 20x file size
        if file_size_mb > 0:
            memory_ratio = memory_delta / file_size_mb
            assert memory_ratio < 20, \
                f"Memory delta {memory_delta:.2f} MB is {memory_ratio:.1f}x file size (too high)"

    def test_memory_usage_optimized_parser(self, very_large_837_content: str):
        """Test memory usage with optimized parser."""
        parser = OptimizedEDIParser()

        # Measure initial memory
        gc.collect()
        initial_memory = get_memory_usage_mb()

        # Parse file
        result = parser.parse(very_large_837_content, "very_large_837.edi")

        # Measure memory after parsing
        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        # Verify parsing succeeded
        assert result["file_type"] == "837"
        assert len(result.get("claims", [])) > 0

        file_size_mb = len(very_large_837_content.encode("utf-8")) / (1024 * 1024)

        print("\n[MEMORY] Optimized Parser:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Memory delta: {memory_delta:.2f} MB")
        print(f"  Memory ratio: {memory_delta / file_size_mb:.2f}x file size")

        # Memory delta should be reasonable
        assert memory_delta < 1000, \
            f"Memory delta {memory_delta:.2f} MB is too high"

        # Memory efficiency check
        if file_size_mb > 0:
            memory_ratio = memory_delta / file_size_mb
            assert memory_ratio < 20, \
                f"Memory delta {memory_delta:.2f} MB is {memory_ratio:.1f}x file size"

    def test_memory_usage_with_database_operations(self, very_large_837_content: str, db_session):
        """Test memory usage during full processing including database operations."""
        # Measure initial memory
        gc.collect()
        initial_memory = get_memory_usage_mb()

        # Process file with database operations
        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            result = process_edi_file.run(
                file_content=very_large_837_content,
                filename="very_large_837.edi",
                file_type="837",
            )

        # Measure memory after processing
        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        # Verify processing succeeded
        assert result["status"] == "success"
        assert result["claims_created"] > 0

        file_size_mb = len(very_large_837_content.encode("utf-8")) / (1024 * 1024)

        print("\n[MEMORY] Full Processing (with DB):")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Memory delta: {memory_delta:.2f} MB")
        print(f"  Claims created: {result['claims_created']}")

        # Memory delta should be reasonable (database operations add overhead)
        assert memory_delta < 1500, \
            f"Memory delta {memory_delta:.2f} MB is too high for full processing"

        # Check performance data if available
        if "_performance" in result:
            perf = result["_performance"]
            perf_memory_delta = perf.get("memory_delta_mb", 0)
            print(f"  Performance monitor memory delta: {perf_memory_delta:.2f} MB")

    def test_memory_usage_835_file(self, very_large_835_content: str, db_session):
        """Test memory usage during 835 file processing."""
        # Measure initial memory
        gc.collect()
        initial_memory = get_memory_usage_mb()

        # Process file
        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            result = process_edi_file.run(
                file_content=very_large_835_content,
                filename="very_large_835.edi",
                file_type="835",
            )

        # Measure memory after processing
        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        # Verify processing succeeded
        assert result["status"] == "success"
        assert result["remittances_created"] > 0

        file_size_mb = len(very_large_835_content.encode("utf-8")) / (1024 * 1024)

        print("\n[MEMORY] 835 File Processing:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Memory delta: {memory_delta:.2f} MB")
        print(f"  Remittances created: {result['remittances_created']}")

        # Memory delta should be reasonable
        assert memory_delta < 1500, \
            f"Memory delta {memory_delta:.2f} MB is too high"

    def test_memory_does_not_grow_unbounded(self, very_large_837_content: str):
        """Test that memory doesn't grow unbounded during processing."""
        parser = EDIParser()

        # Process file multiple times to check for memory leaks
        memory_deltas = []

        for iteration in range(3):
            gc.collect()
            initial_memory = get_memory_usage_mb()

            result = parser.parse(very_large_837_content, f"test_{iteration}.edi")

            gc.collect()
            final_memory = get_memory_usage_mb()
            memory_delta = final_memory - initial_memory
            memory_deltas.append(memory_delta)

            assert result["file_type"] == "837"

        print("\n[MEMORY] Multiple Iterations:")
        for i, delta in enumerate(memory_deltas):
            print(f"  Iteration {i + 1}: {delta:.2f} MB")

        # Memory deltas should be similar (not growing unbounded)
        if len(memory_deltas) > 1:
            avg_delta = sum(memory_deltas) / len(memory_deltas)
            max_delta = max(memory_deltas)

            # Max delta should not be more than 2x average (allowing for some variance)
            assert max_delta < avg_delta * 2, \
                f"Memory leak detected: max delta {max_delta:.2f} MB is > 2x average {avg_delta:.2f} MB"

    def test_memory_usage_batch_processing(self, very_large_837_content: str, db_session):
        """Test that batch processing reduces memory usage."""
        # Measure memory with batch processing (default)
        gc.collect()
        initial_memory = get_memory_usage_mb()

        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            result = process_edi_file.run(
                file_content=very_large_837_content,
                filename="very_large_837.edi",
                file_type="837",
            )

        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        assert result["status"] == "success"

        file_size_mb = len(very_large_837_content.encode("utf-8")) / (1024 * 1024)

        print("\n[MEMORY] Batch Processing:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Memory delta: {memory_delta:.2f} MB")
        print(f"  Claims created: {result['claims_created']}")

        # Batch processing should keep memory reasonable
        assert memory_delta < 1500, \
            f"Memory delta {memory_delta:.2f} MB is too high with batch processing"

        # Memory per claim should be reasonable
        if result["claims_created"] > 0:
            memory_per_claim = memory_delta / result["claims_created"]
            assert memory_per_claim < 1.0, \
                f"Memory per claim {memory_per_claim:.3f} MB is too high"
            print(f"  Memory per claim: {memory_per_claim:.3f} MB")


@pytest.mark.performance
class TestMemoryUsageSmallFiles:
    """Tests for memory usage with small files."""

    def test_memory_usage_small_file(self, db_session):
        """Test memory usage with a small file."""
        # Use a simple small 835 file
        sample_835_content = """ISA*00*          *00*          *ZZ*BCBSILPAYER     *ZZ*MEDPRACTICE001   *241220*143052*^*00501*000000001*0*P*:~
GS*HP*BCBSILPAYER*MEDPRACTICE001*20241220*143052*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*28750.00*C*CHK987654321*20241220*123456789*01*987654321*DA*1234567890*20241220~
TRN*1*REM20241220001*987654321~
REF*EV*REM20241220001~
DTM*405*20241220~
DTM*097*20241220*20241220~
N1*PR*BLUE CROSS BLUE SHIELD OF ILLINOIS~
N3*300 EAST RANDOLPH STREET~
N4*CHICAGO*IL*60601~
PER*BL*CLAIMS DEPARTMENT*TE*8005551234*FX*8005555678~
LX*1~
CLP*CLAIM20241215001*1*1500.00*1200.00*0*11*1234567890*20241215*1~
CAS*PR*1*50.00~
CAS*PR*2*150.00~
CAS*CO*45*100.00~
NM1*QC*1*PATIENT*JOHN*M***MI*123456789~
NM1*82*1*PROVIDER*JANE*M***XX*1234567890~
REF*D9*PATIENT001~
REF*1W*123456789~
AMT*AU*200.00~
AMT*D*50.00~
AMT*F5*150.00~
SVC*HC:99213*1500.00*1200.00*UN*1~
DTM*472*D8*20241215~
CAS*CO*45*100.00~
CAS*PR*1*50.00~
CAS*PR*2*150.00~
SE*24*0001~
GE*1*1~
IEA*1*000000001~"""

        gc.collect()
        initial_memory = get_memory_usage_mb()

        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            result = process_edi_file.run(
                file_content=sample_835_content,
                filename="small_835.edi",
                file_type="835",
            )

        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        assert result["status"] == "success"

        print("\n[MEMORY] Small File:")
        print(f"  Memory delta: {memory_delta:.2f} MB")

        # Small files should use minimal memory
        assert memory_delta < 100, \
            f"Memory delta {memory_delta:.2f} MB is too high for small file"

