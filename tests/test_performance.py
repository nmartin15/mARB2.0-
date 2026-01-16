"""Performance tests for mARB 2.0."""
import time
from pathlib import Path
from statistics import mean, median

import pytest

from app.models.database import Claim
from app.services.edi.parser import EDIParser
from app.utils.cache import cache

# Performance thresholds (in seconds)
PARSER_SMALL_FILE_THRESHOLD = 1.0  # 1 second for small file
PARSER_LARGE_FILE_THRESHOLD = 10.0  # 10 seconds for large file (100 claims)
API_ENDPOINT_THRESHOLD = 0.5  # 500ms for API endpoints
DATABASE_QUERY_THRESHOLD = 0.1  # 100ms for database queries
CACHE_GET_THRESHOLD = 0.01  # 10ms for cache get operations


@pytest.fixture
def sample_837_file_path() -> Path:
    """Get path to sample 837 file."""
    return Path(__file__).parent.parent / "samples" / "sample_837.txt"


@pytest.fixture
def sample_837_content(sample_837_file_path: Path) -> str:
    """Load sample 837 file content."""
    with open(sample_837_file_path, "r") as f:
        return f.read()


@pytest.fixture
def large_837_content() -> str:
    """Create a large 837 file with multiple claims."""
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

    header = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
NM1*41*2*SAMPLE MEDICAL PRACTICE*****46*1234567890~
HL*1**20*1~
PRV*BI*PXC*207RI0001X~
NM1*85*2*DR JOHN SMITH*****XX*1234567890~"""

    footer = """SE*{count}*0001~
GE*1*1~
IEA*1*000000001~"""

    # Create 50 claims for performance testing
    claims = [base_claim.format(idx=i) for i in range(2, 52)]
    return header + "".join(claims) + footer.format(count=len(claims) + 7)


@pytest.mark.performance
class TestParserPerformance:
    """Performance tests for EDI parser."""

    def test_parse_small_837_file_performance(self, sample_837_content: str):
        """Test parsing performance for small 837 file."""
        parser = EDIParser()

        start_time = time.time()
        result = parser.parse(sample_837_content, "sample_837.txt")
        elapsed_time = time.time() - start_time

        assert result["file_type"] == "837"
        assert elapsed_time < PARSER_SMALL_FILE_THRESHOLD, \
            f"Parsing took {elapsed_time:.3f}s, expected < {PARSER_SMALL_FILE_THRESHOLD}s"

        # Log performance metric
        print(f"\n[PERF] Small 837 file parsing: {elapsed_time:.3f}s")

        # Check for performance data if available
        if "_performance" in result:
            perf = result["_performance"]
            print(f"[PERF] Memory delta: {perf.get('memory_delta_mb', 0):.2f} MB")
            print(f"[PERF] Checkpoints: {len(perf.get('checkpoints', []))}")

    def test_parse_large_837_file_performance(self, large_837_content: str):
        """Test parsing performance for large 837 file (50+ claims)."""
        parser = EDIParser()

        start_time = time.time()
        result = parser.parse(large_837_content, "large_837.txt")
        elapsed_time = time.time() - start_time

        assert result["file_type"] == "837"
        claims = result.get("claims", [])
        assert len(claims) >= 10, "Should parse at least 10 claims"
        assert elapsed_time < PARSER_LARGE_FILE_THRESHOLD, \
            f"Parsing took {elapsed_time:.3f}s, expected < {PARSER_LARGE_FILE_THRESHOLD}s"

        # Log performance metrics
        print(f"\n[PERF] Large 837 file parsing: {elapsed_time:.3f}s ({len(claims)} claims)")
        print(f"[PERF] Average time per claim: {elapsed_time/len(claims):.3f}s")

        # Check for performance data if available
        if "_performance" in result:
            perf = result["_performance"]
            print(f"[PERF] Memory delta: {perf.get('memory_delta_mb', 0):.2f} MB")
            print(f"[PERF] Total checkpoints: {len(perf.get('checkpoints', []))}")
            for checkpoint in perf.get("checkpoints", []):
                print(f"  - {checkpoint['name']}: {checkpoint.get('elapsed_seconds', 0):.3f}s")

    def test_parse_multiple_files_sequential(self, sample_837_content: str):
        """Test parsing multiple files sequentially."""
        parser = EDIParser()
        num_files = 10

        start_time = time.time()
        for i in range(num_files):
            result = parser.parse(sample_837_content, f"file_{i}.txt")
            assert result["file_type"] == "837"
        elapsed_time = time.time() - start_time

        avg_time = elapsed_time / num_files
        print(f"\n[PERF] Sequential parsing ({num_files} files): {elapsed_time:.3f}s total, {avg_time:.3f}s avg")

        # Should be able to parse 10 files in reasonable time
        assert avg_time < PARSER_SMALL_FILE_THRESHOLD * 2, \
            f"Average parsing time {avg_time:.3f}s is too high"

    def test_parser_memory_usage(self, large_837_content: str):
        """Test that parser doesn't use excessive memory."""
        import sys

        parser = EDIParser()

        # Parse file and check memory doesn't grow excessively
        initial_size = sys.getsizeof(large_837_content)

        result = parser.parse(large_837_content, "large_837.txt")

        # Result size should be reasonable compared to input
        result_size = sys.getsizeof(str(result))
        size_ratio = result_size / initial_size if initial_size > 0 else 0

        # Result shouldn't be more than 10x the input size
        assert size_ratio < 10, \
            f"Result size ({result_size}) is {size_ratio:.1f}x input size ({initial_size})"

        print(f"\n[PERF] Memory usage: input={initial_size} bytes, result={result_size} bytes, ratio={size_ratio:.2f}x")

        # Check performance monitoring data if available
        if "_performance" in result:
            perf = result["_performance"]
            memory_delta = perf.get("memory_delta_mb", 0)
            print(f"[PERF] Process memory delta: {memory_delta:.2f} MB")

            # Memory delta should be reasonable (less than 500MB for 50 claims)
            assert memory_delta < 500, \
                f"Memory delta {memory_delta:.2f} MB is too high for 50 claims"


