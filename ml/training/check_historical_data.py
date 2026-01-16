"""Check available historical data for ML training."""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config.database import get_db
from app.models.database import Claim, Remittance, ClaimEpisode
from app.utils.logger import get_logger

logger = get_logger(__name__)


def check_historical_data(db: Session) -> Dict:
    """
    Check what historical data is available in the database.
    
    Returns:
        Dictionary with data availability statistics
    """
    print("\n" + "=" * 70)
    print("HISTORICAL DATA AVAILABILITY CHECK")
    print("=" * 70)

    # Check claims
    total_claims = db.query(func.count(Claim.id)).scalar()
    claims_with_dates = (
        db.query(func.count(Claim.id))
        .filter(Claim.created_at.isnot(None))
        .scalar()
    )
    
    # Check remittances
    total_remittances = db.query(func.count(Remittance.id)).scalar()
    remittances_with_dates = (
        db.query(func.count(Remittance.id))
        .filter(Remittance.created_at.isnot(None))
        .scalar()
    )
    
    # Check episodes (linked claims + remittances)
    total_episodes = db.query(func.count(ClaimEpisode.id)).scalar()
    linked_episodes = (
        db.query(func.count(ClaimEpisode.id))
        .filter(ClaimEpisode.remittance_id.isnot(None))
        .scalar()
    )
    
    # Date range analysis
    oldest_claim = (
        db.query(func.min(Claim.created_at))
        .filter(Claim.created_at.isnot(None))
        .scalar()
    )
    newest_claim = (
        db.query(func.max(Claim.created_at))
        .filter(Claim.created_at.isnot(None))
        .scalar()
    )
    
    oldest_remittance = (
        db.query(func.min(Remittance.created_at))
        .filter(Remittance.created_at.isnot(None))
        .scalar()
    )
    newest_remittance = (
        db.query(func.max(Remittance.created_at))
        .filter(Remittance.created_at.isnot(None))
        .scalar()
    )
    
    # Episodes with outcomes (for training)
    episodes_with_outcomes = (
        db.query(ClaimEpisode)
        .join(Claim)
        .join(Remittance)
        .filter(ClaimEpisode.remittance_id.isnot(None))
        .count()
    )
    
    # Episodes by date range
    six_months_ago = datetime.now() - timedelta(days=180)
    episodes_last_6mo = (
        db.query(ClaimEpisode)
        .join(Claim)
        .join(Remittance)
        .filter(
            and_(
                Claim.created_at >= six_months_ago,
                ClaimEpisode.remittance_id.isnot(None),
            )
        )
        .count()
    )
    
    # Denial statistics
    episodes_with_denials = (
        db.query(ClaimEpisode)
        .join(Remittance)
        .filter(
            and_(
                ClaimEpisode.remittance_id.isnot(None),
                Remittance.denial_reasons.isnot(None),
            )
        )
        .count()
    )
    
    # Print summary
    print("\n--- Database Statistics ---")
    print(f"Total Claims:              {total_claims:,}")
    print(f"Claims with Dates:         {claims_with_dates:,}")
    print(f"Total Remittances:         {total_remittances:,}")
    print(f"Remittances with Dates:    {remittances_with_dates:,}")
    print(f"Total Episodes:            {total_episodes:,}")
    print(f"Linked Episodes:           {linked_episodes:,}")
    print(f"Episodes with Outcomes:    {episodes_with_outcomes:,}")
    
    print("\n--- Date Ranges ---")
    if oldest_claim:
        print(f"Oldest Claim:              {oldest_claim.strftime('%Y-%m-%d')}")
    else:
        print("Oldest Claim:              None")
    
    if newest_claim:
        print(f"Newest Claim:              {newest_claim.strftime('%Y-%m-%d')}")
    else:
        print("Newest Claim:              None")
    
    if oldest_remittance:
        print(f"Oldest Remittance:         {oldest_remittance.strftime('%Y-%m-%d')}")
    else:
        print("Oldest Remittance:         None")
    
    if newest_remittance:
        print(f"Newest Remittance:         {newest_remittance.strftime('%Y-%m-%d')}")
    else:
        print("Newest Remittance:         None")
    
    if oldest_claim and newest_claim:
        days_span = (newest_claim - oldest_claim).days
        print(f"Claims Date Span:          {days_span} days ({days_span/30.44:.1f} months)")
    
    print("\n--- Training Data Availability ---")
    print(f"Episodes with Outcomes:     {episodes_with_outcomes:,}")
    print(f"Episodes (Last 6 Months):  {episodes_last_6mo:,}")
    print(f"Episodes with Denials:     {episodes_with_denials:,}")
    
    if episodes_with_outcomes > 0:
        denial_rate = (episodes_with_denials / episodes_with_outcomes) * 100
        print(f"Denial Rate:               {denial_rate:.1f}%")
    
    # ML Training Readiness
    print("\n--- ML Training Readiness ---")
    min_episodes_required = 100
    
    if episodes_with_outcomes >= min_episodes_required:
        print(f"✅ READY FOR TRAINING: {episodes_with_outcomes:,} episodes available")
        print(f"   Minimum required: {min_episodes_required}")
        print(f"   Excess: {episodes_with_outcomes - min_episodes_required:,} episodes")
    else:
        print(f"❌ INSUFFICIENT DATA: {episodes_with_outcomes:,} episodes available")
        print(f"   Minimum required: {min_episodes_required}")
        print(f"   Need: {min_episodes_required - episodes_with_outcomes:,} more episodes")
    
    if episodes_last_6mo >= min_episodes_required:
        print(f"✅ RECENT DATA SUFFICIENT: {episodes_last_6mo:,} episodes in last 6 months")
    else:
        print(f"⚠️  LIMITED RECENT DATA: {episodes_last_6mo:,} episodes in last 6 months")
    
    print("\n" + "=" * 70)
    
    return {
        "total_claims": total_claims,
        "total_remittances": total_remittances,
        "total_episodes": total_episodes,
        "linked_episodes": linked_episodes,
        "episodes_with_outcomes": episodes_with_outcomes,
        "episodes_last_6mo": episodes_last_6mo,
        "episodes_with_denials": episodes_with_denials,
        "oldest_claim": oldest_claim.isoformat() if oldest_claim else None,
        "newest_claim": newest_claim.isoformat() if newest_claim else None,
        "ready_for_training": episodes_with_outcomes >= min_episodes_required,
    }


