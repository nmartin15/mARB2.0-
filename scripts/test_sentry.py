#!/usr/bin/env python3
"""
Test script to verify Sentry error tracking is configured correctly.

This script:
1. Checks if Sentry is configured
2. Sends a test message to Sentry
3. Sends a test exception to Sentry
4. Verifies the connection is working
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config.sentry import init_sentry, capture_message, capture_exception, settings


def print_header(text: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def test_sentry_configuration() -> bool:
    """Test if Sentry is configured."""
    print_header("Checking Sentry Configuration")
    
    if not settings.dsn:
        print("❌ Sentry DSN not configured")
        print("   Run: python scripts/configure_sentry.py")
        return False
    
    print(f"✅ Sentry DSN configured: {settings.dsn[:40]}...")
    print(f"✅ Environment: {settings.environment}")
    if settings.release:
        print(f"✅ Release: {settings.release}")
    print(f"✅ Tracing: {'Enabled' if settings.enable_tracing else 'Disabled'}")
    print(f"✅ Alerts: {'Enabled' if settings.enable_alerts else 'Disabled'}")
    
    return True


def test_sentry_connection() -> bool:
    """Test Sentry connection by sending a test message."""
    print_header("Testing Sentry Connection")
    
    try:
        # Initialize Sentry
        init_sentry()
        
        # Send a test message
        print("Sending test message to Sentry...")
        event_id = capture_message(
            "🧪 Test message from mARB 2.0 Sentry test script",
            level="info",
            context={
                "test": {
                    "type": "configuration_test",
                    "script": "test_sentry.py",
                },
            },
            tags={
                "test": "true",
                "source": "setup_script",
            },
        )
        
        if event_id:
            print(f"✅ Test message sent successfully!")
            print(f"   Event ID: {event_id}")
            print("   Check your Sentry dashboard to verify the message was received.")
            return True
        else:
            print("⚠️  Message sent but no event ID returned")
            print("   This might indicate Sentry is not fully initialized.")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Sentry connection: {e}")
        return False


def test_sentry_exception() -> bool:
    """Test Sentry exception capture."""
    print_header("Testing Exception Capture")
    
    try:
        # Create a test exception
        test_exception = ValueError("This is a test exception from mARB 2.0")
        
        print("Sending test exception to Sentry...")
        event_id = capture_exception(
            test_exception,
            level="error",
            context={
                "test": {
                    "type": "exception_test",
                    "script": "test_sentry.py",
                    "intentional": True,
                },
            },
            tags={
                "test": "true",
                "exception_type": "ValueError",
                "source": "setup_script",
            },
        )
        
        if event_id:
            print(f"✅ Test exception sent successfully!")
            print(f"   Event ID: {event_id}")
            print("   Check your Sentry dashboard to verify the exception was captured.")
            return True
        else:
            print("⚠️  Exception sent but no event ID returned")
            return False
            
    except Exception as e:
        print(f"❌ Error testing exception capture: {e}")
        return False


def main():
    """Main test function."""
    print_header("Sentry Error Tracking Test")
    
    print("This script will test your Sentry configuration and connection.\n")
    
    # Check configuration
    if not test_sentry_configuration():
        print("\n⚠️  Please configure Sentry first:")
        print("   python scripts/configure_sentry.py")
        sys.exit(1)
    
    # Test connection
    if not test_sentry_connection():
        print("\n❌ Sentry connection test failed")
        print("   Please check your DSN and network connection.")
        sys.exit(1)
    
    # Test exception capture
    send_exception = input("\nSend a test exception? (y/n, default: y): ").strip().lower() or "y"
    if send_exception == "y":
        if not test_sentry_exception():
            print("\n⚠️  Exception capture test failed")
            print("   This might be normal if Sentry is not fully initialized.")
    
    print_header("Test Complete!")
    
    print("✅ Sentry is configured and working!")
    print("\nNext steps:")
    print("1. Check your Sentry dashboard to verify test messages were received")
    print("2. Configure alert rules in Sentry dashboard (see SENTRY_SETUP.md)")
    print("3. Restart your application to ensure Sentry is initialized on startup")
    print("\nFor more information, see: SENTRY_SETUP.md")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
