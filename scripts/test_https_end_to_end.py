#!/usr/bin/env python3
"""End-to-end HTTPS testing script for production readiness."""
import os
import sys
import ssl
import socket
import subprocess
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json

try:
    import httpx
    import requests
except ImportError:
    print("⚠ Required packages not installed. Install with:")
    print("  pip install httpx requests")
    sys.exit(1)


def test_https_connection(url: str, verify: bool = True) -> Tuple[bool, Dict]:
    """
    Test HTTPS connection to a URL.
    
    Args:
        url: URL to test
        verify: Whether to verify SSL certificate
        
    Returns:
        Tuple of (success, result_dict)
    """
    result = {
        "url": url,
        "success": False,
        "status_code": None,
        "error": None,
        "ssl_info": {},
        "headers": {},
        "response_time_ms": None
    }
    
    try:
        import time
        start = time.time()
        
        response = requests.get(
            url,
            verify=verify,
            timeout=10,
            allow_redirects=False
        )
        
        response_time = (time.time() - start) * 1000
        result["success"] = True
        result["status_code"] = response.status_code
        result["response_time_ms"] = round(response_time, 2)
        result["headers"] = dict(response.headers)
        
        # Extract SSL info if available
        if hasattr(response, "raw") and hasattr(response.raw, "connection"):
            conn = response.raw.connection
            if hasattr(conn, "sock") and hasattr(conn.sock, "getpeercert"):
                cert = conn.sock.getpeercert()
                if cert:
                    result["ssl_info"] = {
                        "subject": dict(x[0] for x in cert.get("subject", [])),
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "version": cert.get("version"),
                        "notBefore": cert.get("notBefore"),
                        "notAfter": cert.get("notAfter"),
                    }
        
    except requests.exceptions.SSLError as e:
        result["error"] = f"SSL Error: {str(e)}"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"Connection Error: {str(e)}"
    except requests.exceptions.Timeout:
        result["error"] = "Connection timeout"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result["success"], result


def test_ssl_certificate(hostname: str, port: int = 443) -> Tuple[bool, Dict]:
    """
    Test SSL certificate for a hostname.
    
    Args:
        hostname: Hostname to test
        port: Port number (default 443)
        
    Returns:
        Tuple of (is_valid, cert_info)
    """
    cert_info = {
        "hostname": hostname,
        "port": port,
        "valid": False,
        "error": None,
        "subject": None,
        "issuer": None,
        "expires": None,
        "days_until_expiry": None,
        "protocol": None,
        "cipher": None,
    }
    
    try:
        context = ssl.create_default_context()
        
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                
                cert_info["valid"] = True
                cert_info["protocol"] = ssock.version()
                cert_info["cipher"] = cipher[0] if cipher else None
                
                if cert:
                    # Extract subject
                    subject = dict(x[0] for x in cert.get("subject", []))
                    cert_info["subject"] = subject.get("commonName", "Unknown")
                    
                    # Extract issuer
                    issuer = dict(x[0] for x in cert.get("issuer", []))
                    cert_info["issuer"] = issuer.get("organizationName", "Unknown")
                    
                    # Extract expiration
                    not_after = cert.get("notAfter")
                    if not_after:
                        from datetime import datetime
                        try:
                            expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                            cert_info["expires"] = expires.isoformat()
                            
                            now = datetime.utcnow()
                            days = (expires - now).days
                            cert_info["days_until_expiry"] = days
                        except Exception:
                            cert_info["expires"] = not_after
                
    except ssl.SSLError as e:
        cert_info["error"] = f"SSL Error: {str(e)}"
    except socket.timeout:
        cert_info["error"] = "Connection timeout"
    except socket.gaierror as e:
        cert_info["error"] = f"DNS Error: {str(e)}"
    except Exception as e:
        cert_info["error"] = f"Unexpected error: {str(e)}"
    
    return cert_info["valid"], cert_info


