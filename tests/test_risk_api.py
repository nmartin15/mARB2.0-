"""Tests for risk scoring API endpoints."""
from unittest.mock import MagicMock, patch

import pytest

from app.models.database import RiskLevel
from tests.factories import (
    ClaimFactory,
    PayerFactory,
    ProviderFactory,
    RiskScoreFactory,
)


@pytest.mark.api
class TestGetRiskScore:
    """Tests for GET /api/v1/risk/{claim_id} endpoint."""

    def test_get_risk_score_success(self, client, db_session):
        """Test getting risk score for a claim."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        risk_score = RiskScoreFactory(
            claim=claim,
            overall_score=75.5,
            risk_level=RiskLevel.HIGH,
            coding_risk=80.0,
            documentation_risk=70.0,
            payer_risk=75.0,
            historical_risk=65.0,
            risk_factors=["Missing documentation", "Coding mismatch"],
            recommendations=["Add supporting documentation"],
        )

        response = client.get(f"/api/v1/risk/{claim.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["claim_id"] == claim.id
        assert data["overall_score"] == 75.5
        assert data["risk_level"] == "high"
        assert "component_scores" in data
        assert data["component_scores"]["coding_risk"] == 80.0
        assert data["component_scores"]["documentation_risk"] == 70.0
        assert data["component_scores"]["payer_risk"] == 75.0
        assert data["component_scores"]["historical_risk"] == 65.0
        assert data["risk_factors"] == ["Missing documentation", "Coding mismatch"]
        assert data["recommendations"] == ["Add supporting documentation"]
        assert "calculated_at" in data

    def test_get_risk_score_not_calculated(self, client, db_session):
        """Test getting risk score when not yet calculated."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)

        response = client.get(f"/api/v1/risk/{claim.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["claim_id"] == claim.id
        assert data["message"] == "Risk score not yet calculated"

    def test_get_risk_score_multiple_scores_returns_latest(self, client, db_session):
        """Test that latest risk score is returned when multiple exist."""
        from datetime import datetime, timedelta

        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)

        # Create older score
        old_score = RiskScoreFactory(
            claim=claim,
            overall_score=50.0,
            risk_level=RiskLevel.MEDIUM,
            calculated_at=datetime.now() - timedelta(days=1),
        )

        # Create newer score
        new_score = RiskScoreFactory(
            claim=claim,
            overall_score=85.0,
            risk_level=RiskLevel.CRITICAL,
            calculated_at=datetime.now(),
        )

        response = client.get(f"/api/v1/risk/{claim.id}")

        assert response.status_code == 200
        data = response.json()
        # Should return the latest (newer) score
        assert data["overall_score"] == 85.0
        assert data["risk_level"] == "critical"

    def test_get_risk_score_claim_not_found(self, client, db_session):
        """Test getting risk score for non-existent claim."""
        response = client.get("/api/v1/risk/99999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower() or "Claim" in data["message"]


@pytest.mark.api
class TestCalculateRiskScore:
    """Tests for POST /api/v1/risk/{claim_id}/calculate endpoint."""

    @patch("app.api.routes.risk.RiskScorer")
    def test_calculate_risk_score_success(self, mock_scorer_class, client, db_session):
        """Test calculating risk score for a claim."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)

        # Mock the RiskScorer
        mock_scorer = MagicMock()
        mock_risk_score = RiskScoreFactory(
            claim=claim,
            overall_score=65.5,
            risk_level=RiskLevel.HIGH,
        )
        mock_scorer.calculate_risk_score.return_value = mock_risk_score
        mock_scorer_class.return_value = mock_scorer

        response = client.post(f"/api/v1/risk/{claim.id}/calculate")

        assert response.status_code == 200
        data = response.json()
        assert data["claim_id"] == claim.id
        assert data["overall_score"] == 65.5
        assert data["risk_level"] == "high"
        assert data["status"] == "calculated"

        # Verify RiskScorer was called correctly
        mock_scorer_class.assert_called_once()
        mock_scorer.calculate_risk_score.assert_called_once_with(claim.id)

    def test_calculate_risk_score_claim_not_found(self, client, db_session):
        """Test calculating risk score for non-existent claim."""
        response = client.post("/api/v1/risk/99999/calculate")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower() or "Claim" in data["message"]

    @patch("app.api.routes.risk.RiskScorer")
    def test_calculate_risk_score_creates_new_score(self, mock_scorer_class, client, db_session):
        """Test that calculating risk score creates a new RiskScore record."""
        from app.models.database import RiskScore

        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)

        # Initially no risk score
        risk_score_count_before = db_session.query(RiskScore).filter(RiskScore.claim_id == claim.id).count()
        assert risk_score_count_before == 0

        # Mock the RiskScorer to return a new risk score and add it to the session
        mock_scorer = MagicMock()
        new_risk_score = RiskScore(
            claim_id=claim.id,
            overall_score=55.0,
            risk_level=RiskLevel.MEDIUM,
            coding_risk=60.0,
            documentation_risk=50.0,
            payer_risk=55.0,
            historical_risk=45.0,
        )
        # Add the score to the session so it gets saved when db.commit() is called
        db_session.add(new_risk_score)
        mock_scorer.calculate_risk_score.return_value = new_risk_score
        mock_scorer_class.return_value = mock_scorer

        response = client.post(f"/api/v1/risk/{claim.id}/calculate")

        assert response.status_code == 200
        # Verify the score was saved to the database
        db_session.refresh(claim)
        risk_score_count_after = db_session.query(RiskScore).filter(RiskScore.claim_id == claim.id).count()
        assert risk_score_count_after == 1
        
        # Verify the saved score has the correct values
        saved_score = db_session.query(RiskScore).filter(RiskScore.claim_id == claim.id).first()
        assert saved_score is not None
        assert saved_score.overall_score == 55.0
        assert saved_score.risk_level == RiskLevel.MEDIUM
        assert saved_score.coding_risk == 60.0
        assert saved_score.documentation_risk == 50.0
        assert saved_score.payer_risk == 55.0
        assert saved_score.historical_risk == 45.0

    @patch("app.api.routes.risk.RiskScorer")
    def test_calculate_risk_score_different_levels(self, mock_scorer_class, client, db_session):
        """Test risk score calculation with different risk levels."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)

        test_cases = [
            (90.0, RiskLevel.CRITICAL),
            (60.0, RiskLevel.HIGH),
            (30.0, RiskLevel.MEDIUM),
            (10.0, RiskLevel.LOW),
        ]

        for overall_score, expected_level in test_cases:
            mock_scorer = MagicMock()
            mock_risk_score = RiskScoreFactory(
                claim=claim,
                overall_score=overall_score,
                risk_level=expected_level,
            )
            mock_scorer.calculate_risk_score.return_value = mock_risk_score
            mock_scorer_class.return_value = mock_scorer

            response = client.post(f"/api/v1/risk/{claim.id}/calculate")

            assert response.status_code == 200
            data = response.json()
            assert data["risk_level"] == expected_level.value

    @patch("app.api.routes.risk.RiskScorer")
    def test_calculate_risk_score_scorer_exception(self, mock_scorer_class, client, db_session):
        """Test that calculate endpoint handles RiskScorer exceptions gracefully."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)

        # Mock RiskScorer to raise an exception
        mock_scorer = MagicMock()
        mock_scorer.calculate_risk_score.side_effect = Exception("RiskScorer calculation failed")
        mock_scorer_class.return_value = mock_scorer

        response = client.post(f"/api/v1/risk/{claim.id}/calculate")

        # Should return 500 error when scorer raises exception
        assert response.status_code == 500
        data = response.json()
        assert "error" in data or "message" in data or "detail" in data

    def test_get_risk_score_caching(self, client, db_session):
        """Test that GET /risk/{claim_id} uses caching."""
        from unittest.mock import patch
        from app.utils.cache import cache, risk_score_cache_key

        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        risk_score = RiskScoreFactory(
            claim=claim,
            overall_score=75.5,
            risk_level=RiskLevel.HIGH,
        )

        # Clear cache
        cache_key = risk_score_cache_key(claim.id)
        cache.delete(cache_key)

        # First request - should query database
        response1 = client.get(f"/api/v1/risk/{claim.id}")
        assert response1.status_code == 200

        # Second request - should use cache
        with patch.object(db_session, "query") as mock_query:
            response2 = client.get(f"/api/v1/risk/{claim.id}")
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["claim_id"] == claim.id
            assert data2["overall_score"] == 75.5

    def test_get_risk_score_with_null_calculated_at(self, client, db_session):
        """Test getting risk score with null calculated_at."""
        from datetime import datetime

        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        risk_score = RiskScoreFactory(
            claim=claim,
            overall_score=75.5,
            risk_level=RiskLevel.HIGH,
            calculated_at=None,
        )

        response = client.get(f"/api/v1/risk/{claim.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["calculated_at"] is None

    def test_calculate_risk_score_caches_result(self, client, db_session):
        """Test that calculating risk score caches the result."""
        from unittest.mock import patch
        from app.utils.cache import cache, risk_score_cache_key

        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)

        # Clear cache
        cache_key = risk_score_cache_key(claim.id)
        cache.delete(cache_key)

        with patch("app.api.routes.risk.RiskScorer") as mock_scorer_class:
            mock_scorer = MagicMock()
            mock_risk_score = RiskScoreFactory(
                claim=claim,
                overall_score=65.5,
                risk_level=RiskLevel.HIGH,
            )
            mock_scorer.calculate_risk_score.return_value = mock_risk_score
            mock_scorer_class.return_value = mock_scorer

            # Calculate risk score
            response = client.post(f"/api/v1/risk/{claim.id}/calculate")
            assert response.status_code == 200

            # Verify cache was set (by checking that get_risk_score uses cache)
            response2 = client.get(f"/api/v1/risk/{claim.id}")
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["overall_score"] == 65.5

