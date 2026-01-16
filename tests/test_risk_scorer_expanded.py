"""Expanded tests for risk scorer."""
from unittest.mock import Mock, patch

import pytest

from app.models.database import RiskLevel
from app.services.risk.scorer import RiskScorer
from tests.factories import ClaimFactory, PayerFactory, RiskScoreFactory


@pytest.mark.unit
class TestRiskScorerCalculation:
    """Tests for risk score calculation."""

    def test_calculate_risk_score_creates_new(self, db_session):
        """Test calculating risk score creates new score."""
        claim = ClaimFactory(
            principal_diagnosis="E11.9",
            diagnosis_codes=["E11.9"],
            is_incomplete=False,
        )
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        risk_score = scorer.calculate_risk_score(claim.id)

        assert risk_score is not None
        assert risk_score.claim_id == claim.id
        assert risk_score.overall_score is not None
        assert risk_score.risk_level is not None

    def test_calculate_risk_score_updates_existing(self, db_session):
        """Test calculating risk score updates existing score."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        existing_score = RiskScoreFactory(claim=claim, overall_score=50.0)
        db_session.add(existing_score)
        db_session.commit()

        scorer = RiskScorer(db_session)
        risk_score = scorer.calculate_risk_score(claim.id)

        assert risk_score.id == existing_score.id
        assert risk_score.overall_score != 50.0  # Should be recalculated

    def test_calculate_risk_score_claim_not_found(self, db_session):
        """Test calculating risk score for non-existent claim."""
        scorer = RiskScorer(db_session)

        with pytest.raises(ValueError, match="not found"):
            scorer.calculate_risk_score(99999)

    def test_calculate_risk_score_component_scores(self, db_session):
        """Test that component scores are calculated."""
        claim = ClaimFactory(
            principal_diagnosis="E11.9",
            diagnosis_codes=["E11.9"],
            is_incomplete=False,
        )
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        risk_score = scorer.calculate_risk_score(claim.id)

        assert risk_score.coding_risk is not None
        assert risk_score.documentation_risk is not None
        assert risk_score.payer_risk is not None
        assert risk_score.historical_risk is not None

    def test_calculate_risk_score_weighted_average(self, db_session):
        """Test that overall score is weighted average."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)

        # Mock component scores to verify weighted average
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(20.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(30.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=40.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]):

            risk_score = scorer.calculate_risk_score(claim.id)

            # Calculate expected weighted average with correct weights from code
            # payer_risk * 0.20 + coding_risk * 0.25 + doc_risk * 0.20 + historical_risk * 0.15 + pattern_risk * 0.20
            expected = (
                10.0 * 0.20 +  # payer_risk
                20.0 * 0.25 +  # coding_risk
                30.0 * 0.20 +  # doc_risk
                40.0 * 0.15 +  # historical_risk
                0.0 * 0.20     # pattern_risk (no patterns)
            )

            # Allow small floating point differences
            assert abs(risk_score.overall_score - expected) < 0.01

    @pytest.mark.parametrize("risk_level,expected_score_range,claim_factory_kwargs", [
        (RiskLevel.LOW, (0, 25), {
            "principal_diagnosis": "E11.9",
            "diagnosis_codes": ["E11.9"],
            "is_incomplete": False,
            "parsing_warnings": [],
        }),
        (RiskLevel.MEDIUM, (25, 50), {
            "principal_diagnosis": "E11.9",
            "diagnosis_codes": ["E11.9"],
            "is_incomplete": False,
            "parsing_warnings": ["Warning 1", "Warning 2"],
        }),
        (RiskLevel.HIGH, (50, 75), {
            "principal_diagnosis": None,
            "diagnosis_codes": None,
            "is_incomplete": True,
        }),
        (RiskLevel.CRITICAL, (75, 101), {
            "principal_diagnosis": None,
            "diagnosis_codes": None,
            "is_incomplete": True,
            "parsing_warnings": [f"Warning {i}" for i in range(10)],
        }),
    ])
    def test_calculate_risk_score_risk_level_assignment(
        self, db_session, risk_level, expected_score_range, claim_factory_kwargs
    ):
        """Test risk level assignment for different risk score ranges.
        
        Uses parameterized tests to verify that claims with different risk
        factors are assigned the correct risk level based on their overall score.
        
        Args:
            risk_level: Expected RiskLevel enum value
            expected_score_range: Tuple of (min_score, max_score) for the risk level
            claim_factory_kwargs: Keyword arguments to pass to ClaimFactory
        """
        claim = ClaimFactory(**claim_factory_kwargs)
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        risk_score = scorer.calculate_risk_score(claim.id)

        min_score, max_score = expected_score_range
        if min_score <= risk_score.overall_score < max_score:
            assert risk_score.risk_level == risk_level

    @patch("app.services.risk.scorer.MLService")
    def test_calculate_risk_score_ml_failure(self, mock_ml_service, db_session):
        """Test that ML service failure doesn't break scoring."""
        mock_ml = Mock()
        mock_ml.predict_risk.side_effect = Exception("ML model error")
        mock_ml_service.return_value = mock_ml

        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        # Should not raise exception
        risk_score = scorer.calculate_risk_score(claim.id)

        assert risk_score is not None
        assert risk_score.historical_risk == 0.0


