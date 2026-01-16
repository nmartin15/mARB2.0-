"""Tests for learning/pattern detection API endpoints."""
import os
from unittest.mock import MagicMock, patch
import pytest

from tests.factories import PayerFactory, ClaimFactory, ProviderFactory, DenialPatternFactory


# Note: The learning routes use PatternDetector which needs to be mocked
# since it has database dependencies that may not be fully set up in tests
# The conftest should already set REQUIRE_AUTH=false, but we ensure it here


@pytest.mark.api
class TestDetectPatternsForPayer:
    """Tests for POST /api/v1/patterns/detect/{payer_id} endpoint."""

    def test_detect_patterns_for_payer_success(self, client, db_session):
        """Test detecting patterns for a specific payer."""
        payer = PayerFactory()
        db_session.commit()

        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_pattern = MagicMock()
            mock_pattern.id = 1
            mock_pattern.pattern_type = "denial_frequency"
            mock_pattern.pattern_description = "High denial rate"
            mock_pattern.denial_reason_code = "CO-50"
            mock_pattern.occurrence_count = 10
            mock_pattern.frequency = 0.8
            mock_pattern.confidence_score = 0.95
            mock_pattern.conditions = {"threshold": 0.7}
            mock_pattern.first_seen = None
            mock_pattern.last_seen = None
            mock_detector.detect_patterns_for_payer.return_value = [mock_pattern]
            mock_detector_class.return_value = mock_detector

            response = client.post(f"/api/v1/patterns/detect/{payer.id}", params={"days_back": 90})

            assert response.status_code == 200
            data = response.json()
            assert data["payer_id"] == payer.id
            assert data["payer_name"] == payer.name
            assert data["patterns_detected"] == 1
            assert len(data["patterns"]) == 1
            assert data["patterns"][0]["pattern_type"] == "denial_frequency"

    def test_detect_patterns_for_payer_not_found(self, client, db_session):
        """Test detecting patterns for non-existent payer."""
        response = client.post("/api/v1/patterns/detect/99999", params={"days_back": 90})

        assert response.status_code == 404

    def test_detect_patterns_for_payer_custom_days_back(self, client, db_session):
        """Test detecting patterns with custom days_back parameter."""
        payer = PayerFactory()
        db_session.commit()

        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.detect_patterns_for_payer.return_value = []
            mock_detector_class.return_value = mock_detector

            response = client.post(f"/api/v1/patterns/detect/{payer.id}", params={"days_back": 180})

            assert response.status_code == 200
            data = response.json()
            assert data["patterns_detected"] == 0
            assert data["patterns"] == []
            mock_detector.detect_patterns_for_payer.assert_called_once_with(payer.id, 180)

    def test_detect_patterns_for_payer_invalid_days_back(self, client, db_session):
        """Test detecting patterns with invalid days_back parameter."""
        payer = PayerFactory()
        db_session.commit()

        # days_back too large (max is 365)
        response = client.post(f"/api/v1/patterns/detect/{payer.id}", params={"days_back": 500})
        assert response.status_code == 422
        data = response.json()
        # Check for validation error format (could be "detail" or custom error format)
        assert "detail" in data or "details" in data or "message" in data

        # days_back too small (min is 1)
        response = client.post(f"/api/v1/patterns/detect/{payer.id}", params={"days_back": 0})
        assert response.status_code == 422
        data = response.json()
        # Check for validation error format
        assert "detail" in data or "details" in data or "message" in data


@pytest.mark.api
class TestDetectPatternsForAllPayers:
    """Tests for POST /api/v1/patterns/detect-all endpoint."""

    def test_detect_patterns_for_all_payers_success(self, client, db_session):
        """Test detecting patterns for all payers."""
        payer1 = PayerFactory()
        payer2 = PayerFactory()
        db_session.commit()

        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.detect_all_patterns.return_value = {
                payer1.id: [MagicMock(), MagicMock()],
                payer2.id: [MagicMock()],
            }
            mock_detector_class.return_value = mock_detector

            response = client.post("/api/v1/patterns/detect-all", params={"days_back": 90})

            assert response.status_code == 200
            data = response.json()
            assert data["payers_processed"] == 2
            assert data["total_patterns"] == 3
            assert len(data["patterns_by_payer"]) == 2

    def test_detect_patterns_for_all_payers_default_days_back(self, client, db_session):
        """Test detecting patterns with default days_back."""
        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.detect_all_patterns.return_value = {}
            mock_detector_class.return_value = mock_detector

            response = client.post("/api/v1/patterns/detect-all")

            assert response.status_code == 200
            data = response.json()
            assert data["payers_processed"] == 0
            assert data["total_patterns"] == 0
            mock_detector.detect_all_patterns.assert_called_once_with(90)


