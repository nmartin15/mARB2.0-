"""ML service for risk prediction."""
from typing import Dict, Optional
import numpy as np
from pathlib import Path
import os

from app.models.database import Claim
from ml.models.risk_predictor import RiskPredictor
from ml.services.feature_extractor import FeatureExtractor
from app.utils.logger import get_logger
from app.utils.memory_monitor import log_memory_checkpoint, get_memory_usage

logger = get_logger(__name__)


class MLService:
    """ML model service for risk prediction."""

    def __init__(self, model_path: Optional[str] = None, db_session: Optional[object] = None):
        """
        Initialize ML service.
        
        Args:
            model_path: Path to trained model file (optional, will try to find latest)
            db_session: Database session for historical feature extraction
        """
        self.model: Optional[RiskPredictor] = None
        self.model_loaded = False
        self.feature_extractor = FeatureExtractor()
        self.db_session = db_session

        # Try to load model
        if model_path:
            self.load_model(model_path)
        else:
            self._try_load_latest_model()

    def _try_load_latest_model(self) -> None:
        """
        Try to load the latest trained model from default directory.
        
        Searches for model files matching pattern 'risk_predictor_*.pkl' in 'ml/models/saved'
        and loads the most recently modified one. If no models are found, the service
        will use placeholder predictions until a model is trained.
        
        This method delegates to load_model() which handles the actual loading logic
        and exception handling, ensuring no duplication of model loading code.
        """
        model_dir = Path("ml/models/saved")
        if not model_dir.exists():
            logger.info("Model directory not found, using placeholder prediction")
            return

        # Find latest model file
        model_files = list(model_dir.glob("risk_predictor_*.pkl"))
        if not model_files:
            logger.info("No trained models found, using placeholder prediction")
            return

        # Sort by modification time and load latest
        # Delegate to load_model() which handles all loading logic and exception handling
        latest_model = max(model_files, key=lambda p: p.stat().st_mtime)
        try:
            self.load_model(str(latest_model))
        except Exception as e:
            # Additional exception handling for file system operations (stat, max, etc.)
            logger.error("Failed to load model", error=str(e), model_path=str(latest_model))
            self.model_loaded = False

    def load_model(self, model_path: str):
        """
        Load trained model from file with memory monitoring.
        
        Args:
            model_path: Path to model file
        """
        start_memory = get_memory_usage()
        
        try:
            log_memory_checkpoint(
                "ml_model_loading",
                "before_load",
                start_memory_mb=start_memory,
                metadata={"model_path": model_path},
            )
            
            self._load_model_internal(model_path)
            
            log_memory_checkpoint(
                "ml_model_loading",
                "after_load",
                start_memory_mb=start_memory,
                metadata={"model_path": model_path, "model_loaded": True},
            )
            
            logger.info("ML model loaded successfully", model_path=model_path)
        except Exception as e:
            log_memory_checkpoint(
                "ml_model_loading",
                "load_failed",
                start_memory_mb=start_memory,
                metadata={"model_path": model_path, "error": str(e)},
            )
            logger.warning("Failed to load ML model", error=str(e), model_path=model_path)
            self.model_loaded = False

    def _load_model_internal(self, model_path: str) -> None:
        """
        Internal method to load the model without memory monitoring.
        
        This method is called by load_model() which handles memory monitoring.
        Use load_model() instead of this method directly.
        
        Args:
            model_path: Path to model file (must exist and be a valid RiskPredictor model)
            
        Raises:
            FileNotFoundError: If model file doesn't exist
            Exception: If model file is corrupted or invalid
        """
        self.model = RiskPredictor(model_path=model_path)
        self.model_loaded = True

    def predict_risk(self, claim: Claim) -> float:
        """
        Predict risk score using ML model with memory monitoring.
        
        Args:
            claim: The claim to predict risk for
            
        Returns:
            Risk score (0-100)
        """
        if not self.model_loaded or self.model is None:
            logger.debug("ML model not loaded, using placeholder prediction")
            return self._placeholder_prediction(claim)

        start_memory = get_memory_usage()
        
        try:
            log_memory_checkpoint(
                "ml_prediction",
                "start",
                start_memory_mb=start_memory,
                metadata={"claim_id": claim.id},
            )
            
            # Extract features
            features = self.feature_extractor.extract_features(
                claim, include_historical=True, db_session=self.db_session
            )
            
            log_memory_checkpoint(
                "ml_prediction",
                "features_extracted",
                start_memory_mb=start_memory,
                metadata={"claim_id": claim.id, "feature_count": len(features)},
            )

            # Predict denial rate (0.0 to 1.0)
            denial_rate = self.model.predict_single(features)
            
            log_memory_checkpoint(
                "ml_prediction",
                "prediction_complete",
                start_memory_mb=start_memory,
                metadata={"claim_id": claim.id, "denial_rate": denial_rate},
            )

            # Convert to risk score (0-100)
            # Higher denial rate = higher risk score
            risk_score = float(denial_rate * 100)

            logger.debug(
                "ML prediction completed",
                claim_id=claim.id,
                denial_rate=denial_rate,
                risk_score=risk_score,
            )

            return risk_score

        except Exception as e:
            log_memory_checkpoint(
                "ml_prediction",
                "prediction_failed",
                start_memory_mb=start_memory,
                metadata={"claim_id": claim.id, "error": str(e)},
            )
            logger.error("ML prediction failed", error=str(e), claim_id=claim.id)
            return self._placeholder_prediction(claim)

    def _placeholder_prediction(self, claim: Claim) -> float:
        """
        Placeholder prediction until ML model is trained.
        
        Returns a simple heuristic risk score based on claim characteristics.
        
        Args:
            claim: Claim to evaluate
            
        Returns:
            Risk score between 0.0 and 100.0
        """
        # Simple heuristic based on claim characteristics
        risk = 0.0

        if claim.is_incomplete:
            risk += 20.0

        if not claim.principal_diagnosis:
            risk += 15.0

        if len(claim.claim_lines or []) > 10:
            risk += 10.0

        if claim.total_charge_amount and claim.total_charge_amount > 10000:
            risk += 10.0

        return min(risk, 100.0)

