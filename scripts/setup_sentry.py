#!/usr/bin/env python3
"""Interactive script to set up Sentry error tracking configuration."""
import os
import sys
from pathlib import Path
from typing import Optional


def get_env_file_path() -> Path:
    """Get the path to the .env file."""
    project_root = Path(__file__).parent.parent
    return project_root / ".env"


def read_env_file() -> dict:
    """Read existing .env file and return as dictionary."""
    env_file = get_env_file_path()
    env_vars = {}
    
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    
    return env_vars


def write_env_file(env_vars: dict) -> None:
    """Write environment variables to .env file."""
    env_file = get_env_file_path()
    
    # Read existing file to preserve comments and structure
    existing_lines = []
    if env_file.exists():
        with open(env_file, "r") as f:
            existing_lines = f.readlines()
    
    # Create a set of keys we're updating
    updated_keys = set(env_vars.keys())
    
    # Write file, preserving existing structure
    with open(env_file, "w") as f:
        # Write existing lines, updating values for keys we're setting
        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in updated_keys:
                    # Update this line
                    f.write(f"{key}={env_vars[key]}\n")
                    updated_keys.remove(key)
                else:
                    # Keep original line
                    f.write(line)
            else:
                # Keep comments and empty lines
                f.write(line)
        
        # Add any new keys that weren't in the file
        if updated_keys:
            f.write("\n# Sentry Configuration\n")
            for key in sorted(updated_keys):
                if key.startswith("SENTRY_"):
                    f.write(f"{key}={env_vars[key]}\n")


def get_sentry_dsn() -> Optional[str]:
    """Get Sentry DSN from user input."""
    print("\n" + "=" * 70)
    print("Sentry DSN Configuration")
    print("=" * 70)
    print("\nTo get your Sentry DSN:")
    print("1. Sign up at https://sentry.io (or log in to existing account)")
    print("2. Create a new project:")
    print("   - Go to Projects → Create Project")
    print("   - Select 'Python' → 'FastAPI'")
    print("   - Give it a name (e.g., 'mARB 2.0')")
    print("3. Copy the DSN from the project settings")
    print("   - It looks like: https://xxxxx@xxxxx.ingest.sentry.io/xxxxx")
    print("\n" + "-" * 70)
    
    while True:
        dsn = input("\nEnter your Sentry DSN (or press Enter to skip): ").strip()
        
        if not dsn:
            return None
        
        # Validate DSN format
        if not dsn.startswith("https://"):
            print("❌ Error: DSN must start with 'https://'")
            continue
        
        if "@" not in dsn:
            print("❌ Error: DSN format is invalid (missing @)")
            continue
        
        if "sentry.io" not in dsn:
            print("⚠️  Warning: DSN doesn't contain 'sentry.io' - is this correct?")
            confirm = input("Continue anyway? (y/n): ").strip().lower()
            if confirm != "y":
                continue
        
        return dsn


def get_environment() -> str:
    """Get environment name from user."""
    print("\n" + "=" * 70)
    print("Environment Configuration")
    print("=" * 70)
    print("\nSelect environment:")
    print("1. development")
    print("2. staging")
    print("3. production")
    print("4. test")
    
    while True:
        choice = input("\nEnter choice (1-4) [default: 1]: ").strip()
        
        if not choice:
            return "development"
        
        env_map = {
            "1": "development",
            "2": "staging",
            "3": "production",
            "4": "test",
        }
        
        if choice in env_map:
            return env_map[choice]
        
        print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")


def get_release() -> Optional[str]:
    """Get release version from user."""
    print("\n" + "=" * 70)
    print("Release Version (Optional)")
    print("=" * 70)
    print("\nEnter a release version to track in Sentry.")
    print("This helps identify which version of your code caused errors.")
    print("Examples: v2.0.0, 2024.12.21, commit-hash")
    
    release = input("\nEnter release version (or press Enter to skip): ").strip()
    
    return release if release else None


def configure_performance_monitoring(env: str) -> dict:
    """Configure performance monitoring settings."""
    print("\n" + "=" * 70)
    print("Performance Monitoring Configuration")
    print("=" * 70)
    
    if env == "development":
        print("\n⚠️  Development environment detected.")
        print("Recommended: Disable performance monitoring in development.")
        enable_tracing = False
        traces_rate = 0.0
    else:
        print("\nPerformance monitoring helps identify slow endpoints and queries.")
        enable = input("Enable performance tracing? (y/n) [default: y]: ").strip().lower()
        enable_tracing = enable != "n"
        
        if enable_tracing:
            print("\nTrace sample rate determines what percentage of requests are traced.")
            print("Recommended: 0.1 (10%) for production, 1.0 (100%) for staging.")
            rate_input = input("Enter trace sample rate (0.0-1.0) [default: 0.1]: ").strip()
            try:
                traces_rate = float(rate_input) if rate_input else 0.1
                if not 0.0 <= traces_rate <= 1.0:
                    print("⚠️  Rate must be between 0.0 and 1.0, using 0.1")
                    traces_rate = 0.1
            except ValueError:
                print("⚠️  Invalid input, using 0.1")
                traces_rate = 0.1
        else:
            traces_rate = 0.0
    
    return {
        "SENTRY_ENABLE_TRACING": str(enable_tracing).lower(),
        "SENTRY_TRACES_SAMPLE_RATE": str(traces_rate),
    }


