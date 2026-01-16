"""Model evaluation and comparison utilities."""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from sklearn.model_selection import (
    cross_val_score,
    StratifiedKFold,
    KFold,
    learning_curve,
)
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config.database import get_db
from ml.services.data_collector import DataCollector
from ml.models.risk_predictor import RiskPredictor
from ml.training.train_models import prepare_features_and_labels
from app.utils.logger import get_logger

logger = get_logger(__name__)


def evaluate_model_comprehensive(
    model: RiskPredictor,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: Optional[List[str]] = None,
) -> Dict:
    """
    Comprehensive model evaluation with multiple metrics.
    
    Args:
        model: Trained RiskPredictor model
        X_test: Test features
        y_test: Test labels
        feature_names: Optional feature names for reporting
        
    Returns:
        Dictionary with comprehensive evaluation metrics
    """
    # Predictions
    y_pred = model.predict(X_test)
    
    # Regression metrics
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    # Binary classification metrics (using 0.5 threshold)
    y_pred_binary = (y_pred >= 0.5).astype(int)
    y_test_binary = (y_test >= 0.5).astype(int)
    
    accuracy = accuracy_score(y_test_binary, y_pred_binary)
    precision = precision_score(y_test_binary, y_pred_binary, zero_division=0)
    recall = recall_score(y_test_binary, y_pred_binary, zero_division=0)
    f1 = f1_score(y_test_binary, y_pred_binary, zero_division=0)
    
    # ROC AUC (if we have both classes)
    try:
        if len(np.unique(y_test_binary)) > 1:
            roc_auc = roc_auc_score(y_test_binary, y_pred)
        else:
            roc_auc = 0.0
    except Exception:
        roc_auc = 0.0
    
    # Confusion matrix
    cm = confusion_matrix(y_test_binary, y_pred_binary)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    
    # Percentile-based metrics (for risk scoring)
    percentile_errors = {}
    for percentile in [10, 25, 50, 75, 90, 95]:
        threshold = np.percentile(y_test, percentile)
        mask = y_test >= threshold
        if mask.sum() > 0:
            percentile_errors[f"mae_p{percentile}"] = mean_absolute_error(
                y_test[mask], y_pred[mask]
            )
    
    metrics = {
        # Regression metrics
        "test_r2": float(r2),
        "test_rmse": float(rmse),
        "test_mae": float(mae),
        "test_mse": float(mse),
        # Classification metrics
        "test_accuracy": float(accuracy),
        "test_precision": float(precision),
        "test_recall": float(recall),
        "test_f1": float(f1),
        "test_roc_auc": float(roc_auc),
        # Confusion matrix
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
        # Additional metrics
        "mean_prediction": float(np.mean(y_pred)),
        "mean_actual": float(np.mean(y_test)),
        "std_prediction": float(np.std(y_pred)),
        "std_actual": float(np.std(y_test)),
    }
    
    # Add percentile errors
    metrics.update(percentile_errors)
    
    return metrics


def cross_validate_model(
    model: RiskPredictor,
    X: np.ndarray,
    y: np.ndarray,
    cv_folds: int = 5,
    scoring: str = "neg_mean_squared_error",
) -> Dict:
    """
    Perform cross-validation on model.
    
    Args:
        model: RiskPredictor model (not yet trained)
        X: Features
        y: Labels
        cv_folds: Number of CV folds
        scoring: Scoring metric
        
    Returns:
        Dictionary with CV results
    """
    # Use KFold for regression
    cv = KFold(n_splits=cv_folds, shuffle=True, random_state=42)
    
    # Get the underlying sklearn model
    if model.model is None:
        raise ValueError("Model must be trained before cross-validation")
    
    scores = cross_val_score(model.model, X, y, cv=cv, scoring=scoring, n_jobs=-1)
    
    if scoring.startswith("neg_"):
        scores = -scores  # Convert to positive
    
    return {
        "cv_mean": float(np.mean(scores)),
        "cv_std": float(np.std(scores)),
        "cv_min": float(np.min(scores)),
        "cv_max": float(np.max(scores)),
        "cv_scores": scores.tolist(),
    }


