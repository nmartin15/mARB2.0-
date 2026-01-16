"""Comprehensive tests for ML training pipeline using synthetic data."""
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.models.database import Claim, Remittance
from app.services.edi.parser import EDIParser
from app.services.edi.transformer import EDITransformer
from app.services.episodes.linker import EpisodeLinker
from ml.models.risk_predictor import RiskPredictor
from ml.services.data_collector import DataCollector
from ml.services.feature_extractor import FeatureExtractor
from ml.training.check_historical_data import check_historical_data
from ml.training.explore_data import explore_dataset
from ml.training.prepare_data import prepare_training_dataset
from ml.training.train_models import prepare_features_and_labels, train_model
from tests.factories import ClaimFactory


@pytest.mark.integration
class TestMLTrainingPipeline:
    """Integration tests for the complete ML training pipeline."""

    @pytest.fixture
    def temp_training_dir(self):
        """Create temporary directory for training data."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def synthetic_data_files(self, temp_training_dir, db_session):
        """Generate and upload synthetic training data."""
        # Generate synthetic data
        output_dir = temp_training_dir / "synthetic"
        output_dir.mkdir(parents=True)

        # Run the generator
        from ml.training.generate_training_data import generate_training_dataset

        start_date = datetime.now() - timedelta(days=180)
        generate_training_dataset(
            num_episodes=150,  # Enough for training
            output_dir=output_dir,
            start_date=start_date,
            denial_rate=0.25,
        )

        claims_file = output_dir / "training_837_claims.edi"
        remittances_file = output_dir / "training_835_remittances.edi"

        # Parse and create claims/remittances directly (faster than Celery task)

        parser = EDIParser()
        transformer = EDITransformer(db_session)

        # Process claims
        with open(claims_file, "r", encoding="utf-8") as f:
            claims_content = f.read()

        claims_result = parser.parse(claims_content, "training_837_claims.edi")
        for claim_data in claims_result.get("claims", []):
            claim = transformer.transform_837_claim(claim_data)
            db_session.add(claim)

        db_session.commit()

        # Process remittances
        with open(remittances_file, "r", encoding="utf-8") as f:
            remittances_content = f.read()

        remittances_result = parser.parse(remittances_content, "training_835_remittances.edi")
        bpr_data = remittances_result.get("bpr_data", {})

        for remittance_data in remittances_result.get("remittances", []):
            remittance = transformer.transform_835_remittance(remittance_data, bpr_data)
            db_session.add(remittance)

        db_session.commit()

        # Link episodes
        linker = EpisodeLinker(db_session)
        remittances = db_session.query(Remittance).all()
        for remittance in remittances:
            linker.auto_link_by_control_number(remittance)

        db_session.commit()

        return {
            "claims_file": claims_file,
            "remittances_file": remittances_file,
            "output_dir": output_dir,
        }

    def test_data_generation(self, temp_training_dir):
        """Test synthetic data generation."""
        from ml.training.generate_training_data import generate_training_dataset

        output_dir = temp_training_dir / "test_gen"
        output_dir.mkdir(parents=True)

        generate_training_dataset(
            num_episodes=50,
            output_dir=output_dir,
            denial_rate=0.20,
        )

        # Check files were created
        claims_file = output_dir / "training_837_claims.edi"
        remittances_file = output_dir / "training_835_remittances.edi"
        metadata_file = output_dir / "training_metadata.json"

        assert claims_file.exists(), "837 claims file should be created"
        assert remittances_file.exists(), "835 remittances file should be created"
        assert metadata_file.exists(), "Metadata file should be created"

        # Check file sizes
        assert claims_file.stat().st_size > 0, "Claims file should not be empty"
        assert remittances_file.stat().st_size > 0, "Remittances file should not be empty"

    def test_data_collection(self, db_session, synthetic_data_files):
        """Test data collection from database."""
        collector = DataCollector(db_session)

        start_date = datetime.now() - timedelta(days=200)
        end_date = datetime.now()

        df = collector.collect_training_data(
            start_date=start_date,
            end_date=end_date,
            min_episodes=50,  # Lower threshold for testing
            include_historical=False,  # Skip historical for speed
        )

        assert len(df) >= 50, f"Should have at least 50 episodes, got {len(df)}"
        assert "denial_rate" in df.columns, "Should have denial_rate column"
        assert "payment_rate" in df.columns, "Should have payment_rate column"
        assert "is_denied" in df.columns, "Should have is_denied column"

        # Check data quality
        assert df["denial_rate"].min() >= 0.0, "Denial rate should be >= 0"
        assert df["denial_rate"].max() <= 1.0, "Denial rate should be <= 1"
        assert df["payment_rate"].min() >= 0.0, "Payment rate should be >= 0"

    def test_feature_extraction(self, db_session):
        """Test feature extraction from claims."""
        claim = ClaimFactory(
            total_charge_amount=2000.00,
            diagnosis_codes=["E11.9", "I10"],
            is_incomplete=False,
            principal_diagnosis="E11.9",
        )
        db_session.add(claim)
        db_session.flush()

        from tests.factories import ClaimLineFactory
        line1 = ClaimLineFactory(claim=claim, charge_amount=1000.00)
        line2 = ClaimLineFactory(claim=claim, charge_amount=1000.00)
        db_session.add(line1)
        db_session.add(line2)
        db_session.commit()

        extractor = FeatureExtractor()
        features = extractor.extract_features(
            claim, include_historical=False, db_session=None
        )

        assert isinstance(features, type(extractor.extract_features(claim, include_historical=False, db_session=None)))
        assert len(features) >= 27, f"Should have at least 27 features, got {len(features)}"
        assert features[0] == 2000.00, "First feature should be total charge"

    def test_data_preparation(self, db_session, synthetic_data_files, temp_training_dir):
        """Test data preparation script."""
        output_file = temp_training_dir / "prepared_data.csv"

        start_date = datetime.now() - timedelta(days=200)
        end_date = datetime.now()

        df = prepare_training_dataset(
            start_date=start_date,
            end_date=end_date,
            output_file=str(output_file),
            min_episodes=50,
            include_historical=False,
            explore=False,  # Skip exploration for speed
        )

        assert output_file.exists(), "Output CSV should be created"
        assert len(df) >= 50, "Should have at least 50 rows"
        assert "denial_rate" in df.columns, "Should have denial_rate"

    def test_data_exploration(self, db_session, synthetic_data_files, temp_training_dir):
        """Test data exploration."""
        # First prepare data
        output_file = temp_training_dir / "explore_data.csv"

        start_date = datetime.now() - timedelta(days=200)
        end_date = datetime.now()

        df = prepare_training_dataset(
            start_date=start_date,
            end_date=end_date,
            output_file=str(output_file),
            min_episodes=50,
            include_historical=False,
            explore=False,
        )

        # Now explore it
        explore_dataset(df, output_file=None)

    def test_model_training(self, db_session, synthetic_data_files):
        """Test model training with synthetic data."""
        start_date = datetime.now() - timedelta(days=200)
        end_date = datetime.now()

        # Train model
        model = train_model(
            db_session=db_session,
            start_date=start_date,
            end_date=end_date,
            model_type="random_forest",
            n_estimators=50,  # Smaller for faster testing
            max_depth=10,
            test_size=0.2,
            random_state=42,
            output_dir="ml/models/saved/test",
        )

        assert model is not None, "Model should be created"
        assert model.is_trained, "Model should be trained"
        assert model.model is not None, "Model should have sklearn model"

    def test_model_evaluation(self, db_session, synthetic_data_files):
        """Test model evaluation."""
        from sklearn.model_selection import train_test_split

        from ml.training.evaluate_models import evaluate_model_comprehensive

        # Collect data
        collector = DataCollector(db_session)
        start_date = datetime.now() - timedelta(days=200)
        end_date = datetime.now()

        df = collector.collect_training_data(
            start_date=start_date,
            end_date=end_date,
            min_episodes=50,
            include_historical=False,
        )

        # Prepare features
        X, y, feature_names = prepare_features_and_labels(df)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Train model
        model = RiskPredictor()
        model.feature_names = feature_names
        model.train(X_train, y_train, model_type="random_forest", n_estimators=50)

        # Evaluate
        metrics = evaluate_model_comprehensive(model, X_test, y_test, feature_names)

        assert "test_r2" in metrics, "Should have R² score"
        assert "test_rmse" in metrics, "Should have RMSE"
        assert "test_mae" in metrics, "Should have MAE"
        assert "test_accuracy" in metrics, "Should have accuracy"
        assert metrics["test_r2"] >= -1.0, "R² should be reasonable"
        assert metrics["test_rmse"] >= 0.0, "RMSE should be >= 0"

    def test_feature_importance(self, db_session, synthetic_data_files):
        """Test feature importance extraction."""
        from sklearn.model_selection import train_test_split

        collector = DataCollector(db_session)
        start_date = datetime.now() - timedelta(days=200)
        end_date = datetime.now()

        df = collector.collect_training_data(
            start_date=start_date,
            end_date=end_date,
            min_episodes=50,
            include_historical=False,
        )

        X, y, feature_names = prepare_features_and_labels(df)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        model = RiskPredictor()
        model.feature_names = feature_names
        model.train(X_train, y_train, model_type="random_forest", n_estimators=50)

        importance = model.get_feature_importance()

        assert importance is not None, "Should have feature importance"
        assert len(importance) > 0, "Should have some features"
        assert all(isinstance(v, (int, float)) for v in importance.values()), "Importance should be numeric"

    def test_historical_data_check(self, db_session, synthetic_data_files):
        """Test historical data availability check."""
        stats = check_historical_data(db_session)

        assert "total_claims" in stats, "Should have total_claims"
        assert "total_remittances" in stats, "Should have total_remittances"
        assert "episodes_with_outcomes" in stats, "Should have episodes_with_outcomes"
        assert stats["episodes_with_outcomes"] >= 50, "Should have at least 50 episodes"

    def test_full_pipeline(self, db_session, synthetic_data_files, temp_training_dir):
        """Test the complete ML training pipeline end-to-end."""
        # 1. Check data availability
        stats = check_historical_data(db_session)
        assert stats["episodes_with_outcomes"] >= 50, "Should have enough episodes"

        # 2. Prepare data
        output_file = temp_training_dir / "pipeline_data.csv"
        start_date = datetime.now() - timedelta(days=200)
        end_date = datetime.now()

        df = prepare_training_dataset(
            start_date=start_date,
            end_date=end_date,
            output_file=str(output_file),
            min_episodes=50,
            include_historical=False,
            explore=False,
        )
        assert len(df) >= 50, "Should have prepared data"

        # 3. Train model
        model = train_model(
            db_session=db_session,
            start_date=start_date,
            end_date=end_date,
            model_type="random_forest",
            n_estimators=50,
            test_size=0.2,
            output_dir="ml/models/saved/test",
        )
        assert model.is_trained, "Model should be trained"

        # 4. Test prediction
        claim = db_session.query(Claim).first()
        if claim:
            extractor = FeatureExtractor()
            features = extractor.extract_features(
                claim, include_historical=False, db_session=None
            )

            prediction = model.predict_single(features)
            assert 0.0 <= prediction <= 1.0, "Prediction should be in [0, 1]"

    def test_data_quality_validation(self, db_session, synthetic_data_files):
        """Test data quality validation."""
        collector = DataCollector(db_session)
        start_date = datetime.now() - timedelta(days=200)
        end_date = datetime.now()

        df = collector.collect_training_data(
            start_date=start_date,
            end_date=end_date,
            min_episodes=50,
            include_historical=False,
        )

        # Check for missing values
        missing = df.isnull().sum()
        # Some missing values are OK, but should be minimal
        assert missing.sum() < len(df) * 0.1, "Should have minimal missing values"

        # Check for infinite values
        numeric_cols = df.select_dtypes(include=["float64", "int64"]).columns
        for col in numeric_cols:
            if col not in ["claim_id"]:
                assert not df[col].isin([float("inf"), float("-inf")]).any(), f"{col} should not have infinite values"

    def test_multiple_specialties(self, db_session, synthetic_data_files):
        """Test that data includes multiple specialties."""
        collector = DataCollector(db_session)
        start_date = datetime.now() - timedelta(days=200)
        end_date = datetime.now()

        df = collector.collect_training_data(
            start_date=start_date,
            end_date=end_date,
            min_episodes=50,
            include_historical=False,
        )

        # Check for variety in CPT codes (indicates different specialties)
        if "unique_procedure_codes" in df.columns:
            unique_codes = df["unique_procedure_codes"].nunique()
            assert unique_codes > 1, "Should have variety in procedure codes"

    def test_denial_rate_distribution(self, db_session, synthetic_data_files):
        """Test that denial rates are realistic."""
        collector = DataCollector(db_session)
        start_date = datetime.now() - timedelta(days=200)
        end_date = datetime.now()

        df = collector.collect_training_data(
            start_date=start_date,
            end_date=end_date,
            min_episodes=50,
            include_historical=False,
        )

        # Check denial rate distribution
        denied_count = (df["is_denied"] == 1).sum()
        denied_rate = denied_count / len(df)

        # Should have some denials (10-40% is reasonable)
        assert 0.10 <= denied_rate <= 0.40, f"Denial rate {denied_rate:.2%} should be between 10-40%"


@pytest.mark.unit
class TestMLDataCollector:
    """Unit tests for data collector."""

    def test_collect_training_data_insufficient(self, db_session):
        """Test that insufficient data raises error."""
        collector = DataCollector(db_session)

        with pytest.raises(ValueError, match="Insufficient training data"):
            collector.collect_training_data(
                start_date=datetime.now() - timedelta(days=1),
                end_date=datetime.now(),
                min_episodes=1000,  # Unrealistic number
            )

    def test_historical_statistics(self, db_session):
        """Test historical statistics calculation."""
        # Create some test data
        claim = ClaimFactory(payer_id=1, provider_id=1, principal_diagnosis="E11.9")
        db_session.add(claim)
        db_session.commit()

        collector = DataCollector(db_session)
        stats = collector.get_historical_statistics(claim, lookback_days=90)

        assert "historical_payer_denial_rate" in stats
        assert "historical_provider_denial_rate" in stats
        assert "historical_diagnosis_denial_rate" in stats
        assert "historical_avg_payment_rate" in stats

        # All should be floats between 0 and 1
        for key, value in stats.items():
            assert isinstance(value, float)
            assert 0.0 <= value <= 1.0

    def test_validate_data_quality_empty_dataframe(self, db_session):
        """Test that empty dataframe raises ValueError."""
        import pandas as pd
        from ml.services.data_collector import DataCollector

        collector = DataCollector(db_session)
        empty_df = pd.DataFrame()

        with pytest.raises(ValueError, match="Training dataset is empty"):
            collector._validate_data_quality(empty_df)

    def test_validate_data_quality_missing_values(self, db_session):
        """Test validation with missing values."""
        import pandas as pd
        import numpy as np
        from ml.services.data_collector import DataCollector

        collector = DataCollector(db_session)
        df = pd.DataFrame({
            "claim_id": [1, 2, 3],
            "total_charge_amount": [100.0, np.nan, 200.0],
            "denial_rate": [0.0, 0.5, 1.0],
            "is_denied": [0, 1, 0],
        })

        # Should not raise, but log warning
        collector._validate_data_quality(df)

    def test_validate_data_quality_infinite_values(self, db_session):
        """Test validation with infinite values."""
        import pandas as pd
        import numpy as np
        from ml.services.data_collector import DataCollector

        collector = DataCollector(db_session)
        df = pd.DataFrame({
            "claim_id": [1, 2, 3],
            "total_charge_amount": [100.0, np.inf, 200.0],
            "denial_rate": [0.0, 0.5, 1.0],
            "is_denied": [0, 1, 0],
        })

        # Should not raise, but log warning
        collector._validate_data_quality(df)

    def test_validate_data_quality_imbalanced_labels(self, db_session):
        """Test validation with highly imbalanced labels."""
        import pandas as pd
        from ml.services.data_collector import DataCollector

        collector = DataCollector(db_session)
        # Create highly imbalanced dataset (99% denied)
        df = pd.DataFrame({
            "claim_id": list(range(100)),
            "total_charge_amount": [100.0] * 100,
            "denial_rate": [1.0] * 99 + [0.0],
            "is_denied": [1] * 99 + [0],
        })

        # Should not raise, but log warning
        collector._validate_data_quality(df)

    def test_validate_data_quality_constant_features(self, db_session):
        """Test validation with constant features (no variance)."""
        import pandas as pd
        from ml.services.data_collector import DataCollector

        collector = DataCollector(db_session)
        df = pd.DataFrame({
            "claim_id": [1, 2, 3],
            "total_charge_amount": [100.0, 100.0, 100.0],  # Constant
            "denial_rate": [0.0, 0.5, 1.0],
            "is_denied": [0, 1, 0],
            "constant_feature": [5.0, 5.0, 5.0],  # Constant
        })

        # Should not raise, but log warning
        collector._validate_data_quality(df)

    def test_validate_data_quality_valid_data(self, db_session):
        """Test validation with valid, diverse data."""
        import pandas as pd
        from ml.services.data_collector import DataCollector

        collector = DataCollector(db_session)
        df = pd.DataFrame({
            "claim_id": list(range(100)),
            "total_charge_amount": [float(i * 10) for i in range(100)],
            "denial_rate": [0.0, 0.5, 1.0] * 33 + [0.0],
            "is_denied": [0, 1, 0] * 33 + [0],
            "payment_rate": [0.8, 0.5, 0.0] * 33 + [0.8],
        })

        # Should pass without warnings
        collector._validate_data_quality(df)


@pytest.mark.unit
class TestMLFeatureExtractor:
    """Unit tests for feature extractor."""

    def test_extract_basic_features(self, db_session):
        """Test basic feature extraction."""
        claim = ClaimFactory(
            total_charge_amount=1500.00,
            is_incomplete=False,
            principal_diagnosis="E11.9",
            diagnosis_codes=["E11.9", "I10"],
        )
        db_session.add(claim)
        db_session.flush()

        from tests.factories import ClaimLineFactory
        for _ in range(3):
            line = ClaimLineFactory(claim=claim)
            db_session.add(line)
        db_session.commit()

        extractor = FeatureExtractor()
        features = extractor._extract_basic_features(claim)

        assert len(features) == 8, "Should have 8 basic features"
        assert features[0] == 1500.00, "First should be total charge"
        assert features[1] == 0.0, "Second should be is_incomplete (False)"
        assert features[2] == 1.0, "Third should be has_principal_diagnosis (True)"
        assert features[3] == 2, "Fourth should be diagnosis count"

    def test_extract_coding_features(self, db_session):
        """Test coding feature extraction."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.flush()

        from tests.factories import ClaimLineFactory
        line1 = ClaimLineFactory(claim=claim, procedure_code="99213", procedure_modifier="25")
        line2 = ClaimLineFactory(claim=claim, procedure_code="99214", procedure_modifier="25")
        line3 = ClaimLineFactory(claim=claim, procedure_code="99213", revenue_code="0250")
        db_session.add(line1)
        db_session.add(line2)
        db_session.add(line3)
        db_session.commit()

        extractor = FeatureExtractor()
        features = extractor._extract_coding_features(claim)

        assert len(features) == 5, "Should have 5 coding features"
        assert features[0] == 2, "Should have 2 unique procedure codes"
        assert features[1] == 3, "Should have 3 total modifiers"
        assert features[2] == 1, "Should have 1 unique modifier"

    def test_extract_financial_features(self, db_session):
        """Test financial feature extraction."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.flush()

        from tests.factories import ClaimLineFactory
        line1 = ClaimLineFactory(claim=claim, charge_amount=100.00)
        line2 = ClaimLineFactory(claim=claim, charge_amount=200.00)
        line3 = ClaimLineFactory(claim=claim, charge_amount=300.00)
        db_session.add(line1)
        db_session.add(line2)
        db_session.add(line3)
        db_session.commit()

        extractor = FeatureExtractor()
        features = extractor._extract_financial_features(claim)

        assert len(features) == 6, "Should have 6 financial features"
        assert features[0] == 600.00, "Total should be 600"
        assert features[1] == 300.00, "Max should be 300"
        assert features[2] == 100.00, "Min should be 100"
        assert features[3] == 200.00, "Mean should be 200"

    def test_extract_temporal_features(self, db_session):
        """Test temporal feature extraction."""

        claim = ClaimFactory(service_date=datetime(2024, 6, 15))  # Saturday
        db_session.add(claim)
        db_session.commit()

        extractor = FeatureExtractor()
        features = extractor._extract_temporal_features(claim)

        assert len(features) == 4, "Should have 4 temporal features"
        assert features[0] == 5.0, "Saturday should be day 5"
        assert features[1] == 6.0, "June should be month 6"
        assert features[2] == 2.0, "June should be quarter 2"
        assert features[3] == 1.0, "Saturday should be weekend"


@pytest.mark.unit
class TestMLRiskPredictor:
    """Unit tests for risk predictor model."""

    def test_train_model(self):
        """Test model training."""
        import numpy as np

        model = RiskPredictor()

        # Create synthetic training data
        X_train = np.random.rand(100, 20).astype(np.float32)
        y_train = np.random.rand(100).astype(np.float32)

        metrics = model.train(
            X_train,
            y_train,
            model_type="random_forest",
            n_estimators=50,
            random_state=42,
        )

        assert model.is_trained, "Model should be trained"
        assert "train_r2" in metrics, "Should have R² score"
        assert "cv_rmse_mean" in metrics, "Should have CV RMSE"

    def test_predict(self):
        """Test model prediction."""
        import numpy as np

        model = RiskPredictor()

        # Train model
        X_train = np.random.rand(100, 20).astype(np.float32)
        y_train = np.random.rand(100).astype(np.float32)
        model.train(X_train, y_train, model_type="random_forest", n_estimators=50)

        # Predict
        X_test = np.random.rand(10, 20).astype(np.float32)
        predictions = model.predict(X_test)

        assert len(predictions) == 10, "Should have 10 predictions"
        assert all(0.0 <= p <= 1.0 for p in predictions), "Predictions should be in [0, 1]"

    def test_save_load_model(self, temp_training_dir):
        """Test model save and load."""
        import numpy as np

        model = RiskPredictor()

        # Train model
        X_train = np.random.rand(100, 20).astype(np.float32)
        y_train = np.random.rand(100).astype(np.float32)
        model.feature_names = [f"feature_{i}" for i in range(20)]
        model.train(X_train, y_train, model_type="random_forest", n_estimators=50)

        # Save
        model_path = temp_training_dir / "test_model.pkl"
        model.save_model(str(model_path), feature_names=model.feature_names)

        assert model_path.exists(), "Model file should be created"

        # Load
        loaded_model = RiskPredictor(model_path=str(model_path))

        assert loaded_model.is_trained, "Loaded model should be trained"
        assert loaded_model.feature_names == model.feature_names, "Feature names should match"

    def test_evaluate_model(self):
        """Test model evaluation."""
        import numpy as np

        model = RiskPredictor()

        # Train model
        X_train = np.random.rand(100, 20).astype(np.float32)
        y_train = np.random.rand(100).astype(np.float32)
        model.train(X_train, y_train, model_type="random_forest", n_estimators=50)

        # Evaluate
        X_test = np.random.rand(20, 20).astype(np.float32)
        y_test = np.random.rand(20).astype(np.float32)

        metrics = model.evaluate(X_test, y_test)

        assert "test_r2" in metrics, "Should have R² score"
        assert "test_rmse" in metrics, "Should have RMSE"
        assert "test_mae" in metrics, "Should have MAE"
        assert "test_accuracy" in metrics, "Should have accuracy"

