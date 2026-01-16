"""
Script to run pattern detection on all historical data.

This script analyzes historical claim and remittance data to detect
denial patterns for all payers in the system.
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config.database import get_db
from app.services.learning.pattern_detector import PatternDetector
from app.models.database import Payer, DenialPattern
from app.utils.logger import get_logger

logger = get_logger(__name__)


def run_pattern_detection_for_all_payers(
    db_session, days_back: int = 90, min_frequency: float = 0.05
) -> Dict:
    """
    Run pattern detection for all payers.
    
    Args:
        db_session: Database session
        days_back: Number of days to look back
        min_frequency: Minimum frequency threshold for patterns (default: 5%)
        
    Returns:
        Dictionary with detection results
    """
    detector = PatternDetector(db_session)
    
    # Get all payers
    payers = db_session.query(Payer).all()
    
    results = {
        "total_payers": len(payers),
        "payers_processed": 0,
        "total_patterns": 0,
        "patterns_by_payer": {},
        "errors": [],
    }
    
    print("\n" + "=" * 70)
    print("PATTERN DETECTION FOR ALL PAYERS")
    print("=" * 70)
    print(f"Days Back: {days_back}")
    print(f"Minimum Frequency: {min_frequency * 100:.1f}%")
    print(f"Total Payers: {len(payers)}")
    print("=" * 70 + "\n")
    
    for payer in payers:
        try:
            print(f"Processing payer: {payer.name} (ID: {payer.id})...", end=" ")
            
            patterns = detector.detect_patterns_for_payer(
                payer_id=payer.id,
                days_back=days_back,
            )
            
            # Filter by minimum frequency
            filtered_patterns = [
                p for p in patterns
                if p.frequency >= min_frequency
            ]
            
            results["patterns_by_payer"][payer.id] = {
                "payer_name": payer.name,
                "payer_id": payer.id,
                "total_patterns": len(patterns),
                "filtered_patterns": len(filtered_patterns),
                "patterns": [
                    {
                        "id": p.id,
                        "pattern_type": p.pattern_type,
                        "pattern_description": p.pattern_description,
                        "denial_reason_code": p.denial_reason_code,
                        "frequency": p.frequency,
                        "confidence_score": p.confidence_score,
                        "occurrence_count": p.occurrence_count,
                    }
                    for p in filtered_patterns
                ],
            }
            
            results["total_patterns"] += len(filtered_patterns)
            results["payers_processed"] += 1
            
            print(f"✓ Found {len(filtered_patterns)} patterns")
            
        except Exception as e:
            error_msg = f"Failed for payer {payer.id}: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)
            print(f"✗ Error: {str(e)}")
    
    # Commit all changes
    try:
        db_session.commit()
        print("\n✓ All patterns saved to database")
    except Exception as e:
        logger.error("Failed to commit patterns", error=str(e))
        results["errors"].append(f"Commit failed: {str(e)}")
    
    return results


def print_pattern_summary(results: Dict) -> None:
    """Print summary of detected patterns."""
    print("\n" + "=" * 70)
    print("PATTERN DETECTION SUMMARY")
    print("=" * 70)
    print(f"Total Payers: {results['total_payers']}")
    print(f"Payers Processed: {results['payers_processed']}")
    print(f"Total Patterns Detected: {results['total_patterns']}")
    
    if results["errors"]:
        print(f"\nErrors: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"  - {error}")
    
    # Show top patterns by payer
    print("\n--- Patterns by Payer ---")
    for payer_id, payer_data in results["patterns_by_payer"].items():
        if payer_data["filtered_patterns"] > 0:
            print(f"\n{payer_data['payer_name']} (ID: {payer_id}):")
            print(f"  Total Patterns: {payer_data['filtered_patterns']}")
            
            # Sort by frequency (highest first)
            patterns = sorted(
                payer_data["patterns"],
                key=lambda x: x["frequency"],
                reverse=True,
            )
            
            for i, pattern in enumerate(patterns[:5], 1):  # Show top 5
                print(
                    f"  {i}. {pattern['pattern_description']} "
                    f"(Frequency: {pattern['frequency']*100:.1f}%, "
                    f"Confidence: {pattern['confidence_score']:.2f})"
                )
    
    print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run pattern detection on all historical data"
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=90,
        help="Number of days to look back for pattern detection (default: 90)",
    )
    parser.add_argument(
        "--min-frequency",
        type=float,
        default=0.05,
        help="Minimum frequency threshold for patterns (default: 0.05 = 5%%)",
    )
    parser.add_argument(
        "--payer-id",
        type=int,
        help="Run detection for specific payer only (optional)",
    )

    args = parser.parse_args()

    # Get database session
    db = next(get_db())

    try:
        if args.payer_id:
            # Run for specific payer
            detector = PatternDetector(db)
            payer = db.query(Payer).filter(Payer.id == args.payer_id).first()
            
            if not payer:
                print(f"Error: Payer with ID {args.payer_id} not found")
                sys.exit(1)
            
            print(f"Running pattern detection for payer: {payer.name}")
            patterns = detector.detect_patterns_for_payer(
                payer_id=args.payer_id,
                days_back=args.days_back,
            )
            
            db.commit()
            
            print(f"\n✓ Found {len(patterns)} patterns")
            for pattern in patterns:
                print(
                    f"  - {pattern.pattern_description} "
                    f"(Frequency: {pattern.frequency*100:.1f}%)"
                )
        else:
            # Run for all payers
            results = run_pattern_detection_for_all_payers(
                db_session=db,
                days_back=args.days_back,
                min_frequency=args.min_frequency,
            )
            print_pattern_summary(results)
            
            if results["errors"]:
                sys.exit(1)

    except Exception as e:
        logger.error("Pattern detection failed", error=str(e), exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

