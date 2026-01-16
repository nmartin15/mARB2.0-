#!/usr/bin/env python3
"""Health check monitoring script for production."""
import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

try:
    import requests
    import psutil
except ImportError:
    print("⚠ Required packages not installed. Install with:")
    print("  pip install requests psutil")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_api_health(base_url: str) -> Dict:
    """
    Check API health endpoint.
    
    Args:
        base_url: Base URL of the API
        
    Returns:
        Health check result dictionary
    """
    result = {
        "endpoint": f"{base_url}/api/v1/health",
        "status": "unknown",
        "response_time_ms": None,
        "error": None,
        "data": None,
    }
    
    try:
        start = time.time()
        response = requests.get(
            result["endpoint"],
            timeout=10,
            verify=True  # Verify SSL in production
        )
        response_time = (time.time() - start) * 1000
        
        result["response_time_ms"] = round(response_time, 2)
        result["status_code"] = response.status_code
        
        if response.status_code == 200:
            result["status"] = "healthy"
            try:
                result["data"] = response.json()
            except Exception:
                result["data"] = response.text
        else:
            result["status"] = "unhealthy"
            result["error"] = f"Status code: {response.status_code}"
            
    except requests.exceptions.Timeout:
        result["status"] = "unhealthy"
        result["error"] = "Request timeout"
    except requests.exceptions.ConnectionError as e:
        result["status"] = "unhealthy"
        result["error"] = f"Connection error: {str(e)}"
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)
    
    return result


def check_detailed_health(base_url: str) -> Dict:
    """
    Check detailed health endpoint.
    
    Args:
        base_url: Base URL of the API
        
    Returns:
        Detailed health check result dictionary
    """
    result = {
        "endpoint": f"{base_url}/api/v1/health/detailed",
        "status": "unknown",
        "response_time_ms": None,
        "error": None,
        "components": {},
    }
    
    try:
        start = time.time()
        response = requests.get(
            result["endpoint"],
            timeout=15,  # Longer timeout for detailed check
            verify=True
        )
        response_time = (time.time() - start) * 1000
        
        result["response_time_ms"] = round(response_time, 2)
        result["status_code"] = response.status_code
        
        if response.status_code == 200:
            data = response.json()
            result["status"] = data.get("status", "unknown")
            result["components"] = data.get("components", {})
            result["version"] = data.get("version", "unknown")
            result["timestamp"] = data.get("timestamp", "unknown")
        else:
            result["status"] = "unhealthy"
            result["error"] = f"Status code: {response.status_code}"
            
    except requests.exceptions.Timeout:
        result["status"] = "unhealthy"
        result["error"] = "Request timeout"
    except requests.exceptions.ConnectionError as e:
        result["status"] = "unhealthy"
        result["error"] = f"Connection error: {str(e)}"
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)
    
    return result


def check_system_resources() -> Dict:
    """
    Check system resource usage.
    
    Returns:
        System resource information dictionary with keys:
        - cpu_percent: CPU usage percentage
        - memory_percent: Memory usage percentage
        - memory_available_mb: Available memory in MB
        - disk_usage_percent: Disk usage percentage
        - error: Error message if check failed
    """
    result = {
        "cpu_percent": None,
        "memory_percent": None,
        "memory_available_mb": None,
        "disk_usage_percent": None,
        "error": None,
    }
    
    try:
        # CPU usage
        result["cpu_percent"] = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        result["memory_percent"] = memory.percent
        result["memory_available_mb"] = round(memory.available / (1024 * 1024), 2)
        
        # Disk usage (root partition)
        disk = psutil.disk_usage("/")
        result["disk_usage_percent"] = disk.percent
        
    except psutil.Error as e:
        error_msg = f"psutil error: {str(e)}"
        result["error"] = error_msg
        logger.error("Error checking system resources", extra={"error": error_msg}, exc_info=True)
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        result["error"] = error_msg
        logger.error("Unexpected error checking system resources", extra={"error": error_msg}, exc_info=True)
    
    return result


