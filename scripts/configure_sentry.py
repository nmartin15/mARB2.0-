#!/usr/bin/env python3
"""
Interactive script to configure Sentry error tracking.

This script helps you:
1. Get your Sentry DSN
2. Configure environment variables
3. Test the Sentry connection
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def print_header(text: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def get_env_file_path() -> Path:
    """Get the path to the .env file."""
    env_file = project_root / ".env"
    if not env_file.exists():
        # Check if .env.example exists
        example_file = project_root / ".env.example"
        if example_file.exists():
            print(f"⚠️  .env file not found. Creating from .env.example...")
            import shutil
            shutil.copy(example_file, env_file)
            print(f"✅ Created .env file from .env.example")
        else:
            print(f"⚠️  .env file not found. Creating new .env file...")
            env_file.touch()
    return env_file


def read_env_file(env_file: Path) -> dict:
    """Read environment variables from .env file."""
    env_vars = {}
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def write_env_file(env_file: Path, env_vars: dict) -> None:
    """Write environment variables to .env file."""
    # Read existing file to preserve comments and other vars
    existing_lines = []
    if env_file.exists():
        with open(env_file, "r") as f:
            existing_lines = f.readlines()
    
    # Update or add Sentry variables
    sentry_vars = {
        "SENTRY_DSN": env_vars.get("SENTRY_DSN", ""),
        "SENTRY_ENVIRONMENT": env_vars.get("SENTRY_ENVIRONMENT", "development"),
        "SENTRY_RELEASE": env_vars.get("SENTRY_RELEASE", ""),
        "SENTRY_TRACES_SAMPLE_RATE": env_vars.get("SENTRY_TRACES_SAMPLE_RATE", "0.1"),
        "SENTRY_PROFILES_SAMPLE_RATE": env_vars.get("SENTRY_PROFILES_SAMPLE_RATE", "0.1"),
        "SENTRY_ENABLE_ALERTS": env_vars.get("SENTRY_ENABLE_ALERTS", "true"),
        "SENTRY_ALERT_ON_ERRORS": env_vars.get("SENTRY_ALERT_ON_ERRORS", "true"),
        "SENTRY_ALERT_ON_WARNINGS": env_vars.get("SENTRY_ALERT_ON_WARNINGS", "false"),
        "SENTRY_ENABLE_TRACING": env_vars.get("SENTRY_ENABLE_TRACING", "true"),
        "SENTRY_ENABLE_PROFILING": env_vars.get("SENTRY_ENABLE_PROFILING", "false"),
        "SENTRY_SEND_DEFAULT_PII": env_vars.get("SENTRY_SEND_DII", "false"),
    }
    
    # Write updated file
    with open(env_file, "w") as f:
        # Write existing non-Sentry lines
        in_sentry_section = False
        for line in existing_lines:
            stripped = line.strip()
            if stripped.startswith("# Sentry") or stripped.startswith("#Sentry"):
                in_sentry_section = True
                f.write(line)
            elif in_sentry_section and (stripped.startswith("#") or not stripped or "=" not in stripped):
                f.write(line)
            elif in_sentry_section and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key.startswith("SENTRY_"):
                    continue  # Skip old Sentry vars
                else:
                    in_sentry_section = False
                    f.write(line)
            elif not any(key in line for key in sentry_vars.keys()):
                f.write(line)
        
        # Write Sentry section
        if not in_sentry_section:
            f.write("\n# Sentry Error Tracking Configuration\n")
        for key, value in sentry_vars.items():
            f.write(f"{key}={value}\n")


def get_sentry_dsn() -> str:
    """Get Sentry DSN from user."""
    print_header("Step 1: Get Your Sentry DSN")
    
    print("To get your Sentry DSN:")
    print("1. Go to https://sentry.io and sign up (or log in)")
    print("2. Create a new project:")
    print("   - Click 'Create Project'")
    print("   - Select 'Python' → 'FastAPI'")
    print("   - Give it a name (e.g., 'mARB 2.0')")
    print("3. Copy the DSN from the setup page")
    print("   (It looks like: https://xxxxx@xxxxx.ingest.sentry.io/xxxxx)\n")
    
    dsn = input("Enter your Sentry DSN (or press Enter to skip): ").strip()
    
    if not dsn:
        print("⚠️  No DSN provided. Sentry will be disabled.")
        return ""
    
    if not dsn.startswith("https://"):
        print("⚠️  Warning: DSN should start with 'https://'")
        confirm = input("Continue anyway? (y/n): ").strip().lower()
        if confirm != "y":
            return get_sentry_dsn()
    
    return dsn


def get_environment() -> str:
    """Get environment name from user."""
    print_header("Step 2: Configure Environment")
    
    print("Select your environment:")
    print("1. development")
    print("2. staging")
    print("3. production")
    print("4. custom")
    
    choice = input("\nEnter choice (1-4, default: 1): ").strip() or "1"
    
    if choice == "1":
        return "development"
    elif choice == "2":
        return "staging"
    elif choice == "3":
        return "production"
    elif choice == "4":
        return input("Enter custom environment name: ").strip() or "development"
    else:
        return "development"


def get_release() -> str:
    """Get release version from user."""
    print_header("Step 3: Configure Release (Optional)")
    
    release = input("Enter release version (e.g., v2.0.0, or press Enter to skip): ").strip()
    return release


def configure_settings(env: str) -> dict:
    """Configure Sentry settings based on environment."""
    print_header("Step 4: Configure Settings")
    
    if env == "development":
        print("Using development settings (tracing disabled, alerts disabled)")
        return {
            "SENTRY_TRACES_SAMPLE_RATE": "0.0",
            "SENTRY_ENABLE_ALERTS": "false",
            "SENTRY_ALERT_ON_ERRORS": "false",
            "SENTRY_ALERT_ON_WARNINGS": "false",
            "SENTRY_ENABLE_TRACING": "false",
            "SENTRY_ENABLE_PROFILING": "false",
        }
    elif env == "production":
        print("Using production settings (10% tracing, alerts enabled)")
        return {
            "SENTRY_TRACES_SAMPLE_RATE": "0.1",
            "SENTRY_ENABLE_ALERTS": "true",
            "SENTRY_ALERT_ON_ERRORS": "true",
            "SENTRY_ALERT_ON_WARNINGS": "false",
            "SENTRY_ENABLE_TRACING": "true",
            "SENTRY_ENABLE_PROFILING": "false",
        }
    else:  # staging
        print("Using staging settings (10% tracing, alerts enabled)")
        return {
            "SENTRY_TRACES_SAMPLE_RATE": "0.1",
            "SENTRY_ENABLE_ALERTS": "true",
            "SENTRY_ALERT_ON_ERRORS": "true",
            "SENTRY_ALERT_ON_WARNINGS": "false",
            "SENTRY_ENABLE_TRACING": "true",
            "SENTRY_ENABLE_PROFILING": "false",
        }


def test_sentry_connection(dsn: str) -> bool:
    """Test Sentry connection."""
    if not dsn:
        return False
    
    print_header("Step 5: Test Sentry Connection")
    
    try:
        import sentry_sdk
        from sentry_sdk import capture_message
        
        sentry_sdk.init(
            dsn=dsn,
            environment="test",
            traces_sample_rate=0.0,
        )
        
        print("Sending test message to Sentry...")
        event_id = capture_message("Sentry configuration test from mARB 2.0", level="info")
        
        if event_id:
            print(f"✅ Success! Test message sent (Event ID: {event_id})")
            print("Check your Sentry dashboard to verify the message was received.")
            return True
        else:
            print("⚠️  Warning: Message sent but no event ID returned")
            return True
    except ImportError:
        print("❌ Error: sentry-sdk not installed")
        print("Run: pip install sentry-sdk[fastapi]")
        return False
    except Exception as e:
        print(f"❌ Error testing Sentry connection: {e}")
        return False


def main():
    """Main setup function."""
    print_header("Sentry Error Tracking Setup")
    
    print("This script will help you configure Sentry error tracking for mARB 2.0.")
    print("Sentry is already integrated into the codebase - you just need to add your DSN.\n")
    
    # Get .env file
    env_file = get_env_file_path()
    existing_vars = read_env_file(env_file)
    
    # Check if already configured
    if existing_vars.get("SENTRY_DSN"):
        print(f"✅ Sentry DSN already configured: {existing_vars['SENTRY_DSN'][:30]}...")
        reconfigure = input("Reconfigure? (y/n, default: n): ").strip().lower()
        if reconfigure != "y":
            print("Keeping existing configuration.")
            return
    
    # Get configuration
    dsn = get_sentry_dsn()
    if not dsn:
        print("\n⚠️  Sentry not configured. You can configure it later by:")
        print("   1. Adding SENTRY_DSN to your .env file")
        print("   2. Running this script again")
        return
    
    env = get_environment()
    release = get_release()
    settings = configure_settings(env)
    
    # Prepare all variables
    all_vars = {
        "SENTRY_DSN": dsn,
        "SENTRY_ENVIRONMENT": env,
        "SENTRY_RELEASE": release,
        "SENTRY_TRACES_SAMPLE_RATE": settings.get("SENTRY_TRACES_SAMPLE_RATE", "0.1"),
        "SENTRY_PROFILES_SAMPLE_RATE": "0.1",
        "SENTRY_ENABLE_ALERTS": settings.get("SENTRY_ENABLE_ALERTS", "true"),
        "SENTRY_ALERT_ON_ERRORS": settings.get("SENTRY_ALERT_ON_ERRORS", "true"),
        "SENTRY_ALERT_ON_WARNINGS": settings.get("SENTRY_ALERT_ON_WARNINGS", "false"),
        "SENTRY_ENABLE_TRACING": settings.get("SENTRY_ENABLE_TRACING", "true"),
        "SENTRY_ENABLE_PROFILING": settings.get("SENTRY_ENABLE_PROFILING", "false"),
        "SENTRY_SEND_DEFAULT_PII": "false",
    }
    
    # Merge with existing vars
    for key, value in all_vars.items():
        existing_vars[key] = value
    
    # Write to .env file
    write_env_file(env_file, existing_vars)
    print(f"\n✅ Configuration saved to {env_file}")
    
    # Test connection
    test = input("\nTest Sentry connection now? (y/n, default: y): ").strip().lower() or "y"
    if test == "y":
        test_sentry_connection(dsn)
    
    print_header("Setup Complete!")
    
    print("Next steps:")
    print("1. Restart your application to load the new configuration")
    print("2. Check your Sentry dashboard to see test messages")
    print("3. Configure alerts in Sentry dashboard (see SENTRY_SETUP.md)")
    print("\nFor more information, see: SENTRY_SETUP.md")


if __name__ == "__main__":
    main()

