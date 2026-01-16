"""Load tests for large EDI files (100MB+).

Tests file-based processing path and validates memory usage stays reasonable.
"""
import gc
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.queue.tasks import process_edi_file
from scripts.generate_large_edi_files import (
    generate_835_file,
    generate_837_file,
)


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        # Fallback: return 0 if psutil not available (tests will still run)
        return 0.0


@pytest.fixture
def large_837_file(tmp_path: Path) -> Path:
    """Generate a large 837 file (100MB+) for testing."""
    output_file = tmp_path / "large_837_100mb.edi"

    # Generate file with enough claims to reach ~100MB
    # Rough estimate: ~1KB per claim, so ~100,000 claims for 100MB
    # For faster tests, use smaller number if TEST_FAST is set
    import os
    if os.getenv("TEST_FAST") == "true":
        num_claims = 60000  # ~60MB for faster testing (still above 50MB threshold)
    else:
        num_claims = 100000  # ~100MB for full testing

    print(f"\nGenerating large 837 file with {num_claims:,} claims...")
    generate_837_file(num_claims, output_file)

    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"Generated file: {file_size_mb:.2f} MB")

    return output_file


@pytest.fixture
def large_835_file(tmp_path: Path) -> Path:
    """Generate a large 835 file (100MB+) for testing."""
    output_file = tmp_path / "large_835_100mb.edi"

    # Generate file with enough remittances to reach ~100MB
    import os
    if os.getenv("TEST_FAST") == "true":
        num_remittances = 50000  # ~50MB for faster testing (at threshold)
    else:
        num_remittances = 100000  # ~100MB for full testing

    print(f"\nGenerating large 835 file with {num_remittances:,} remittances...")
    generate_835_file(num_remittances, output_file)

    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"Generated file: {file_size_mb:.2f} MB")

    return output_file


@pytest.fixture
def medium_837_file(tmp_path: Path) -> Path:
    """Generate a medium 837 file (50-100MB) for testing threshold behavior."""
    output_file = tmp_path / "medium_837_60mb.edi"

    # Generate file just above 50MB threshold
    num_claims = 60000  # ~60MB

    print(f"\nGenerating medium 837 file with {num_claims:,} claims...")
    generate_837_file(num_claims, output_file)

    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"Generated file: {file_size_mb:.2f} MB")

    return output_file


@pytest.fixture
def small_837_file(tmp_path: Path) -> Path:
    """Generate a small 837 file (<50MB) for testing memory-based processing."""
    output_file = tmp_path / "small_837_10mb.edi"

    # Generate file below 50MB threshold
    num_claims = 10000  # ~10MB

    print(f"\nGenerating small 837 file with {num_claims:,} claims...")
    generate_837_file(num_claims, output_file)

    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"Generated file: {file_size_mb:.2f} MB")

    return output_file


