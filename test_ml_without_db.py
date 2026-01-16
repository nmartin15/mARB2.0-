#!/usr/bin/env python3
"""
Test ML models without database connection.

This script tests the deep learning model and SHAP explainability
using the generated mock training data directly, without needing
a database connection.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ml.models.deep_risk_predictor import DeepRiskPredictor
from ml.services.model_explainer import ModelExplainer
from ml.services.feature_extractor import FeatureExtractor
from ml.training.generate_training_data import generate_training_dataset
from app.services.edi.parser import EDIParser
from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_mock_claim_features(num_samples=100):
    """Create mock feature data for testing."""
    np.random.seed(42)
    
    # Simulate 31 features (matching FeatureExtractor)
    features = []
    for _ in range(num_samples):
        sample = [
            np.random.uniform(100, 10000),  # total_charge_amount
            np.random.choice([0, 1]),  # is_incomplete
            np.random.choice([0, 1]),  # has_principal_diagnosis
            np.random.randint(1, 10),  # diagnosis_count
            np.random.randint(1, 20),  # claim_line_count
            np.random.uniform(50, 500),  # charge_per_line
            np.random.uniform(0.1, 2.0),  # diagnosis_per_line
            np.random.uniform(0, 365),  # claim_age_days
            np.random.randint(1, 15),  # unique_procedure_codes
            np.random.randint(0, 10),  # modifier_count
            np.random.randint(0, 5),  # unique_modifiers
            np.random.choice([0, 1]),  # has_revenue_code
            np.random.randint(0, 5),  # revenue_code_count
            np.random.uniform(1000, 5000),  # total_line_charges
            np.random.uniform(100, 1000),  # max_line_charge
            np.random.uniform(10, 100),  # min_line_charge
            np.random.uniform(50, 500),  # avg_line_charge
            np.random.uniform(50, 500),  # median_line_charge
            np.random.uniform(10, 200),  # std_line_charge
            np.random.choice([0, 1]),  # has_attending_provider
            np.random.choice([0, 1]),  # has_operating_provider
            np.random.choice([0, 1]),  # has_referring_provider
            np.random.choice([0, 1]),  # has_provider
            np.random.randint(0, 3),  # provider_count
            np.random.randint(0, 7),  # service_date_day_of_week
            np.random.randint(1, 13),  # service_date_month
            np.random.randint(1, 5),  # service_date_quarter
            np.random.choice([0, 1]),  # service_date_is_weekend
            np.random.uniform(0, 0.5),  # historical_payer_denial_rate
            np.random.uniform(0, 0.5),  # historical_provider_denial_rate
            np.random.uniform(0, 0.5),  # historical_diagnosis_denial_rate
            np.random.uniform(0.5, 1.0),  # historical_avg_payment_rate
        ]
        features.append(sample)
    
    return np.array(features, dtype=np.float32)


def test_deep_learning_model():
    """Test deep learning model without database."""
    print("\n" + "=" * 70)
    print("TESTING DEEP LEARNING MODEL (No Database Required)")
    print("=" * 70)
    
    # Create mock data
    print("\n[1/4] Creating mock training data...")
    X_train = create_mock_claim_features(200)
    X_test = create_mock_claim_features(50)
    
    # Create labels (denial rates)
    np.random.seed(42)
    y_train = np.random.beta(2, 5, size=len(X_train)).astype(np.float32)
    y_test = np.random.beta(2, 5, size=len(X_test)).astype(np.float32)
    
    print(f"   ✓ Created {len(X_train)} training samples, {len(X_test)} test samples")
    print(f"   ✓ Features: {X_train.shape[1]}, Labels: {y_train.shape[0]}")
    
    # Train model
    print("\n[2/4] Training deep learning model...")
    predictor = DeepRiskPredictor()
    
    # Split training data for validation
    split_idx = int(len(X_train) * 0.8)
    X_train_split = X_train[:split_idx]
    y_train_split = y_train[:split_idx]
    X_val = X_train[split_idx:]
    y_val = y_train[split_idx:]
    
    metrics = predictor.train(
        X_train_split,
        y_train_split,
        X_val=X_val,
        y_val=y_val,
        hidden_sizes=[64, 32],
        epochs=20,  # Reduced for faster testing
        batch_size=16,
        learning_rate=0.001,
    )
    
    print(f"   ✓ Training complete!")
    print(f"   ✓ Train R²: {metrics['train_r2']:.4f}")
    print(f"   ✓ Train RMSE: {metrics['train_rmse']:.4f}")
    if metrics.get('val_r2'):
        print(f"   ✓ Val R²: {metrics['val_r2']:.4f}")
        print(f"   ✓ Val RMSE: {metrics['val_rmse']:.4f}")
    
    # Evaluate
    print("\n[3/4] Evaluating on test set...")
    test_metrics = predictor.evaluate(X_test, y_test)
    print(f"   ✓ Test R²: {test_metrics['test_r2']:.4f}")
    print(f"   ✓ Test RMSE: {test_metrics['test_rmse']:.4f}")
    print(f"   ✓ Test Accuracy: {test_metrics['test_accuracy']:.4f}")
    
    # Test prediction
    print("\n[4/4] Testing single prediction...")
    sample_features = X_test[0]
    prediction = predictor.predict_single(sample_features)
    actual = y_test[0]
    print(f"   ✓ Predicted denial rate: {prediction:.4f}")
    print(f"   ✓ Actual denial rate: {actual:.4f}")
    print(f"   ✓ Error: {abs(prediction - actual):.4f}")
    
    return predictor, X_test


def test_shap_explainability(predictor, X_test):
    """Test SHAP explainability."""
    print("\n" + "=" * 70)
    print("TESTING SHAP MODEL EXPLAINABILITY (No Database Required)")
    print("=" * 70)
    
    try:
        # Create feature names
        feature_names = [
            "total_charge_amount", "is_incomplete", "has_principal_diagnosis",
            "diagnosis_count", "claim_line_count", "charge_per_line",
            "diagnosis_per_line", "claim_age_days", "unique_procedure_codes",
            "modifier_count", "unique_modifiers", "has_revenue_code",
            "revenue_code_count", "total_line_charges", "max_line_charge",
            "min_line_charge", "avg_line_charge", "median_line_charge",
            "std_line_charge", "has_attending_provider", "has_operating_provider",
            "has_referring_provider", "has_provider", "provider_count",
            "service_date_day_of_week", "service_date_month", "service_date_quarter",
            "service_date_is_weekend", "historical_payer_denial_rate",
            "historical_provider_denial_rate", "historical_diagnosis_denial_rate",
            "historical_avg_payment_rate",
        ]
        
        print("\n[1/2] Initializing SHAP explainer...")
        explainer = ModelExplainer(predictor.model, feature_names=feature_names)
        print("   ✓ SHAP explainer initialized")
        
        print("\n[2/2] Explaining sample prediction...")
        sample = X_test[0]
        explanation = explainer.explain_prediction(sample, max_evals=50)
        
        # Show top 10 most important features
        sorted_features = sorted(explanation.items(), key=lambda x: abs(x[1]), reverse=True)
        print("\n   Top 10 Feature Contributions:")
        for i, (feature, value) in enumerate(sorted_features[:10], 1):
            sign = "+" if value >= 0 else ""
            print(f"   {i:2d}. {feature:35s} {sign}{value:8.4f}")
        
        print("\n   ✓ SHAP explanation complete!")
        
    except ImportError:
        print("\n   ⚠️  SHAP not installed. Install with: pip install shap")
    except Exception as e:
        print(f"\n   ❌ Error: {e}")


def test_edi_parsing():
    """Test EDI parsing without database."""
    print("\n" + "=" * 70)
    print("TESTING EDI PARSING (No Database Required)")
    print("=" * 70)
    
    claims_file = Path("samples/training/training_837_claims.edi")
    
    if not claims_file.exists():
        print("\n   ⚠️  Training data not found. Generating...")
        generate_training_dataset(
            num_episodes=50,
            output_dir=Path("samples/training"),
            start_date=datetime.now() - timedelta(days=180),
            denial_rate=0.25,
        )
        print("   ✓ Training data generated")
    
    print(f"\n[1/2] Parsing EDI file: {claims_file}")
    parser = EDIParser()
    
    with open(claims_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    result = parser.parse(content, str(claims_file))
    
    claim_count = len(result.get("claims", []))
    print(f"   ✓ Parsed {claim_count} claims from EDI file")
    
    if claim_count > 0:
        print("\n[2/2] Sample claim data:")
        sample_claim = result["claims"][0]
        print(f"   ✓ Claim Control Number: {sample_claim.get('claim_control_number', 'N/A')}")
        print(f"   ✓ Patient Control Number: {sample_claim.get('patient_control_number', 'N/A')}")
        print(f"   ✓ Total Charge: ${sample_claim.get('total_charge_amount', 0):.2f}")
        print(f"   ✓ Line Count: {len(sample_claim.get('claim_lines', []))}")
    
    print("\n   ✓ EDI parsing test complete!")


def main():
    """Run all tests without database."""
    print("\n" + "=" * 70)
    print("ML MODEL TESTING (No Database Connection Required)")
    print("=" * 70)
    print("\nThis script tests:")
    print("  1. Deep Learning Model (PyTorch)")
    print("  2. SHAP Model Explainability")
    print("  3. EDI File Parsing")
    print("\nNo database connection needed!")
    
    try:
        # Test 1: Deep Learning
        predictor, X_test = test_deep_learning_model()
        
        # Test 2: SHAP (optional)
        test_shap_explainability(predictor, X_test)
        
        # Test 3: EDI Parsing
        test_edi_parsing()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS COMPLETE (No Database Required!)")
        print("=" * 70)
        print("\nYou can now:")
        print("  1. Train models with: python ml/training/train_models.py")
        print("  2. Use deep learning: from ml.models.deep_risk_predictor import DeepRiskPredictor")
        print("  3. Use SHAP: from ml.services.model_explainer import ModelExplainer")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

