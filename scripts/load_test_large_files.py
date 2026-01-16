#!/usr/bin/env python3
"""Load testing script for large EDI files (100MB+).

This script tests the API's ability to handle very large files with:
- File-based processing path validation
- Memory usage monitoring
- Performance metrics collection

Usage:
    python scripts/load_test_large_files.py --base-url http://localhost:8000 --file-size 100
"""
import argparse
import asyncio
import os
import sys
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

import httpx
import psutil

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.generate_large_edi_files import (
    generate_837_file,
    generate_835_file,
)


class MemoryMonitor:
    """Monitor memory usage during file processing."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.checkpoints: List[Dict] = []

    def get_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / (1024 * 1024)

    def checkpoint(self, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Record a memory checkpoint."""
        memory = self.get_memory_mb()
        checkpoint = {
            "name": name,
            "memory_mb": memory,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        self.checkpoints.append(checkpoint)
        return checkpoint

    def get_summary(self) -> Dict:
        """Get memory usage summary."""
        if not self.checkpoints:
            return {"error": "No checkpoints recorded"}

        initial = self.checkpoints[0]["memory_mb"]
        final = self.checkpoints[-1]["memory_mb"]
        peak = max(cp["memory_mb"] for cp in self.checkpoints)

        return {
            "initial_mb": initial,
            "final_mb": final,
            "peak_mb": peak,
            "delta_mb": final - initial,
            "peak_delta_mb": peak - initial,
            "checkpoints": len(self.checkpoints),
        }


class LargeFileLoadTest:
    """Load test for large EDI files."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.results: List[Dict] = []
        self.errors: List[Dict] = []

    async def upload_file(
        self,
        client: httpx.AsyncClient,
        file_path: Path,
        endpoint: str,
        monitor: MemoryMonitor,
    ) -> Dict:
        """Upload a file and monitor memory usage."""
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        filename = file_path.name

        monitor.checkpoint("before_upload", {"filename": filename, "file_size_mb": file_size_mb})

        try:
            # Open file and upload
            with open(file_path, "rb") as f:
                files = {"file": (filename, f, "text/plain")}
                monitor.checkpoint("file_opened")

                start_time = time.time()
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    files=files,
                    timeout=300.0,  # 5 minute timeout for large files
                )
                upload_duration = time.time() - start_time

                monitor.checkpoint("upload_complete", {"status_code": response.status_code})

                if response.status_code == 200:
                    result_data = response.json()
                    task_id = result_data.get("task_id")
                    processing_mode = result_data.get("processing_mode", "unknown")

                    monitor.checkpoint(
                        "task_queued",
                        {
                            "task_id": task_id,
                            "processing_mode": processing_mode,
                            "upload_duration": upload_duration,
                        },
                    )

                    # Wait for task completion (poll task status)
                    if task_id:
                        task_result = await self.wait_for_task_completion(
                            client, task_id, monitor
                        )
                        result_data.update(task_result)
                else:
                    result_data = {"error": response.text, "status_code": response.status_code}

                monitor.checkpoint("complete", {"success": response.status_code == 200})

                return {
                    "filename": filename,
                    "file_size_mb": file_size_mb,
                    "endpoint": endpoint,
                    "status_code": response.status_code,
                    "upload_duration": upload_duration,
                    "result": result_data,
                    "memory_summary": monitor.get_summary(),
                }

        except Exception as e:
            monitor.checkpoint("error", {"error": str(e)})
            error_info = {
                "filename": filename,
                "file_size_mb": file_size_mb,
                "endpoint": endpoint,
                "error": str(e),
                "memory_summary": monitor.get_summary(),
            }
            self.errors.append(error_info)
            return error_info

    async def wait_for_task_completion(
        self, client: httpx.AsyncClient, task_id: str, monitor: MemoryMonitor, max_wait: int = 600
    ) -> Dict:
        """Wait for Celery task to complete by polling task status endpoint."""
        start_time = time.time()
        poll_interval = 2  # Poll every 2 seconds
        task_status = "UNKNOWN"

        while time.time() - start_time < max_wait:
            try:
                # Poll task status endpoint
                response = await client.get(
                    f"{self.base_url}/api/v1/tasks/{task_id}",
                    timeout=10.0
                )
                response.raise_for_status()
                task_data = response.json()
                task_status = task_data.get("status", "UNKNOWN")

                monitor.checkpoint(
                    "task_polling",
                    {
                        "elapsed": time.time() - start_time,
                        "task_status": task_status
                    }
                )

                # Break if task is complete (success or failure)
                if task_status in ["SUCCESS", "FAILURE", "COMPLETE"]:
                    break

                await asyncio.sleep(poll_interval)

            except httpx.HTTPStatusError as e:
                # If endpoint doesn't exist (404), fall back to time-based waiting
                if e.response.status_code == 404:
                    monitor.checkpoint(
                        "task_status_endpoint_not_found",
                        {"elapsed": time.time() - start_time}
                    )
                    # Fall back to time-based assumption if endpoint doesn't exist
                    await asyncio.sleep(poll_interval)
                    if time.time() - start_time > max_wait * 0.9:
                        task_status = "TIMEOUT"
                        break
                else:
                    monitor.checkpoint("poll_error", {"error": f"HTTP {e.response.status_code}: {str(e)}"})
                    break
            except httpx.RequestError as e:
                monitor.checkpoint("poll_error", {"error": f"Request error: {str(e)}"})
                break
            except Exception as e:
                monitor.checkpoint("poll_error", {"error": f"Unexpected error: {type(e).__name__}: {str(e)}"})
                break

        return {
            "task_id": task_id,
            "processing_duration": time.time() - start_time,
            "task_status": task_status,
        }

    async def test_file_based_processing(
        self, file_path: Path, endpoint: str, expected_mode: str = "file-based"
    ) -> Dict:
        """Test file-based processing path."""
        monitor = MemoryMonitor()
        monitor.checkpoint("test_start")

        async with httpx.AsyncClient() as client:
            result = await self.upload_file(client, file_path, endpoint, monitor)

        result["expected_mode"] = expected_mode
        result["actual_mode"] = result.get("result", {}).get("processing_mode", "unknown")

        # Validate file-based processing was used
        if result.get("status_code") == 200:
            if expected_mode == "file-based":
                assert (
                    result["actual_mode"] == "file-based"
                ), f"Expected file-based processing, got {result['actual_mode']}"

        self.results.append(result)
        return result

    def validate_memory_usage(self, result: Dict, max_memory_mb: float = 2000) -> bool:
        """
        Validate that memory usage is reasonable.
        
        Args:
            result: Test result dictionary containing 'memory_summary' and 'file_size_mb'
            max_memory_mb: Maximum acceptable memory delta in MB (default: 2000)
            
        Returns:
            True if memory usage is within acceptable limits, False otherwise
        """
        memory_summary = result.get("memory_summary", {})
        peak_delta = memory_summary.get("peak_delta_mb", 0)
        file_size_mb = result.get("file_size_mb", 0)

        # Check absolute memory limit
        if peak_delta > max_memory_mb:
            print(
                f"⚠️  WARNING: Peak memory delta {peak_delta:.2f} MB exceeds limit {max_memory_mb} MB"
            )
            return False

        # Check memory efficiency (should be less than 20x file size)
        if file_size_mb > 0:
            memory_ratio = peak_delta / file_size_mb
            if memory_ratio > 20:
                print(
                    f"⚠️  WARNING: Memory ratio {memory_ratio:.2f}x is high (peak_delta={peak_delta:.2f} MB, file_size={file_size_mb:.2f} MB)"
                )
                return False

        return True

    def print_summary(self):
        """
        Print test summary to stdout.
        
        Displays:
        - Test results grouped by endpoint
        - File sizes, status codes, and processing modes
        - Memory usage statistics and validation results
        - Error summary if any errors occurred
        """
        print("\n" + "=" * 80)
        print("LARGE FILE LOAD TEST SUMMARY")
        print("=" * 80)

        if not self.results:
            print("No results to display")
            return

        # Group by endpoint
        by_endpoint = defaultdict(list)
        for result in self.results:
            by_endpoint[result["endpoint"]].append(result)

        for endpoint, results in by_endpoint.items():
            print(f"\n{endpoint}:")
            print(f"  Tests: {len(results)}")

            for result in results:
                filename = result["filename"]
                file_size = result["file_size_mb"]
                status = result.get("status_code", "error")
                memory = result.get("memory_summary", {})
                peak_delta = memory.get("peak_delta_mb", 0)
                processing_mode = result.get("actual_mode", "unknown")

                print(f"\n  {filename}:")
                print(f"    File size: {file_size:.2f} MB")
                print(f"    Status: {status}")
                print(f"    Processing mode: {processing_mode}")
                print(f"    Peak memory delta: {peak_delta:.2f} MB")
                print(f"    Memory ratio: {peak_delta / file_size:.2f}x" if file_size > 0 else "")

                # Memory validation
                is_valid = self.validate_memory_usage(result)
                print(f"    Memory validation: {'✓ PASS' if is_valid else '✗ FAIL'}")

        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  {error['filename']}: {error.get('error', 'Unknown error')}")

        print("=" * 80 + "\n")


async def generate_test_file(
    file_type: str, target_size_mb: float, output_dir: Path
) -> Path:
    """
    Generate a test file of approximately the target size.
    
    Args:
        file_type: Type of EDI file to generate ("837" or "835")
        target_size_mb: Target file size in megabytes
        output_dir: Directory where the generated file will be saved
        
    Returns:
        Path object pointing to the generated file
        
    Raises:
        ValueError: If file_type is not "837" or "835"
        IOError: If file cannot be written
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Estimate number of claims/remittances needed
    # Rough estimate: ~1KB per claim/remittance
    # So for 100MB, we need ~100,000 claims/remittances
    target_size_bytes = target_size_mb * 1024 * 1024
    estimated_items = int(target_size_bytes / 1024)  # ~1KB per item

    # Start with a reasonable estimate and adjust
    items = max(1000, estimated_items)

    if file_type == "837":
        filename = f"load_test_837_{int(target_size_mb)}mb.edi"
        output_path = output_dir / filename

        print(f"Generating {file_type} file targeting {target_size_mb} MB...")
        print(f"  Estimated items: {items:,}")

        # Generate file
        generate_837_file(items, output_path)

        # Check actual size and adjust if needed
        actual_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  Actual size: {actual_size_mb:.2f} MB")

        # If significantly smaller, generate a larger one
        if actual_size_mb < target_size_mb * 0.9:
            print(f"  File is smaller than target, generating larger file...")
            larger_items = int(items * (target_size_mb / actual_size_mb))
            generate_837_file(larger_items, output_path)
            actual_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"  New size: {actual_size_mb:.2f} MB")

    elif file_type == "835":
        filename = f"load_test_835_{int(target_size_mb)}mb.edi"
        output_path = output_dir / filename

        print(f"Generating {file_type} file targeting {target_size_mb} MB...")
        print(f"  Estimated items: {items:,}")

        generate_835_file(items, output_path)

        actual_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  Actual size: {actual_size_mb:.2f} MB")

        if actual_size_mb < target_size_mb * 0.9:
            print(f"  File is smaller than target, generating larger file...")
            larger_items = int(items * (target_size_mb / actual_size_mb))
            generate_835_file(larger_items, output_path)
            actual_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"  New size: {actual_size_mb:.2f} MB")

    else:
        raise ValueError(f"Unknown file type: {file_type}")

    return output_path


