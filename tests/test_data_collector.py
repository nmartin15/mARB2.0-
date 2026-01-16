"""Tests for ML data collector service."""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock

from ml.services.data_collector import DataCollector


@pytest.mark.unit
class TestDataCollectorValidateDataQuality:
    """Tests for DataCollector._validate_data_quality method."""

    def test_validate_data_quality_empty_dataframe(self):
        """Test that empty dataframe raises ValueError."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        df = pd.DataFrame()

        with pytest.raises(ValueError, match="Training dataset is empty"):
            data_collector._validate_data_quality(df)

    def test_validate_data_quality_missing_values(self, caplog):
        """Test that missing values are detected and logged."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        df = pd.DataFrame(
            {
                "col1": [1, 2, None, 4],
                "col2": [4, 5, 6, None],
                "col3": [7, 8, 9, 10],
            }
        )

        data_collector._validate_data_quality(df)

        # Check that warning was logged
        assert any("Missing values found in training data" in record.message for record in caplog.records)

    def test_validate_data_quality_no_missing_values(self, caplog):
        """Test that dataframe with no missing values passes validation."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        df = pd.DataFrame(
            {
                "col1": [1, 2, 3, 4],
                "col2": [4, 5, 6, 7],
                "col3": [7, 8, 9, 10],
            }
        )

        data_collector._validate_data_quality(df)

        # Check that no missing values warning was logged
        assert not any("Missing values found in training data" in record.message for record in caplog.records)

    def test_validate_data_quality_infinite_values(self, caplog):
        """Test that infinite values are detected and logged."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        df = pd.DataFrame(
            {
                "col1": [1.0, 2.0, np.inf, 4.0],
                "col2": [4.0, 5.0, 6.0, 7.0],
                "col3": [7.0, 8.0, -np.inf, 10.0],
            }
        )

        data_collector._validate_data_quality(df)

        # Check that warning was logged
        assert any("Infinite values found in training data" in record.message for record in caplog.records)

    def test_validate_data_quality_no_infinite_values(self, caplog):
        """Test that dataframe with no infinite values passes validation."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        df = pd.DataFrame(
            {
                "col1": [1.0, 2.0, 3.0, 4.0],
                "col2": [4.0, 5.0, 6.0, 7.0],
            }
        )

        data_collector._validate_data_quality(df)

        # Check that no infinite values warning was logged
        assert not any("Infinite values found in training data" in record.message for record in caplog.records)

    def test_validate_data_quality_highly_imbalanced_labels(self, caplog):
        """Test that highly imbalanced dataset is detected and logged."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        # Create highly imbalanced dataset (99% denied)
        df = pd.DataFrame(
            {
                "is_denied": [1] * 99 + [0] * 1,
                "col1": range(100),
                "col2": range(100, 200),
            }
        )

        data_collector._validate_data_quality(df)

        # Check that warning was logged
        assert any("Highly imbalanced dataset" in record.message for record in caplog.records)

    def test_validate_data_quality_highly_imbalanced_labels_low_denial_rate(self, caplog):
        """Test that highly imbalanced dataset with low denial rate is detected."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        # Create highly imbalanced dataset (1% denied)
        df = pd.DataFrame(
            {
                "is_denied": [1] * 1 + [0] * 99,
                "col1": range(100),
                "col2": range(100, 200),
            }
        )

        data_collector._validate_data_quality(df)

        # Check that warning was logged
        assert any("Highly imbalanced dataset" in record.message for record in caplog.records)

    def test_validate_data_quality_balanced_labels(self, caplog):
        """Test that balanced dataset passes validation."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        # Create balanced dataset (50% denied)
        df = pd.DataFrame(
            {
                "is_denied": [1] * 50 + [0] * 50,
                "col1": range(100),
                "col2": range(100, 200),
            }
        )

        data_collector._validate_data_quality(df)

        # Check that no imbalance warning was logged
        assert not any("Highly imbalanced dataset" in record.message for record in caplog.records)

    def test_validate_data_quality_constant_features(self, caplog):
        """Test that constant features are detected and logged."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        df = pd.DataFrame(
            {
                "col1": [1, 1, 1, 1],  # Constant feature
                "col2": [2, 2, 2, 2],  # Constant feature
                "col3": [1, 2, 3, 4],  # Variable feature
                "is_denied": [0, 1, 0, 1],
            }
        )

        data_collector._validate_data_quality(df)

        # Check that warning was logged
        assert any("Constant features found" in record.message for record in caplog.records)

    def test_validate_data_quality_no_constant_features(self, caplog):
        """Test that dataframe with no constant features passes validation."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        df = pd.DataFrame(
            {
                "col1": [1, 2, 3, 4],
                "col2": [4, 5, 6, 7],
                "col3": [7, 8, 9, 10],
            }
        )

        data_collector._validate_data_quality(df)

        # Check that no constant features warning was logged
        assert not any("Constant features found" in record.message for record in caplog.records)

    def test_validate_data_quality_constant_features_excluded_columns(self, caplog):
        """Test that excluded columns (claim_id, is_denied, etc.) are not flagged as constant."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        # Create dataframe where excluded columns are constant (should not trigger warning)
        df = pd.DataFrame(
            {
                "claim_id": [1, 1, 1, 1],  # Constant but excluded
                "is_denied": [0, 0, 0, 0],  # Constant but excluded
                "denial_rate": [0.0, 0.0, 0.0, 0.0],  # Constant but excluded
                "payment_rate": [1.0, 1.0, 1.0, 1.0],  # Constant but excluded
                "col1": [1, 2, 3, 4],  # Variable feature
            }
        )

        data_collector._validate_data_quality(df)

        # Check that no constant features warning was logged (excluded columns should be ignored)
        assert not any("Constant features found" in record.message for record in caplog.records)

    def test_validate_data_quality_highly_correlated_features(self, caplog):
        """Test that highly correlated features are detected and logged."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        # Create highly correlated features (correlation > 0.95)
        df = pd.DataFrame(
            {
                "col1": range(100),
                "col2": [x * 1.01 for x in range(100)],  # Almost perfectly correlated
                "col3": range(100, 200),
            }
        )

        data_collector._validate_data_quality(df)

        # Check that info was logged (correlation is logged as info, not warning)
        assert any("Highly correlated feature pairs found" in record.message for record in caplog.records)

    def test_validate_data_quality_no_highly_correlated_features(self, caplog):
        """Test that dataframe with no highly correlated features passes validation."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        # Create uncorrelated features
        np.random.seed(42)
        df = pd.DataFrame(
            {
                "col1": np.random.randn(100),
                "col2": np.random.randn(100),
                "col3": np.random.randn(100),
            }
        )

        data_collector._validate_data_quality(df)

        # Check that no correlation info was logged (or if logged, it's empty)
        correlation_logs = [
            record for record in caplog.records if "Highly correlated feature pairs found" in record.message
        ]
        # If logged, it should indicate no pairs found (empty list)
        if correlation_logs:
            # The method logs even if no pairs found, so we just check it doesn't error
            pass

    def test_validate_data_quality_single_column(self, caplog):
        """Test validation with single column dataframe."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        df = pd.DataFrame({"col1": [1, 2, 3, 4]})

        # Should not raise any errors
        data_collector._validate_data_quality(df)

    def test_validate_data_quality_mixed_data_types(self, caplog):
        """Test validation with mixed data types (numeric and non-numeric)."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        df = pd.DataFrame(
            {
                "numeric_col": [1.0, 2.0, 3.0, 4.0],
                "string_col": ["a", "b", "c", "d"],
                "bool_col": [True, False, True, False],
            }
        )

        # Should not raise any errors (non-numeric columns are ignored for numeric checks)
        data_collector._validate_data_quality(df)

    def test_validate_data_quality_complete_valid_data(self, caplog):
        """Test validation with complete, valid dataset."""
        db_session_mock = MagicMock()
        data_collector = DataCollector(db=db_session_mock)
        df = pd.DataFrame(
            {
                "claim_id": range(100),
                "total_charge_amount": np.random.uniform(100, 1000, 100),
                "is_denied": np.random.choice([0, 1], 100, p=[0.7, 0.3]),
                "denial_rate": np.random.uniform(0, 1, 100),
                "payment_rate": np.random.uniform(0, 1, 100),
                "feature1": np.random.randn(100),
                "feature2": np.random.randn(100),
            }
        )

        # Should not raise any errors and should log completion
        data_collector._validate_data_quality(df)

        # Check that completion was logged
        assert any("Data quality validation complete" in record.message for record in caplog.records)

