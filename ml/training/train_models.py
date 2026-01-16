"""Model training script for risk prediction."""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config.database import get_db
from ml.services.data_collector import DataCollector
from ml.models.risk_predictor import RiskPredictor
from app.utils.logger import get_logger

logger = get_logger(__name__)


def prepare_features_and_labels(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """
    Prepare features and labels from training dataframe.
    
    Args:
        df: Training dataframe with features and labels
        
    Returns:
        Tuple of (features, labels) as numpy arrays
    """
    # Feature columns (exclude labels and IDs)
    exclude_cols = [
        "claim_id",
        "denial_rate",
        "payment_rate",
        "is_denied",
        "denial_count",
        "adjustment_count",
        "payment_amount",
    ]

    feature_cols = [col for col in df.columns if col not in exclude_cols]

    # Handle categorical columns (one-hot encode)
    categorical_cols = ["facility_type_code"]
    df_encoded = pd.get_dummies(df, columns=categorical_cols, prefix=categorical_cols)

    # Update feature columns after encoding
    feature_cols = [col for col in df_encoded.columns if col not in exclude_cols]

    # Extract features and labels
    X = df_encoded[feature_cols].values.astype(np.float32)
    y = df_encoded["denial_rate"].values.astype(np.float32)  # Use denial_rate as target

    # Handle NaN values
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    y = np.nan_to_num(y, nan=0.0, posinf=1.0, neginf=0.0)

    logger.info(
        "Features and labels prepared",
        n_samples=X.shape[0],
        n_features=X.shape[1],
        feature_names=feature_cols,
    )

    return X, y, feature_cols


def train_model(
    db_session,
    start_date: datetime = None,
    end_date: datetime = None,
    model_type: str = "random_forest",
    n_estimators: int = 100,
    max_depth: int = None,
    test_size: float = 0.2,
    random_state: int = 42,
    output_dir: str = "ml/models/saved",
) -> RiskPredictor:
    """
    Train risk prediction model.
    
    Args:
        db_session: Database session
        start_date: Start date for training data
        end_date: End date for training data
        model_type: Type of model ('random_forest' or 'gradient_boosting')
        n_estimators: Number of trees
        max_depth: Maximum depth of trees
        test_size: Proportion of data for testing
        random_state: Random seed
        output_dir: Directory to save trained model
        
    Returns:
        Trained RiskPredictor model
    """
    logger.info("Starting model training", model_type=model_type)

    # Collect training data
    collector = DataCollector(db_session)
    df = collector.collect_training_data(start_date=start_date, end_date=end_date)

    logger.info("Training data collected", rows=len(df), columns=len(df.columns))

    # Prepare features and labels
    X, y, feature_names = prepare_features_and_labels(df)

    # Split into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=None
    )

    logger.info(
        "Data split",
        train_samples=X_train.shape[0],
        test_samples=X_test.shape[0],
    )

    # Train model
    model = RiskPredictor()
    model.feature_names = feature_names

    training_metrics = model.train(
        X_train,
        y_train,
        model_type=model_type,
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=random_state,
    )

    # Evaluate on test set
    test_metrics = model.evaluate(X_test, y_test)

    # Comprehensive evaluation
    from ml.training.evaluate_models import evaluate_model_comprehensive, print_evaluation_report

    comprehensive_metrics = evaluate_model_comprehensive(model, X_test, y_test, feature_names)

    # Print metrics
    print("\n" + "=" * 70)
    print("TRAINING METRICS (Cross-Validation)")
    print("=" * 70)
    for key, value in training_metrics.items():
        print(f"{key:25s}: {value:.4f}")

    # Print comprehensive evaluation report
    print_evaluation_report(comprehensive_metrics, model_name=f"{model_type.upper()} Model")

    # Feature importance
    feature_importance = model.get_feature_importance()
    if feature_importance:
        print("\n" + "=" * 60)
        print("TOP 10 FEATURE IMPORTANCE")
        print("=" * 60)
        sorted_features = sorted(
            feature_importance.items(), key=lambda x: x[1], reverse=True
        )[:10]
        for feature, importance in sorted_features:
            print(f"{feature}: {importance:.4f}")

    # Save model
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_filename = f"risk_predictor_{model_type}_{timestamp}.pkl"
    model_path = output_path / model_filename

    model.save_model(str(model_path), feature_names=feature_names)

    print("\n" + "=" * 60)
    print(f"Model saved to: {model_path}")
    print("=" * 60)

    return model


def main():
    """Main training script."""
    parser = argparse.ArgumentParser(description="Train risk prediction model")
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for training data (YYYY-MM-DD)",
        default=None,
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date for training data (YYYY-MM-DD)",
        default=None,
    )
    parser.add_argument(
        "--model-type",
        type=str,
        choices=["random_forest", "gradient_boosting"],
        default="random_forest",
        help="Type of model to train",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of trees/estimators",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Maximum depth of trees",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proportion of data for testing",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="ml/models/saved",
        help="Directory to save trained model",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )

    args = parser.parse_args()

    # Parse dates
    start_date = None
    end_date = None

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    else:
        start_date = datetime.now() - timedelta(days=180)

    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        end_date = datetime.now()

    # Get database session
    db = next(get_db())

    try:
        # Train model
        model = train_model(
            db_session=db,
            start_date=start_date,
            end_date=end_date,
            model_type=args.model_type,
            n_estimators=args.n_estimators,
            max_depth=args.max_depth,
            test_size=args.test_size,
            random_state=args.random_state,
            output_dir=args.output_dir,
        )

        logger.info("Model training completed successfully")

    except Exception as e:
        logger.error("Model training failed", error=str(e))
        raise


if __name__ == "__main__":
    main()
