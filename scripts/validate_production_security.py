#!/usr/bin/env python3
"""Validate production security settings."""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.setup_production_env import check_production_security


def main():
    """
    Validate production security settings.
    
    Checks the .env file for security issues and validates production readiness.
    Separates errors (must be fixed) from warnings (should be addressed).
    
    Returns:
        Exit code: 0 if secure, 1 if errors found, 0 if only warnings
    """
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    print("=" * 70)
    print("mARB 2.0 - Production Security Validation")
    print("=" * 70)
    print()
    
    if not env_file.exists():
        print(f"✗ .env file not found at {env_file}")
        print("  Run: python scripts/setup_production_env.py")
        return 1
    
    is_secure, issues = check_production_security(env_file)
    
    # Separate errors from warnings
    errors = []
    warnings = []
    
    for issue in issues:
        if any(keyword in issue.upper() for keyword in ["MUST", "NEVER", "NOT SET", "DEFAULT VALUE"]):
            errors.append(issue)
        else:
            warnings.append(issue)
    
    if errors:
        print("✗ SECURITY ERRORS (must be fixed before production):")
        print()
        for error in errors:
            print(f"  ❌ {error}")
        print()
    
    if warnings:
        print("⚠ WARNINGS (should be addressed for production):")
        print()
        for warning in warnings:
            print(f"  ⚠️  {warning}")
        print()
    
    if is_secure and not errors:
        print("✓ All security checks passed!")
        if warnings:
            print("  (Some warnings present, but no critical issues)")
        return 0
    elif errors:
        print("✗ Security validation failed. Please fix the errors above.")
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())

