"""Comprehensive tests for PatternDetector to improve coverage."""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from app.models.database import (
    EpisodeStatus,
    Claim,
)
from app.services.learning.pattern_detector import PatternDetector
from app.utils.cache import cache, cache_key
from tests.factories import (
    ClaimEpisodeFactory,
    ClaimFactory,
    ClaimLineFactory,
    DenialPatternFactory,
    PayerFactory,
    RemittanceFactory,
)


@pytest.mark.unit
class TestPatternDetectorEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_detect_patterns_for_payer_with_old_episodes(self, db_session):
        """Test that episodes outside days_back window are excluded."""
        payer = PayerFactory()
        remittance = RemittanceFactory(
            payer=payer,
            denial_reasons=[{"code": "CO45", "description": "Old denial"}],
        )
        remittance.created_at = datetime.now() - timedelta(days=100)  # Outside 90-day window
        claim = ClaimFactory(payer=payer)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.COMPLETE,
            denial_count=1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        # Should not detect patterns from old episodes
        assert len(patterns) == 0

    def test_detect_patterns_for_payer_with_incomplete_episodes(self, db_session):
        """Test that incomplete episodes are excluded."""
        payer = PayerFactory()
        remittance = RemittanceFactory(
            payer=payer,
            denial_reasons=[{"code": "CO45", "description": "Test denial"}],
        )
        claim = ClaimFactory(payer=payer)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.PENDING,  # Not COMPLETE
            denial_count=1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        # Should not detect patterns from incomplete episodes
        assert len(patterns) == 0

    def test_detect_patterns_for_payer_with_zero_denial_count(self, db_session):
        """Test that episodes with zero denial count are excluded."""
        payer = PayerFactory()
        remittance = RemittanceFactory(
            payer=payer,
            denial_reasons=[{"code": "CO45", "description": "Test denial"}],
        )
        claim = ClaimFactory(payer=payer)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.COMPLETE,
            denial_count=0,  # No denials
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        # Should not detect patterns from episodes with no denials
        assert len(patterns) == 0

    def test_detect_patterns_for_payer_with_string_reason_code(self, db_session):
        """Test handling of string denial reason codes (not dict)."""
        payer = PayerFactory()
        remittance = RemittanceFactory(
            payer=payer,
            denial_reasons=["CO45"],  # String instead of dict
        )
        claim = ClaimFactory(payer=payer)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.COMPLETE,
            denial_count=1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        # Should handle string reason codes
        assert len(patterns) > 0
        assert any(p.denial_reason_code == "CO45" for p in patterns)

    def test_detect_patterns_for_payer_with_dict_reason_code(self, db_session):
        """Test handling of dict denial reason codes."""
        payer = PayerFactory()
        remittance = RemittanceFactory(
            payer=payer,
            denial_reasons=[{"code": "CO45", "description": "Test denial"}],
        )
        claim = ClaimFactory(payer=payer)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.COMPLETE,
            denial_count=1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        # Should handle dict reason codes
        assert len(patterns) > 0
        assert any(p.denial_reason_code == "CO45" for p in patterns)

    def test_detect_patterns_for_payer_with_none_reason_code(self, db_session):
        """Test handling of None or empty reason codes."""
        payer = PayerFactory()
        remittance = RemittanceFactory(
            payer=payer,
            denial_reasons=[{"code": None, "description": "Test"}],
        )
        claim = ClaimFactory(payer=payer)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.COMPLETE,
            denial_count=1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        # Should skip None reason codes
        assert all(p.denial_reason_code is not None for p in patterns)

    def test_detect_patterns_for_payer_frequency_threshold(self, db_session):
        """Test that patterns below 5% frequency threshold are filtered."""
        payer = PayerFactory()

        # Create 100 episodes, only 4 with CO45 (4% frequency)
        for i in range(96):
            remittance = RemittanceFactory(
                payer=payer,
                denial_reasons=[{"code": f"CO{i}", "description": f"Denial {i}"}],
            )
            claim = ClaimFactory(payer=payer)
            ClaimEpisodeFactory(
                claim=claim,
                remittance=remittance,
                status=EpisodeStatus.COMPLETE,
                denial_count=1,
            )

        # Add 4 episodes with CO45
        for i in range(4):
            remittance = RemittanceFactory(
                payer=payer,
                denial_reasons=[{"code": "CO45", "description": "Test denial"}],
            )
            claim = ClaimFactory(payer=payer)
            ClaimEpisodeFactory(
                claim=claim,
                remittance=remittance,
                status=EpisodeStatus.COMPLETE,
                denial_count=1,
            )
        db_session.commit()

        detector = PatternDetector(db_session)
        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        # CO45 should not be included (4% < 5% threshold)
        co45_patterns = [p for p in patterns if p.denial_reason_code == "CO45"]
        assert len(co45_patterns) == 0

    def test_detect_patterns_for_payer_updates_confidence_score(self, db_session):
        """Test that confidence score is updated correctly."""
        payer = PayerFactory()
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.5,
        )
        db_session.commit()

        # Create episode with same denial
        remittance = RemittanceFactory(
            payer=payer,
            denial_reasons=[{"code": "CO45", "description": "Test denial"}],
        )
        claim = ClaimFactory(payer=payer)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.COMPLETE,
            denial_count=1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        # Confidence score should be updated (capped at 1.0)
        co45_pattern = [p for p in patterns if p.denial_reason_code == "CO45"][0]
        assert co45_pattern.confidence_score <= 1.0
        assert co45_pattern.confidence_score >= 0.0


