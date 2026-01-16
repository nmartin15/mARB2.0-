"""Deep learning risk prediction model using PyTorch."""
from typing import Optional, Dict, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import joblib
from pathlib import Path
from sklearn.preprocessing import StandardScaler

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ClaimDataset(Dataset):
    """PyTorch dataset for claim features."""

    def __init__(self, features: np.ndarray, labels: Optional[np.ndarray] = None):
        """
        Initialize dataset.
        
        Args:
            features: Feature array (n_samples, n_features)
            labels: Optional labels (n_samples,)
        """
        self.features = torch.FloatTensor(features)
        self.labels = torch.FloatTensor(labels) if labels is not None else None

    def __len__(self) -> int:
        """Return dataset size."""
        return len(self.features)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Get item by index.
        
        Args:
            idx: Index
            
        Returns:
            Tuple of (features, label) or (features, None) if no labels
        """
        if self.labels is not None:
            return self.features[idx], self.labels[idx]
        return self.features[idx], None


class RiskPredictionNet(nn.Module):
    """Neural network for risk prediction."""

    def __init__(self, input_size: int, hidden_sizes: list = [128, 64, 32], dropout_rate: float = 0.3):
        """
        Initialize neural network.
        
        Args:
            input_size: Number of input features
            hidden_sizes: List of hidden layer sizes
            dropout_rate: Dropout rate for regularization
        """
        super(RiskPredictionNet, self).__init__()

        layers = []
        prev_size = input_size

        # Build hidden layers
        for hidden_size in hidden_sizes:
            layers.append(nn.Linear(prev_size, hidden_size))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout_rate))
            prev_size = hidden_size

        # Output layer (single value for regression)
        layers.append(nn.Linear(prev_size, 1))
        layers.append(nn.Sigmoid())  # Ensure output is in [0, 1]

        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input features
            
        Returns:
            Predicted denial rate (0.0 to 1.0)
        """
        return self.network(x).squeeze()


