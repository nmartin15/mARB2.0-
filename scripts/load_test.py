#!/usr/bin/env python3
"""Load testing script for mARB 2.0 API.

This script tests the API performance under load by making concurrent requests
to various endpoints.

Usage:
    python scripts/load_test.py --base-url http://localhost:8000 --concurrent 10 --requests 100
"""
import argparse
import asyncio
import time
from collections import defaultdict
from typing import Dict, List
import httpx
from statistics import mean, median, stdev


class LoadTestResults:
    """Store load test results."""

    def __init__(self):
        self.results: List[Dict] = []
        self.errors: List[Dict] = []

    def add_result(self, endpoint: str, method: str, status_code: int, duration: float):
        """Add a test result."""
        self.results.append({
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration": duration,
        })

    def add_error(self, endpoint: str, method: str, error: str):
        """Add an error result."""
        self.errors.append({
            "endpoint": endpoint,
            "method": method,
            "error": error,
        })

    def get_stats(self) -> Dict:
        """Get statistics for all results."""
        if not self.results:
            return {"error": "No results to analyze"}

        durations = [r["duration"] for r in self.results]
        status_codes = [r["status_code"] for r in self.results]

        # Group by endpoint
        by_endpoint = defaultdict(list)
        for r in self.results:
            by_endpoint[r["endpoint"]].append(r["duration"])

        endpoint_stats = {}
        for endpoint, times in by_endpoint.items():
            endpoint_stats[endpoint] = {
                "count": len(times),
                "mean": round(mean(times), 3),
                "median": round(median(times), 3),
                "min": round(min(times), 3),
                "max": round(max(times), 3),
                "stdev": round(stdev(times), 3) if len(times) > 1 else 0.0,
            }

        # Status code distribution
        status_dist = defaultdict(int)
        for code in status_codes:
            status_dist[code] += 1

        return {
            "total_requests": len(self.results),
            "total_errors": len(self.errors),
            "success_rate": round((len(self.results) / (len(self.results) + len(self.errors)) * 100), 2) if (self.results or self.errors) else 0.0,
            "overall": {
                "mean": round(mean(durations), 3),
                "median": round(median(durations), 3),
                "min": round(min(durations), 3),
                "max": round(max(durations), 3),
                "stdev": round(stdev(durations), 3) if len(durations) > 1 else 0.0,
            },
            "by_endpoint": endpoint_stats,
            "status_codes": dict(status_dist),
        }

    def print_summary(self):
        """Print a summary of results."""
        stats = self.get_stats()
        
        print("\n" + "=" * 80)
        print("LOAD TEST SUMMARY")
        print("=" * 80)
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Total Errors: {stats['total_errors']}")
        print(f"Success Rate: {stats['success_rate']}%")
        print("\nOverall Response Times (seconds):")
        print(f"  Mean:   {stats['overall']['mean']:.3f}s")
        print(f"  Median: {stats['overall']['median']:.3f}s")
        print(f"  Min:    {stats['overall']['min']:.3f}s")
        print(f"  Max:    {stats['overall']['max']:.3f}s")
        print(f"  StdDev: {stats['overall']['stdev']:.3f}s")
        
        print("\nStatus Code Distribution:")
        for code, count in sorted(stats['status_codes'].items()):
            print(f"  {code}: {count}")
        
        print("\nPerformance by Endpoint:")
        for endpoint, ep_stats in stats['by_endpoint'].items():
            print(f"\n  {endpoint}:")
            print(f"    Requests: {ep_stats['count']}")
            print(f"    Mean:     {ep_stats['mean']:.3f}s")
            print(f"    Median:   {ep_stats['median']:.3f}s")
            print(f"    Min:      {ep_stats['min']:.3f}s")
            print(f"    Max:      {ep_stats['max']:.3f}s")
        
        if self.errors:
            print("\nErrors:")
            error_summary = defaultdict(int)
            for err in self.errors:
                error_summary[err['error']] += 1
            for error, count in error_summary.items():
                print(f"  {error}: {count}")
        
        print("=" * 80 + "\n")