def print_data_sources():
    """Print information about where to get historical data."""
    print("\n" + "=" * 70)
    print("HISTORICAL DATA SOURCES")
    print("=" * 70)
    
    print("\n1. EXISTING DATABASE DATA")
    print("   - Check your database for existing claims and remittances")
    print("   - Data comes from uploaded EDI files (837 claims, 835 remittances)")
    print("   - Episodes link claims to their remittance outcomes")
    
    print("\n2. UPLOAD SAMPLE FILES")
    print("   - Sample files available in: samples/")
    print("   - sample_837.txt - Sample claim file")
    print("   - sample_835.txt - Sample remittance file")
    print("   - large/ - Larger sample files for testing")
    print("   - Upload via API: POST /api/v1/claims/upload or /api/v1/remits/upload")
    
    print("\n3. IMPORT FROM EXTERNAL SOURCES")
    print("   - Export EDI files from your practice management system")
    print("   - Export from clearinghouse (Availity, Change Healthcare, etc.)")
    print("   - Historical data from billing software")
    print("   - Format: X12 EDI 837 (claims) and 835 (remittances)")
    
    print("\n4. GENERATE SYNTHETIC DATA (Development/Testing)")
    print("   - Use scripts/generate_large_edi_files.py (if available)")
    print("   - Create test data for development")
    print("   - ⚠️  Not recommended for production model training")
    
    print("\n5. DATA REQUIREMENTS FOR ML TRAINING")
    print("   - Minimum: 100 episodes with outcomes (claims + remittances)")
    print("   - Recommended: 500+ episodes for better model performance")
    print("   - Ideal: 6+ months of historical data")
    print("   - Need both claims (837) AND remittances (835) linked together")
    
    print("\n6. HOW TO LINK CLAIMS AND REMITTANCES")
    print("   - Episodes are automatically linked when remittances are uploaded")
    print("   - Linking uses claim control numbers")
    print("   - Manual linking: POST /api/v1/episodes/{episode_id}/link")
    print("   - Auto-link remittance: POST /api/v1/remits/{remittance_id}/link")
    
    print("\n" + "=" * 70)


def main():
    """Main script to check historical data availability."""
    parser = argparse.ArgumentParser(description="Check available historical data for ML training")
    parser.add_argument(
        "--show-sources",
        action="store_true",
        help="Show information about data sources",
    )

    args = parser.parse_args()

    # Get database session
    db = next(get_db())

    try:
        # Check data availability
        stats = check_historical_data(db)
        
        # Show data sources if requested
        if args.show_sources:
            print_data_sources()
        
        # Provide recommendations
        print("\n--- RECOMMENDATIONS ---")
        if not stats["ready_for_training"]:
            print("❌ You need more historical data to train ML models.")
            print("\nNext steps:")
            print("1. Upload sample files from samples/ directory")
            print("2. Import historical EDI files from your system")
            print("3. Ensure both 837 (claims) and 835 (remittances) are uploaded")
            print("4. Episodes will be automatically linked when remittances are processed")
            print("\nRun with --show-sources for more information about data sources.")
        else:
            print("✅ You have sufficient data to train ML models!")
            print(f"\nYou can now:")
            print("1. Run: python ml/training/prepare_data.py")
            print("2. Run: python ml/training/train_models.py")
            print("3. Run: python ml/training/tune_hyperparameters.py")
        
        logger.info("Historical data check completed", **stats)

    except Exception as e:
        logger.error("Historical data check failed", error=str(e))
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