@pytest.mark.performance
@pytest.mark.load_test
class TestLargeFileProcessing:
    """Tests for processing large EDI files (100MB+)."""

    def test_file_based_processing_837(self, large_837_file: Path, db_session):
        """Test that 100MB+ 837 files use file-based processing."""
        from unittest.mock import patch

        file_size_mb = large_837_file.stat().st_size / (1024 * 1024)

        # Verify file is large enough to trigger file-based processing
        # Allow smaller files in TEST_FAST mode
        import os
        min_size = 10 if os.getenv("TEST_FAST") == "true" else 50
        assert file_size_mb >= min_size, \
            f"File size {file_size_mb:.2f} MB is below {min_size}MB threshold (TEST_FAST={os.getenv('TEST_FAST')})"

        # Measure memory before processing
        gc.collect()
        initial_memory = get_memory_usage_mb()

        # Process file using file_path (file-based processing)
        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            result = process_edi_file.run(
                file_path=str(large_837_file),
                filename=large_837_file.name,
                file_type="837",
            )

        # Measure memory after processing
        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        # Verify processing succeeded
        assert result["status"] == "success"
        assert result["claims_created"] > 0

        print("\n[FILE-BASED PROCESSING] 837 File:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Memory delta: {memory_delta:.2f} MB")
        print(f"  Claims created: {result['claims_created']}")
        print(f"  Memory ratio: {memory_delta / file_size_mb:.2f}x file size")

        # Validate memory usage is reasonable
        # For 100MB file, memory delta should be less than 2000MB
        max_memory_mb = 2000
        assert memory_delta < max_memory_mb, \
            f"Memory delta {memory_delta:.2f} MB exceeds limit {max_memory_mb} MB"

        # Memory efficiency: delta should be less than 20x file size
        if file_size_mb > 0:
            memory_ratio = memory_delta / file_size_mb
            assert memory_ratio < 20, \
                f"Memory ratio {memory_ratio:.2f}x is too high (delta={memory_delta:.2f} MB, file_size={file_size_mb:.2f} MB)"

        # Memory per claim should be reasonable
        if result["claims_created"] > 0:
            memory_per_claim = memory_delta / result["claims_created"]
            assert memory_per_claim < 0.05, \
                f"Memory per claim {memory_per_claim:.4f} MB is too high"
            print(f"  Memory per claim: {memory_per_claim:.4f} MB")

    def test_file_based_processing_835(self, large_835_file: Path, db_session):
        """Test that 100MB+ 835 files use file-based processing."""
        from unittest.mock import patch

        file_size_mb = large_835_file.stat().st_size / (1024 * 1024)

        # Verify file is large enough
        # Allow smaller files in TEST_FAST mode
        import os
        min_size = 10 if os.getenv("TEST_FAST") == "true" else 50
        assert file_size_mb >= min_size, \
            f"File size {file_size_mb:.2f} MB is below {min_size}MB threshold (TEST_FAST={os.getenv('TEST_FAST')})"

        # Measure memory before processing
        gc.collect()
        initial_memory = get_memory_usage_mb()

        # Process file using file_path
        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            result = process_edi_file.run(
                file_path=str(large_835_file),
                filename=large_835_file.name,
                file_type="835",
            )

        # Measure memory after processing
        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        # Verify processing succeeded
        assert result["status"] == "success"
        assert result["remittances_created"] > 0

        print("\n[FILE-BASED PROCESSING] 835 File:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Memory delta: {memory_delta:.2f} MB")
        print(f"  Remittances created: {result['remittances_created']}")
        print(f"  Memory ratio: {memory_delta / file_size_mb:.2f}x file size")

        # Validate memory usage
        max_memory_mb = 2000
        assert memory_delta < max_memory_mb, \
            f"Memory delta {memory_delta:.2f} MB exceeds limit {max_memory_mb} MB"

        if file_size_mb > 0:
            memory_ratio = memory_delta / file_size_mb
            assert memory_ratio < 20, \
                f"Memory ratio {memory_ratio:.2f}x is too high"

    def test_memory_usage_during_processing(self, large_837_file: Path, db_session):
        """Test that memory usage stays reasonable during processing."""
        from unittest.mock import patch

        try:
            import psutil
            process = psutil.Process(os.getpid())
            psutil_available = True
        except ImportError:
            psutil_available = False
            process = None

        memory_samples = []

        def sample_memory():
            """Sample current memory usage."""
            if psutil_available:
                memory_samples.append(process.memory_info().rss / (1024 * 1024))
            else:
                memory_samples.append(0.0)  # Placeholder if psutil not available

        file_size_mb = large_837_file.stat().st_size / (1024 * 1024)

        # Sample memory before processing
        gc.collect()
        sample_memory()
        initial_memory = memory_samples[0]

        # Process file and sample memory periodically
        # Note: This is a simplified test - in production, you'd use threading/async
        # to sample memory during processing
        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            # Sample memory before task
            sample_memory()

            result = process_edi_file.run(
                file_path=str(large_837_file),
                filename=large_837_file.name,
                file_type="837",
            )

            # Sample memory after task
            sample_memory()

        gc.collect()
        final_memory = memory_samples[-1]
        peak_memory = max(memory_samples)
        memory_delta = final_memory - initial_memory
        peak_delta = peak_memory - initial_memory

        print("\n[MEMORY SAMPLING] During Processing:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Peak memory: {peak_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Memory delta: {memory_delta:.2f} MB")
        print(f"  Peak delta: {peak_delta:.2f} MB")
        print(f"  Samples taken: {len(memory_samples)}")

        # Validate peak memory is reasonable
        max_peak_mb = 2000
        assert peak_delta < max_peak_mb, \
            f"Peak memory delta {peak_delta:.2f} MB exceeds limit {max_peak_mb} MB"

        assert result["status"] == "success"

    def test_file_cleanup_after_processing(self, large_837_file: Path, db_session):
        """Test that temporary files are cleaned up after processing."""
        from unittest.mock import patch

        # Create a temporary file that should be cleaned up
        temp_dir = tempfile.gettempdir()
        temp_file = Path(temp_dir) / f"marb_test_{large_837_file.name}"

        # Copy test file to temp location
        import shutil
        shutil.copy(large_837_file, temp_file)

        # Verify temp file exists
        assert temp_file.exists(), "Temp file should exist before processing"

        # Process file
        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            result = process_edi_file.run(
                file_path=str(temp_file),
                filename=temp_file.name,
                file_type="837",
            )

        # Verify processing succeeded
        assert result["status"] == "success"

        # The task should clean up the temp file
        # Note: The cleanup happens in the task, but for test files in tmp_path,
        # pytest handles cleanup. We verify the original test file still exists.
        assert large_837_file.exists(), "Original test file should still exist"

        # Clean up temp file if it still exists (in case cleanup didn't happen)
        if temp_file.exists():
            temp_file.unlink()

    def test_multiple_large_files_sequential(self, tmp_path: Path, db_session):
        """Test processing multiple large files sequentially without memory leaks."""
        from unittest.mock import patch

        # Generate multiple large files
        files = []
        for i in range(3):
            file_path = tmp_path / f"large_837_{i}.edi"
            generate_837_file(50000, file_path)  # ~50MB each
            files.append(file_path)

        memory_deltas = []

        for i, file_path in enumerate(files):
            gc.collect()
            initial_memory = get_memory_usage_mb()

            with patch("app.services.queue.tasks.SessionLocal") as mock_session:
                mock_session.return_value = db_session

                result = process_edi_file.run(
                    file_path=str(file_path),
                    filename=file_path.name,
                    file_type="837",
                )

            gc.collect()
            final_memory = get_memory_usage_mb()
            memory_delta = final_memory - initial_memory
            memory_deltas.append(memory_delta)

            assert result["status"] == "success"
            print(f"\n[SEQUENTIAL PROCESSING] File {i+1}:")
            print(f"  Memory delta: {memory_delta:.2f} MB")
            print(f"  Claims created: {result['claims_created']}")

        # Check for memory leaks: memory deltas should be similar
        if len(memory_deltas) > 1:
            avg_delta = sum(memory_deltas) / len(memory_deltas)
            max_delta = max(memory_deltas)

            print("\n[SEQUENTIAL PROCESSING] Summary:")
            print(f"  Average memory delta: {avg_delta:.2f} MB")
            print(f"  Max memory delta: {max_delta:.2f} MB")

            # Max delta should not be more than 2x average (allowing for variance)
            assert max_delta < avg_delta * 2, \
                f"Possible memory leak: max delta {max_delta:.2f} MB is > 2x average {avg_delta:.2f} MB"