def configure_alerts(env: str) -> dict:
    """Configure alert settings."""
    print("\n" + "=" * 70)
    print("Alert Configuration")
    print("=" * 70)
    
    if env == "development":
        print("\n⚠️  Development environment detected.")
        print("Recommended: Disable alerts in development to avoid noise.")
        enable_alerts = False
        alert_on_errors = False
        alert_on_warnings = False
    else:
        print("\nAlerts notify you when errors occur in your application.")
        enable = input("Enable alerts? (y/n) [default: y]: ").strip().lower()
        enable_alerts = enable != "n"
        
        if enable_alerts:
            errors = input("Alert on errors (5xx)? (y/n) [default: y]: ").strip().lower()
            alert_on_errors = errors != "n"
            
            warnings = input("Alert on warnings (4xx)? (y/n) [default: n]: ").strip().lower()
            alert_on_warnings = warnings == "y"
        else:
            alert_on_errors = False
            alert_on_warnings = False
    
    return {
        "SENTRY_ENABLE_ALERTS": str(enable_alerts).lower(),
        "SENTRY_ALERT_ON_ERRORS": str(alert_on_errors).lower(),
        "SENTRY_ALERT_ON_WARNINGS": str(alert_on_warnings).lower(),
    }


def main():
    """Main setup function."""
    print("\n" + "=" * 70)
    print("Sentry Error Tracking Setup")
    print("=" * 70)
    print("\nThis script will help you configure Sentry error tracking for mARB 2.0.")
    print("Sentry provides error tracking, performance monitoring, and alerting.")
    
    # Read existing configuration
    existing_vars = read_env_file()
    
    # Get Sentry DSN
    dsn = get_sentry_dsn()
    if not dsn:
        print("\n⚠️  No DSN provided. Sentry will be disabled.")
        print("You can configure it later by adding SENTRY_DSN to your .env file.")
        
        # Still update other settings if they exist
        if any(k.startswith("SENTRY_") for k in existing_vars.keys()):
            update = input("\nUpdate other Sentry settings? (y/n): ").strip().lower()
            if update != "y":
                print("\n✅ Setup complete. Sentry is disabled.")
                return
        
        # Set DSN to empty
        dsn = ""
    
    # Get environment
    env = get_environment()
    
    # Get release (optional)
    release = get_release()
    
    # Configure performance monitoring
    perf_config = configure_performance_monitoring(env)
    
    # Configure alerts
    alert_config = configure_alerts(env)
    
    # Build configuration
    config = {
        "SENTRY_DSN": dsn,
        "SENTRY_ENVIRONMENT": env,
    }
    
    if release:
        config["SENTRY_RELEASE"] = release
    
    config.update(perf_config)
    config.update(alert_config)
    
    # Set defaults for other settings
    config.setdefault("SENTRY_ENABLE_PROFILING", "false")
    config.setdefault("SENTRY_PROFILES_SAMPLE_RATE", "0.1")
    config.setdefault("SENTRY_SEND_DEFAULT_PII", "false")
    
    # Update .env file
    print("\n" + "=" * 70)
    print("Updating Configuration")
    print("=" * 70)
    
    # Merge with existing vars
    all_vars = {**existing_vars, **config}
    write_env_file(all_vars)
    
    print(f"\n✅ Configuration saved to {get_env_file_path()}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Configuration Summary")
    print("=" * 70)
    print(f"DSN: {'✅ Configured' if dsn else '❌ Not configured (disabled)'}")
    print(f"Environment: {env}")
    if release:
        print(f"Release: {release}")
    print(f"Tracing: {'✅ Enabled' if config['SENTRY_ENABLE_TRACING'] == 'true' else '❌ Disabled'}")
    print(f"Alerts: {'✅ Enabled' if config['SENTRY_ENABLE_ALERTS'] == 'true' else '❌ Disabled'}")
    
    if dsn:
        print("\n" + "=" * 70)
        print("Next Steps")
        print("=" * 70)
        print("1. Restart your application to load the new configuration")
        print("2. Test Sentry by running: python scripts/test_sentry.py")
        print("3. Check your Sentry dashboard to verify errors are being captured")
        print("4. Set up alert rules in Sentry dashboard (see SENTRY_SETUP.md)")
    else:
        print("\n⚠️  Sentry is disabled. Add SENTRY_DSN to your .env file to enable it.")
    
    print("\n✅ Setup complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        sys.exit(1)

