"""Tests for ML service."""
from unittest.mock import Mock, patch

import numpy as np
import pytest

from app.services.risk.ml_service import MLService
from tests.factories import ClaimFactory, ClaimLineFactory


@pytest.mark.unit
class TestMLService:
    """Tests for MLService."""

    def test_predict_risk_placeholder(self, db_session):
        """Test placeholder prediction when model not loaded."""
        claim = ClaimFactory(
            is_incomplete=False,
            principal_diagnosis="E11.9",
            total_charge_amount=1000.00,
        )
        db_session.add(claim)
        db_session.commit()

        service = MLService()
        risk = service.predict_risk(claim)

        assert 0 <= risk <= 100
        assert risk < 50  # Should be low risk for valid claim

    def test_predict_risk_incomplete_claim(self, db_session):
        """Test prediction for incomplete claim."""
        claim = ClaimFactory(is_incomplete=True)
        db_session.add(claim)
        db_session.commit()

        service = MLService()
        risk = service.predict_risk(claim)

        assert risk >= 20.0  # Incomplete adds risk

    def test_predict_risk_missing_diagnosis(self, db_session):
        """Test prediction for claim missing principal diagnosis."""
        claim = ClaimFactory(principal_diagnosis=None)
        db_session.add(claim)
        db_session.commit()

        service = MLService()
        risk = service.predict_risk(claim)

        assert risk >= 15.0  # Missing diagnosis adds risk

    def test_predict_risk_many_lines(self, db_session):
        """Test prediction for claim with many lines."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.flush()

        # Add 15 lines
        for i in range(15):
            line = ClaimLineFactory(claim=claim)
            db_session.add(line)
        db_session.commit()

        service = MLService()
        risk = service.predict_risk(claim)

        assert risk >= 10.0  # Many lines adds risk

    def test_predict_risk_high_amount(self, db_session):
        """Test prediction for high-value claim."""
        claim = ClaimFactory(total_charge_amount=15000.00)
        db_session.add(claim)
        db_session.commit()

        service = MLService()
        risk = service.predict_risk(claim)

        assert risk >= 10.0  # High amount adds risk

    def test_predict_risk_combined_factors(self, db_session):
        """Test prediction with multiple risk factors."""
        claim = ClaimFactory(
            is_incomplete=True,
            principal_diagnosis=None,
            total_charge_amount=15000.00,
        )
        db_session.add(claim)
        db_session.flush()

        for i in range(15):
            line = ClaimLineFactory(claim=claim)
            db_session.add(line)
        db_session.commit()

        service = MLService()
        risk = service.predict_risk(claim)

        assert risk >= 50.0  # Multiple factors should increase risk

    def test_predict_risk_capped_at_100(self, db_session):
        """Test that risk is capped at 100."""
        claim = ClaimFactory(
            is_incomplete=True,
            principal_diagnosis=None,
            total_charge_amount=50000.00,
        )
        db_session.add(claim)
        db_session.flush()

        for i in range(20):
            line = ClaimLineFactory(claim=claim)
            db_session.add(line)
        db_session.commit()

        service = MLService()
        risk = service.predict_risk(claim)

        assert risk <= 100.0

    def test_extract_features(self, db_session):
        """Test feature extraction."""
        claim = ClaimFactory(
            total_charge_amount=2000.00,
            diagnosis_codes=["E11.9", "I10"],
            is_incomplete=False,
        )
        db_session.add(claim)
        db_session.flush()

        line1 = ClaimLineFactory(claim=claim)
        line2 = ClaimLineFactory(claim=claim)
        db_session.add(line1)
        db_session.add(line2)
        db_session.commit()

        service = MLService()
        features = service._extract_features(claim)

        assert isinstance(features, np.ndarray)
        assert len(features) == 4
        assert features[0] == 2000.00  # Charge amount
        assert features[1] == 2  # Diagnosis count
        assert features[2] == 2  # Line count
        assert features[3] == 0.0  # Not incomplete

    def test_extract_features_none_values(self, db_session):
        """Test feature extraction with None values."""
        claim = ClaimFactory(
            total_charge_amount=None,
            diagnosis_codes=None,
        )
        db_session.add(claim)
        db_session.commit()

        service = MLService()
        features = service._extract_features(claim)

        assert features[0] == 0.0  # None charge amount becomes 0
        assert features[1] == 0  # None diagnosis codes becomes 0
        assert features[2] == 0  # No lines

    @patch("app.services.risk.ml_service.MLService._placeholder_prediction")
    def test_predict_risk_model_loaded(self, mock_placeholder, db_session):
        """Test prediction when model is loaded."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        service = MLService()
        service.model_loaded = True
        service.model = Mock()
        service.model.predict.return_value = np.array([0.5])  # 50% risk

        risk = service.predict_risk(claim)

        assert risk == 50.0  # 0.5 * 100
        service.model.predict.assert_called_once()
        mock_placeholder.assert_not_called()

    @patch("app.services.risk.ml_service.MLService._placeholder_prediction")
    def test_predict_risk_model_error(self, mock_placeholder, db_session):
        """Test prediction when model raises error."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        service = MLService()
        service.model_loaded = True
        service.model = Mock()
        service.model.predict.side_effect = Exception("Model error")
        mock_placeholder.return_value = 25.0

        risk = service.predict_risk(claim)

        assert risk == 25.0  # Falls back to placeholder
        mock_placeholder.assert_called_once_with(claim)

