#!/usr/bin/env python3
"""Direct test of 835 processing pipeline (without Celery)."""
import sys
from pathlib import Path
from sqlalchemy.orm import Session

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config.database import SessionLocal
from app.services.edi.parser import EDIParser
from app.services.edi.transformer import EDITransformer
from app.models.database import Remittance
from app.utils.logger import get_logger

logger = get_logger(__name__)


def test_835_processing():
    """Test 835 processing pipeline directly."""
    print("=" * 60)
    print("835 Remittance Processing Test (Direct)")
    print("=" * 60)
    
    # Load sample file
    sample_file = Path(__file__).parent / "samples" / "sample_835.txt"
    if not sample_file.exists():
        print(f"❌ Sample file not found: {sample_file}")
        return False
    
    print(f"\n📄 Reading sample file: {sample_file}")
    with open(sample_file, "r") as f:
        file_content = f.read()
    
    # Parse the file
    print("\n🔍 Parsing 835 file...")
    parser = EDIParser()
    try:
        parsed_data = parser.parse(file_content, "sample_835.txt")
        print(f"✅ File parsed successfully")
        print(f"   File type: {parsed_data.get('file_type')}")
        print(f"   Remittances found: {len(parsed_data.get('remittances', []))}")
        print(f"   Warnings: {len(parsed_data.get('warnings', []))}")
        
        remittances = parsed_data.get("remittances", [])
        if not remittances:
            print("❌ No remittances extracted from file")
            return False
        
        # Show first remittance details
        if remittances:
            rem = remittances[0]
            print(f"\n📋 First Remittance Details:")
            print(f"   Claim Control Number: {rem.get('claim_control_number')}")
            print(f"   Claim Status Code: {rem.get('claim_status_code')}")
            print(f"   Payment Amount: ${rem.get('payment_amount')}")
            print(f"   Adjustments: {len(rem.get('adjustments', []))}")
            print(f"   Service Lines: {len(rem.get('service_lines', []))}")
        
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Transform and save to database
    print("\n💾 Transforming and saving to database...")
    db: Session = SessionLocal()
    
    try:
        transformer = EDITransformer(db, filename="sample_835.txt")
        bpr_data = parsed_data.get("bpr", {})
        
        saved_remittances = []
        for remittance_data in remittances:
            try:
                remittance = transformer.transform_835_remittance(remittance_data, bpr_data)
                db.add(remittance)
                db.flush()
                saved_remittances.append(remittance)
                print(f"   ✅ Saved remittance: {remittance.remittance_control_number}")
            except Exception as e:
                print(f"   ❌ Failed to transform remittance: {e}")
                import traceback
                traceback.print_exc()
                db.rollback()
                continue
        
        db.commit()
        
        print(f"\n✅ Successfully saved {len(saved_remittances)} remittance(s) to database")
        
        # Verify in database
        total = db.query(Remittance).count()
        print(f"   Total remittances in database: {total}")
        
        # Show details of first saved remittance
        if saved_remittances:
            rem = saved_remittances[0]
            print(f"\n📄 Database Record Details:")
            print(f"   ID: {rem.id}")
            print(f"   Remittance Control Number: {rem.remittance_control_number}")
            print(f"   Claim Control Number: {rem.claim_control_number}")
            print(f"   Payer Name: {rem.payer_name}")
            print(f"   Payment Amount: ${rem.payment_amount}")
            print(f"   Payment Date: {rem.payment_date}")
            print(f"   Status: {rem.status.value if rem.status else None}")
            
            if rem.denial_reasons:
                print(f"   Denial Reasons: {rem.denial_reasons}")
            
            if rem.adjustment_reasons:
                print(f"   Adjustment Reasons: {len(rem.adjustment_reasons)} adjustment(s)")
                for adj in rem.adjustment_reasons[:3]:
                    print(f"     - {adj.get('group_code')}{adj.get('reason_code')}: ${adj.get('amount')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database operation failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = test_835_processing()
    print("\n" + "=" * 60)
    if success:
        print("✅ Test completed successfully!")
    else:
        print("❌ Test failed")
    print("=" * 60)
    sys.exit(0 if success else 1)

