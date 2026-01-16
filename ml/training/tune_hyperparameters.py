"""Hyperparameter tuning for risk prediction models."""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config.database import get_db
from ml.services.data_collector import DataCollector
from ml.models.risk_predictor import RiskPredictor
from ml.training.train_models import prepare_features_and_labels
from app.utils.logger import get_logger

logger = get_logger(__name__)


def tune_random_forest(
    X_train: np.ndarray,
    y_train: np.ndarray,
    n_iter: int = 20,
    cv: int = 5,
    n_jobs: int = -1,
    random_state: int = 42,
) -> Dict:
    """
    Tune Random Forest hyperparameters using randomized search.
    
    Args:
        X_train: Training features
        y_train: Training labels
        n_iter: Number of iterations for randomized search
        cv: Number of CV folds
        n_jobs: Number of parallel jobs
        random_state: Random seed
        
    Returns:
        Dictionary with best parameters and best score
    """
    logger.info("Tuning Random Forest hyperparameters", n_iter=n_iter, cv=cv)

    # Parameter grid for Random Forest
    param_distributions = {
        "regressor__n_estimators": [50, 100, 200, 300, 500],
        "regressor__max_depth": [None, 10, 20, 30, 50],
        "regressor__min_samples_split": [2, 5, 10],
        "regressor__min_samples_leaf": [1, 2, 4],
        "regressor__max_features": ["sqrt", "log2", None],
    }

    # Create pipeline
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("regressor", RandomForestRegressor(random_state=random_state, n_jobs=n_jobs)),
        ]
    )

    # Randomized search
    search = RandomizedSearchCV(
        pipeline,
        param_distributions,
        n_iter=n_iter,
        cv=cv,
        scoring="neg_mean_squared_error",
        n_jobs=n_jobs,
        random_state=random_state,
        verbose=1,
    )

    search.fit(X_train, y_train)

    best_params = search.best_params_
    best_score = -search.best_score_  # Convert to positive RMSE

    logger.info(
        "Random Forest tuning complete",
        best_params=best_params,
        best_score=best_score,
    )

    return {
        "best_params": best_params,
        "best_score": float(best_score),
        "best_estimator": search.best_estimator_,
    }


def tune_gradient_boosting(
    X_train: np.ndarray,
    y_train: np.ndarray,
    n_iter: int = 20,
    cv: int = 5,
    random_state: int = 42,
) -> Dict:
    """
    Tune Gradient Boosting hyperparameters using randomized search.
    
    Args:
        X_train: Training features
        y_train: Training labels
        n_iter: Number of iterations for randomized search
        cv: Number of CV folds
        random_state: Random seed
        
    Returns:
        Dictionary with best parameters and best score
    """
    logger.info("Tuning Gradient Boosting hyperparameters", n_iter=n_iter, cv=cv)

    # Parameter grid for Gradient Boosting
    param_distributions = {
        "regressor__n_estimators": [50, 100, 200, 300],
        "regressor__max_depth": [3, 5, 7, 10],
        "regressor__learning_rate": [0.01, 0.05, 0.1, 0.2],
        "regressor__min_samples_split": [2, 5, 10],
        "regressor__min_samples_leaf": [1, 2, 4],
        "regressor__subsample": [0.8, 0.9, 1.0],
    }

    # Create pipeline
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("regressor", GradientBoostingRegressor(random_state=random_state)),
        ]
    )

    # Randomized search
    search = RandomizedSearchCV(
        pipeline,
        param_distributions,
        n_iter=n_iter,
        cv=cv,
        scoring="neg_mean_squared_error",
        random_state=random_state,
        verbose=1,
    )

    search.fit(X_train, y_train)

    best_params = search.best_params_
    best_score = -search.best_score_  # Convert to positive RMSE

    logger.info(
        "Gradient Boosting tuning complete",
        best_params=best_params,
        best_score=best_score,
    )

    return {
        "best_params": best_params,
        "best_score": float(best_score),
        "best_estimator": search.best_estimator_,
    }


def main():
    """Main hyperparameter tuning script."""
    parser = argparse.ArgumentParser(description="Tune hyperparameters for risk prediction model")
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
        help="Type of model to tune",
    )
    parser.add_argument(
        "--n-iter",
        type=int,
        default=20,
        help="Number of iterations for randomized search",
    )
    parser.add_argument(
        "--cv",
        type=int,
        default=5,
        help="Number of CV folds",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="ml/models/saved",
        help="Directory to save tuned model",
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
        # Collect training data
        logger.info("Collecting training data")
        collector = DataCollector(db)
        df = collector.collect_training_data(
            start_date=start_date, end_date=end_date, include_historical=True
        )

        logger.info("Training data collected", rows=len(df), columns=len(df.columns))

        # Prepare features and labels
        X, y, feature_names = prepare_features_and_labels(df)

        logger.info(
            "Features and labels prepared",
            n_samples=X.shape[0],
            n_features=X.shape[1],
        )

        # Tune hyperparameters
        if args.model_type == "random_forest":
            results = tune_random_forest(
                X, y, n_iter=args.n_iter, cv=args.cv, random_state=args.random_state
            )
        else:
            results = tune_gradient_boosting(
                X, y, n_iter=args.n_iter, cv=args.cv, random_state=args.random_state
            )

        # Print results
        print("\n" + "=" * 70)
        print(f"HYPERPARAMETER TUNING RESULTS: {args.model_type.upper()}")
        print("=" * 70)
        print(f"\nBest CV Score (RMSE): {results['best_score']:.4f}")
        print("\nBest Parameters:")
        for param, value in results["best_params"].items():
            print(f"  {param}: {value}")

        # Save tuned model
        output_path = Path(args.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_filename = f"risk_predictor_{args.model_type}_tuned_{timestamp}.pkl"
        model_path = output_path / model_filename

        # Create RiskPredictor with tuned model
        tuned_model = RiskPredictor()
        tuned_model.model = results["best_estimator"]
        tuned_model.feature_names = feature_names
        tuned_model.is_trained = True

        tuned_model.save_model(str(model_path), feature_names=feature_names)

        print("\n" + "=" * 70)
        print(f"Tuned model saved to: {model_path}")
        print("=" * 70)

        logger.info("Hyperparameter tuning completed successfully", model_path=str(model_path))

    except Exception as e:
        logger.error("Hyperparameter tuning failed", error=str(e))
        raise


if __name__ == "__main__":
    main()