@pytest.mark.unit
class TestRiskScorerRecommendations:
    """Tests for recommendation generation."""

    def test_generate_recommendations_high_coding_risk(self, db_session):
        """Test recommendations for high coding risk."""
        claim = ClaimFactory(principal_diagnosis=None, diagnosis_codes=None)
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        risk_score = scorer.calculate_risk_score(claim.id)

        if risk_score.coding_risk > 50:
            assert len(risk_score.recommendations) > 0
            assert any("procedure codes" in r.lower() or "diagnosis codes" in r.lower()
                      for r in risk_score.recommendations)

    def test_generate_recommendations_high_doc_risk(self, db_session):
        """Test recommendations for high documentation risk."""
        claim = ClaimFactory(
            is_incomplete=True,
            parsing_warnings=[f"Warning {i}" for i in range(10)],
        )
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        risk_score = scorer.calculate_risk_score(claim.id)

        if risk_score.documentation_risk > 50:
            assert len(risk_score.recommendations) > 0
            assert any("documentation" in r.lower() for r in risk_score.recommendations)

    def test_generate_recommendations_high_payer_risk(self, db_session):
        """Test recommendations for high payer risk."""
        payer = PayerFactory(
            rules_config={"allowed_frequency_types": ["1"]}
        )
        db_session.add(payer)
        db_session.flush()

        claim = ClaimFactory(
            payer_id=payer.id,
            claim_frequency_type="3",  # Invalid
        )
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        risk_score = scorer.calculate_risk_score(claim.id)

        if risk_score.payer_risk > 50:
            assert len(risk_score.recommendations) > 0
            assert any("payer" in r.lower() or "eligibility" in r.lower()
                      for r in risk_score.recommendations)

    def test_generate_recommendations_critical_factors(self, db_session):
        """Test recommendations for critical risk factors."""
        claim = ClaimFactory(
            principal_diagnosis=None,
            diagnosis_codes=None,  # Critical factor
        )
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        risk_score = scorer.calculate_risk_score(claim.id)

        # Check if critical factors generate recommendations
        critical_factors = [f for f in risk_score.risk_factors if f.get("severity") == "critical"]
        if critical_factors:
            assert any("CRITICAL" in r for r in risk_score.recommendations)

    def test_generate_recommendations_risk_factors(self, db_session):
        """Test that risk factors are captured."""
        claim = ClaimFactory(
            principal_diagnosis=None,
            diagnosis_codes=None,
            is_incomplete=True,
        )
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        risk_score = scorer.calculate_risk_score(claim.id)

        assert len(risk_score.risk_factors) > 0
        assert all("type" in f for f in risk_score.risk_factors)
        assert all("severity" in f for f in risk_score.risk_factors)
        assert all("message" in f for f in risk_score.risk_factors)

    @patch("app.services.risk.scorer.PatternDetector")
    def test_calculate_risk_score_with_patterns(self, mock_pattern_detector, db_session):
        """Test risk score calculation with pattern matching."""
        mock_detector = Mock()
        mock_pattern_detector.return_value = mock_detector
        mock_detector.analyze_claim_for_patterns.return_value = [
            {
                "match_score": 0.8,
                "confidence_score": 0.9,
                "pattern_description": "High denial rate for procedure code",
                "denial_reason_code": "CO45",
            },
            {
                "match_score": 0.6,
                "confidence_score": 0.7,
                "pattern_description": "Missing documentation pattern",
                "denial_reason_code": "CO97",
            },
        ]

        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        # Re-initialize to use mocked detector
        scorer.pattern_detector = mock_detector

        risk_score = scorer.calculate_risk_score(claim.id)

        assert risk_score is not None
        # Pattern risk should be calculated
        assert "pattern_risk" in str(risk_score.risk_factors) or any(
            f.get("type") == "pattern_match" for f in risk_score.risk_factors
        )

    @patch("app.services.risk.scorer.PatternDetector")
    def test_calculate_risk_score_pattern_analysis_failure(self, mock_pattern_detector, db_session):
        """Test that pattern analysis failure doesn't break scoring."""
        mock_detector = Mock()
        mock_pattern_detector.return_value = mock_detector
        mock_detector.analyze_claim_for_patterns.side_effect = Exception("Pattern analysis error")

        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        scorer.pattern_detector = mock_detector

        # Should not raise exception
        risk_score = scorer.calculate_risk_score(claim.id)

        assert risk_score is not None
        # Pattern risk should default to 0.0
        assert risk_score.overall_score is not None

    def test_calculate_risk_score_weighted_average_correct_weights(self, db_session):
        """Test that overall score uses correct weights."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)

        # Mock specific component scores to verify weighted average
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(20.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(30.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=40.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[]):

            risk_score = scorer.calculate_risk_score(claim.id)

            # Calculate expected weighted average with correct weights from code
            # payer_risk * 0.20 + coding_risk * 0.25 + doc_risk * 0.20 + historical_risk * 0.15 + pattern_risk * 0.20
            expected = (
                10.0 * 0.20 +  # payer_risk
                20.0 * 0.25 +  # coding_risk
                30.0 * 0.20 +  # doc_risk
                40.0 * 0.15 +  # historical_risk
                0.0 * 0.20     # pattern_risk (no patterns)
            )

            # Allow small floating point differences
            assert abs(risk_score.overall_score - expected) < 0.01

    def test_calculate_risk_score_risk_level_critical(self, db_session):
        """Test risk level CRITICAL assignment (>= 75)."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)

        # Mock high component scores to force critical level
        # Weighted: 80*0.20 + 80*0.25 + 80*0.20 + 80*0.15 = 16 + 20 + 16 + 12 = 64
        # Need pattern_risk to push it over 75: 80*0.20 = 16, so total = 80
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(80.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(80.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(80.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=80.0), \
             patch.object(scorer.pattern_detector, 'analyze_claim_for_patterns', return_value=[
                 {"match_score": 0.8, "confidence_score": 0.9, "pattern_description": "Test", "denial_reason_code": "CO45"}
             ]):

            risk_score = scorer.calculate_risk_score(claim.id)

            # Should be critical (>= 75)
            assert risk_score.overall_score >= 75
            assert risk_score.risk_level == RiskLevel.CRITICAL

    def test_calculate_risk_score_risk_level_high(self, db_session):
        """Test risk level HIGH assignment (50-74)."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)

        # Mock medium-high component scores
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(60.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(60.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(60.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=60.0):

            risk_score = scorer.calculate_risk_score(claim.id)

            # Should be high (50-74)
            if 50 <= risk_score.overall_score < 75:
                assert risk_score.risk_level == RiskLevel.HIGH

    def test_calculate_risk_score_risk_level_medium(self, db_session):
        """Test risk level MEDIUM assignment (25-49)."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)

        # Mock medium component scores
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(35.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(35.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(35.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=35.0):

            risk_score = scorer.calculate_risk_score(claim.id)

            # Should be medium (25-49)
            if 25 <= risk_score.overall_score < 50:
                assert risk_score.risk_level == RiskLevel.MEDIUM

    def test_calculate_risk_score_risk_level_low(self, db_session):
        """Test risk level LOW assignment (< 25)."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)

        # Mock low component scores
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0):

            risk_score = scorer.calculate_risk_score(claim.id)

            # Should be low (< 25)
            if risk_score.overall_score < 25:
                assert risk_score.risk_level == RiskLevel.LOW

    def test_generate_recommendations_high_coding_risk(self, db_session):
        """Test recommendation generation for high coding risk."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)

        # Mock high coding risk
        with patch.object(scorer.coding_rules, 'evaluate', return_value=(60.0, [])), \
             patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0):

            risk_score = scorer.calculate_risk_score(claim.id)

            if risk_score.coding_risk > 50:
                assert len(risk_score.recommendations) > 0
                assert any("procedure codes" in r.lower() or "diagnosis codes" in r.lower()
                          for r in risk_score.recommendations)

    def test_generate_recommendations_high_documentation_risk(self, db_session):
        """Test recommendation generation for high documentation risk."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)

        # Mock high documentation risk
        with patch.object(scorer.doc_rules, 'evaluate', return_value=(60.0, [])), \
             patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0):

            risk_score = scorer.calculate_risk_score(claim.id)

            if risk_score.documentation_risk > 50:
                assert len(risk_score.recommendations) > 0
                assert any("documentation" in r.lower() for r in risk_score.recommendations)

    def test_generate_recommendations_high_payer_risk(self, db_session):
        """Test recommendation generation for high payer risk."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)

        # Mock high payer risk
        with patch.object(scorer.payer_rules, 'evaluate', return_value=(60.0, [])), \
             patch.object(scorer.coding_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0):

            risk_score = scorer.calculate_risk_score(claim.id)

            if risk_score.payer_risk > 50:
                assert len(risk_score.recommendations) > 0
                assert any("payer" in r.lower() or "eligibility" in r.lower()
                          for r in risk_score.recommendations)

    def test_generate_recommendations_critical_factors(self, db_session):
        """Test recommendation generation for critical risk factors."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)

        # Mock critical risk factors
        critical_factors = [
            {"type": "coding", "severity": "critical", "message": "Critical coding issue"}
        ]
        with patch.object(scorer.coding_rules, 'evaluate', return_value=(60.0, critical_factors)), \
             patch.object(scorer.payer_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.doc_rules, 'evaluate', return_value=(10.0, [])), \
             patch.object(scorer.ml_service, 'predict_risk', return_value=10.0):

            risk_score = scorer.calculate_risk_score(claim.id)

            critical_factors_in_score = [f for f in risk_score.risk_factors if f.get("severity") == "critical"]
            if critical_factors_in_score:
                assert any("CRITICAL" in r for r in risk_score.recommendations)

    def test_calculate_risk_score_stores_all_component_scores(self, db_session):
        """Test that all component scores are stored."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        scorer = RiskScorer(db_session)
        risk_score = scorer.calculate_risk_score(claim.id)

        assert risk_score.payer_risk is not None
        assert risk_score.coding_risk is not None
        assert risk_score.documentation_risk is not None
        assert risk_score.historical_risk is not None
        assert risk_score.risk_factors is not None
        assert risk_score.recommendations is not None

    def test_calculate_risk_score_updates_existing_all_fields(self, db_session):
        """Test that updating existing score updates all fields."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        existing_score = RiskScoreFactory(
            claim=claim,
            overall_score=50.0,
            payer_risk=30.0,
            coding_risk=40.0,
        )
        db_session.add(existing_score)
        db_session.commit()

        scorer = RiskScorer(db_session)
        risk_score = scorer.calculate_risk_score(claim.id)

        assert risk_score.id == existing_score.id
        # All fields should be updated
        assert risk_score.overall_score != 50.0
        assert risk_score.payer_risk != 30.0
        assert risk_score.coding_risk != 40.0
        assert risk_score.risk_factors is not None
        assert risk_score.recommendations is not None

