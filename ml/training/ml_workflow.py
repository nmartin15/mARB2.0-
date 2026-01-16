"""
Comprehensive ML workflow script.

This script provides a unified interface for all ML operations:
- Check data availability
- Collect and prepare training data
- Train models
- Evaluate models
- Run pattern detection
- Generate reports

Usage:
    python ml/training/ml_workflow.py check                    # Check data availability
    python ml/training/ml_workflow.py prepare                  # Prepare training data
    python ml/training/ml_workflow.py train                    # Train model
    python ml/training/ml_workflow.py evaluate                 # Evaluate model
    python ml/training/ml_workflow.py patterns                 # Run pattern detection
    python ml/training/ml_workflow.py full                     # Run full pipeline
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config.database import get_db
from ml.training.check_historical_data import check_historical_data, print_data_sources
from ml.training.prepare_data import main as prepare_data_main
from ml.training.train_models import train_model
from ml.training.evaluate_models import main as evaluate_models_main
from ml.training.run_pattern_detection import run_pattern_detection_for_all_payers, print_pattern_summary
from ml.training.continuous_learning_pipeline import ContinuousLearningPipeline
from app.utils.logger import get_logger

logger = get_logger(__name__)


def cmd_check(args):
    """Check data availability."""
    db = next(get_db())
    try:
        stats = check_historical_data(db)
        if args.show_sources:
            print_data_sources()
    finally:
        db.close()


def cmd_prepare(args):
    """Prepare training data."""
    # Import and run prepare_data script
    sys.argv = ["prepare_data.py"] + (args.extra_args or [])
    prepare_data_main()


def cmd_train(args):
    """Train model."""
    db = next(get_db())
    try:
        # Parse dates
        start_date = (
            datetime.fromisoformat(args.start_date)
            if args.start_date
            else datetime.now() - timedelta(days=180)
        )
        end_date = (
            datetime.fromisoformat(args.end_date)
            if args.end_date
            else datetime.now()
        )
        
        train_model(
            db_session=db,
            start_date=start_date,
            end_date=end_date,
            model_type=args.model_type,
            n_estimators=args.n_estimators,
            max_depth=args.max_depth,
            output_dir=args.output_dir,
        )
    finally:
        db.close()


def cmd_evaluate(args):
    """Evaluate model."""
    sys.argv = ["evaluate_models.py"] + (args.extra_args or [])
    evaluate_models_main()


def cmd_patterns(args):
    """Run pattern detection."""
    db = next(get_db())
    try:
        results = run_pattern_detection_for_all_payers(
            db_session=db,
            days_back=args.days_back,
            min_frequency=args.min_frequency,
        )
        print_pattern_summary(results)
    finally:
        db.close()


def cmd_full(args):
    """Run full continuous learning pipeline."""
    db = next(get_db())
    try:
        # Parse dates
        start_date = (
            datetime.fromisoformat(args.start_date)
            if args.start_date
            else datetime.now() - timedelta(days=180)
        )
        end_date = (
            datetime.fromisoformat(args.end_date)
            if args.end_date
            else datetime.now()
        )
        
        pipeline = ContinuousLearningPipeline(db)
        results = pipeline.run_full_pipeline(
            start_date=start_date,
            end_date=end_date,
            model_type=args.model_type,
            n_estimators=args.n_estimators,
            days_back=args.days_back,
            output_dir=args.output_dir,
            run_pattern_detection=not args.skip_patterns,
            min_episodes=args.min_episodes,
        )
        
        # Print summary
        print("\n" + "=" * 70)
        print("WORKFLOW COMPLETED")
        print("=" * 70)
        print(f"Steps Completed: {len(results['steps_completed'])}")
        for step in results["steps_completed"]:
            print(f"  ✓ {step}")
        
        if results["errors"]:
            print(f"\nErrors: {len(results['errors'])}")
            for error in results["errors"]:
                print(f"  ✗ {error}")
        
        if "model_metrics" in results:
            print("\nModel Metrics:")
            for key, value in results["model_metrics"].items():
                print(f"  {key}: {value:.4f}")
        
        print("=" * 70)
        
        if results["errors"]:
            sys.exit(1)
    finally:
        db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Comprehensive ML workflow script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check data availability
  python ml/training/ml_workflow.py check
  
  # Prepare training data
  python ml/training/ml_workflow.py prepare --start-date 2024-01-01
  
  # Train model
  python ml/training/ml_workflow.py train --model-type random_forest
  
  # Run pattern detection
  python ml/training/ml_workflow.py patterns --days-back 90
  
  # Run full pipeline
  python ml/training/ml_workflow.py full
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Check command
    check_parser = subparsers.add_parser("check", help="Check data availability")
    check_parser.add_argument(
        "--show-sources",
        action="store_true",
        help="Show information about data sources",
    )
    check_parser.set_defaults(func=cmd_check)
    
    # Prepare command
    prepare_parser = subparsers.add_parser("prepare", help="Prepare training data")
    prepare_parser.add_argument(
        "extra_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments passed to prepare_data.py",
    )
    prepare_parser.set_defaults(func=cmd_prepare)
    
    # Train command
    train_parser = subparsers.add_parser("train", help="Train model")
    train_parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD, default: 6 months ago)",
    )
    train_parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD, default: today)",
    )
    train_parser.add_argument(
        "--model-type",
        choices=["random_forest", "gradient_boosting"],
        default="random_forest",
        help="Model type",
    )
    train_parser.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of trees",
    )
    train_parser.add_argument(
        "--max-depth",
        type=int,
        help="Maximum tree depth",
    )
    train_parser.add_argument(
        "--output-dir",
        type=str,
        default="ml/models/saved",
        help="Output directory",
    )
    train_parser.set_defaults(func=cmd_train)
    
    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate model")
    eval_parser.add_argument(
        "extra_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments passed to evaluate_models.py",
    )
    eval_parser.set_defaults(func=cmd_evaluate)
    
    # Patterns command
    patterns_parser = subparsers.add_parser("patterns", help="Run pattern detection")
    patterns_parser.add_argument(
        "--days-back",
        type=int,
        default=90,
        help="Days to look back",
    )
    patterns_parser.add_argument(
        "--min-frequency",
        type=float,
        default=0.05,
        help="Minimum frequency threshold",
    )
    patterns_parser.set_defaults(func=cmd_patterns)
    
    # Full command
    full_parser = subparsers.add_parser("full", help="Run full pipeline")
    full_parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD, default: 6 months ago)",
    )
    full_parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD, default: today)",
    )
    full_parser.add_argument(
        "--model-type",
        choices=["random_forest", "gradient_boosting"],
        default="random_forest",
        help="Model type",
    )
    full_parser.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of trees",
    )
    full_parser.add_argument(
        "--days-back",
        type=int,
        default=90,
        help="Days to look back for pattern detection",
    )
    full_parser.add_argument(
        "--output-dir",
        type=str,
        default="ml/models/saved",
        help="Output directory",
    )
    full_parser.add_argument(
        "--skip-patterns",
        action="store_true",
        help="Skip pattern detection",
    )
    full_parser.add_argument(
        "--min-episodes",
        type=int,
        default=100,
        help="Minimum episodes required",
    )
    full_parser.set_defaults(func=cmd_full)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()