def test_http_to_https_redirect(url: str) -> Tuple[bool, Dict]:
    """
    Test HTTP to HTTPS redirect.
    
    Args:
        url: HTTP URL to test (should redirect to HTTPS)
        
    Returns:
        Tuple of (redirects_to_https, result_dict)
    """
    result = {
        "url": url,
        "redirects_to_https": False,
        "status_code": None,
        "redirect_url": None,
        "error": None,
    }
    
    try:
        response = requests.get(
            url,
            allow_redirects=False,
            timeout=10
        )
        
        result["status_code"] = response.status_code
        
        if response.status_code in [301, 302, 307, 308]:
            redirect_url = response.headers.get("Location", "")
            result["redirect_url"] = redirect_url
            
            if redirect_url.startswith("https://"):
                result["redirects_to_https"] = True
        
    except Exception as e:
        result["error"] = str(e)
    
    return result["redirects_to_https"], result


def check_security_headers(url: str) -> Tuple[bool, Dict]:
    """
    Check security headers in HTTPS response.
    
    Args:
        url: HTTPS URL to test
        
    Returns:
        Tuple of (has_required_headers, headers_dict)
    """
    result = {
        "url": url,
        "has_required_headers": False,
        "headers": {},
        "missing_headers": [],
        "error": None,
    }
    
    required_headers = [
        "Strict-Transport-Security",
        "X-Frame-Options",
        "X-Content-Type-Options",
    ]
    
    try:
        response = requests.get(url, verify=True, timeout=10)
        result["headers"] = dict(response.headers)
        
        missing = []
        for header in required_headers:
            if header not in result["headers"]:
                # Check case-insensitive
                found = False
                for key in result["headers"].keys():
                    if key.lower() == header.lower():
                        found = True
                        break
                
                if not found:
                    missing.append(header)
        
        result["missing_headers"] = missing
        result["has_required_headers"] = len(missing) == 0
        
    except Exception as e:
        result["error"] = str(e)
    
    return result["has_required_headers"], result


def test_openssl_connection(hostname: str, port: int = 443) -> Tuple[bool, str]:
    """
    Test SSL connection using openssl command.
    
    Args:
        hostname: Hostname to test
        port: Port number
        
    Returns:
        Tuple of (success, output)
    """
    try:
        result = subprocess.run(
            [
                "openssl", "s_client",
                "-connect", f"{hostname}:{port}",
                "-servername", hostname,
            ],
            input="",
            capture_output=True,
            text=True,
            timeout=10
        )
        
        return result.returncode == 0, result.stdout
        
    except FileNotFoundError:
        return False, "openssl command not found"
    except subprocess.TimeoutExpired:
        return False, "openssl command timed out"
    except Exception as e:
        return False, str(e)