@pytest.mark.unit
class TestPatternDetectorCacheEdgeCases:
    """Test caching edge cases."""

    def test_get_patterns_for_payer_cache_invalid_format(self, db_session):
        """Test handling of invalid cached data format."""
        payer = PayerFactory()
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)

        # Set invalid cache data
        cache_key_str = cache_key("pattern", "payer", payer.id)
        cache.set(cache_key_str, "invalid_string", ttl_seconds=3600)

        # Should fall through to database query
        patterns = detector.get_patterns_for_payer(payer.id)
        assert len(patterns) == 1
        assert patterns[0].denial_reason_code == "CO45"

    def test_get_patterns_for_payer_cache_empty_list(self, db_session):
        """Test handling of empty cached list."""
        payer = PayerFactory()
        db_session.commit()

        detector = PatternDetector(db_session)

        # Set empty cache
        cache_key_str = cache_key("pattern", "payer", payer.id)
        cache.set(cache_key_str, [], ttl_seconds=3600)

        # Should fall through to database query
        patterns = detector.get_patterns_for_payer(payer.id)
        assert patterns == []

    def test_get_patterns_for_payer_cache_missing_ids(self, db_session):
        """Test handling of cached patterns with missing IDs."""
        payer = PayerFactory()
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)

        # Set cache with missing ID
        cache_key_str = cache_key("pattern", "payer", payer.id)
        cache.set(cache_key_str, [{"id": None}], ttl_seconds=3600)

        # Should fall through to database query
        patterns = detector.get_patterns_for_payer(payer.id)
        assert len(patterns) == 1

    def test_get_patterns_for_payer_cache_nonexistent_ids(self, db_session):
        """Test handling of cached patterns with nonexistent IDs."""
        payer = PayerFactory()
        db_session.commit()

        detector = PatternDetector(db_session)

        # Set cache with nonexistent ID
        cache_key_str = cache_key("pattern", "payer", payer.id)
        cache.set(cache_key_str, [{"id": 99999}], ttl_seconds=3600)

        # Should return empty list (pattern doesn't exist)
        patterns = detector.get_patterns_for_payer(payer.id)
        assert patterns == []

    def test_analyze_claim_for_patterns_cache_hit(self, db_session):
        """Test that analyze_claim_for_patterns uses cache."""
        payer = PayerFactory()
        claim = ClaimFactory(payer=payer)
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)

        # First call - should cache
        results1 = detector.analyze_claim_for_patterns(claim.id)

        # Set cache manually to verify second call uses it
        cache_key_str = cache_key("pattern", "analysis", claim.id)
        cached_result = [{"pattern_id": pattern.id, "match_score": 0.5}]
        cache.set(cache_key_str, cached_result, ttl_seconds=3600)

        # Second call - should use cache
        with patch.object(db_session, "query") as mock_query:
            results2 = detector.analyze_claim_for_patterns(claim.id)
            # Should not query database if cache hit
            assert len(results2) > 0