async def main():
    """
    Main entry point for large file load testing.
    
    Generates large EDI files, uploads them to the API, monitors memory usage,
    and validates that file-based processing is used for large files.
    
    Command-line arguments:
        --base-url: Base URL of the API (default: http://localhost:8000)
        --file-size: Target file size in MB (default: 100)
        --file-type: Type of EDI file to test - "837", "835", or "both" (default: both)
        --test-dir: Directory for test files (default: samples/load_test)
        --max-memory: Maximum acceptable memory delta in MB (default: 2000)
        --keep-files: Keep generated test files after testing (default: False)
    """
    parser = argparse.ArgumentParser(
        description="Load test mARB 2.0 API with large EDI files (100MB+)"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--file-size",
        type=float,
        default=100.0,
        help="Target file size in MB (default: 100)",
    )
    parser.add_argument(
        "--file-type",
        choices=["837", "835", "both"],
        default="both",
        help="Type of EDI file to test (default: both)",
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=Path("samples/load_test"),
        help="Directory for test files (default: samples/load_test)",
    )
    parser.add_argument(
        "--max-memory",
        type=float,
        default=2000.0,
        help="Maximum acceptable memory delta in MB (default: 2000)",
    )
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Keep generated test files after testing",
    )

    args = parser.parse_args()

    # Create test directory
    test_dir = args.test_dir
    test_dir.mkdir(parents=True, exist_ok=True)

    # Generate test files
    test_files = []

    if args.file_type in ["837", "both"]:
        print(f"\n{'='*80}")
        print("Generating 837 test file...")
        print(f"{'='*80}")
        file_837 = await generate_test_file("837", args.file_size, test_dir)
        test_files.append(("837", file_837, "/api/v1/claims/upload"))

    if args.file_type in ["835", "both"]:
        print(f"\n{'='*80}")
        print("Generating 835 test file...")
        print(f"{'='*80}")
        file_835 = await generate_test_file("835", args.file_size, test_dir)
        test_files.append(("835", file_835, "/api/v1/remits/upload"))

    # Run load tests
    print(f"\n{'='*80}")
    print("Running load tests...")
    print(f"{'='*80}")

    load_test = LargeFileLoadTest(args.base_url)

    for file_type, file_path, endpoint in test_files:
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        print(f"\nTesting {file_type} file: {file_path.name} ({file_size_mb:.2f} MB)")

        # Verify file is large enough to trigger file-based processing
        if file_size_mb < 50:
            print(
                f"⚠️  WARNING: File size {file_size_mb:.2f} MB is below 50MB threshold for file-based processing"
            )

        result = await load_test.test_file_based_processing(
            file_path, endpoint, expected_mode="file-based" if file_size_mb >= 50 else "memory-based"
        )

        # Validate memory usage
        is_valid = load_test.validate_memory_usage(result, max_memory_mb=args.max_memory)
        if not is_valid:
            print(f"⚠️  Memory usage validation failed for {file_path.name}")

    # Print summary
    load_test.print_summary()

    # Clean up test files unless --keep-files is specified
    if not args.keep_files:
        print("\nCleaning up test files...")
        for _, file_path, _ in test_files:
            try:
                file_path.unlink()
                print(f"  Deleted: {file_path}")
            except Exception as e:
                print(f"  Failed to delete {file_path}: {e}")

    print("\n✓ Load test complete!")


if __name__ == "__main__":
    asyncio.run(main())

