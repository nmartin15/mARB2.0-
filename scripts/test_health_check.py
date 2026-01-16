#!/usr/bin/env python3
"""Test script for health check endpoints."""
import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/v1"


def test_basic_health():
    """Test basic health endpoint."""
    print("Testing basic health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Basic Health: {data['status']} (version {data['version']})")
        return True
    else:
        print(f"❌ Basic Health: Failed with status {response.status_code}")
        return False


def test_detailed_health():
    """Test detailed health endpoint."""
    print("\nTesting detailed health endpoint...")
    response = requests.get(f"{BASE_URL}/health/detailed")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Overall Status: {data['status'].upper()}")
        print(f"   Version: {data['version']}")
        print(f"   Timestamp: {data['timestamp']}")
        print("\n   Component Status:")
        
        all_healthy = True
        for name, comp in data['components'].items():
            status_icon = "✅" if comp['status'] == "healthy" else "❌"
            status_text = f"{status_icon} {name.upper()}: {comp['status']}"
            
            if 'response_time_ms' in comp:
                status_text += f" ({comp['response_time_ms']}ms)"
            if 'active_workers' in comp:
                status_text += f" - {comp['active_workers']} worker(s)"
            if 'worker_names' in comp:
                status_text += f" {comp['worker_names']}"
            
            print(f"     {status_text}")
            
            if comp['status'] != "healthy":
                all_healthy = False
                if 'error' in comp:
                    print(f"       Error: {comp['error']}")
        
        return all_healthy
    else:
        print(f"❌ Detailed Health: Failed with status {response.status_code}")
        return False


def test_cache_stats():
    """Test cache stats endpoint."""
    print("\nTesting cache stats endpoint...")
    response = requests.get(f"{BASE_URL}/cache/stats")
    
    if response.status_code == 200:
        data = response.json()
        overall = data.get('overall', {})
        hit_rate = overall.get('hit_rate', 0) * 100
        print(f"✅ Cache Stats:")
        print(f"   Hits: {overall.get('hits', 0)}")
        print(f"   Misses: {overall.get('misses', 0)}")
        print(f"   Total: {overall.get('total', 0)}")
        print(f"   Hit Rate: {hit_rate:.2f}%")
        return True
    else:
        print(f"❌ Cache Stats: Failed with status {response.status_code}")
        return False


def main():
    """Run all health check tests."""
    print("=" * 60)
    print("mARB 2.0 Health Check Test Suite")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("Basic Health", test_basic_health()))
        results.append(("Detailed Health", test_detailed_health()))
        results.append(("Cache Stats", test_cache_stats()))
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to API server.")
        print("   Make sure the server is running on http://localhost:8000")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

