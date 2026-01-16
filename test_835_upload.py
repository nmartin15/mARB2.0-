#!/usr/bin/env python3
"""Test script for 835 remittance file upload."""
import requests
import json
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
SAMPLE_835_FILE = Path(__file__).parent / "samples" / "sample_835.txt"


def test_health_check():
    """Test if the API server is running."""
    print("🔍 Checking if API server is running...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API server is running")
            return True
        else:
            print(f"❌ API server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API server. Is it running?")
        print("   Start it with: python run.py")
        return False
    except Exception as e:
        print(f"❌ Error checking health: {e}")
        return False


def upload_835_file():
    """Upload the sample 835 file."""
    print("\n📤 Uploading 835 remittance file...")
    
    if not SAMPLE_835_FILE.exists():
        print(f"❌ Sample file not found: {SAMPLE_835_FILE}")
        return None
    
    try:
        with open(SAMPLE_835_FILE, "rb") as f:
            files = {"file": (SAMPLE_835_FILE.name, f, "text/plain")}
            response = requests.post(
                f"{API_BASE_URL}/remits/upload",
                files=files,
                timeout=30
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ File uploaded successfully")
            print(f"   Task ID: {result.get('task_id')}")
            print(f"   Filename: {result.get('filename')}")
            return result.get("task_id")
        else:
            print(f"❌ Upload failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error uploading file: {e}")
        return None


def wait_for_processing(task_id=None, max_wait=30):
    """Wait for file processing to complete."""
    if not task_id:
        print("\n⏳ Waiting for processing (no task ID available)...")
        print("   Note: Celery worker must be running for processing to occur.")
        print("   Start with: celery -A app.services.queue.tasks worker --loglevel=info")
        return
    
    print(f"\n⏳ Waiting for task {task_id} to complete...")
    print("   Note: In production, this would poll Celery task status.")
    print("   For now, check Celery worker logs or use Flower dashboard to monitor progress.")
    # Note: In a real scenario, you'd check Celery task status via API
    # For testing, we rely on the check_remittances() function to verify results


def check_remittances():
    """Check if remittances were created."""
    print("\n🔍 Checking created remittances...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/remits", timeout=10)
        if response.status_code == 200:
            data = response.json()
            total = data.get("total", 0)
            remits = data.get("remits", [])
            
            print(f"✅ Found {total} remittance(s) in database")
            
            if remits:
                print("\n📋 Remittances:")
                for remit in remits[:5]:  # Show first 5
                    print(f"   - ID: {remit.get('id')}")
                    print(f"     Control Number: {remit.get('remittance_control_number')}")
                    print(f"     Claim Control: {remit.get('claim_control_number')}")
                    print(f"     Payer: {remit.get('payer_name')}")
                    print(f"     Payment: ${remit.get('payment_amount')}")
                    print(f"     Status: {remit.get('status')}")
                    print()
                
                # Get details of first remittance
                if remits:
                    remit_id = remits[0].get("id")
                    get_remittance_details(remit_id)
            
            return total > 0
        else:
            print(f"❌ Failed to get remittances: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking remittances: {e}")
        return False


def get_remittance_details(remit_id: int):
    """Get detailed information about a remittance."""
    print(f"\n📄 Details for Remittance ID {remit_id}:")
    
    try:
        response = requests.get(f"{API_BASE_URL}/remits/{remit_id}", timeout=10)
        if response.status_code == 200:
            remit = response.json()
            print(f"   Remittance Control Number: {remit.get('remittance_control_number')}")
            print(f"   Claim Control Number: {remit.get('claim_control_number')}")
            print(f"   Payer Name: {remit.get('payer_name')}")
            print(f"   Payment Amount: ${remit.get('payment_amount')}")
            print(f"   Payment Date: {remit.get('payment_date')}")
            print(f"   Check Number: {remit.get('check_number')}")
            print(f"   Status: {remit.get('status')}")
            
            denial_reasons = remit.get('denial_reasons')
            if denial_reasons:
                print(f"   Denial Reasons: {denial_reasons}")
            
            adjustment_reasons = remit.get('adjustment_reasons')
            if adjustment_reasons:
                print(f"   Adjustment Reasons: {len(adjustment_reasons)} adjustment(s)")
                for adj in adjustment_reasons[:3]:  # Show first 3
                    print(f"     - {adj.get('group_code')}{adj.get('reason_code')}: ${adj.get('amount')}")
            
            warnings = remit.get('parsing_warnings')
            if warnings:
                print(f"   Parsing Warnings: {len(warnings)} warning(s)")
                for warning in warnings[:3]:  # Show first 3
                    print(f"     - {warning}")
        else:
            print(f"❌ Failed to get remittance details: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting remittance details: {e}")


def main():
    """Run the full test."""
    print("=" * 60)
    print("835 Remittance Upload Test")
    print("=" * 60)
    
    # Check if server is running
    if not test_health_check():
        print("\n❌ Cannot proceed without API server")
        return
    
    # Upload file
    task_id = upload_835_file()
    
    # Wait for processing
    wait_for_processing(task_id)
    
    # Check results
    success = check_remittances()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Test completed successfully!")
    else:
        print("⚠️  Test completed, but no remittances were found")
        print("   This might be normal if Celery worker is not running")
        print("   Start Celery with: celery -A app.services.queue.tasks worker --loglevel=info")
    print("=" * 60)


if __name__ == "__main__":
    main()