@pytest.mark.performance
class TestAPIPerformance:
    """Performance tests for API endpoints."""

    def test_health_endpoint_performance(self, client):
        """Test health endpoint response time."""
        times = []
        num_requests = 10

        for _ in range(num_requests):
            start_time = time.time()
            response = client.get("/api/v1/health")
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)
            assert response.status_code == 200

        avg_time = mean(times)
        median_time = median(times)
        max_time = max(times)

        print(f"\n[PERF] Health endpoint ({num_requests} requests):")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  Median: {median_time:.3f}s")
        print(f"  Max: {max_time:.3f}s")

        assert avg_time < API_ENDPOINT_THRESHOLD, \
            f"Average response time {avg_time:.3f}s exceeds threshold {API_ENDPOINT_THRESHOLD}s"

    def test_claims_list_endpoint_performance(self, client, db_session):
        """Test claims list endpoint performance."""
        from tests.factories import ClaimFactory, PayerFactory, ProviderFactory

        # Create test data
        provider = ProviderFactory()
        payer = PayerFactory()
        for _ in range(20):
            ClaimFactory(provider=provider, payer=payer)
        db_session.commit()

        times = []
        num_requests = 5

        for _ in range(num_requests):
            start_time = time.time()
            response = client.get("/api/v1/claims?skip=0&limit=100")
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)
            assert response.status_code == 200

        avg_time = mean(times)
        print(f"\n[PERF] Claims list endpoint ({num_requests} requests): {avg_time:.3f}s avg")

        assert avg_time < API_ENDPOINT_THRESHOLD * 2, \
            f"Average response time {avg_time:.3f}s exceeds threshold"

    def test_claim_detail_endpoint_performance(self, client, db_session):
        """Test claim detail endpoint performance."""
        from tests.factories import ClaimFactory, PayerFactory, ProviderFactory

        # Create test claim
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        db_session.commit()

        times = []
        num_requests = 10

        for _ in range(num_requests):
            start_time = time.time()
            response = client.get(f"/api/v1/claims/{claim.id}")
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)
            assert response.status_code == 200

        avg_time = mean(times)
        print(f"\n[PERF] Claim detail endpoint ({num_requests} requests): {avg_time:.3f}s avg")

        assert avg_time < API_ENDPOINT_THRESHOLD, \
            f"Average response time {avg_time:.3f}s exceeds threshold"

    def test_concurrent_api_requests(self, client, db_session):
        """Test API performance under concurrent load."""
        import concurrent.futures

        from tests.factories import ClaimFactory, PayerFactory, ProviderFactory

        # Create test data
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        db_session.commit()

        num_requests = 20
        num_workers = 5

        def make_request():
            start_time = time.time()
            response = client.get(f"/api/v1/claims/{claim.id}")
            elapsed_time = time.time() - start_time
            assert response.status_code == 200
            return elapsed_time

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            times = list(executor.map(make_request, range(num_requests)))
        total_time = time.time() - start_time

        avg_time = mean(times)
        max_time = max(times)

        print(f"\n[PERF] Concurrent API requests ({num_requests} requests, {num_workers} workers):")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  Max: {max_time:.3f}s")
        print(f"  Requests/sec: {num_requests/total_time:.2f}")

        # Average should still be reasonable even under load
        assert avg_time < API_ENDPOINT_THRESHOLD * 3, \
            f"Average response time {avg_time:.3f}s too high under load"