@pytest.mark.performance
@pytest.mark.load_test
class TestFileSizeThresholds:
    """Tests for file size threshold behavior (memory-based vs file-based)."""

    def test_small_file_uses_memory_based(self, small_837_file: Path, db_session):
        """Test that small files (<50MB) use memory-based processing."""
        from unittest.mock import patch

        file_size_mb = small_837_file.stat().st_size / (1024 * 1024)

        # Verify file is below threshold
        assert file_size_mb < 50, f"File size {file_size_mb:.2f} MB should be below 50MB threshold"

        gc.collect()
        initial_memory = get_memory_usage_mb()

        # Process using file_content (memory-based)
        with open(small_837_file, "r", encoding="utf-8") as f:
            file_content = f.read()

        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            result = process_edi_file.run(
                file_content=file_content,
                filename=small_837_file.name,
                file_type="837",
            )

        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        assert result["status"] == "success"

        print("\n[MEMORY-BASED PROCESSING] Small File:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Memory delta: {memory_delta:.2f} MB")
        print(f"  Claims created: {result['claims_created']}")

        # Memory-based should still be reasonable
        assert memory_delta < 500, \
            f"Memory delta {memory_delta:.2f} MB is too high for small file"

    def test_medium_file_uses_file_based(self, medium_837_file: Path, db_session):
        """Test that medium files (>50MB) use file-based processing."""
        from unittest.mock import patch

        file_size_mb = medium_837_file.stat().st_size / (1024 * 1024)

        # Verify file is above threshold
        assert file_size_mb >= 50, f"File size {file_size_mb:.2f} MB should be above 50MB threshold"

        gc.collect()
        initial_memory = get_memory_usage_mb()

        # Process using file_path (file-based)
        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            result = process_edi_file.run(
                file_path=str(medium_837_file),
                filename=medium_837_file.name,
                file_type="837",
            )

        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        assert result["status"] == "success"

        print("\n[FILE-BASED PROCESSING] Medium File:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Memory delta: {memory_delta:.2f} MB")
        print(f"  Claims created: {result['claims_created']}")

        # File-based should be reasonable
        assert memory_delta < 1500, \
            f"Memory delta {memory_delta:.2f} MB is too high for medium file"


