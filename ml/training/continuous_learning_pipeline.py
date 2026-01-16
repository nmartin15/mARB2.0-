"""
Continuous learning pipeline for automated model retraining and pattern detection.

This script automates the ML model development workflow:
1. Collects historical data
2. Trains/retrains models
3. Evaluates model performance
4. Runs pattern detection on historical data
5. Generates reports

Can be run manually or scheduled via cron/Celery.
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config.database import get_db
from ml.services.data_collector import DataCollector
from ml.models.risk_predictor import RiskPredictor
from ml.training.train_models import train_model, prepare_features_and_labels
from ml.training.evaluate_models import evaluate_model_comprehensive, print_evaluation_report
from app.services.learning.pattern_detector import PatternDetector
from app.models.database import Payer
from app.utils.logger import get_logger
import pandas as pd

logger = get_logger(__name__)


class ContinuousLearningPipeline:
    """Automated pipeline for continuous model learning and pattern detection."""

    def __init__(self, db_session):
        self.db = db_session
        self.data_collector = DataCollector(db_session)
        self.pattern_detector = PatternDetector(db_session)

    def run_full_pipeline(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        model_type: str = "random_forest",
        n_estimators: int = 100,
        days_back: int = 90,
        output_dir: str = "ml/models/saved",
        run_pattern_detection: bool = True,
        min_episodes: int = 100,
    ) -> Dict:
        """
        Run the complete continuous learning pipeline.
        
        Args:
            start_date: Start date for training data (default: 6 months ago)
            end_date: End date for training data (default: today)
            model_type: Type of model to train ('random_forest' or 'gradient_boosting')
            n_estimators: Number of trees for ensemble models
            days_back: Days to look back for pattern detection
            output_dir: Directory to save trained models
            run_pattern_detection: Whether to run pattern detection
            min_episodes: Minimum episodes required for training
            
        Returns:
            Dictionary with pipeline results and metrics
        """
        results = {
            "started_at": datetime.now().isoformat(),
            "steps_completed": [],
            "errors": [],
            "metrics": {},
        }

        logger.info("Starting continuous learning pipeline")

        # Step 1: Check data availability
        try:
            logger.info("Step 1: Checking data availability")
            data_stats = self._check_data_availability(start_date, end_date, min_episodes)
            results["data_stats"] = data_stats
            
            if not data_stats["ready_for_training"]:
                error_msg = f"Insufficient data: {data_stats['episodes_with_outcomes']} episodes, need {min_episodes}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
                return results
            
            results["steps_completed"].append("data_check")
            logger.info("Data availability check passed", **data_stats)
        except Exception as e:
            error_msg = f"Data check failed: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)
            return results

        # Step 2: Collect and prepare training data
        try:
            logger.info("Step 2: Collecting training data")
            df = self.data_collector.collect_training_data(
                start_date=start_date,
                end_date=end_date,
                min_episodes=min_episodes,
                include_historical=True,
            )
            results["training_data_rows"] = len(df)
            results["training_data_columns"] = len(df.columns)
            results["steps_completed"].append("data_collection")
            logger.info("Training data collected", rows=len(df))
        except Exception as e:
            error_msg = f"Data collection failed: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)
            return results

        # Step 3: Train model
        try:
            logger.info("Step 3: Training model")
            model = train_model(
                db_session=self.db,
                start_date=start_date,
                end_date=end_date,
                model_type=model_type,
                n_estimators=n_estimators,
                output_dir=output_dir,
            )
            
            # Get training metrics
            X, y, feature_names = prepare_features_and_labels(df)
            from sklearn.model_selection import train_test_split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            comprehensive_metrics = evaluate_model_comprehensive(
                model, X_test, y_test, feature_names
            )
            
            results["model_metrics"] = {
                "r2_score": comprehensive_metrics.get("r2_score", 0.0),
                "rmse": comprehensive_metrics.get("rmse", 0.0),
                "mae": comprehensive_metrics.get("mae", 0.0),
                "accuracy": comprehensive_metrics.get("accuracy", 0.0),
                "f1_score": comprehensive_metrics.get("f1_score", 0.0),
            }
            results["model_path"] = model.model_path if hasattr(model, "model_path") else None
            results["steps_completed"].append("model_training")
            logger.info("Model training completed", **results["model_metrics"])
        except Exception as e:
            error_msg = f"Model training failed: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)
            # Continue to pattern detection even if training fails

        # Step 4: Run pattern detection
        if run_pattern_detection:
            try:
                logger.info("Step 4: Running pattern detection")
                pattern_results = self._run_pattern_detection(days_back)
                results["pattern_detection"] = pattern_results
                results["steps_completed"].append("pattern_detection")
                logger.info("Pattern detection completed", **pattern_results)
            except Exception as e:
                error_msg = f"Pattern detection failed: {str(e)}"
                results["errors"].append(error_msg)
                logger.error(error_msg, exc_info=True)

        results["completed_at"] = datetime.now().isoformat()
        results["duration_seconds"] = (
            datetime.fromisoformat(results["completed_at"])
            - datetime.fromisoformat(results["started_at"])
        ).total_seconds()

        logger.info(
            "Continuous learning pipeline completed",
            steps_completed=len(results["steps_completed"]),
            errors=len(results["errors"]),
            duration_seconds=results["duration_seconds"],
        )

        return results

    def _check_data_availability(
        self, start_date: Optional[datetime], end_date: Optional[datetime], min_episodes: int
    ) -> Dict:
        """Check if sufficient data is available for training."""
        from ml.training.check_historical_data import check_historical_data
        
        stats = check_historical_data(self.db)
        
        # Filter by date range if provided
        if start_date or end_date:
            from app.models.database import ClaimEpisode, Claim, Remittance
            from sqlalchemy import and_
            
            query = (
                self.db.query(ClaimEpisode)
                .join(Claim)
                .join(Remittance)
                .filter(ClaimEpisode.remittance_id.isnot(None))
            )
            
            if start_date:
                query = query.filter(Claim.created_at >= start_date)
            if end_date:
                query = query.filter(Claim.created_at <= end_date)
            
            episodes_in_range = query.count()
            stats["episodes_in_date_range"] = episodes_in_range
            stats["ready_for_training"] = episodes_in_range >= min_episodes
        else:
            stats["episodes_in_date_range"] = stats["episodes_with_outcomes"]
        
        return stats

    def _run_pattern_detection(self, days_back: int) -> Dict:
        """Run pattern detection for all payers."""
        # Get all payers
        payers = self.db.query(Payer).all()
        
        total_patterns = 0
        payers_processed = 0
        patterns_by_payer = {}
        
        for payer in payers:
            try:
                patterns = self.pattern_detector.detect_patterns_for_payer(
                    payer_id=payer.id,
                    days_back=days_back,
                )
                patterns_by_payer[payer.id] = {
                    "payer_name": payer.name,
                    "pattern_count": len(patterns),
                }
                total_patterns += len(patterns)
                payers_processed += 1
            except Exception as e:
                logger.warning(
                    "Pattern detection failed for payer",
                    payer_id=payer.id,
                    error=str(e),
                )
        
        self.db.commit()
        
        return {
            "total_patterns": total_patterns,
            "payers_processed": payers_processed,
            "total_payers": len(payers),
            "patterns_by_payer": patterns_by_payer,
        }


def main():
    """Main entry point for continuous learning pipeline."""
    parser = argparse.ArgumentParser(
        description="Continuous learning pipeline for ML model training and pattern detection"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for training data (YYYY-MM-DD, default: 6 months ago)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date for training data (YYYY-MM-DD, default: today)",
    )
    parser.add_argument(
        "--model-type",
        choices=["random_forest", "gradient_boosting"],
        default="random_forest",
        help="Type of model to train",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of trees for ensemble models",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=90,
        help="Days to look back for pattern detection",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="ml/models/saved",
        help="Directory to save trained models",
    )
    parser.add_argument(
        "--skip-pattern-detection",
        action="store_true",
        help="Skip pattern detection step",
    )
    parser.add_argument(
        "--min-episodes",
        type=int,
        default=100,
        help="Minimum episodes required for training",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        help="Path to save results as JSON",
    )

    args = parser.parse_args()

    # Parse dates
    if args.start_date:
        start_date = datetime.fromisoformat(args.start_date)
    else:
        start_date = datetime.now() - timedelta(days=180)
    
    if args.end_date:
        end_date = datetime.fromisoformat(args.end_date)
    else:
        end_date = datetime.now()

    # Get database session
    db = next(get_db())

    try:
        # Run pipeline
        pipeline = ContinuousLearningPipeline(db)
        results = pipeline.run_full_pipeline(
            start_date=start_date,
            end_date=end_date,
            model_type=args.model_type,
            n_estimators=args.n_estimators,
            days_back=args.days_back,
            output_dir=args.output_dir,
            run_pattern_detection=not args.skip_pattern_detection,
            min_episodes=args.min_episodes,
        )

        # Print summary
        print("\n" + "=" * 70)
        print("CONTINUOUS LEARNING PIPELINE RESULTS")
        print("=" * 70)
        print(f"Started:     {results['started_at']}")
        print(f"Completed:   {results.get('completed_at', 'N/A')}")
        print(f"Duration:    {results.get('duration_seconds', 0):.1f} seconds")
        print(f"\nSteps Completed: {len(results['steps_completed'])}")
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
        
        if "pattern_detection" in results:
            pd_results = results["pattern_detection"]
            print(f"\nPattern Detection:")
            print(f"  Total Patterns: {pd_results['total_patterns']}")
            print(f"  Payers Processed: {pd_results['payers_processed']}/{pd_results['total_payers']}")

        # Save results to JSON if requested
        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\nResults saved to: {args.output_json}")

        print("=" * 70)

        # Exit with error code if there were errors
        if results["errors"]:
            sys.exit(1)

    except Exception as e:
        logger.error("Pipeline failed", error=str(e), exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

