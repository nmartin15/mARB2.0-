"""Comprehensive tests for RiskScorer to improve coverage."""
from unittest.mock import Mock, patch, MagicMock

import pytest

from app.models.database import RiskLevel, Claim, RiskScore
from app.services.risk.scorer import RiskScorer
from tests.factories import ClaimFactory, PayerFactory, ProviderFactory, RiskScoreFactory


@pytest.mark.unit
class TestRiskScorerComprehensive:
    """Comprehensive tests for RiskScorer."""

    def test_init_with_custom_weights(self, db_session):
        """Test RiskScorer initialization with custom weights."""
        custom_weights = {
            "payer_risk": 0.30,
            "coding_risk": 0.30,
            "doc_risk": 0.20,
            "historical_risk": 0.10,
            "pattern_risk": 0.10,
        }
        scorer = RiskScorer(db_session, weights=custom_weights)
        assert scorer.weights == custom_weights

    def test_init_with_default_weights(self, db_session):
        """Test RiskScorer initialization with default weights."""
        scorer = RiskScorer(db_session)
        assert scorer.weights is not None
        assert "payer_risk" in scorer.weights
        assert "coding_risk" in scorer.weights
        assert "doc_risk" in scorer.weights
        assert "historical_risk" in scorer.weights
        assert "pattern_risk" in scorer.weights

    def test_init_with_invalid_weights_warns(self, db_session):
        """Test RiskScorer initialization with invalid weights logs warning."""
        invalid_weights = {
            "payer_risk": 0.50,
            "coding_risk": 0.50,  # Sum > 1.0
            "doc_risk": 0.20,
            "historical_risk": 0.15,
            "pattern_risk": 0.20,
        }
        with patch("app.services.risk.scorer.logger") as mock_logger:
            scorer = RiskScorer(db_session, weights=invalid_weights)
            # Should log warning about weights not summing to 1.0
            assert mock_logger.warning.called

    def test_calculate_risk_score_critical_level(self, db_session):
        """Test risk score calculation results in CRITICAL level."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(80.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(80.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(80.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=80.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]):

            risk_score = scorer.calculate_risk_score(claim.id)
            assert risk_score.risk_level == RiskLevel.CRITICAL
            assert risk_score.overall_score >= 75

    def test_calculate_risk_score_high_level(self, db_session):
        """Test risk score calculation results in HIGH level."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(60.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(60.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(60.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=60.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]):

            risk_score = scorer.calculate_risk_score(claim.id)
            assert risk_score.risk_level == RiskLevel.HIGH
            assert 50 <= risk_score.overall_score < 75

    def test_calculate_risk_score_medium_level(self, db_session):
        """Test risk score calculation results in MEDIUM level."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(30.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(30.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(30.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=30.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]):

            risk_score = scorer.calculate_risk_score(claim.id)
            assert risk_score.risk_level == RiskLevel.MEDIUM
            assert 25 <= risk_score.overall_score < 50

    def test_calculate_risk_score_low_level(self, db_session):
        """Test risk score calculation results in LOW level."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]):

            risk_score = scorer.calculate_risk_score(claim.id)
            assert risk_score.risk_level == RiskLevel.LOW
            assert risk_score.overall_score < 25

    def test_calculate_risk_score_ml_service_failure(self, db_session):
        """Test risk score calculation handles ML service failure."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', side_effect=Exception("ML error")), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]), \
             patch("app.services.risk.scorer.logger") as mock_logger:

            risk_score = scorer.calculate_risk_score(claim.id)
            # Should handle error gracefully
            assert risk_score.historical_risk == 0.0
            assert mock_logger.warning.called
            assert any("ML prediction failed" in str(call) for call in mock_logger.warning.call_args_list)

    def test_calculate_risk_score_pattern_detector_failure(self, db_session):
        """Test risk score calculation handles pattern detector failure."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', side_effect=Exception("Pattern error")), \
             patch("app.services.risk.scorer.logger") as mock_logger:

            risk_score = scorer.calculate_risk_score(claim.id)
            # Should handle error gracefully
            assert risk_score.overall_score is not None
            assert mock_logger.warning.called
            assert any("Pattern analysis failed" in str(call) for call in mock_logger.warning.call_args_list)

    def test_calculate_risk_score_with_patterns(self, db_session):
        """Test risk score calculation with matching patterns."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        matching_patterns = [
            {
                "match_score": 0.8,
                "confidence_score": 0.9,
                "pattern_description": "High denial rate for procedure code",
                "denial_reason_code": "CO45",
            },
            {
                "match_score": 0.6,
                "confidence_score": 0.7,
                "pattern_description": "Common denial pattern",
                "denial_reason_code": "CO97",
            },
        ]

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=matching_patterns):

            risk_score = scorer.calculate_risk_score(claim.id)
            # Should include pattern risk factors
            assert len(risk_score.risk_factors) > 0
            pattern_factors = [f for f in risk_score.risk_factors if f.get("type") == "pattern_match"]
            assert len(pattern_factors) > 0

    def test_calculate_risk_score_pattern_risk_calculation(self, db_session):
        """Test pattern risk calculation from matching patterns."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        matching_patterns = [
            {
                "match_score": 0.8,
                "confidence_score": 0.9,
                "pattern_description": "Test pattern",
                "denial_reason_code": "CO45",
            },
        ]

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=0.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=matching_patterns):

            risk_score = scorer.calculate_risk_score(claim.id)
            # Pattern risk should be calculated: 0.8 * 100 * 0.9 = 72.0
            # Overall score should include pattern risk weighted
            assert risk_score.overall_score > 0

    def test_calculate_risk_score_top_3_patterns_only(self, db_session):
        """Test that only top 3 patterns are included in risk factors."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        matching_patterns = [
            {"match_score": 0.9, "confidence_score": 0.9, "pattern_description": "Pattern 1", "denial_reason_code": "CO1"},
            {"match_score": 0.8, "confidence_score": 0.8, "pattern_description": "Pattern 2", "denial_reason_code": "CO2"},
            {"match_score": 0.7, "confidence_score": 0.7, "pattern_description": "Pattern 3", "denial_reason_code": "CO3"},
            {"match_score": 0.6, "confidence_score": 0.6, "pattern_description": "Pattern 4", "denial_reason_code": "CO4"},
            {"match_score": 0.5, "confidence_score": 0.5, "pattern_description": "Pattern 5", "denial_reason_code": "CO5"},
        ]

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=0.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=matching_patterns):

            risk_score = scorer.calculate_risk_score(claim.id)
            pattern_factors = [f for f in risk_score.risk_factors if f.get("type") == "pattern_match"]
            # Should only include top 3 patterns
            assert len(pattern_factors) <= 3

    def test_calculate_risk_score_pattern_severity_high(self, db_session):
        """Test pattern severity classification for high match scores."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        matching_patterns = [
            {
                "match_score": 0.8,  # > 0.7 = high severity
                "confidence_score": 0.9,
                "pattern_description": "High match pattern",
                "denial_reason_code": "CO45",
            },
        ]

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=0.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=matching_patterns):

            risk_score = scorer.calculate_risk_score(claim.id)
            pattern_factors = [f for f in risk_score.risk_factors if f.get("type") == "pattern_match"]
            assert len(pattern_factors) > 0
            assert pattern_factors[0].get("severity") == "high"

    def test_calculate_risk_score_pattern_severity_medium(self, db_session):
        """Test pattern severity classification for medium match scores."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        matching_patterns = [
            {
                "match_score": 0.5,  # <= 0.7 = medium severity
                "confidence_score": 0.6,
                "pattern_description": "Medium match pattern",
                "denial_reason_code": "CO45",
            },
        ]

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=0.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=matching_patterns):

            risk_score = scorer.calculate_risk_score(claim.id)
            pattern_factors = [f for f in risk_score.risk_factors if f.get("type") == "pattern_match"]
            assert len(pattern_factors) > 0
            assert pattern_factors[0].get("severity") == "medium"

    def test_calculate_risk_score_notification_failure(self, db_session):
        """Test risk score calculation handles notification failure."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]), \
             patch("app.services.risk.scorer.notify_risk_score_calculated", side_effect=Exception("Notification error")), \
             patch("app.services.risk.scorer.logger") as mock_logger:

            risk_score = scorer.calculate_risk_score(claim.id)
            # Should not fail, should log warning
            assert risk_score is not None
            assert mock_logger.warning.called
            assert any("Failed to send risk score notification" in str(call) for call in mock_logger.warning.call_args_list)

    def test_calculate_risk_score_caches_result(self, db_session):
        """Test that risk score is cached after calculation."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]), \
             patch("app.services.risk.scorer.cache") as mock_cache:

            risk_score = scorer.calculate_risk_score(claim.id)
            # Should cache the result
            assert mock_cache.set.called

    def test_generate_recommendations_high_coding_risk(self, db_session):
        """Test recommendation generation for high coding risk."""
        scorer = RiskScorer(db_session)
        risk_factors = []
        component_scores = {"coding_risk": 60.0, "documentation_risk": 10.0, "payer_risk": 10.0}
        
        recommendations = scorer._generate_recommendations(risk_factors, component_scores)
        
        assert len(recommendations) > 0
        assert any("procedure codes" in rec.lower() for rec in recommendations)
        assert any("diagnosis codes" in rec.lower() for rec in recommendations)

    def test_generate_recommendations_high_documentation_risk(self, db_session):
        """Test recommendation generation for high documentation risk."""
        scorer = RiskScorer(db_session)
        risk_factors = []
        component_scores = {"coding_risk": 10.0, "documentation_risk": 60.0, "payer_risk": 10.0}
        
        recommendations = scorer._generate_recommendations(risk_factors, component_scores)
        
        assert len(recommendations) > 0
        assert any("documentation" in rec.lower() for rec in recommendations)
        assert any("signatures" in rec.lower() for rec in recommendations)

    def test_generate_recommendations_high_payer_risk(self, db_session):
        """Test recommendation generation for high payer risk."""
        scorer = RiskScorer(db_session)
        risk_factors = []
        component_scores = {"coding_risk": 10.0, "documentation_risk": 10.0, "payer_risk": 60.0}
        
        recommendations = scorer._generate_recommendations(risk_factors, component_scores)
        
        assert len(recommendations) > 0
        assert any("payer" in rec.lower() for rec in recommendations)
        assert any("eligibility" in rec.lower() for rec in recommendations)

    def test_generate_recommendations_critical_factors(self, db_session):
        """Test recommendation generation for critical risk factors."""
        scorer = RiskScorer(db_session)
        risk_factors = [
            {"type": "coding", "severity": "critical", "message": "Critical issue"},
            {"type": "documentation", "severity": "high", "message": "High issue"},
        ]
        component_scores = {"coding_risk": 10.0, "documentation_risk": 10.0, "payer_risk": 10.0}
        
        recommendations = scorer._generate_recommendations(risk_factors, component_scores)
        
        assert len(recommendations) > 0
        assert any("CRITICAL" in rec for rec in recommendations)

    def test_generate_recommendations_no_high_risks(self, db_session):
        """Test recommendation generation when no high risks."""
        scorer = RiskScorer(db_session)
        risk_factors = []
        component_scores = {"coding_risk": 10.0, "documentation_risk": 10.0, "payer_risk": 10.0}
        
        recommendations = scorer._generate_recommendations(risk_factors, component_scores)
        
        # Should return empty list or minimal recommendations
        assert isinstance(recommendations, list)

    def test_calculate_risk_score_eager_loading(self, db_session):
        """Test that claim is loaded with eager loading."""
        payer = PayerFactory()
        provider = ProviderFactory()
        claim = ClaimFactory(payer=payer, provider=provider)
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]):

            # Should not raise error accessing relationships
            risk_score = scorer.calculate_risk_score(claim.id)
            assert risk_score is not None

    def test_calculate_risk_score_with_risk_factors(self, db_session):
        """Test risk score calculation includes risk factors from all components."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        payer_factors = [{"type": "payer", "severity": "high", "message": "Payer issue"}]
        coding_factors = [{"type": "coding", "severity": "medium", "message": "Coding issue"}]
        doc_factors = [{"type": "documentation", "severity": "low", "message": "Doc issue"}]

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, payer_factors)), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, coding_factors)), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, doc_factors)), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]):

            risk_score = scorer.calculate_risk_score(claim.id)
            # Should include all risk factors
            assert len(risk_score.risk_factors) >= 3
            assert any(f.get("type") == "payer" for f in risk_score.risk_factors)
            assert any(f.get("type") == "coding" for f in risk_score.risk_factors)
            assert any(f.get("type") == "documentation" for f in risk_score.risk_factors)

    def test_calculate_risk_score_updates_existing_with_pattern_risk(self, db_session):
        """Test updating existing risk score includes pattern risk in component scores."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        existing_score = RiskScoreFactory(claim=claim, overall_score=50.0)
        db_session.add(existing_score)
        db_session.commit()

        matching_patterns = [
            {
                "match_score": 0.8,
                "confidence_score": 0.9,
                "pattern_description": "Test pattern",
                "denial_reason_code": "CO45",
            },
        ]

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=matching_patterns):

            risk_score = scorer.calculate_risk_score(claim.id)
            assert risk_score.id == existing_score.id
            # Should be updated with new scores
            assert risk_score.overall_score != 50.0

    def test_calculate_risk_score_pattern_missing_fields(self, db_session):
        """Test pattern risk calculation handles missing fields gracefully."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        matching_patterns = [
            {
                "match_score": 0.8,
                # Missing confidence_score
                "pattern_description": "Test pattern",
            },
        ]

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(0.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=0.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=matching_patterns):

            # Should handle missing fields gracefully
            risk_score = scorer.calculate_risk_score(claim.id)
            assert risk_score is not None

    def test_calculate_risk_score_empty_pattern_list(self, db_session):
        """Test risk score calculation with empty pattern list."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]):

            risk_score = scorer.calculate_risk_score(claim.id)
            # Pattern risk should be 0.0
            assert risk_score.overall_score is not None
            # No pattern factors should be added
            pattern_factors = [f for f in risk_score.risk_factors if f.get("type") == "pattern_match"]
            assert len(pattern_factors) == 0