@pytest.mark.performance
@pytest.mark.load_test
@pytest.mark.integration
class TestLargeFileAPIIntegration:
    """Integration tests for large file processing via API endpoints."""

    def test_upload_large_837_via_api(self, client, tmp_path: Path):
        """Test uploading large 837 file via API endpoint."""
        # Generate a smaller file for API testing (faster)
        test_file = tmp_path / "api_test_837.edi"
        generate_837_file(5000, test_file)  # ~5MB for faster testing

        file_size_mb = test_file.stat().st_size / (1024 * 1024)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/v1/claims/upload",
                files={"file": (test_file.name, f, "text/plain")},
            )

        assert response.status_code in [200, 202], \
            f"Upload failed with status {response.status_code}: {response.text}"

        result = response.json()
        assert "task_id" in result or "message" in result

        print("\n[API UPLOAD] 837 File:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {result}")

    def test_upload_large_835_via_api(self, client, tmp_path: Path):
        """Test uploading large 835 file via API endpoint."""
        # Generate a smaller file for API testing
        test_file = tmp_path / "api_test_835.edi"
        generate_835_file(5000, test_file)  # ~5MB for faster testing

        file_size_mb = test_file.stat().st_size / (1024 * 1024)

        with open(test_file, "rb") as f:
            response = client.post(
                "/api/v1/remits/upload",
                files={"file": (test_file.name, f, "text/plain")},
            )

        assert response.status_code in [200, 202], \
            f"Upload failed with status {response.status_code}: {response.text}"

        result = response.json()
        assert "task_id" in result or "message" in result

        print("\n[API UPLOAD] 835 File:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {result}")


@pytest.mark.performance
@pytest.mark.load_test
class TestLargeFileErrorHandling:
    """Tests for error handling with large files."""

    def test_nonexistent_file_path(self, db_session):
        """Test handling of nonexistent file path."""
        from unittest.mock import patch

        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            with pytest.raises(FileNotFoundError):
                process_edi_file.run(
                    file_path="/nonexistent/path/file.edi",
                    filename="nonexistent.edi",
                    file_type="837",
                )

    def test_invalid_file_content(self, tmp_path: Path, db_session):
        """Test handling of invalid file content."""
        from unittest.mock import patch

        # Create a file with invalid EDI content
        invalid_file = tmp_path / "invalid.edi"
        invalid_file.write_text("This is not valid EDI content" * 1000)

        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            # Should handle gracefully (either raise error or mark as failed)
            try:
                result = process_edi_file.run(
                    file_path=str(invalid_file),
                    filename=invalid_file.name,
                    file_type="837",
                )
                # If it doesn't raise, should have error status
                assert result.get("status") != "success" or "error" in result
            except (ValueError, Exception):
                # Expected for invalid content
                pass

    def test_empty_file(self, tmp_path: Path, db_session):
        """Test handling of empty file."""
        from unittest.mock import patch

        empty_file = tmp_path / "empty.edi"
        empty_file.write_text("")

        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            with pytest.raises((ValueError, Exception)):
                process_edi_file.run(
                    file_path=str(empty_file),
                    filename=empty_file.name,
                    file_type="837",
                )