@pytest.mark.performance
class TestDatabasePerformance:
    """Performance tests for database queries."""

    def test_query_claims_by_payer_performance(self, db_session):
        """Test querying claims by payer performance."""
        from tests.factories import ClaimFactory, PayerFactory, ProviderFactory

        # Create test data
        provider = ProviderFactory()
        payer1 = PayerFactory()
        payer2 = PayerFactory()

        # Create 50 claims for payer1, 50 for payer2
        for _ in range(50):
            ClaimFactory(provider=provider, payer=payer1)
            ClaimFactory(provider=provider, payer=payer2)
        db_session.commit()

        times = []
        num_queries = 10

        for _ in range(num_queries):
            start_time = time.time()
            claims = db_session.query(Claim).filter(Claim.payer_id == payer1.id).all()
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)
            assert len(claims) == 50

        avg_time = mean(times)
        print(f"\n[PERF] Query claims by payer ({num_queries} queries): {avg_time:.3f}s avg")

        assert avg_time < DATABASE_QUERY_THRESHOLD * 5, \
            f"Average query time {avg_time:.3f}s exceeds threshold"

    def test_query_with_joins_performance(self, db_session):
        """Test query performance with joins."""
        from sqlalchemy.orm import joinedload

        from tests.factories import ClaimFactory, PayerFactory, ProviderFactory

        # Create test data
        provider = ProviderFactory()
        payer = PayerFactory()
        for _ in range(20):
            ClaimFactory(provider=provider, payer=payer)
        db_session.commit()

        times = []
        num_queries = 10

        for _ in range(num_queries):
            start_time = time.time()
            claims = db_session.query(Claim).options(
                joinedload(Claim.provider),
                joinedload(Claim.payer)
            ).limit(20).all()
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)
            assert len(claims) == 20

        avg_time = mean(times)
        print(f"\n[PERF] Query with joins ({num_queries} queries): {avg_time:.3f}s avg")

        assert avg_time < DATABASE_QUERY_THRESHOLD * 10, \
            f"Average query time {avg_time:.3f}s exceeds threshold"

    def test_bulk_insert_performance(self, db_session):
        """Test bulk insert performance."""
        from app.models.database import ClaimStatus
        from tests.factories import PayerFactory, ProviderFactory

        provider = ProviderFactory()
        payer = PayerFactory()

        num_claims = 100

        start_time = time.time()
        claims = []
        for i in range(num_claims):
            claim = Claim(
                claim_control_number=f"CLM{i:03d}",
                patient_control_number=f"PAT{i:03d}",
                provider_id=provider.id,
                payer_id=payer.id,
                total_charge_amount=1000.00 + i,
                status=ClaimStatus.PENDING,
                practice_id="PRACTICE001",
            )
            claims.append(claim)

        db_session.bulk_save_objects(claims)
        db_session.commit()
        elapsed_time = time.time() - start_time

        avg_time = elapsed_time / num_claims
        print(f"\n[PERF] Bulk insert ({num_claims} claims): {elapsed_time:.3f}s total, {avg_time:.3f}s per claim")

        # Should be able to insert 100 claims quickly
        assert elapsed_time < 5.0, \
            f"Bulk insert took {elapsed_time:.3f}s, expected < 5.0s"