def check_cache_stats(base_url: str) -> Optional[Dict]:
    """
    Check cache statistics.
    
    Args:
        base_url: Base URL of the API
        
    Returns:
        Cache statistics dictionary or None
    """
    try:
        response = requests.get(
            f"{base_url}/api/v1/cache/stats",
            timeout=10,
            verify=True
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(
                "Cache stats endpoint returned non-200 status",
                extra={"status_code": response.status_code, "base_url": base_url}
            )
        
    except requests.exceptions.Timeout:
        logger.warning(
            "Timeout fetching cache stats",
            extra={"base_url": base_url, "endpoint": "/api/v1/cache/stats"}
        )
    except requests.exceptions.ConnectionError as e:
        logger.warning(
            "Connection error fetching cache stats",
            extra={"base_url": base_url, "error": str(e)}
        )
    except requests.exceptions.RequestException as e:
        logger.error(
            "Request exception fetching cache stats",
            extra={"base_url": base_url, "error": str(e)},
            exc_info=True
        )
    except Exception as e:
        logger.error(
            "Unexpected error fetching cache stats",
            extra={"base_url": base_url, "error": str(e)},
            exc_info=True
        )
    
    return None


def format_health_report(results: Dict) -> str:
    """
    Format health check results as a readable report.
    
    Args:
        results: Health check results dictionary containing:
            - timestamp: ISO timestamp string
            - basic_health: Dictionary with 'status', 'response_time_ms', 'error', 'data'
            - detailed_health: Dictionary with 'status', 'components', 'version', 'timestamp'
            - system_resources: Dictionary with 'cpu_percent', 'memory_percent', 
              'memory_available_mb', 'disk_usage_percent', 'error'
            - cache_stats: Optional dictionary with cache statistics
            - overall_status: Overall health status string ("healthy", "degraded", "unhealthy")
        
    Returns:
        Formatted multi-line report string with health check summary
    """
    report = []
    report.append("=" * 70)
    report.append("mARB 2.0 - Health Check Report")
    report.append("=" * 70)
    report.append(f"Timestamp: {results.get('timestamp', 'Unknown')}")
    report.append("")
    
    # Basic Health
    basic = results.get("basic_health", {})
    report.append("Basic Health Check:")
    report.append(f"  Status: {basic.get('status', 'unknown').upper()}")
    if basic.get("response_time_ms"):
        report.append(f"  Response Time: {basic.get('response_time_ms')} ms")
    if basic.get("error"):
        report.append(f"  Error: {basic.get('error')}")
    report.append("")
    
    # Detailed Health
    detailed = results.get("detailed_health", {})
    report.append("Detailed Health Check:")
    report.append(f"  Overall Status: {detailed.get('status', 'unknown').upper()}")
    
    components = detailed.get("components", {})
    if components:
        report.append("  Components:")
        for name, comp in components.items():
            status = comp.get("status", "unknown")
            status_icon = "✓" if status == "healthy" else "✗"
            report.append(f"    {status_icon} {name}: {status}")
            
            if comp.get("response_time_ms"):
                report.append(f"      Response Time: {comp.get('response_time_ms')} ms")
            if comp.get("error"):
                report.append(f"      Error: {comp.get('error')}")
    
    report.append("")
    
    # System Resources
    system = results.get("system_resources", {})
    if system and not system.get("error"):
        report.append("System Resources:")
        if system.get("cpu_percent") is not None:
            cpu = system.get("cpu_percent")
            cpu_icon = "⚠" if cpu > 80 else "✓"
            report.append(f"  {cpu_icon} CPU Usage: {cpu}%")
        
        if system.get("memory_percent") is not None:
            mem = system.get("memory_percent")
            mem_icon = "⚠" if mem > 80 else "✓"
            report.append(f"  {mem_icon} Memory Usage: {mem}%")
            if system.get("memory_available_mb"):
                report.append(f"    Available: {system.get('memory_available_mb')} MB")
        
        if system.get("disk_usage_percent") is not None:
            disk = system.get("disk_usage_percent")
            disk_icon = "⚠" if disk > 80 else "✓"
            report.append(f"  {disk_icon} Disk Usage: {disk}%")
        report.append("")
    
    # Cache Stats
    cache = results.get("cache_stats")
    if cache:
        report.append("Cache Statistics:")
        overall = cache.get("overall", {})
        if overall:
            hits = overall.get("hits", 0)
            misses = overall.get("misses", 0)
            total = overall.get("total", 0)
            hit_rate = overall.get("hit_rate", 0)
            report.append(f"  Total Requests: {total}")
            report.append(f"  Hits: {hits}")
            report.append(f"  Misses: {misses}")
            report.append(f"  Hit Rate: {hit_rate:.2%}")
        report.append("")
    
    # Summary
    report.append("=" * 70)
    overall_status = results.get("overall_status", "unknown")
    if overall_status == "healthy":
        report.append("✓ Overall Status: HEALTHY")
    elif overall_status == "degraded":
        report.append("⚠ Overall Status: DEGRADED")
    else:
        report.append("✗ Overall Status: UNHEALTHY")
    report.append("=" * 70)
    
    return "\n".join(report)


def main():
    """Main monitoring function."""
    # Get base URL from environment or command line
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = os.getenv("API_URL", "http://localhost:8000")
    
    # Remove trailing slash
    base_url = base_url.rstrip("/")
    
    print("=" * 70)
    print("mARB 2.0 - Health Check Monitoring")
    print("=" * 70)
    print(f"Base URL: {base_url}")
    print()
    
    results = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "base_url": base_url,
        "basic_health": {},
        "detailed_health": {},
        "system_resources": {},
        "cache_stats": None,
        "overall_status": "unknown",
    }
    
    # Run checks
    print("Running health checks...")
    print()
    
    # Basic health
    print("1. Checking basic health endpoint...")
    results["basic_health"] = check_api_health(base_url)
    print(f"   Status: {results['basic_health'].get('status', 'unknown')}")
    print()
    
    # Detailed health
    print("2. Checking detailed health endpoint...")
    results["detailed_health"] = check_detailed_health(base_url)
    print(f"   Status: {results['detailed_health'].get('status', 'unknown')}")
    print()
    
    # System resources (if running locally)
    if "localhost" in base_url or "127.0.0.1" in base_url:
        print("3. Checking system resources...")
        results["system_resources"] = check_system_resources()
        if results["system_resources"].get("error"):
            print(f"   ⚠ Error checking system resources: {results['system_resources']['error']}")
            # Mark as degraded if system resource check fails (not critical for API health)
            if results["overall_status"] == "unknown":
                results["overall_status"] = "degraded"
        else:
            print("   ✓ System resources checked")
        print()
    else:
        print("3. Skipping system resources (remote server)")
        print()
    
    # Cache stats
    print("4. Checking cache statistics...")
    cache_stats = check_cache_stats(base_url)
    if cache_stats:
        results["cache_stats"] = cache_stats
        print("   ✓ Cache statistics retrieved")
    else:
        print("   ⚠ Cache statistics not available")
    print()
    
    # Determine overall status
    basic_status = results["basic_health"].get("status")
    detailed_status = results["detailed_health"].get("status")
    system_resources_error = results["system_resources"].get("error")
    
    # System resources check is only performed for localhost, so we need to check
    # if it was actually run (not skipped) before considering its error
    system_resources_checked = "localhost" in base_url or "127.0.0.1" in base_url
    
    # Determine overall status considering all checks
    if basic_status == "healthy" and detailed_status == "healthy":
        if system_resources_checked and system_resources_error:
            # API is healthy but system resource check failed - degraded
            results["overall_status"] = "degraded"
        else:
            # Everything is healthy
            results["overall_status"] = "healthy"
    elif (
        basic_status == "unhealthy"
        or detailed_status == "unhealthy"
        or (system_resources_checked and system_resources_error)
    ):
        # API is unhealthy or system resources failed - overall status is unhealthy
        results["overall_status"] = "unhealthy"
    else:
        # Mixed or unknown status - degraded
        results["overall_status"] = "degraded"
    
    # Print report
    report = format_health_report(results)
    print(report)
    
    # Save to file if requested
    output_file = os.getenv("HEALTH_CHECK_OUTPUT")
    if output_file:
        output_path = Path(output_file)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_path}")
    
    # Exit code based on status
    if results["overall_status"] == "healthy":
        return 0
    elif results["overall_status"] == "degraded":
        return 1
    else:
        return 2


if __name__ == "__main__":
    sys.exit(main())