async def make_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    results: LoadTestResults,
):
    """
    Make a single HTTP request and record the result.
    
    Args:
        client: HTTP client for making requests
        method: HTTP method (GET, POST, etc.)
        url: URL to request
        results: LoadTestResults instance to store results
        
    Returns:
        None (results are added to the LoadTestResults instance)
    """
    start_time = time.time()
    method_upper = method.upper()
    try:
        if method_upper == "GET":
            response = await client.get(url, timeout=30.0)
        elif method_upper == "POST":
            response = await client.post(url, timeout=30.0)
        else:
            response = await client.request(method_upper, url, timeout=30.0)
        
        duration = time.time() - start_time
        results.add_result(url, method_upper, response.status_code, duration)
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        duration = time.time() - start_time
        results.add_error(url, method_upper, str(e))
    except httpx.HTTPStatusError as e:
        duration = time.time() - start_time
        results.add_error(url, method_upper, f"HTTP {e.response.status_code}: {str(e)}")
    except Exception as e:
        duration = time.time() - start_time
        results.add_error(url, method_upper, f"Unexpected error: {type(e).__name__}: {str(e)}")
        # Re-raise unexpected exceptions to avoid masking serious errors
        raise


async def run_load_test(
    base_url: str,
    endpoints: List[Dict[str, str]],
    concurrent: int,
    requests_per_endpoint: int,
):
    """
    Run load test with specified parameters.
    
    Args:
        base_url: Base URL of the API to test
        endpoints: List of endpoint configurations, each with 'path', 'method', and optional 'count'
        concurrent: Maximum number of concurrent requests
        requests_per_endpoint: Default number of requests per endpoint (if not specified in config)
        
    Returns:
        LoadTestResults instance containing all test results
    """
    results = LoadTestResults()
    
    # Create tasks for all requests
    tasks = []
    
    async with httpx.AsyncClient() as client:
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(concurrent)
        
        async def bounded_request(method: str, url: str):
            async with semaphore:
                await make_request(client, method, url, results)
        
        # Generate all request tasks
        for endpoint_config in endpoints:
            method = endpoint_config.get("method", "GET")
            path = endpoint_config["path"]
            url = f"{base_url}{path}"
            count = endpoint_config.get("count", requests_per_endpoint)
            
            for _ in range(count):
                tasks.append(bounded_request(method, url))
        
        # Run all tasks
        print(f"Starting load test: {len(tasks)} requests, {concurrent} concurrent...")
        start_time = time.time()
        await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        print(f"Completed in {total_time:.2f} seconds")
        print(f"Requests per second: {len(tasks) / total_time:.2f}")
    
    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Load test mARB 2.0 API")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="Number of concurrent requests (default: 10)",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Number of requests per endpoint (default: 100)",
    )
    parser.add_argument(
        "--endpoints",
        nargs="+",
        help="Specific endpoints to test (default: all common endpoints)",
    )
    
    args = parser.parse_args()
    
    # Default endpoints to test
    default_endpoints = [
        {"path": "/api/v1/health", "method": "GET", "count": args.requests},
        {"path": "/api/v1/claims", "method": "GET", "count": args.requests},
        {"path": "/api/v1/remits", "method": "GET", "count": args.requests},
        {"path": "/api/v1/episodes", "method": "GET", "count": args.requests},
        {"path": "/api/v1/cache/stats", "method": "GET", "count": args.requests // 2},
    ]
    
    # If specific endpoints provided, use those
    if args.endpoints:
        endpoints = [
            {"path": ep, "method": "GET", "count": args.requests}
            for ep in args.endpoints
        ]
    else:
        endpoints = default_endpoints
    
    # Run load test
    results = asyncio.run(
        run_load_test(
            base_url=args.base_url,
            endpoints=endpoints,
            concurrent=args.concurrent,
            requests_per_endpoint=args.requests,
        )
    )
    
    # Print results
    results.print_summary()


if __name__ == "__main__":
    main()