@pytest.mark.performance
class TestCachePerformance:
    """Performance tests for caching."""

    def test_cache_get_performance(self):
        """Test cache get operation performance."""
        cache_key = "test:performance:key"
        cache_value = {"test": "data", "number": 123}

        # Set value first
        cache.set(cache_key, cache_value, ttl=60)

        times = []
        num_operations = 100

        for _ in range(num_operations):
            start_time = time.time()
            value = cache.get(cache_key)
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)
            assert value == cache_value

        avg_time = mean(times)
        max_time = max(times)

        print(f"\n[PERF] Cache get ({num_operations} operations):")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  Max: {max_time:.3f}s")

        assert avg_time < CACHE_GET_THRESHOLD, \
            f"Average cache get time {avg_time:.3f}s exceeds threshold {CACHE_GET_THRESHOLD}s"

    def test_cache_set_performance(self):
        """Test cache set operation performance."""
        times = []
        num_operations = 100

        for i in range(num_operations):
            cache_key = f"test:performance:set:{i}"
            cache_value = {"test": "data", "number": i}

            start_time = time.time()
            cache.set(cache_key, cache_value, ttl=60)
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)

        avg_time = mean(times)
        print(f"\n[PERF] Cache set ({num_operations} operations): {avg_time:.3f}s avg")

        # Cache set should be fast
        assert avg_time < CACHE_GET_THRESHOLD * 2, \
            f"Average cache set time {avg_time:.3f}s exceeds threshold"

    def test_cache_miss_performance(self):
        """Test cache miss performance."""
        times = []
        num_operations = 100

        for i in range(num_operations):
            cache_key = f"test:performance:miss:{i}"

            start_time = time.time()
            value = cache.get(cache_key)
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)
            assert value is None

        avg_time = mean(times)
        print(f"\n[PERF] Cache miss ({num_operations} operations): {avg_time:.3f}s avg")

        # Cache miss should still be fast
        assert avg_time < CACHE_GET_THRESHOLD * 2, \
            f"Average cache miss time {avg_time:.3f}s exceeds threshold"

    def test_cache_hit_rate_impact(self, client, db_session):
        """Test that caching improves API response times."""
        from tests.factories import ClaimFactory, PayerFactory, ProviderFactory

        # Create test claim
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        db_session.commit()

        # Clear cache
        cache.clear_namespace()

        # First request (cache miss)
        start_time = time.time()
        response1 = client.get(f"/api/v1/claims/{claim.id}")
        first_request_time = time.time() - start_time
        assert response1.status_code == 200

        # Second request (cache hit)
        start_time = time.time()
        response2 = client.get(f"/api/v1/claims/{claim.id}")
        second_request_time = time.time() - start_time
        assert response2.status_code == 200

        improvement = (first_request_time - second_request_time) / first_request_time * 100

        print("\n[PERF] Cache impact on API response:")
        print(f"  First request (miss): {first_request_time:.3f}s")
        print(f"  Second request (hit): {second_request_time:.3f}s")
        print(f"  Improvement: {improvement:.1f}%")

        # Cached request should be faster
        assert second_request_time < first_request_time, \
            "Cached request should be faster than uncached"


@pytest.mark.performance
class TestEndToEndPerformance:
    """End-to-end performance tests."""

    def test_complete_claim_processing_flow(self, client, db_session, sample_837_content):
        """Test performance of complete claim processing flow."""
        from io import BytesIO
        from unittest.mock import MagicMock, patch

        from app.services.queue.tasks import process_edi_file

        # Upload file
        file_content = sample_837_content.encode("utf-8")
        file = ("test_837_perf.edi", BytesIO(file_content), "text/plain")

        with patch("app.api.routes.claims.process_edi_file") as mock_task:
            mock_task_instance = MagicMock()
            mock_task_instance.id = "test-task-id"
            mock_task.delay = MagicMock(return_value=mock_task_instance)

            start_time = time.time()
            response = client.post("/api/v1/claims/upload", files={"file": file})
            upload_time = time.time() - start_time

            assert response.status_code == 200

            call_args = mock_task.delay.call_args
            task_file_content = call_args[1]["file_content"]

        # Process file
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            start_time = time.time()
            result = process_edi_file.run(
                file_content=task_file_content,
                filename="test_837_perf.edi",
                file_type="837",
            )
            processing_time = time.time() - start_time

            assert result["status"] == "success"

        total_time = upload_time + processing_time

        print("\n[PERF] Complete claim processing flow:")
        print(f"  Upload: {upload_time:.3f}s")
        print(f"  Processing: {processing_time:.3f}s")
        print(f"  Total: {total_time:.3f}s")

        # Should complete in reasonable time
        assert total_time < 5.0, \
            f"Complete flow took {total_time:.3f}s, expected < 5.0s"

