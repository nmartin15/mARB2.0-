"""Risk prediction model using scikit-learn."""
from typing import Optional, Dict, Tuple
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from app.utils.logger import get_logger

logger = get_logger(__name__)


class RiskPredictor:
    """
    ML model for predicting claim denial risk.
    
    Attributes:
        model: Scikit-learn Pipeline containing StandardScaler and regressor (RandomForest or GradientBoosting)
        model_path: Path to the saved model file (if loaded from disk)
        feature_names: List of feature names used during training (for feature importance analysis)
        model_version: Version string of the model (default: "1.0")
        is_trained: Boolean indicating whether the model has been trained or loaded
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize risk predictor.
        
        Args:
            model_path: Path to saved model file (optional)
        """
        self.model: Optional[Pipeline] = None
        self.model_path = model_path
        self.feature_names: Optional[list] = None
        self.model_version = "1.0"
        self.is_trained = False

        if model_path and Path(model_path).exists():
            self.load_model(model_path)

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        model_type: str = "random_forest",
        n_estimators: int = 100,
        max_depth: Optional[int] = None,
        random_state: int = 42,
    ) -> Dict[str, float]:
        """
        Train the risk prediction model.
        
        Args:
            X_train: Training features (n_samples, n_features)
            y_train: Training labels (denial rate: 0.0 to 1.0)
            model_type: Type of model ('random_forest' or 'gradient_boosting')
            n_estimators: Number of trees
            max_depth: Maximum depth of trees
            random_state: Random seed for reproducibility
            
        Returns:
            Dictionary with training metrics
        """
        logger.info(
            "Training risk prediction model",
            model_type=model_type,
            n_samples=X_train.shape[0],
            n_features=X_train.shape[1],
        )

        # Select model
        if model_type == "random_forest":
            regressor = RandomForestRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=random_state,
                n_jobs=-1,
            )
        elif model_type == "gradient_boosting":
            regressor = GradientBoostingRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=random_state,
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        # Create pipeline with scaling
        self.model = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("regressor", regressor),
            ]
        )

        # Train model
        self.model.fit(X_train, y_train)

        # Evaluate with cross-validation
        cv_scores = cross_val_score(
            self.model, X_train, y_train, cv=5, scoring="neg_mean_squared_error"
        )
        mse_scores = -cv_scores
        rmse_scores = np.sqrt(mse_scores)

        # Calculate R² score
        train_score = self.model.score(X_train, y_train)

        metrics = {
            "train_r2": float(train_score),
            "cv_rmse_mean": float(np.mean(rmse_scores)),
            "cv_rmse_std": float(np.std(rmse_scores)),
            "cv_rmse_min": float(np.min(rmse_scores)),
            "cv_rmse_max": float(np.max(rmse_scores)),
        }

        self.is_trained = True

        logger.info("Model training complete", **metrics)

        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict denial risk for claims.
        
        Args:
            X: Feature array (n_samples, n_features)
            
        Returns:
            Predicted denial rates (0.0 to 1.0)
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained. Call train() first or load a saved model.")

        predictions = self.model.predict(X)

        # Ensure predictions are in [0, 1] range
        predictions = np.clip(predictions, 0.0, 1.0)

        return predictions

    def predict_single(self, features: np.ndarray) -> float:
        """
        Predict denial risk for a single claim.
        
        Args:
            features: Feature array (n_features,)
            
        Returns:
            Predicted denial rate (0.0 to 1.0)
        """
        # Reshape for single sample
        if features.ndim == 1:
            features = features.reshape(1, -1)

        predictions = self.predict(features)
        return float(predictions[0])

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """
        Evaluate model on test data.
        
        Args:
            X_test: Test features
            y_test: Test labels
            
        Returns:
            Dictionary with evaluation metrics
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained. Call train() first or load a saved model.")

        predictions = self.predict(X_test)

        # Calculate metrics
        mse = np.mean((predictions - y_test) ** 2)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(predictions - y_test))
        r2 = self.model.score(X_test, y_test)

        # Calculate accuracy for binary classification (threshold at 0.5)
        binary_predictions = (predictions >= 0.5).astype(int)
        binary_labels = (y_test >= 0.5).astype(int)
        accuracy = np.mean(binary_predictions == binary_labels)

        metrics = {
            "test_r2": float(r2),
            "test_rmse": float(rmse),
            "test_mae": float(mae),
            "test_accuracy": float(accuracy),
        }

        logger.info("Model evaluation complete", **metrics)

        return metrics

    def save_model(self, model_path: str, feature_names: Optional[list] = None):
        """
        Save trained model to disk.
        
        Args:
            model_path: Path to save model
            feature_names: Optional list of feature names
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained. Cannot save untrained model.")

        # Create directory if it doesn't exist
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)

        # Save model
        model_data = {
            "model": self.model,
            "model_version": self.model_version,
            "feature_names": feature_names or self.feature_names,
            "is_trained": self.is_trained,
        }

        joblib.dump(model_data, model_path)
        self.model_path = model_path

        logger.info("Model saved", model_path=model_path)

    def load_model(self, model_path: str):
        """
        Load trained model from disk.
        
        Args:
            model_path: Path to saved model
        """
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        model_data = joblib.load(model_path)

        self.model = model_data["model"]
        self.model_version = model_data.get("model_version", "1.0")
        self.feature_names = model_data.get("feature_names")
        self.is_trained = model_data.get("is_trained", True)
        self.model_path = model_path

        logger.info("Model loaded", model_path=model_path, version=self.model_version)

    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """
        Get feature importance from trained model.
        
        Returns:
            Dictionary mapping feature names to importance scores
        """
        if not self.is_trained or self.model is None:
            return None

        # Get regressor from pipeline
        regressor = self.model.named_steps["regressor"]

        if not hasattr(regressor, "feature_importances_"):
            return None

        importances = regressor.feature_importances_

        if self.feature_names:
            return dict(zip(self.feature_names, importances.tolist()))
        else:
            return {f"feature_{i}": float(imp) for i, imp in enumerate(importances)}
