"""Model explainability using SHAP values."""
from typing import Dict, List, Optional
import numpy as np
from pathlib import Path

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Try to import SHAP, but make it optional
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("SHAP not available. Install with: pip install shap")


class ModelExplainer:
    """
    Explain ML model predictions using SHAP values.
    
    Provides feature importance and contribution analysis for individual predictions.
    """

    def __init__(self, model, feature_names: Optional[List[str]] = None):
        """
        Initialize model explainer.
        
        Args:
            model: Trained model (scikit-learn or PyTorch)
            feature_names: Optional list of feature names
        """
        if not SHAP_AVAILABLE:
            raise ImportError(
                "SHAP is required for model explainability. Install with: pip install shap"
            )

        self.model = model
        self.feature_names = feature_names
        self.explainer = None
        self._initialize_explainer()

    def _initialize_explainer(self):
        """Initialize SHAP explainer based on model type."""
        try:
            # Check if it's a scikit-learn model
            if hasattr(self.model, "predict") and hasattr(self.model, "named_steps"):
                # It's a Pipeline
                self.explainer = shap.TreeExplainer(self.model.named_steps["regressor"])
            elif hasattr(self.model, "predict") and hasattr(self.model, "feature_importances_"):
                # It's a tree-based model
                self.explainer = shap.TreeExplainer(self.model)
            elif hasattr(self.model, "predict") and hasattr(self.model, "network"):
                # It's a PyTorch model - use KernelExplainer
                logger.warning("PyTorch models use KernelExplainer (slower). Consider using TreeExplainer for faster explanations.")
                # For PyTorch, we'll need to wrap the predict function
                device = next(self.model.parameters()).device
                def model_predict(X):
                    import torch
                    self.model.eval()
                    with torch.no_grad():
                        X_tensor = torch.FloatTensor(X).to(device)
                        return self.model(X_tensor).cpu().numpy()
                self.explainer = shap.KernelExplainer(model_predict, np.zeros((1, self.model.network[0].in_features)))
            else:
                # Fallback to KernelExplainer
                logger.warning("Using KernelExplainer (slower). Consider TreeExplainer for tree-based models.")
                self.explainer = shap.KernelExplainer(self.model.predict, np.zeros((1, 10)))
        except Exception as e:
            logger.error("Failed to initialize SHAP explainer", error=str(e))
            raise

    def explain_prediction(self, features: np.ndarray, max_evals: int = 100) -> Dict[str, float]:
        """
        Explain a single prediction.
        
        Args:
            features: Feature array (n_features,) for single prediction
            max_evals: Maximum evaluations for SHAP (for KernelExplainer)
            
        Returns:
            Dictionary mapping feature names to SHAP values
        """
        if self.explainer is None:
            raise ValueError("Explainer not initialized")

        # Reshape for single sample
        if features.ndim == 1:
            features = features.reshape(1, -1)

        try:
            # Calculate SHAP values
            if isinstance(self.explainer, shap.explainers.Tree):
                shap_values = self.explainer.shap_values(features)
            else:
                shap_values = self.explainer.shap_values(features[0], nsamples=max_evals)

            # Handle different output formats
            if isinstance(shap_values, list):
                shap_values = shap_values[0]  # Take first output for regression

            # Flatten if needed
            if shap_values.ndim > 1:
                shap_values = shap_values.flatten()

            # Create feature importance dictionary
            if self.feature_names and len(self.feature_names) == len(shap_values):
                importance_dict = dict(zip(self.feature_names, shap_values.tolist()))
            else:
                importance_dict = {
                    f"feature_{i}": float(val) for i, val in enumerate(shap_values)
                }

            return importance_dict

        except Exception as e:
            logger.error("Failed to calculate SHAP values", error=str(e))
            raise

    def explain_batch(self, features: np.ndarray, max_evals: int = 100) -> List[Dict[str, float]]:
        """
        Explain multiple predictions.
        
        Args:
            features: Feature array (n_samples, n_features)
            max_evals: Maximum evaluations for SHAP (for KernelExplainer)
            
        Returns:
            List of dictionaries, one per sample
        """
        explanations = []
        for i in range(len(features)):
            try:
                explanation = self.explain_prediction(features[i], max_evals=max_evals)
                explanations.append(explanation)
            except Exception as e:
                logger.warning("Failed to explain sample", sample_idx=i, error=str(e))
                explanations.append({})

        return explanations

    def get_feature_importance(self, X_sample: np.ndarray, n_samples: int = 100) -> Dict[str, float]:
        """
        Get global feature importance from SHAP values.
        
        Args:
            X_sample: Sample of features to calculate importance on
            n_samples: Number of samples to use for importance calculation
            
        Returns:
            Dictionary mapping feature names to average absolute SHAP values
        """
        if self.explainer is None:
            raise ValueError("Explainer not initialized")

        # Sample if needed
        if len(X_sample) > n_samples:
            indices = np.random.choice(len(X_sample), n_samples, replace=False)
            X_sample = X_sample[indices]

        try:
            # Calculate SHAP values for sample
            if isinstance(self.explainer, shap.explainers.Tree):
                shap_values = self.explainer.shap_values(X_sample)
            else:
                # For KernelExplainer, calculate for each sample
                shap_values_list = []
                for i in range(len(X_sample)):
                    sv = self.explainer.shap_values(X_sample[i], nsamples=50)
                    if isinstance(sv, list):
                        sv = sv[0]
                    shap_values_list.append(sv)
                shap_values = np.array(shap_values_list)

            # Calculate mean absolute importance
            if shap_values.ndim > 1:
                importance = np.mean(np.abs(shap_values), axis=0)
            else:
                importance = np.abs(shap_values)

            # Create feature importance dictionary
            if self.feature_names and len(self.feature_names) == len(importance):
                importance_dict = dict(zip(self.feature_names, importance.tolist()))
            else:
                importance_dict = {
                    f"feature_{i}": float(imp) for i, imp in enumerate(importance)
                }

            return importance_dict

        except Exception as e:
            logger.error("Failed to calculate feature importance", error=str(e))
            raise