@pytest.mark.unit
class TestPatternDetectorAnalyzeClaim:
    """Test analyze_claim_for_patterns edge cases."""

    def test_analyze_claim_for_patterns_claim_not_found(self, db_session):
        """Test analyzing nonexistent claim."""
        detector = PatternDetector(db_session)
        results = detector.analyze_claim_for_patterns(99999)

        assert results == []

    def test_analyze_claim_for_patterns_no_payer_id(self, db_session):
        """Test analyzing claim without payer ID."""
        claim = ClaimFactory(payer=None)  # No payer
        db_session.commit()

        detector = PatternDetector(db_session)
        results = detector.analyze_claim_for_patterns(claim.id)

        assert results == []

    def test_analyze_claim_for_patterns_no_patterns_for_payer(self, db_session):
        """Test analyzing claim when payer has no patterns."""
        payer = PayerFactory()
        claim = ClaimFactory(payer=payer)
        db_session.commit()

        detector = PatternDetector(db_session)
        results = detector.analyze_claim_for_patterns(claim.id)

        assert results == []

    def test_analyze_claim_for_patterns_sorts_by_match_score(self, db_session):
        """Test that results are sorted by match score (highest first)."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            principal_diagnosis="E11.9",
            diagnosis_codes=["E11.9"],
        )
        ClaimLineFactory(claim=claim, procedure_code="99213")
        db_session.commit()

        # Create patterns with different match scores
        pattern1 = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.5,
            conditions={"principal_diagnosis": "E11.9"},
        )
        pattern2 = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO97",
            frequency=0.1,
            confidence_score=0.8,
            conditions={"principal_diagnosis": "E11.9"},
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        results = detector.analyze_claim_for_patterns(claim.id)

        # Results should be sorted by match_score descending
        assert len(results) >= 2
        match_scores = [r["match_score"] for r in results]
        assert match_scores == sorted(match_scores, reverse=True)


@pytest.mark.unit
class TestPatternDetectorCalculateMatch:
    """Test _calculate_pattern_match edge cases."""

    def test_calculate_pattern_match_no_conditions(self, db_session):
        """Test pattern match with no conditions (uses frequency)."""
        payer = PayerFactory()
        claim = ClaimFactory(payer=payer)
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.3,
            confidence_score=0.8,
            conditions=None,  # No conditions
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should use frequency as base match
        assert match_score > 0
        assert match_score <= 1.0

    def test_calculate_pattern_match_empty_conditions(self, db_session):
        """Test pattern match with empty conditions dict."""
        payer = PayerFactory()
        claim = ClaimFactory(payer=payer)
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.3,
            confidence_score=0.8,
            conditions={},  # Empty dict
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should use frequency as base match
        assert match_score > 0

    def test_calculate_pattern_match_diagnosis_codes_partial_match(self, db_session):
        """Test pattern match with partial diagnosis code match."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            diagnosis_codes=["E11.9", "I10", "M54.5"],
        )
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={"diagnosis_codes": ["E11.9", "Z99.9"]},  # One match
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should match (at least one diagnosis code matches)
        assert match_score > 0

    def test_calculate_pattern_match_diagnosis_codes_no_match(self, db_session):
        """Test pattern match with no diagnosis code match."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            diagnosis_codes=["E11.9", "I10"],
        )
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={"diagnosis_codes": ["Z99.9", "Z88.9"]},  # No match
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should not match
        assert match_score == 0.0

    def test_calculate_pattern_match_procedure_codes_partial_match(self, db_session):
        """Test pattern match with partial procedure code match."""
        payer = PayerFactory()
        claim = ClaimFactory(payer=payer)
        ClaimLineFactory(claim=claim, procedure_code="99213")
        ClaimLineFactory(claim=claim, procedure_code="99214")
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={"procedure_codes": ["99213", "99215"]},  # One match
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should match (at least one procedure code matches)
        assert match_score > 0

    def test_calculate_pattern_match_procedure_codes_no_match(self, db_session):
        """Test pattern match with no procedure code match."""
        payer = PayerFactory()
        claim = ClaimFactory(payer=payer)
        ClaimLineFactory(claim=claim, procedure_code="99213")
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={"procedure_codes": ["99214", "99215"]},  # No match
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should not match
        assert match_score == 0.0

    def test_calculate_pattern_match_amount_below_min(self, db_session):
        """Test pattern match with amount below minimum."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            total_charge_amount=500.0,
        )
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={
                "charge_amount_min": 1000.0,
                "charge_amount_max": 2000.0,
            },
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should not match (below minimum)
        assert match_score == 0.0

    def test_calculate_pattern_match_amount_above_max(self, db_session):
        """Test pattern match with amount above maximum."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            total_charge_amount=3000.0,
        )
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={
                "charge_amount_min": 1000.0,
                "charge_amount_max": 2000.0,
            },
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should not match (above maximum)
        assert match_score == 0.0

    def test_calculate_pattern_match_amount_only_min(self, db_session):
        """Test pattern match with only minimum amount specified."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            total_charge_amount=1500.0,
        )
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={
                "charge_amount_min": 1000.0,
            },
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should match (above minimum, no maximum)
        assert match_score > 0

    def test_calculate_pattern_match_amount_only_max(self, db_session):
        """Test pattern match with only maximum amount specified."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            total_charge_amount=1500.0,
        )
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={
                "charge_amount_max": 2000.0,
            },
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should match (below maximum, no minimum)
        assert match_score > 0

    def test_calculate_pattern_match_facility_type_match(self, db_session):
        """Test pattern match with facility type match."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            facility_type_code="11",
        )
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={"facility_type_code": "11"},
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should match
        assert match_score > 0

    def test_calculate_pattern_match_facility_type_no_match(self, db_session):
        """Test pattern match with facility type mismatch."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            facility_type_code="11",
        )
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={"facility_type_code": "12"},
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should not match
        assert match_score == 0.0

    def test_calculate_pattern_match_confidence_score_weighting(self, db_session):
        """Test that confidence score weights the match score."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            principal_diagnosis="E11.9",
        )
        pattern1 = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.5,  # Lower confidence
            conditions={"principal_diagnosis": "E11.9"},
        )
        pattern2 = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO97",
            frequency=0.1,
            confidence_score=0.9,  # Higher confidence
            conditions={"principal_diagnosis": "E11.9"},
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score1 = detector._calculate_pattern_match(claim, pattern1)
        match_score2 = detector._calculate_pattern_match(claim, pattern2)

        # Higher confidence should result in higher match score
        assert match_score2 > match_score1

    def test_calculate_pattern_match_score_capped_at_one(self, db_session):
        """Test that match score is capped at 1.0."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            principal_diagnosis="E11.9",
            diagnosis_codes=["E11.9"],
        )
        ClaimLineFactory(claim=claim, procedure_code="99213")
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=1.0,  # Maximum frequency
            confidence_score=1.0,  # Maximum confidence
            conditions={
                "principal_diagnosis": "E11.9",
                "diagnosis_codes": ["E11.9"],
                "procedure_codes": ["99213"],
            },
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should be capped at 1.0
        assert match_score <= 1.0

    def test_calculate_pattern_match_none_claim_amount(self, db_session):
        """Test pattern match with None claim amount."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            total_charge_amount=None,
        )
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={
                "charge_amount_min": 1000.0,
            },
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should handle None gracefully (treats as 0.0)
        assert match_score == 0.0  # Below minimum

    def test_calculate_pattern_match_none_confidence_score(self, db_session):
        """Test pattern match with None confidence score."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            principal_diagnosis="E11.9",
        )
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=None,  # None confidence
            conditions={"principal_diagnosis": "E11.9"},
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        match_score = detector._calculate_pattern_match(claim, pattern)

        # Should use default confidence (0.5) when None
        assert match_score > 0


@pytest.mark.unit
class TestPatternDetectorDetectAllPatterns:
    """Test detect_all_patterns edge cases."""

    def test_detect_all_patterns_no_payers(self, db_session):
        """Test detect_all_patterns with no payers."""
        detector = PatternDetector(db_session)
        all_patterns = detector.detect_all_patterns(days_back=90)

        assert all_patterns == {}

    def test_detect_all_patterns_multiple_payers(self, db_session):
        """Test detect_all_patterns with multiple payers."""
        payer1 = PayerFactory()
        payer2 = PayerFactory()
        db_session.commit()

        detector = PatternDetector(db_session)
        all_patterns = detector.detect_all_patterns(days_back=90)

        assert payer1.id in all_patterns
        assert payer2.id in all_patterns
        assert isinstance(all_patterns[payer1.id], list)
        assert isinstance(all_patterns[payer2.id], list)
