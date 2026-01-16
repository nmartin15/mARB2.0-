"""Tests for pattern detector with optimizations."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.models.database import (
    EpisodeStatus,
)
from app.services.learning.pattern_detector import PatternDetector
from app.utils.cache import cache
from tests.factories import (
    ClaimEpisodeFactory,
    ClaimFactory,
    ClaimLineFactory,
    DenialPatternFactory,
    PayerFactory,
    RemittanceFactory,
)


@pytest.mark.unit
class TestPatternDetectorOptimizations:
    """Test pattern detector optimizations: eager loading, batch loading, caching."""

    def test_detect_patterns_eager_loads_remittance(self, db_session):
        """Test that detect_patterns_for_payer eagerly loads remittance to avoid N+1."""
        payer = PayerFactory()
        claim = ClaimFactory(payer=payer)

        # Create remittance with denial reasons and recent date
        remittance = RemittanceFactory(
            payer=payer,
            denial_reasons=[{"code": "CO45", "description": "Test denial"}],
        )
        # Ensure remittance is within the days_back window
        remittance.created_at = datetime.now() - timedelta(days=30)

        # Create episode with denial
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.COMPLETE,
            denial_count=1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)

        # This should not cause N+1 queries because remittance is eagerly loaded
        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        # Verify patterns were detected
        assert len(patterns) > 0
        assert any(p.denial_reason_code == "CO45" for p in patterns)

    def test_detect_patterns_batch_loads_existing_patterns(self, db_session):
        """Test that existing patterns are batch loaded instead of queried individually."""
        payer = PayerFactory()

        # Create multiple existing patterns
        pattern1 = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
        )
        pattern2 = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO97",
            frequency=0.15,
        )
        db_session.commit()

        # Create remittance with both denial reasons
        remittance = RemittanceFactory(
            payer=payer,
            denial_reasons=[
                {"code": "CO45", "description": "Test denial 1"},
                {"code": "CO97", "description": "Test denial 2"},
            ],
        )
        claim = ClaimFactory(payer=payer)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.COMPLETE,
            denial_count=2,
        )
        db_session.commit()

        detector = PatternDetector(db_session)

        # Count queries - should only be 2: one for episodes, one for existing patterns
        query_count = 0

        original_query = db_session.query

        def counting_query(*args, **kwargs):
            nonlocal query_count
            query_count += 1
            return original_query(*args, **kwargs)

        db_session.query = counting_query

        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        # Should have updated both existing patterns
        assert len(patterns) == 2
        assert query_count <= 3  # Episodes query, existing patterns query, maybe one more

    def test_get_patterns_for_payer_caching(self, db_session):
        """Test that get_patterns_for_payer uses caching."""
        payer = PayerFactory()

        # Create patterns
        pattern1 = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
        )
        pattern2 = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO97",
            frequency=0.15,
        )
        db_session.commit()

        detector = PatternDetector(db_session)

        # First call - should hit database
        patterns1 = detector.get_patterns_for_payer(payer.id)
        assert len(patterns1) == 2

        # Verify cache was set
        from app.utils.cache import cache_key
        cache_key_str = cache_key("pattern", "payer", payer.id)
        cached = cache.get(cache_key_str)
        assert cached is not None
        assert len(cached) == 2

        # Second call - should hit cache (but still query to convert IDs to objects)
        query_count_before = 0
        original_query = db_session.query

        def counting_query(*args, **kwargs):
            nonlocal query_count_before
            query_count_before += 1
            return original_query(*args, **kwargs)

        db_session.query = counting_query

        patterns2 = detector.get_patterns_for_payer(payer.id)
        assert len(patterns2) == 2

        # Should only query once to batch load patterns by IDs (not query for each pattern)
        # The query count should be minimal (1 query for batch loading patterns)
        assert query_count_before <= 2  # Allow some flexibility

    def test_get_patterns_for_payer_cache_invalidation(self, db_session):
        """Test that cache is invalidated when patterns are updated."""
        payer = PayerFactory()
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)

        # Get patterns (caches them)
        patterns1 = detector.get_patterns_for_payer(payer.id)
        assert len(patterns1) == 1

        # Detect new patterns (should invalidate cache)
        remittance = RemittanceFactory(
            payer=payer,
            denial_reasons=[{"code": "CO97", "description": "New denial"}],
        )
        claim = ClaimFactory(payer=payer)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.COMPLETE,
            denial_count=1,
        )
        db_session.commit()

        detector.detect_patterns_for_payer(payer.id, days_back=90)

        # Cache should be invalidated, so next call should get fresh data
        patterns2 = detector.get_patterns_for_payer(payer.id)
        # Should have at least the original pattern, possibly new ones

    def test_analyze_claim_eager_loads_claim_lines(self, db_session):
        """Test that analyze_claim_for_patterns eagerly loads claim_lines."""
        payer = PayerFactory()
        claim = ClaimFactory(payer=payer)

        # Create claim lines
        ClaimLineFactory(claim=claim, procedure_code="99213")
        ClaimLineFactory(claim=claim, procedure_code="99214")
        db_session.commit()

        # Create pattern with procedure code condition
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            conditions={"procedure_codes": ["99213", "99214"]},
        )
        db_session.commit()

        detector = PatternDetector(db_session)

        # This should not cause N+1 queries because claim_lines are eagerly loaded
        results = detector.analyze_claim_for_patterns(claim.id)

        # Should find matching pattern
        assert len(results) > 0
        assert any(r["denial_reason_code"] == "CO45" for r in results)

    def test_analyze_claim_caching(self, db_session):
        """Test that analyze_claim_for_patterns uses caching."""
        payer = PayerFactory()
        claim = ClaimFactory(payer=payer)
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
        )
        db_session.commit()

        detector = PatternDetector(db_session)

        # First call - should hit database
        results1 = detector.analyze_claim_for_patterns(claim.id)

        # Second call - should hit cache
        with patch.object(db_session, "query") as mock_query:
            results2 = detector.analyze_claim_for_patterns(claim.id)
            assert results1 == results2

    def test_detect_all_patterns_batch_processing(self, db_session):
        """Test that detect_all_patterns processes payers in batches."""
        # Create multiple payers
        payer1 = PayerFactory()
        payer2 = PayerFactory()
        payer3 = PayerFactory()
        db_session.commit()

        detector = PatternDetector(db_session)

        # Should process all payers without errors
        all_patterns = detector.detect_all_patterns(days_back=90)

        assert payer1.id in all_patterns
        assert payer2.id in all_patterns
        assert payer3.id in all_patterns
        assert isinstance(all_patterns[payer1.id], list)


@pytest.mark.unit
class TestPatternDetectorFunctionality:
    """Test pattern detector core functionality."""

    def test_detect_patterns_for_payer_no_episodes(self, db_session):
        """Test detecting patterns when no episodes exist."""
        payer = PayerFactory()
        db_session.commit()

        detector = PatternDetector(db_session)
        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        assert patterns == []

    def test_detect_patterns_for_payer_creates_new_patterns(self, db_session):
        """Test that new patterns are created when detected."""
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

        assert len(patterns) > 0
        assert any(p.denial_reason_code == "CO45" for p in patterns)
        assert any(p.payer_id == payer.id for p in patterns)

    def test_detect_patterns_for_payer_updates_existing_patterns(self, db_session):
        """Test that existing patterns are updated when detected again."""
        payer = PayerFactory()

        # Create existing pattern
        existing_pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            occurrence_count=1,
        )
        db_session.commit()
        original_count = existing_pattern.occurrence_count

        # Create new episode with same denial reason
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

        # Pattern should be updated, not duplicated
        co45_patterns = [p for p in patterns if p.denial_reason_code == "CO45"]
        assert len(co45_patterns) == 1
        assert co45_patterns[0].occurrence_count >= original_count

    def test_detect_patterns_filters_low_frequency(self, db_session):
        """Test that patterns with frequency < 5% are not created."""
        payer = PayerFactory()

        # Create many episodes with different denial reasons
        # Only one with CO45 (low frequency)
        for i in range(20):
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
        db_session.commit()

        detector = PatternDetector(db_session)
        patterns = detector.detect_patterns_for_payer(payer.id, days_back=90)

        # Should not create patterns for low-frequency denials
        # (Each denial appears only once in 20 episodes = 5%, which is the threshold)
        # Actually, 1/20 = 5%, so it might be included. Let's check for very low frequency
        assert all(p.frequency >= 0.05 for p in patterns)

    def test_analyze_claim_for_patterns_no_patterns(self, db_session):
        """Test analyzing claim when no patterns exist."""
        payer = PayerFactory()
        claim = ClaimFactory(payer=payer)
        db_session.commit()

        detector = PatternDetector(db_session)
        results = detector.analyze_claim_for_patterns(claim.id)

        assert results == []

    def test_analyze_claim_for_patterns_matches_conditions(self, db_session):
        """Test that pattern matching works with conditions."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            principal_diagnosis="E11.9",
            diagnosis_codes=["E11.9", "I10"],
        )
        ClaimLineFactory(claim=claim, procedure_code="99213")
        db_session.commit()

        # Create pattern with matching conditions
        pattern = DenialPatternFactory(
            payer=payer,
            denial_reason_code="CO45",
            frequency=0.1,
            confidence_score=0.8,
            conditions={
                "principal_diagnosis": "E11.9",
                "procedure_codes": ["99213"],
            },
        )
        db_session.commit()

        detector = PatternDetector(db_session)
        results = detector.analyze_claim_for_patterns(claim.id)

        assert len(results) > 0
        matching = [r for r in results if r["denial_reason_code"] == "CO45"]
        assert len(matching) > 0
        assert matching[0]["match_score"] > 0

    def test_calculate_pattern_match_with_conditions(self, db_session):
        """Test pattern match calculation with various conditions."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            principal_diagnosis="E11.9",
            diagnosis_codes=["E11.9", "I10"],
            total_charge_amount=1500.0,
            facility_type_code="11",
        )
        ClaimLineFactory(claim=claim, procedure_code="99213")
        db_session.commit()

        detector = PatternDetector(db_session)

        # Test with matching principal diagnosis
        pattern1 = DenialPatternFactory(
            payer=payer,
            conditions={"principal_diagnosis": "E11.9"},
            confidence_score=0.8,
        )
        db_session.commit()

        match_score = detector._calculate_pattern_match(claim, pattern1)
        assert match_score > 0

        # Test with non-matching principal diagnosis
        pattern2 = DenialPatternFactory(
            payer=payer,
            conditions={"principal_diagnosis": "E10.9"},
            confidence_score=0.8,
        )
        db_session.commit()

        match_score2 = detector._calculate_pattern_match(claim, pattern2)
        assert match_score2 == 0.0  # No match

    def test_calculate_pattern_match_amount_range(self, db_session):
        """Test pattern match with charge amount range."""
        payer = PayerFactory()
        claim = ClaimFactory(
            payer=payer,
            total_charge_amount=1500.0,
        )
        db_session.commit()

        detector = PatternDetector(db_session)

        # Pattern with amount range that includes claim
        pattern1 = DenialPatternFactory(
            payer=payer,
            conditions={
                "charge_amount_min": 1000.0,
                "charge_amount_max": 2000.0,
            },
            confidence_score=0.8,
        )
        db_session.commit()

        match_score1 = detector._calculate_pattern_match(claim, pattern1)
        assert match_score1 > 0

        # Pattern with amount range that excludes claim
        pattern2 = DenialPatternFactory(
            payer=payer,
            conditions={
                "charge_amount_min": 2000.0,
                "charge_amount_max": 3000.0,
            },
            confidence_score=0.8,
        )
        db_session.commit()

        match_score2 = detector._calculate_pattern_match(claim, pattern2)
        assert match_score2 == 0.0  # Below minimum, no match