class DeepRiskPredictor:
    """
    Deep learning model for predicting claim denial risk.
    
    Uses PyTorch neural network with configurable architecture.
    Supports both training and inference modes.
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize deep risk predictor.
        
        Args:
            model_path: Path to saved model file (optional)
        """
        self.model: Optional[RiskPredictionNet] = None
        self.scaler: Optional[StandardScaler] = None
        self.model_path = model_path
        self.feature_names: Optional[list] = None
        self.model_version = "1.0"
        self.is_trained = False
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        if model_path and Path(model_path).exists():
            self.load_model(model_path)

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        hidden_sizes: list = [128, 64, 32],
        dropout_rate: float = 0.3,
        learning_rate: float = 0.001,
        batch_size: int = 32,
        epochs: int = 100,
        early_stopping_patience: int = 10,
        random_state: int = 42,
    ) -> Dict[str, float]:
        """
        Train the deep learning model.
        
        Args:
            X_train: Training features (n_samples, n_features)
            y_train: Training labels (denial rate: 0.0 to 1.0)
            X_val: Optional validation features
            y_val: Optional validation labels
            hidden_sizes: List of hidden layer sizes
            dropout_rate: Dropout rate for regularization
            learning_rate: Learning rate for optimizer
            batch_size: Batch size for training
            epochs: Number of training epochs
            early_stopping_patience: Patience for early stopping
            random_state: Random seed for reproducibility
            
        Returns:
            Dictionary with training metrics
        """
        logger.info(
            "Training deep learning risk prediction model",
            n_samples=X_train.shape[0],
            n_features=X_train.shape[1],
            hidden_sizes=hidden_sizes,
            device=str(self.device),
        )

        # Set random seed
        torch.manual_seed(random_state)
        np.random.seed(random_state)

        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val) if X_val is not None else None

        # Create model
        self.model = RiskPredictionNet(
            input_size=X_train.shape[1], hidden_sizes=hidden_sizes, dropout_rate=dropout_rate
        ).to(self.device)

        # Loss and optimizer
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)

        # Create datasets
        train_dataset = ClaimDataset(X_train_scaled, y_train)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

        val_loader = None
        if X_val_scaled is not None and y_val is not None:
            val_dataset = ClaimDataset(X_val_scaled, y_val)
            val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

        # Training loop
        best_val_loss = float("inf")
        patience_counter = 0
        train_losses = []
        val_losses = []

        for epoch in range(epochs):
            # Training phase
            self.model.train()
            train_loss = 0.0
            for features, labels in train_loader:
                features = features.to(self.device)
                labels = labels.to(self.device)

                optimizer.zero_grad()
                outputs = self.model(features)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                train_loss += loss.item()

            train_loss /= len(train_loader)
            train_losses.append(train_loss)

            # Validation phase
            val_loss = None
            if val_loader is not None:
                self.model.eval()
                val_loss = 0.0
                with torch.no_grad():
                    for features, labels in val_loader:
                        features = features.to(self.device)
                        labels = labels.to(self.device)
                        outputs = self.model(features)
                        loss = criterion(outputs, labels)
                        val_loss += loss.item()

                val_loss /= len(val_loader)
                val_losses.append(val_loss)

                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= early_stopping_patience:
                        logger.info("Early stopping triggered", epoch=epoch + 1)
                        break

            if (epoch + 1) % 10 == 0:
                logger.debug(
                    "Training progress",
                    epoch=epoch + 1,
                    train_loss=train_loss,
                    val_loss=val_loss,
                )

        # Mark as trained before calculating metrics (so predict() works)
        self.is_trained = True
        
        # Calculate final metrics
        self.model.eval()
        with torch.no_grad():
            # Use internal prediction to avoid is_trained check
            X_train_scaled = self.scaler.transform(X_train)
            X_train_tensor = torch.FloatTensor(X_train_scaled).to(self.device)
            train_pred = self.model(X_train_tensor).cpu().numpy().flatten()
            train_pred = np.clip(train_pred, 0.0, 1.0)
            train_r2 = self._calculate_r2(y_train, train_pred)
            train_rmse = np.sqrt(np.mean((y_train - train_pred) ** 2))

            if X_val is not None and y_val is not None:
                X_val_scaled = self.scaler.transform(X_val)
                X_val_tensor = torch.FloatTensor(X_val_scaled).to(self.device)
                val_pred = self.model(X_val_tensor).cpu().numpy().flatten()
                val_pred = np.clip(val_pred, 0.0, 1.0)
                val_r2 = self._calculate_r2(y_val, val_pred)
                val_rmse = np.sqrt(np.mean((y_val - val_pred) ** 2))
            else:
                val_r2 = None
                val_rmse = None

        metrics = {
            "train_r2": float(train_r2),
            "train_rmse": float(train_rmse),
            "val_r2": float(val_r2) if val_r2 is not None else None,
            "val_rmse": float(val_rmse) if val_rmse is not None else None,
            "final_epoch": epoch + 1,
        }

        self.is_trained = True

        logger.info("Deep learning model training complete", **metrics)

        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict denial risk for claims.
        
        Args:
            X: Feature array (n_samples, n_features)
            
        Returns:
            Predicted denial rates (0.0 to 1.0)
        """
        if not self.is_trained or self.model is None or self.scaler is None:
            raise ValueError("Model not trained. Call train() first or load a saved model.")

        self.model.eval()
        X_scaled = self.scaler.transform(X)
        X_tensor = torch.FloatTensor(X_scaled).to(self.device)

        with torch.no_grad():
            predictions = self.model(X_tensor).cpu().numpy()

        # Ensure predictions are in [0, 1] range
        predictions = np.clip(predictions, 0.0, 1.0)
        
        # Ensure it's always an array (flatten if needed)
        if predictions.ndim == 0:
            predictions = np.array([predictions])
        elif predictions.ndim > 1:
            predictions = predictions.flatten()

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
        # Handle both array and scalar returns
        if isinstance(predictions, np.ndarray) and len(predictions) > 0:
            return float(predictions[0])
        return float(predictions)

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
        r2 = self._calculate_r2(y_test, predictions)

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

    def _calculate_r2(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate R² score."""
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        return 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

    def save_model(self, model_path: str, feature_names: Optional[list] = None):
        """
        Save trained model to disk.
        
        Args:
            model_path: Path to save model
            feature_names: Optional list of feature names
        """
        if not self.is_trained or self.model is None or self.scaler is None:
            raise ValueError("Model not trained. Cannot save untrained model.")

        # Create directory if it doesn't exist
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)

        # Save model state and metadata
        model_data = {
            "model_state_dict": self.model.state_dict(),
            "model_config": {
                "input_size": self.model.network[0].in_features,
                "hidden_sizes": [
                    self.model.network[i].out_features
                    for i in range(0, len(self.model.network) - 2, 3)
                ],
                "dropout_rate": self.model.network[2].p if len(self.model.network) > 2 else 0.0,
            },
            "scaler": self.scaler,
            "model_version": self.model_version,
            "feature_names": feature_names or self.feature_names,
            "is_trained": self.is_trained,
        }

        joblib.dump(model_data, model_path)
        self.model_path = model_path

        logger.info("Deep learning model saved", model_path=model_path)

    def load_model(self, model_path: str):
        """
        Load trained model from disk.
        
        Args:
            model_path: Path to saved model
        """
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        model_data = joblib.load(model_path)

        # Reconstruct model
        model_config = model_data["model_config"]
        self.model = RiskPredictionNet(
            input_size=model_config["input_size"],
            hidden_sizes=model_config["hidden_sizes"],
            dropout_rate=model_config.get("dropout_rate", 0.3),
        ).to(self.device)
        self.model.load_state_dict(model_data["model_state_dict"])

        self.scaler = model_data["scaler"]
        self.model_version = model_data.get("model_version", "1.0")
        self.feature_names = model_data.get("feature_names")
        self.is_trained = model_data.get("is_trained", True)
        self.model_path = model_path

        logger.info("Deep learning model loaded", model_path=model_path, version=self.model_version)