def main():
    """Main testing function."""
    print("=" * 70)
    print("mARB 2.0 - End-to-End HTTPS Testing")
    print("=" * 70)
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print()
    
    # Get URL from environment or command line
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = os.getenv("API_URL", "https://api.yourdomain.com")
    
    print(f"Testing URL: {base_url}")
    print()
    
    parsed = urllib.parse.urlparse(base_url)
    hostname = parsed.hostname or "localhost"
    scheme = parsed.scheme or "https"
    
    all_tests_passed = True
    issues = []
    
    # Test 1: SSL Certificate
    print("1. Testing SSL Certificate...")
    is_valid, cert_info = test_ssl_certificate(hostname)
    
    if is_valid:
        print(f"   ✓ SSL Certificate is valid")
        print(f"     Subject: {cert_info.get('subject', 'Unknown')}")
        print(f"     Issuer: {cert_info.get('issuer', 'Unknown')}")
        print(f"     Protocol: {cert_info.get('protocol', 'Unknown')}")
        print(f"     Cipher: {cert_info.get('cipher', 'Unknown')}")
        
        if cert_info.get("days_until_expiry"):
            days = cert_info["days_until_expiry"]
            if days < 30:
                print(f"     ⚠ Certificate expires in {days} days - renewal needed soon")
                issues.append(f"Certificate expires in {days} days")
            else:
                print(f"     ✓ Certificate expires in {days} days")
    else:
        print(f"   ✗ SSL Certificate test failed: {cert_info.get('error', 'Unknown error')}")
        all_tests_passed = False
        issues.append(f"SSL Certificate: {cert_info.get('error', 'Unknown error')}")
    print()
    
    # Test 2: HTTPS Connection
    print("2. Testing HTTPS Connection...")
    https_url = f"https://{hostname}{parsed.path or '/api/v1/health'}"
    success, result = test_https_connection(https_url)
    
    if success:
        print(f"   ✓ HTTPS connection successful")
        print(f"     Status Code: {result.get('status_code')}")
        print(f"     Response Time: {result.get('response_time_ms')} ms")
    else:
        print(f"   ✗ HTTPS connection failed: {result.get('error', 'Unknown error')}")
        all_tests_passed = False
        issues.append(f"HTTPS Connection: {result.get('error', 'Unknown error')}")
    print()
    
    # Test 3: HTTP to HTTPS Redirect
    print("3. Testing HTTP to HTTPS Redirect...")
    http_url = f"http://{hostname}{parsed.path or '/api/v1/health'}"
    redirects, redirect_result = test_http_to_https_redirect(http_url)
    
    if redirects:
        print(f"   ✓ HTTP redirects to HTTPS")
        print(f"     Redirect URL: {redirect_result.get('redirect_url')}")
    else:
        print(f"   ⚠ HTTP does not redirect to HTTPS")
        print(f"     Status Code: {redirect_result.get('status_code')}")
        issues.append("HTTP to HTTPS redirect not configured")
    print()
    
    # Test 4: Security Headers
    print("4. Checking Security Headers...")
    has_headers, headers_result = check_security_headers(https_url)
    
    if has_headers:
        print(f"   ✓ Required security headers present")
        for header, value in headers_result.get("headers", {}).items():
            if header.lower() in ["strict-transport-security", "x-frame-options", 
                                  "x-content-type-options"]:
                print(f"     {header}: {value}")
    else:
        missing = headers_result.get("missing_headers", [])
        print(f"   ⚠ Missing security headers: {', '.join(missing)}")
        issues.append(f"Missing security headers: {', '.join(missing)}")
    print()
    
    # Test 5: OpenSSL Connection (if available)
    print("5. Testing with OpenSSL (if available)...")
    openssl_success, openssl_output = test_openssl_connection(hostname)
    
    if openssl_success:
        print(f"   ✓ OpenSSL connection successful")
        # Extract key info from output
        if "Verify return code: 0" in openssl_output:
            print(f"     Certificate verification: OK")
        else:
            print(f"     ⚠ Certificate verification issues detected")
            issues.append("OpenSSL certificate verification issues")
    else:
        if "not found" in openssl_output:
            print(f"   ⚠ OpenSSL not available (optional test)")
        else:
            print(f"   ⚠ OpenSSL test failed: {openssl_output}")
    print()
    
    # Summary
    print("=" * 70)
    print("HTTPS TEST SUMMARY")
    print("=" * 70)
    print()
    
    if all_tests_passed and not issues:
        print("✓ All HTTPS tests passed!")
        print()
        print("Your HTTPS setup appears to be correctly configured.")
        print()
        print("Next steps:")
        print("  - Verify SSL Labs rating (https://www.ssllabs.com/ssltest/)")
        print("  - Test certificate auto-renewal")
        print("  - Monitor certificate expiration")
        return 0
    else:
        if issues:
            print("⚠ Issues found:")
            for issue in issues:
                print(f"  • {issue}")
            print()
        
        if not all_tests_passed:
            print("✗ Some HTTPS tests failed. Please review the errors above.")
            return 1
        else:
            print("⚠ Warnings found, but no critical failures.")
            return 0


if __name__ == "__main__":
    # Allow URL to be passed as argument
    sys.exit(main())