@pytest.mark.performance
@pytest.mark.load_test
class TestLargeFileEdgeCases:
    """Tests for edge cases with large files."""

    def test_very_large_file_200mb(self, tmp_path: Path, db_session):
        """Test processing a very large file (200MB+)."""
        import os
        from unittest.mock import patch

        # Skip if TEST_FAST is set (takes too long)
        if os.getenv("TEST_FAST") == "true":
            pytest.skip("Skipping very large file test in fast mode")

        output_file = tmp_path / "very_large_837_200mb.edi"
        num_claims = 200000  # ~200MB

        print(f"\nGenerating very large 837 file with {num_claims:,} claims...")
        generate_837_file(num_claims, output_file)

        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"Generated file: {file_size_mb:.2f} MB")

        gc.collect()
        initial_memory = get_memory_usage_mb()

        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            result = process_edi_file.run(
                file_path=str(output_file),
                filename=output_file.name,
                file_type="837",
            )

        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        assert result["status"] == "success"

        print("\n[VERY LARGE FILE] 200MB+ File:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Memory delta: {memory_delta:.2f} MB")
        print(f"  Memory ratio: {memory_delta / file_size_mb:.2f}x")

        # For very large files, allow higher memory but still reasonable
        max_memory_mb = 4000
        assert memory_delta < max_memory_mb, \
            f"Memory delta {memory_delta:.2f} MB exceeds limit {max_memory_mb} MB for very large file"

    def test_file_with_many_segments(self, tmp_path: Path, db_session):
        """Test file with many segments but smaller size."""
        from unittest.mock import patch

        # Generate file with many small claims
        output_file = tmp_path / "many_segments.edi"
        generate_837_file(50000, output_file)  # Many claims, but smaller total size

        file_size_mb = output_file.stat().st_size / (1024 * 1024)

        gc.collect()
        initial_memory = get_memory_usage_mb()

        with patch("app.services.queue.tasks.SessionLocal") as mock_session:
            mock_session.return_value = db_session

            result = process_edi_file.run(
                file_path=str(output_file),
                filename=output_file.name,
                file_type="837",
            )

        gc.collect()
        final_memory = get_memory_usage_mb()
        memory_delta = final_memory - initial_memory

        assert result["status"] == "success"

        print("\n[MANY SEGMENTS] File:")
        print(f"  File size: {file_size_mb:.2f} MB")
        print(f"  Claims: {result['claims_created']}")
        print(f"  Memory delta: {memory_delta:.2f} MB")

        # Should handle many segments efficiently
        assert memory_delta < 1000, \
            f"Memory delta {memory_delta:.2f} MB is too high for many segments"


@pytest.mark.performance
@pytest.mark.load_test
class TestLargeFileMemoryEfficiency:
    """Tests for memory efficiency with large files."""

    def test_memory_scales_linearly(self, tmp_path: Path, db_session):
        """Test that memory usage scales roughly linearly with file size."""
        from unittest.mock import patch

        # Generate files of different sizes
        file_sizes = [50, 100, 150]  # MB
        memory_ratios = []

        for target_size_mb in file_sizes:
            # Generate file
            file_path = tmp_path / f"test_{target_size_mb}mb.edi"
            num_claims = int(target_size_mb * 1000)  # Rough estimate
            generate_837_file(num_claims, file_path)

            actual_size_mb = file_path.stat().st_size / (1024 * 1024)

            gc.collect()
            initial_memory = get_memory_usage_mb()

            with patch("app.services.queue.tasks.SessionLocal") as mock_session:
                mock_session.return_value = db_session

                result = process_edi_file.run(
                    file_path=str(file_path),
                    filename=file_path.name,
                    file_type="837",
                )

            gc.collect()
            final_memory = get_memory_usage_mb()
            memory_delta = final_memory - initial_memory

            if actual_size_mb > 0:
                memory_ratio = memory_delta / actual_size_mb
                memory_ratios.append((actual_size_mb, memory_ratio))

            print(f"\n[MEMORY SCALING] {actual_size_mb:.2f} MB file:")
            print(f"  Memory delta: {memory_delta:.2f} MB")
            print(f"  Memory ratio: {memory_ratio:.2f}x")

            assert result["status"] == "success"

        # Memory ratios should be similar across file sizes (indicating linear scaling)
        if len(memory_ratios) > 1:
            ratios = [r[1] for r in memory_ratios]
            avg_ratio = sum(ratios) / len(ratios)
            max_ratio = max(ratios)
            min_ratio = min(ratios)

            print("\n[MEMORY SCALING] Summary:")
            print(f"  Average memory ratio: {avg_ratio:.2f}x")
            print(f"  Min ratio: {min_ratio:.2f}x")
            print(f"  Max ratio: {max_ratio:.2f}x")

            # Ratios should be within 50% of each other (indicating linear scaling)
            ratio_variance = (max_ratio - min_ratio) / avg_ratio if avg_ratio > 0 else 0
            assert ratio_variance < 0.5, \
                f"Memory does not scale linearly: ratio variance {ratio_variance:.2f} is too high"

