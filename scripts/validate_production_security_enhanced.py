#!/usr/bin/env python3
"""Enhanced production security validation with dependency checks."""
import os
import sys
import subprocess
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.setup_production_env import check_production_security

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_pip_installed() -> bool:
    """Check if pip is installed."""
    try:
        subprocess.run(
            ["pip", "--version"],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_safety_installed() -> bool:
    """Check if safety (vulnerability scanner) is installed."""
    try:
        subprocess.run(
            ["safety", "--version"],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_dependency_vulnerabilities() -> Tuple[bool, List[str]]:
    """
    Check for known vulnerabilities in dependencies.
    
    Returns:
        Tuple of (is_secure, list_of_issues)
    """
    issues = []
    
    if not check_pip_installed():
        return True, []  # Skip if pip not available
    
    if not check_safety_installed():
        issues.append(
            "⚠ safety package not installed - cannot check for dependency vulnerabilities. "
            "Install with: pip install safety"
        )
        return True, issues
    
    try:
        # Run safety check
        result = subprocess.run(
            ["safety", "check", "--json"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=project_root
        )
        
        if result.returncode == 0:
            return True, issues
        
        # Parse safety output
        try:
            vulnerabilities = json.loads(result.stdout)
            for vuln in vulnerabilities:
                package = vuln.get("package", "unknown")
                installed = vuln.get("installed_version", "unknown")
                vulnerability_id = vuln.get("vulnerability_id", "unknown")
                advisory = vuln.get("advisory", "No advisory available")
                
                issues.append(
                    f"❌ {package}=={installed}: {vulnerability_id} - {advisory}"
                )
        except json.JSONDecodeError:
            # If JSON parsing fails, use raw output
            if result.stdout:
                issues.append(f"⚠ Dependency vulnerabilities found:\n{result.stdout}")
        
        return len(issues) == 0, issues
        
    except subprocess.TimeoutExpired:
        issues.append("⚠ Safety check timed out - manual review recommended")
        return True, issues
    except Exception as e:
        issues.append(f"⚠ Could not check dependencies: {str(e)}")
        return True, issues


def check_outdated_packages() -> Tuple[bool, List[str]]:
    """
    Check for outdated packages.
    
    Returns:
        Tuple of (has_outdated, list_of_outdated_packages)
    """
    issues = []
    
    if not check_pip_installed():
        logger.info("pip not installed, skipping outdated packages check")
        return False, []
    
    try:
        result = subprocess.run(
            ["pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=project_root
        )
        
        if result.returncode != 0:
            logger.error(
                f"pip list --outdated failed with return code: {result.returncode}, "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )
            issues.append(
                f"⚠ Could not check for outdated packages: pip command failed "
                f"(return code {result.returncode})"
            )
            return False, issues
        
        try:
            outdated = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse pip list output as JSON: {e}. "
                f"Raw output: {result.stdout[:200]}"
            )
            issues.append(
                "⚠ Could not parse pip output - pip may be misconfigured or output format changed"
            )
            return False, issues
        
        if outdated:
            issues.append(f"⚠ Found {len(outdated)} outdated packages:")
            for pkg in outdated[:10]:  # Limit to first 10
                name = pkg.get("name", "unknown")
                current = pkg.get("version", "unknown")
                latest = pkg.get("latest_version", "unknown")
                issues.append(f"  - {name}: {current} -> {latest}")
            
            if len(outdated) > 10:
                issues.append(f"  ... and {len(outdated) - 10} more")
        
        return len(outdated) > 0, issues
        
    except subprocess.TimeoutExpired:
        logger.warning(
            "pip list --outdated timed out after 30 seconds. "
            "This may indicate network issues or a large package list."
        )
        issues.append("⚠ Package check timed out - manual review recommended")
        return False, issues
    except FileNotFoundError:
        logger.error("pip command not found in PATH")
        issues.append("⚠ pip command not found - cannot check for outdated packages")
        return False, issues
    except PermissionError as e:
        logger.error(f"Permission denied running pip command: {e}")
        issues.append("⚠ Permission denied when checking packages - may need elevated privileges")
        return False, issues
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred while checking for outdated packages: {e}",
            exc_info=True
        )
        issues.append(f"⚠ Unexpected error during package check: {type(e).__name__}")
        return False, issues


def check_file_permissions() -> Tuple[bool, List[str]]:
    """Check file permissions for security."""
    issues = []
    
    env_file = project_root / ".env"
    
    if env_file.exists():
        try:
            stat = env_file.stat()
            mode = oct(stat.st_mode)[-3:]
            
            # .env should be 600 (read/write for owner only)
            if mode != "600":
                issues.append(
                    f"⚠ .env file permissions are {mode}, should be 600 "
                    f"(run: chmod 600 .env)"
                )
        except OSError:
            pass  # Windows doesn't support file modes the same way
    
    return len(issues) == 0, issues


def check_environment_variables(env_content: str) -> Tuple[bool, List[str]]:
    """
    Check environment variables for security issues.
    
    Args:
        env_content: Content of the .env file as a string
        
    Returns:
        Tuple of (is_secure, list_of_issues)
    """
    issues = []
    
    # Check for secrets in environment
    sensitive_vars = [
        "JWT_SECRET_KEY",
        "ENCRYPTION_KEY",
        "REDIS_PASSWORD",
        "DATABASE_URL"
    ]
    
    # Check if secrets are in the file (basic check)
    for var in sensitive_vars:
        if f"{var}=" in env_content:
            # Check for default/placeholder values
            lines = env_content.split("\n")
            for line in lines:
                if line.startswith(f"{var}="):
                    # Extract value and sanitize
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    
                    # Sanitize value to prevent false positives and injection
                    # Remove any control characters, normalize whitespace, and escape special chars
                    sanitized_value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
                    sanitized_value = re.sub(r'\s+', ' ', sanitized_value).strip().lower()
                    
                    # Check for placeholder patterns using word boundaries to avoid false positives
                    # This prevents matching "change-me-safe" when looking for "change-me"
                    placeholder_patterns = [
                        r'\bchange-me\b',
                        r'\bchange_me\b',
                        r'\bplaceholder\b',
                        r'\bdefault\b',
                        r'^change-me$',
                        r'^change_me$',
                        r'^placeholder$',
                        r'^default$'
                    ]
                    
                    # Check for exact matches or word-boundary matches
                    if any(re.search(pattern, sanitized_value) for pattern in placeholder_patterns):
                        issues.append(
                            f"❌ {var} still contains placeholder value"
                        )
                    # Also check for common insecure patterns
                    elif len(sanitized_value) < 8:
                        issues.append(
                            f"⚠ {var} value is too short (may be insecure)"
                        )
    
    return len(issues) == 0, issues


def check_ssl_configuration(env_content: str) -> Tuple[bool, List[str]]:
    """
    Check SSL/TLS configuration.
    
    Args:
        env_content: Content of the .env file as a string
        
    Returns:
        Tuple of (is_secure, list_of_issues)
    """
    issues = []
    
    # Check database URL for SSL
    if "DATABASE_URL=" in env_content:
        if "sslmode=require" not in env_content and "sslmode=prefer" not in env_content:
            issues.append(
                "⚠ DATABASE_URL should include ?sslmode=require for production"
            )
    
    # Check nginx config exists
    nginx_config = project_root / "deployment" / "nginx.conf.example"
    if not nginx_config.exists():
        issues.append(
            "⚠ nginx configuration template not found at deployment/nginx.conf.example"
        )
    
    return len(issues) == 0, issues


def check_logging_configuration(env_content: str) -> Tuple[bool, List[str]]:
    """
    Check logging configuration.
    
    Args:
        env_content: Content of the .env file as a string
        
    Returns:
        Tuple of (is_secure, list_of_issues)
    """
    issues = []
    
    # Check for production logging
    if "ENVIRONMENT=production" in env_content:
        if "LOG_FILE=" not in env_content:
            issues.append(
                "⚠ LOG_FILE should be set in production for log rotation"
            )
    
    return len(issues) == 0, issues


def main():
    """Main validation function."""
    print("=" * 70)
    print("mARB 2.0 - Enhanced Production Security Validation")
    print("=" * 70)
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print()
    
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    all_errors = []
    all_warnings = []
    
    # 1. Basic security validation
    print("1. Running basic security validation...")
    if env_file.exists():
        is_secure, issues = check_production_security(env_file)
        
        for issue in issues:
            if any(keyword in issue.upper() for keyword in ["MUST", "NEVER", "NOT SET", "DEFAULT VALUE"]):
                all_errors.append(issue)
            else:
                all_warnings.append(issue)
    else:
        all_errors.append(".env file not found")
    print("   ✓ Basic validation complete")
    print()
    
    # Read .env file once
    env_content = None
    if env_file.exists():
        try:
            with open(env_file, "r") as f:
                env_content = f.read()
        except Exception as e:
            logger.error(f"Failed to read .env file: {e}")
            all_errors.append(f"Cannot read .env file: {e}")
    
    # 2. Environment variable checks
    print("2. Checking environment variables...")
    if env_content:
        is_secure, issues = check_environment_variables(env_content)
        for issue in issues:
            if "❌" in issue:
                all_errors.append(issue.replace("❌", "").strip())
            else:
                all_warnings.append(issue)
    else:
        all_errors.append("Cannot check environment variables due to missing .env file")
    print("   ✓ Environment variables checked")
    print()
    
    # 3. File permissions
    print("3. Checking file permissions...")
    is_secure, issues = check_file_permissions()
    all_warnings.extend(issues)
    print("   ✓ File permissions checked")
    print()
    
    # 4. SSL/TLS configuration
    print("4. Checking SSL/TLS configuration...")
    if env_content:
        is_secure, issues = check_ssl_configuration(env_content)
        all_warnings.extend(issues)
    else:
        all_errors.append("Cannot check SSL/TLS configuration due to missing .env file")
    print("   ✓ SSL/TLS configuration checked")
    print()
    
    # 5. Logging configuration
    print("5. Checking logging configuration...")
    if env_content:
        is_secure, issues = check_logging_configuration(env_content)
        all_warnings.extend(issues)
    else:
        all_errors.append("Cannot check logging configuration due to missing .env file")
    print("   ✓ Logging configuration checked")
    print()
    
    # 6. Dependency vulnerability check
    print("6. Checking for dependency vulnerabilities...")
    is_secure, issues = check_dependency_vulnerabilities()
    for issue in issues:
        if "❌" in issue:
            all_errors.append(issue.replace("❌", "").strip())
        else:
            all_warnings.append(issue)
    print("   ✓ Dependency check complete")
    print()
    
    # 7. Outdated packages check
    print("7. Checking for outdated packages...")
    has_outdated, issues = check_outdated_packages()
    if has_outdated:
        all_warnings.extend(issues)
    print("   ✓ Outdated packages checked")
    print()
    
    # Summary
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print()
    
    if all_errors:
        print("❌ SECURITY ERRORS (must be fixed before production):")
        print()
        for error in all_errors:
            print(f"  • {error}")
        print()
    
    if all_warnings:
        print("⚠ WARNINGS (should be addressed for production):")
        print()
        for warning in all_warnings:
            print(f"  • {warning}")
        print()
    
    if not all_errors and not all_warnings:
        print("✓ All security checks passed!")
        print()
        print("Your application appears ready for production deployment.")
        print("However, please also:")
        print("  - Test HTTPS setup end-to-end")
        print("  - Verify monitoring/health checks")
        print("  - Review deployment checklist")
        return 0
    elif all_errors:
        print("✗ Security validation failed. Please fix the errors above.")
        print()
        print("Run: python scripts/validate_production_security.py for basic checks")
        return 1
    else:
        print("⚠ Warnings found, but no critical errors.")
        print("Review warnings before deploying to production.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