@pytest.mark.api
class TestGetPatternsForPayer:
    """Tests for GET /api/v1/patterns/payer/{payer_id} endpoint."""

    def test_get_patterns_for_payer_success(self, client, db_session):
        """Test getting patterns for a payer."""
        payer = PayerFactory()
        db_session.commit()

        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_pattern = MagicMock()
            mock_pattern.id = 1
            mock_pattern.pattern_type = "denial_frequency"
            mock_pattern.pattern_description = "High denial rate"
            mock_pattern.denial_reason_code = "CO-50"
            mock_pattern.occurrence_count = 10
            mock_pattern.frequency = 0.8
            mock_pattern.confidence_score = 0.95
            mock_pattern.conditions = {"threshold": 0.7}
            mock_pattern.first_seen = None
            mock_pattern.last_seen = None
            mock_detector.get_patterns_for_payer.return_value = [mock_pattern]
            mock_detector_class.return_value = mock_detector

            response = client.get(f"/api/v1/patterns/payer/{payer.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["payer_id"] == payer.id
            assert data["payer_name"] == payer.name
            assert len(data["patterns"]) == 1

    def test_get_patterns_for_payer_not_found(self, client, db_session):
        """Test getting patterns for non-existent payer."""
        response = client.get("/api/v1/patterns/payer/99999")

        assert response.status_code == 404

    def test_get_patterns_for_payer_no_patterns(self, client, db_session):
        """Test getting patterns when payer has no patterns."""
        payer = PayerFactory()
        db_session.commit()

        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.get_patterns_for_payer.return_value = []
            mock_detector_class.return_value = mock_detector

            response = client.get(f"/api/v1/patterns/payer/{payer.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["patterns"] == []


@pytest.mark.api
class TestAnalyzeClaimForPatterns:
    """Tests for POST /api/v1/patterns/analyze-claim/{claim_id} endpoint."""

    def test_analyze_claim_for_patterns_success(self, client, db_session):
        """Test analyzing a claim for patterns."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        db_session.commit()

        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            # analyze_claim_for_patterns returns a list of pattern objects or dicts
            mock_detector.analyze_claim_for_patterns.return_value = [
                {"pattern_id": 1, "match_score": 0.9}
            ]
            mock_detector_class.return_value = mock_detector

            response = client.post(f"/api/v1/patterns/analyze-claim/{claim.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["claim_id"] == claim.id
            assert data["payer_id"] == payer.id
            assert data["matching_patterns_count"] == 1
            # The response should include matching_patterns
            assert "matching_patterns" in data

    def test_analyze_claim_for_patterns_not_found(self, client, db_session):
        """Test analyzing non-existent claim."""
        # Don't patch PatternDetector - let it fail naturally when claim not found
        response = client.post("/api/v1/patterns/analyze-claim/99999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower() or "Claim" in data["message"]

    def test_analyze_claim_for_patterns_no_matches(self, client, db_session):
        """Test analyzing claim with no matching patterns."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        db_session.commit()

        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.analyze_claim_for_patterns.return_value = []
            mock_detector_class.return_value = mock_detector

            response = client.post(f"/api/v1/patterns/analyze-claim/{claim.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["claim_id"] == claim.id
            assert data["payer_id"] == payer.id
            assert data["matching_patterns_count"] == 0
            assert data["matching_patterns"] == []
            mock_detector.analyze_claim_for_patterns.assert_called_once_with(claim.id)

    def test_detect_patterns_for_payer_empty_result(self, client, db_session):
        """Test detecting patterns when no patterns are found."""
        payer = PayerFactory()
        db_session.commit()

        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.detect_patterns_for_payer.return_value = []
            mock_detector_class.return_value = mock_detector

            response = client.post(f"/api/v1/patterns/detect/{payer.id}", params={"days_back": 90})

            assert response.status_code == 200
            data = response.json()
            assert data["patterns_detected"] == 0
            assert data["patterns"] == []

    def test_detect_patterns_for_payer_with_dates(self, client, db_session):
        """Test detecting patterns with first_seen and last_seen dates."""
        from datetime import datetime, timedelta

        payer = PayerFactory()
        db_session.commit()

        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_pattern = MagicMock()
            mock_pattern.id = 1
            mock_pattern.pattern_type = "denial_frequency"
            mock_pattern.pattern_description = "High denial rate"
            mock_pattern.denial_reason_code = "CO-50"
            mock_pattern.occurrence_count = 10
            mock_pattern.frequency = 0.8
            mock_pattern.confidence_score = 0.95
            mock_pattern.conditions = {"threshold": 0.7}
            mock_pattern.first_seen = datetime.now() - timedelta(days=30)
            mock_pattern.last_seen = datetime.now()
            mock_detector.detect_patterns_for_payer.return_value = [mock_pattern]
            mock_detector_class.return_value = mock_detector

            response = client.post(f"/api/v1/patterns/detect/{payer.id}", params={"days_back": 90})

            assert response.status_code == 200
            data = response.json()
            assert len(data["patterns"]) == 1
            assert data["patterns"][0]["first_seen"] is not None
            assert data["patterns"][0]["last_seen"] is not None

    def test_detect_patterns_for_all_payers_empty(self, client, db_session):
        """Test detecting patterns for all payers when no payers exist."""
        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.detect_all_patterns.return_value = {}
            mock_detector_class.return_value = mock_detector

            response = client.post("/api/v1/patterns/detect-all", params={"days_back": 90})

            assert response.status_code == 200
            data = response.json()
            assert data["payers_processed"] == 0
            assert data["total_patterns"] == 0

    def test_get_patterns_for_payer_with_multiple_patterns(self, client, db_session):
        """Test getting multiple patterns for a payer."""
        payer = PayerFactory()
        db_session.commit()

        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_pattern1 = MagicMock()
            mock_pattern1.id = 1
            mock_pattern1.pattern_type = "denial_frequency"
            mock_pattern1.pattern_description = "High denial rate"
            mock_pattern1.denial_reason_code = "CO-50"
            mock_pattern1.occurrence_count = 10
            mock_pattern1.frequency = 0.8
            mock_pattern1.confidence_score = 0.95
            mock_pattern1.conditions = {"threshold": 0.7}
            mock_pattern1.first_seen = None
            mock_pattern1.last_seen = None

            mock_pattern2 = MagicMock()
            mock_pattern2.id = 2
            mock_pattern2.pattern_type = "procedure_code"
            mock_pattern2.pattern_description = "Procedure code pattern"
            mock_pattern2.denial_reason_code = "CO-51"
            mock_pattern2.occurrence_count = 5
            mock_pattern2.frequency = 0.6
            mock_pattern2.confidence_score = 0.85
            mock_pattern2.conditions = {"code": "99213"}
            mock_pattern2.first_seen = None
            mock_pattern2.last_seen = None

            mock_detector.get_patterns_for_payer.return_value = [mock_pattern1, mock_pattern2]
            mock_detector_class.return_value = mock_detector

            response = client.get(f"/api/v1/patterns/payer/{payer.id}")

            assert response.status_code == 200
            data = response.json()
            assert len(data["patterns"]) == 2
            assert data["patterns"][0]["pattern_type"] == "denial_frequency"
            assert data["patterns"][1]["pattern_type"] == "procedure_code"

    def test_analyze_claim_for_patterns_with_multiple_matches(self, client, db_session):
        """Test analyzing claim with multiple matching patterns."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        db_session.commit()

        with patch("app.api.routes.learning.PatternDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.analyze_claim_for_patterns.return_value = [
                {"pattern_id": 1, "match_score": 0.9},
                {"pattern_id": 2, "match_score": 0.7},
            ]
            mock_detector_class.return_value = mock_detector

            response = client.post(f"/api/v1/patterns/analyze-claim/{claim.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["matching_patterns_count"] == 2
            assert len(data["matching_patterns"]) == 2

