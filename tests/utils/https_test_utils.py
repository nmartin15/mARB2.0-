"""Utilities for HTTPS and SSL testing.

This module provides helper functions for testing HTTPS/SSL functionality,
including certificate generation, validation, and security header checking.
These utilities are used in integration tests to verify SSL/TLS configuration
and security headers are properly set.

Functions:
    generate_self_signed_certificate: Generate self-signed SSL certificates for testing
    check_ssl_certificate: Validate and inspect SSL certificate details
    verify_ssl_connection: Test SSL connection to a remote host
    get_security_headers: Extract security headers from HTTP responses
    validate_hsts_header: Validate HSTS header configuration
"""
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from ipaddress import IPv4Address
from pathlib import Path
from typing import Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.general_name import DNSName, IPAddress
from cryptography.x509.oid import NameOID


def generate_self_signed_certificate(
    hostname: str = "localhost",
    key_size: int = 2048,
    valid_days: int = 365,
    output_dir: Optional[Path] = None,
) -> Tuple[Path, Path]:
    """
    Generate a self-signed SSL certificate for testing.
    
    Args:
        hostname: The hostname for the certificate (default: localhost)
        key_size: RSA key size in bits (default: 2048)
        valid_days: Certificate validity period in days (default: 365)
        output_dir: Directory to save certificates (default: temp directory)
        
    Returns:
        Tuple of (certificate_path, key_path)
    """
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp())
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )

    # Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Test"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Test"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "mARB Test"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=valid_days)
    ).add_extension(
        x509.SubjectAlternativeName([
            DNSName(hostname),
            DNSName("localhost"),
            IPAddress(IPv4Address("127.0.0.1")),
        ]),
        critical=False,
    ).sign(private_key, hashes.SHA256())

    # Write certificate
    cert_path = output_dir / "test_cert.pem"
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    # Write private key
    key_path = output_dir / "test_key.pem"
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Set appropriate permissions
    os.chmod(cert_path, 0o644)
    os.chmod(key_path, 0o600)

    return cert_path, key_path


def check_ssl_certificate(cert_path: Path) -> dict:
    """
    Check SSL certificate details.
    
    Args:
        cert_path: Path to certificate file
        
    Returns:
        Dictionary with certificate information
    """
    try:
        result = subprocess.run(
            ["openssl", "x509", "-in", str(cert_path), "-text", "-noout"],
            capture_output=True,
            text=True,
            check=True,
        )

        cert_info = {
            "valid": True,
            "details": result.stdout,
        }

        # Parse certificate expiration
        lines = result.stdout.split("\n")
        for i, line in enumerate(lines):
            if "Not After" in line:
                cert_info["expiration"] = line.strip()
                break

        return cert_info
    except subprocess.CalledProcessError as e:
        return {
            "valid": False,
            "error": e.stderr,
        }
    except FileNotFoundError:
        return {
            "valid": False,
            "error": f"openssl command not found in PATH. Please ensure OpenSSL is installed and available in your system PATH. Certificate path: {cert_path}",
        }


def verify_ssl_connection(
    hostname: str,
    port: int = 443,
    timeout: int = 5,
) -> dict:
    """
    Verify SSL connection to a host.
    
    Args:
        hostname: Hostname to connect to
        port: Port number (default: 443)
        timeout: Connection timeout in seconds (default: 5)
        
    Returns:
        Dictionary with connection verification results
    """
    try:
        result = subprocess.run(
            [
                "openssl", "s_client",
                "-connect", f"{hostname}:{port}",
                "-servername", hostname,
                "-verify_return_error",
            ],
            input="",
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = result.stdout + result.stderr

        return {
            "success": result.returncode == 0,
            "output": output,
            "verified": "Verify return code: 0" in output,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"SSL connection timeout after {timeout} seconds while connecting to {hostname}:{port}. The server may be down or unreachable.",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"openssl command not found in PATH. Please ensure OpenSSL is installed and available in your system PATH. Attempted to connect to {hostname}:{port}",
        }


def get_security_headers(response_headers: dict) -> dict:
    """
    Extract security headers from response headers.
    
    Args:
        response_headers: Dictionary of response headers
        
    Returns:
        Dictionary of security headers found
    """
    security_headers = {
        "Strict-Transport-Security": None,
        "X-Frame-Options": None,
        "X-Content-Type-Options": None,
        "X-XSS-Protection": None,
        "Referrer-Policy": None,
        "Content-Security-Policy": None,
        "Permissions-Policy": None,
    }

    # Case-insensitive header lookup
    header_lower = {k.lower(): v for k, v in response_headers.items()}

    for header_name in security_headers.keys():
        header_key = header_name.lower()
        if header_key in header_lower:
            security_headers[header_name] = header_lower[header_key]

    return security_headers


def validate_hsts_header(hsts_value: Optional[str]) -> dict:
    """
    Validate HSTS (Strict-Transport-Security) header value.
    
    Args:
        hsts_value: HSTS header value
        
    Returns:
        Dictionary with validation results
    """
    if not hsts_value:
        return {
            "valid": False,
            "error": "HSTS header not present",
        }

    # Parse HSTS header: max-age=31536000; includeSubDomains; preload
    parts = [p.strip() for p in hsts_value.split(";")]

    result = {
        "valid": True,
        "max_age": None,
        "include_subdomains": False,
        "preload": False,
    }

    for part in parts:
        if "max-age" in part.lower():
            try:
                result["max_age"] = int(part.split("=")[1].strip())
            except (ValueError, IndexError):
                result["valid"] = False
                result["error"] = f"Invalid max-age value: {part}"
                return result
        elif "includesubdomains" in part.lower():
            result["include_subdomains"] = True
        elif "preload" in part.lower():
            result["preload"] = True

    if result["max_age"] is None:
        result["valid"] = False
        result["error"] = "max-age directive not found"
        return result

    # Validate max-age is reasonable (at least 1 day = 86400 seconds)
    if result["max_age"] < 86400:
        result["warning"] = f"max-age is less than 1 day: {result['max_age']}"

    return result