def compare_models(
    models: Dict[str, RiskPredictor],
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> pd.DataFrame:
    """
    Compare multiple models and return comparison DataFrame.
    
    Args:
        models: Dictionary mapping model names to RiskPredictor instances
        X_test: Test features
        y_test: Test labels
        
    Returns:
        DataFrame with comparison metrics
    """
    results = []
    
    for name, model in models.items():
        metrics = evaluate_model_comprehensive(model, X_test, y_test)
        metrics["model_name"] = name
        results.append(metrics)
    
    df = pd.DataFrame(results)
    df = df.set_index("model_name")
    
    return df


def print_evaluation_report(metrics: Dict, model_name: str = "Model"):
    """Print formatted evaluation report."""
    print("\n" + "=" * 70)
    print(f"EVALUATION REPORT: {model_name}")
    print("=" * 70)
    
    print("\n--- Regression Metrics ---")
    print(f"R² Score:        {metrics['test_r2']:.4f}")
    print(f"RMSE:             {metrics['test_rmse']:.4f}")
    print(f"MAE:              {metrics['test_mae']:.4f}")
    print(f"MSE:              {metrics['test_mse']:.4f}")
    
    print("\n--- Classification Metrics (threshold=0.5) ---")
    print(f"Accuracy:         {metrics['test_accuracy']:.4f}")
    print(f"Precision:        {metrics['test_precision']:.4f}")
    print(f"Recall:           {metrics['test_recall']:.4f}")
    print(f"F1 Score:         {metrics['test_f1']:.4f}")
    print(f"ROC AUC:          {metrics['test_roc_auc']:.4f}")
    
    print("\n--- Confusion Matrix ---")
    print(f"True Negatives:   {metrics['true_negatives']}")
    print(f"False Positives:  {metrics['false_positives']}")
    print(f"False Negatives:  {metrics['false_negatives']}")
    print(f"True Positives:   {metrics['true_positives']}")
    
    print("\n--- Prediction Statistics ---")
    print(f"Mean Prediction:  {metrics['mean_prediction']:.4f}")
    print(f"Mean Actual:      {metrics['mean_actual']:.4f}")
    print(f"Std Prediction:   {metrics['std_prediction']:.4f}")
    print(f"Std Actual:       {metrics['std_actual']:.4f}")
    
    print("=" * 70)


def main():
    """Main evaluation script."""
    parser = argparse.ArgumentParser(description="Evaluate trained ML model")
    parser.add_argument(
        "--model-path",
        type=str,
        required=True,
        help="Path to trained model file",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for test data (YYYY-MM-DD)",
        default=None,
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date for test data (YYYY-MM-DD)",
        default=None,
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proportion of data for testing",
    )
    parser.add_argument(
        "--cv-folds",
        type=int,
        default=5,
        help="Number of cross-validation folds",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for evaluation report (CSV)",
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
        # Load model
        logger.info("Loading model", model_path=args.model_path)
        model = RiskPredictor(model_path=args.model_path)

        # Collect data
        collector = DataCollector(db)
        df = collector.collect_training_data(
            start_date=start_date, end_date=end_date, include_historical=True
        )

        logger.info("Data collected", rows=len(df), columns=len(df.columns))

        # Prepare features and labels
        X, y, feature_names = prepare_features_and_labels(df)

        # Split data (use same random state as training)
        from sklearn.model_selection import train_test_split

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=args.test_size, random_state=42
        )

        logger.info(
            "Data split",
            train_samples=X_train.shape[0],
            test_samples=X_test.shape[0],
        )

        # Evaluate on test set
        logger.info("Evaluating model on test set")
        metrics = evaluate_model_comprehensive(model, X_test, y_test, feature_names)

        # Print report
        print_evaluation_report(metrics, model_name=Path(args.model_path).stem)

        # Feature importance
        feature_importance = model.get_feature_importance()
        if feature_importance:
            print("\n" + "=" * 70)
            print("TOP 15 FEATURE IMPORTANCE")
            print("=" * 70)
            sorted_features = sorted(
                feature_importance.items(), key=lambda x: x[1], reverse=True
            )[:15]
            for i, (feature, importance) in enumerate(sorted_features, 1):
                print(f"{i:2d}. {feature:40s} {importance:.4f}")

        # Save report if requested
        if args.output:
            report_df = pd.DataFrame([metrics])
            report_df.to_csv(args.output, index=False)
            logger.info("Evaluation report saved", output_file=args.output)

        logger.info("Model evaluation completed successfully")

    except Exception as e:
        logger.error("Model evaluation failed", error=str(e))
        raise


if __name__ == "__main__":
    main()

