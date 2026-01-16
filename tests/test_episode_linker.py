"""Tests for episode linker."""
from datetime import datetime

import pytest

from app.models.database import EpisodeStatus
from app.services.episodes.linker import EpisodeLinker
from tests.factories import ClaimEpisodeFactory, ClaimFactory, RemittanceFactory


@pytest.mark.unit
class TestEpisodeLinker:
    """Tests for EpisodeLinker."""

    def test_link_claim_to_remittance_success(self, db_session):
        """Test successfully linking claim to remittance."""
        claim = ClaimFactory(claim_control_number="CLM001")
        remittance = RemittanceFactory(
            claim_control_number="CLM001",
            payment_amount=1000.00,
        )
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episode = linker.link_claim_to_remittance(claim.id, remittance.id)

        assert episode is not None
        assert episode.claim_id == claim.id
        assert episode.remittance_id == remittance.id
        assert episode.status == EpisodeStatus.LINKED
        assert episode.payment_amount == 1000.00

    def test_link_claim_to_remittance_claim_not_found(self, db_session):
        """Test linking with non-existent claim."""
        remittance = RemittanceFactory()
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episode = linker.link_claim_to_remittance(99999, remittance.id)

        assert episode is None

    def test_link_claim_to_remittance_remittance_not_found(self, db_session):
        """Test linking with non-existent remittance."""
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episode = linker.link_claim_to_remittance(claim.id, 99999)

        assert episode is None

    def test_link_claim_to_remittance_already_exists(self, db_session):
        """Test linking when episode already exists."""
        claim = ClaimFactory()
        remittance = RemittanceFactory()
        existing_episode = ClaimEpisodeFactory(claim=claim, remittance=remittance)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(existing_episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episode = linker.link_claim_to_remittance(claim.id, remittance.id)

        assert episode is not None
        assert episode.id == existing_episode.id

    def test_link_claim_to_remittance_denial_count(self, db_session):
        """Test that denial count is captured."""
        claim = ClaimFactory()
        remittance = RemittanceFactory(
            denial_reasons=["CO45", "CO97"],
        )
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episode = linker.link_claim_to_remittance(claim.id, remittance.id)

        assert episode.denial_count == 2

    def test_link_claim_to_remittance_adjustment_count(self, db_session):
        """Test that adjustment count is captured."""
        claim = ClaimFactory()
        remittance = RemittanceFactory(
            adjustment_reasons=["PR1", "PR2", "CO45"],
        )
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episode = linker.link_claim_to_remittance(claim.id, remittance.id)

        assert episode.adjustment_count == 3

    def test_auto_link_by_control_number_success(self, db_session):
        """Test auto-linking by control number."""
        claim = ClaimFactory(claim_control_number="CLM001")
        remittance = RemittanceFactory(claim_control_number="CLM001")
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_control_number(remittance)

        assert len(episodes) == 1
        assert episodes[0].claim_id == claim.id
        assert episodes[0].remittance_id == remittance.id

    def test_auto_link_by_control_number_no_match(self, db_session):
        """Test auto-linking when no matching claim found."""
        remittance = RemittanceFactory(claim_control_number="CLM999")
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_control_number(remittance)

        assert len(episodes) == 0

    def test_auto_link_by_control_number_no_control_number(self, db_session):
        """Test auto-linking when remittance has no control number."""
        remittance = RemittanceFactory(claim_control_number=None)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_control_number(remittance)

        assert len(episodes) == 0

    def test_auto_link_by_control_number_multiple_claims(self, db_session):
        """Test auto-linking with multiple matching claims."""
        # Use different control numbers since claim_control_number must be unique
        claim1 = ClaimFactory(claim_control_number="CLM001A")
        claim2 = ClaimFactory(claim_control_number="CLM001B")
        # Create remittance that matches both (this would be unusual but test the logic)
        # Actually, remittance can only match one control number, so let's test with one claim
        remittance = RemittanceFactory(claim_control_number="CLM001A")
        db_session.add(claim1)
        db_session.add(claim2)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_control_number(remittance)

        # Should link to claim1 (matching control number)
        assert len(episodes) == 1
        assert episodes[0].claim_id == claim1.id

    def test_get_episodes_for_claim(self, db_session):
        """Test getting episodes for a claim."""
        claim = ClaimFactory()
        remittance1 = RemittanceFactory()
        remittance2 = RemittanceFactory()
        episode1 = ClaimEpisodeFactory(claim=claim, remittance=remittance1)
        episode2 = ClaimEpisodeFactory(claim=claim, remittance=remittance2)
        db_session.add(claim)
        db_session.add(remittance1)
        db_session.add(remittance2)
        db_session.add(episode1)
        db_session.add(episode2)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.get_episodes_for_claim(claim.id)

        assert len(episodes) == 2
        assert all(ep.claim_id == claim.id for ep in episodes)

    def test_get_unlinked_claims(self, db_session):
        """Test getting unlinked claims."""
        linked_claim = ClaimFactory()
        unlinked_claim1 = ClaimFactory()
        unlinked_claim2 = ClaimFactory()
        remittance = RemittanceFactory()
        episode = ClaimEpisodeFactory(claim=linked_claim, remittance=remittance)
        db_session.add(linked_claim)
        db_session.add(unlinked_claim1)
        db_session.add(unlinked_claim2)
        db_session.add(remittance)
        db_session.add(episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        unlinked = linker.get_unlinked_claims(limit=10)

        assert len(unlinked) >= 2
        assert all(claim.id in [unlinked_claim1.id, unlinked_claim2.id] for claim in unlinked)
        assert linked_claim.id not in [claim.id for claim in unlinked]

    def test_update_episode_status_success(self, db_session):
        """Test updating episode status."""
        claim = ClaimFactory()
        remittance = RemittanceFactory()
        episode = ClaimEpisodeFactory(claim=claim, remittance=remittance, status=EpisodeStatus.LINKED)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        updated = linker.update_episode_status(episode.id, EpisodeStatus.COMPLETE)

        assert updated is not None
        assert updated.status == EpisodeStatus.COMPLETE
        assert updated.linked_at is not None

    def test_update_episode_status_not_found(self, db_session):
        """Test updating status of non-existent episode."""
        linker = EpisodeLinker(db_session)
        updated = linker.update_episode_status(99999, EpisodeStatus.COMPLETE)

        assert updated is None

    def test_update_episode_status_to_complete_sets_linked_at(self, db_session):
        """Test that updating to COMPLETE sets linked_at if not already set."""
        claim = ClaimFactory()
        remittance = RemittanceFactory()
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.LINKED,
            linked_at=None
        )
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        updated = linker.update_episode_status(episode.id, EpisodeStatus.COMPLETE)

        assert updated.linked_at is not None

    def test_mark_episode_complete(self, db_session):
        """Test marking episode as complete."""
        claim = ClaimFactory()
        remittance = RemittanceFactory()
        episode = ClaimEpisodeFactory(claim=claim, remittance=remittance, status=EpisodeStatus.LINKED)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        updated = linker.mark_episode_complete(episode.id)

        assert updated is not None
        assert updated.status == EpisodeStatus.COMPLETE

    def test_mark_episode_complete_not_found(self, db_session):
        """Test marking non-existent episode as complete."""
        linker = EpisodeLinker(db_session)
        updated = linker.mark_episode_complete(99999)

        assert updated is None

    def test_auto_link_by_patient_and_date_success(self, db_session):
        """Test auto-linking by patient and date."""
        from datetime import timedelta

        from tests.factories import PayerFactory

        payer = PayerFactory()
        payment_date = datetime.now()
        service_date = payment_date - timedelta(days=10)  # Within 30 day tolerance

        claim = ClaimFactory(
            payer=payer,
            service_date=service_date
        )
        remittance = RemittanceFactory(
            payer=payer,
            payment_date=payment_date
        )
        db_session.add(payer)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_patient_and_date(remittance)

        assert len(episodes) == 1
        assert episodes[0].claim_id == claim.id
        assert episodes[0].remittance_id == remittance.id

    def test_auto_link_by_patient_and_date_no_payer(self, db_session):
        """Test auto-linking when remittance has no payer."""
        remittance = RemittanceFactory(payer=None)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_patient_and_date(remittance)

        assert len(episodes) == 0

    def test_auto_link_by_patient_and_date_no_payment_date(self, db_session):
        """Test auto-linking when remittance has no payment date."""
        from tests.factories import PayerFactory

        payer = PayerFactory()
        remittance = RemittanceFactory(payer=payer, payment_date=None)
        db_session.add(payer)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_patient_and_date(remittance)

        assert len(episodes) == 0

    def test_auto_link_by_patient_and_date_outside_tolerance(self, db_session):
        """Test auto-linking when claim date is outside tolerance."""
        from datetime import timedelta

        from tests.factories import PayerFactory

        payer = PayerFactory()
        payment_date = datetime.now()
        service_date = payment_date - timedelta(days=60)  # Outside 30 day tolerance

        claim = ClaimFactory(
            payer=payer,
            service_date=service_date
        )
        remittance = RemittanceFactory(
            payer=payer,
            payment_date=payment_date
        )
        db_session.add(payer)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_patient_and_date(remittance)

        assert len(episodes) == 0

    def test_auto_link_by_patient_and_date_custom_tolerance(self, db_session):
        """Test auto-linking with custom days tolerance."""
        from datetime import timedelta

        from tests.factories import PayerFactory

        payer = PayerFactory()
        payment_date = datetime.now()
        service_date = payment_date - timedelta(days=45)  # Outside default 30 day tolerance

        claim = ClaimFactory(
            payer=payer,
            service_date=service_date
        )
        remittance = RemittanceFactory(
            payer=payer,
            payment_date=payment_date
        )
        db_session.add(payer)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_patient_and_date(remittance, days_tolerance=60)

        assert len(episodes) == 1

    def test_auto_link_by_patient_and_date_skips_existing(self, db_session):
        """Test that auto-linking skips already linked episodes."""
        from datetime import timedelta

        from tests.factories import PayerFactory

        payer = PayerFactory()
        payment_date = datetime.now()
        service_date = payment_date - timedelta(days=10)

        claim = ClaimFactory(
            payer=payer,
            service_date=service_date
        )
        remittance = RemittanceFactory(
            payer=payer,
            payment_date=payment_date
        )
        # Create existing episode
        existing_episode = ClaimEpisodeFactory(claim=claim, remittance=remittance)
        db_session.add(payer)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(existing_episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_patient_and_date(remittance)

        # Should return existing episode but not create a new one
        assert len(episodes) == 1
        assert episodes[0].id == existing_episode.id

    def test_auto_link_by_patient_and_date_multiple_claims(self, db_session):
        """Test auto-linking with multiple matching claims."""
        from datetime import timedelta

        from tests.factories import PayerFactory

        payer = PayerFactory()
        payment_date = datetime.now()
        service_date1 = payment_date - timedelta(days=5)
        service_date2 = payment_date - timedelta(days=10)

        claim1 = ClaimFactory(
            payer=payer,
            service_date=service_date1
        )
        claim2 = ClaimFactory(
            payer=payer,
            service_date=service_date2
        )
        remittance = RemittanceFactory(
            payer=payer,
            payment_date=payment_date
        )
        db_session.add(payer)
        db_session.add(claim1)
        db_session.add(claim2)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_patient_and_date(remittance)

        assert len(episodes) == 2
        claim_ids = [ep.claim_id for ep in episodes]
        assert claim1.id in claim_ids
        assert claim2.id in claim_ids

    def test_complete_episode_if_ready_already_complete(self, db_session):
        """Test completing episode that's already complete."""
        claim = ClaimFactory()
        remittance = RemittanceFactory()
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.COMPLETE
        )
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        result = linker.complete_episode_if_ready(episode.id)

        assert result is not None
        assert result.status == EpisodeStatus.COMPLETE

    def test_complete_episode_if_ready_not_found(self, db_session):
        """Test completing non-existent episode."""
        linker = EpisodeLinker(db_session)
        result = linker.complete_episode_if_ready(99999)

        assert result is None

    def test_complete_episode_if_ready_no_remittance(self, db_session):
        """Test completing episode with no remittance."""
        claim = ClaimFactory()
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=None,
            status=EpisodeStatus.LINKED
        )
        db_session.add(claim)
        db_session.add(episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        result = linker.complete_episode_if_ready(episode.id)

        # Should return episode but not mark as complete
        assert result is not None
        assert result.status == EpisodeStatus.LINKED

    def test_complete_episode_if_ready_remittance_processed(self, db_session):
        """Test completing episode when remittance is processed."""
        from app.models.database import RemittanceStatus

        claim = ClaimFactory()
        remittance = RemittanceFactory(status=RemittanceStatus.PROCESSED)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.LINKED
        )
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        result = linker.complete_episode_if_ready(episode.id)

        assert result is not None
        assert result.status == EpisodeStatus.COMPLETE

    def test_complete_episode_if_ready_remittance_not_processed(self, db_session):
        """Test that episode is not completed when remittance is not processed."""
        from app.models.database import RemittanceStatus

        claim = ClaimFactory()
        remittance = RemittanceFactory(status=RemittanceStatus.PENDING)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            status=EpisodeStatus.LINKED
        )
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        result = linker.complete_episode_if_ready(episode.id)

        # Should return episode but not mark as complete
        assert result is not None
        assert result.status == EpisodeStatus.LINKED

    def test_link_claim_to_remittance_flush_error(self, db_session):
        """Test handling of database flush errors when linking."""
        from unittest.mock import patch

        claim = ClaimFactory()
        remittance = RemittanceFactory()
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock flush to raise an exception
        with patch.object(db_session, 'flush', side_effect=Exception("Database error")):
            with pytest.raises(Exception, match="Database error"):
                linker.link_claim_to_remittance(claim.id, remittance.id)

    def test_link_claim_to_remittance_notification_failure(self, db_session):
        """Test that notification failures don't prevent episode creation."""
        from unittest.mock import patch

        claim = ClaimFactory()
        remittance = RemittanceFactory()
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock notification to fail
        with patch('app.services.episodes.linker.notify_episode_linked', side_effect=Exception("Notification error")):
            episode = linker.link_claim_to_remittance(claim.id, remittance.id)
            
            # Episode should still be created despite notification failure
            assert episode is not None
            assert episode.claim_id == claim.id
            assert episode.remittance_id == remittance.id

    def test_link_claim_to_remittance_outer_exception(self, db_session):
        """Test handling of outer exception when linking."""
        from unittest.mock import patch

        claim = ClaimFactory()
        remittance = RemittanceFactory()
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock query to raise an exception
        with patch.object(db_session, 'query', side_effect=Exception("Query error")):
            with pytest.raises(Exception, match="Query error"):
                linker.link_claim_to_remittance(claim.id, remittance.id)

    def test_auto_link_by_control_number_existing_episode(self, db_session):
        """Test auto-linking when episode already exists."""
        claim = ClaimFactory(claim_control_number="CLM001")
        remittance = RemittanceFactory(claim_control_number="CLM001")
        existing_episode = ClaimEpisodeFactory(claim=claim, remittance=remittance)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(existing_episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_control_number(remittance)

        # Should return existing episode, not create new one
        assert len(episodes) == 1
        assert episodes[0].id == existing_episode.id

    def test_auto_link_by_control_number_flush_error(self, db_session):
        """Test handling of database flush errors in auto-link by control number."""
        from unittest.mock import patch

        claim = ClaimFactory(claim_control_number="CLM001")
        remittance = RemittanceFactory(claim_control_number="CLM001")
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock flush to raise an exception
        with patch.object(db_session, 'flush', side_effect=Exception("Database error")):
            with pytest.raises(Exception, match="Database error"):
                linker.auto_link_by_control_number(remittance)

    def test_auto_link_by_control_number_notification_failure(self, db_session):
        """Test that notification failures don't prevent auto-linking."""
        from unittest.mock import patch

        claim = ClaimFactory(claim_control_number="CLM001")
        remittance = RemittanceFactory(claim_control_number="CLM001")
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock notification to fail
        with patch('app.services.episodes.linker.notify_episode_linked', side_effect=Exception("Notification error")):
            episodes = linker.auto_link_by_control_number(remittance)
            
            # Episodes should still be created despite notification failure
            assert len(episodes) == 1
            assert episodes[0].claim_id == claim.id

    def test_auto_link_by_control_number_outer_exception(self, db_session):
        """Test handling of outer exception in auto-link by control number."""
        from unittest.mock import patch

        remittance = RemittanceFactory(claim_control_number="CLM001")
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock query to raise an exception
        with patch.object(db_session, 'query', side_effect=Exception("Query error")):
            with pytest.raises(Exception, match="Query error"):
                linker.auto_link_by_control_number(remittance)

    def test_get_episodes_for_claim_exception(self, db_session):
        """Test handling of exceptions when getting episodes for claim."""
        from unittest.mock import patch

        linker = EpisodeLinker(db_session)
        
        # Mock query to raise an exception
        with patch.object(db_session, 'query', side_effect=Exception("Query error")):
            with pytest.raises(Exception, match="Query error"):
                linker.get_episodes_for_claim(1)

    def test_get_unlinked_claims_exception(self, db_session):
        """Test handling of exceptions when getting unlinked claims."""
        from unittest.mock import patch

        linker = EpisodeLinker(db_session)
        
        # Mock query to raise an exception
        with patch.object(db_session, 'query', side_effect=Exception("Query error")):
            with pytest.raises(Exception, match="Query error"):
                linker.get_unlinked_claims()

    def test_update_episode_status_flush_error(self, db_session):
        """Test handling of database flush errors when updating episode status."""
        from unittest.mock import patch

        claim = ClaimFactory()
        remittance = RemittanceFactory()
        episode = ClaimEpisodeFactory(claim=claim, remittance=remittance, status=EpisodeStatus.LINKED)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock flush to raise an exception
        with patch.object(db_session, 'flush', side_effect=Exception("Database error")):
            with pytest.raises(Exception, match="Database error"):
                linker.update_episode_status(episode.id, EpisodeStatus.COMPLETE)

    def test_update_episode_status_notification_failure(self, db_session):
        """Test that notification failures don't prevent status update."""
        from unittest.mock import patch
        from app.models.database import RemittanceStatus

        claim = ClaimFactory()
        remittance = RemittanceFactory(status=RemittanceStatus.PROCESSED)
        episode = ClaimEpisodeFactory(claim=claim, remittance=remittance, status=EpisodeStatus.LINKED)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock notification to fail
        with patch('app.services.episodes.linker.notify_episode_completed', side_effect=Exception("Notification error")):
            updated = linker.update_episode_status(episode.id, EpisodeStatus.COMPLETE)
            
            # Status should still be updated despite notification failure
            assert updated is not None
            assert updated.status == EpisodeStatus.COMPLETE

    def test_update_episode_status_outer_exception(self, db_session):
        """Test handling of outer exception when updating episode status."""
        from unittest.mock import patch

        linker = EpisodeLinker(db_session)
        
        # Mock query to raise an exception
        with patch.object(db_session, 'query', side_effect=Exception("Query error")):
            with pytest.raises(Exception, match="Query error"):
                linker.update_episode_status(1, EpisodeStatus.COMPLETE)

    def test_auto_link_by_patient_and_date_flush_error(self, db_session):
        """Test handling of database flush errors in auto-link by patient and date."""
        from datetime import timedelta
        from unittest.mock import patch
        from tests.factories import PayerFactory

        payer = PayerFactory()
        payment_date = datetime.now()
        service_date = payment_date - timedelta(days=10)

        claim = ClaimFactory(payer=payer, service_date=service_date)
        remittance = RemittanceFactory(payer=payer, payment_date=payment_date)
        db_session.add(payer)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock flush to raise an exception
        with patch.object(db_session, 'flush', side_effect=Exception("Database error")):
            with pytest.raises(Exception, match="Database error"):
                linker.auto_link_by_patient_and_date(remittance)

    def test_auto_link_by_patient_and_date_notification_failure(self, db_session):
        """Test that notification failures don't prevent auto-linking by patient/date."""
        from datetime import timedelta
        from unittest.mock import patch
        from tests.factories import PayerFactory

        payer = PayerFactory()
        payment_date = datetime.now()
        service_date = payment_date - timedelta(days=10)

        claim = ClaimFactory(payer=payer, service_date=service_date)
        remittance = RemittanceFactory(payer=payer, payment_date=payment_date)
        db_session.add(payer)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock notification to fail
        with patch('app.services.episodes.linker.notify_episode_linked', side_effect=Exception("Notification error")):
            episodes = linker.auto_link_by_patient_and_date(remittance)
            
            # Episodes should still be created despite notification failure
            assert len(episodes) == 1
            assert episodes[0].claim_id == claim.id

    def test_auto_link_by_patient_and_date_outer_exception(self, db_session):
        """Test handling of outer exception in auto-link by patient and date."""
        from unittest.mock import patch
        from tests.factories import PayerFactory

        payer = PayerFactory()
        remittance = RemittanceFactory(payer=payer, payment_date=datetime.now())
        db_session.add(payer)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock query to raise an exception
        with patch.object(db_session, 'query', side_effect=Exception("Query error")):
            with pytest.raises(Exception, match="Query error"):
                linker.auto_link_by_patient_and_date(remittance)

    def test_link_claim_to_remittance_cache_invalidation(self, db_session):
        """Test that cache is invalidated when linking claim to remittance."""
        from unittest.mock import patch
        from app.utils.cache import cache

        claim = ClaimFactory()
        remittance = RemittanceFactory()
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock cache methods to verify they're called
        with patch.object(cache, 'delete') as mock_delete, \
             patch.object(cache, 'delete_pattern') as mock_delete_pattern:
            episode = linker.link_claim_to_remittance(claim.id, remittance.id)
            
            # Verify cache invalidation was called
            assert mock_delete.called
            assert mock_delete_pattern.called

    def test_auto_link_by_control_number_cache_invalidation(self, db_session):
        """Test that cache is invalidated when auto-linking by control number."""
        from unittest.mock import patch
        from app.utils.cache import cache

        claim = ClaimFactory(claim_control_number="CLM001")
        remittance = RemittanceFactory(claim_control_number="CLM001")
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock cache methods to verify they're called
        with patch.object(cache, 'delete') as mock_delete, \
             patch.object(cache, 'delete_pattern') as mock_delete_pattern:
            episodes = linker.auto_link_by_control_number(remittance)
            
            # Verify cache invalidation was called
            assert len(episodes) == 1
            # Cache invalidation should be called for newly created episodes
            if episodes[0].id:
                assert mock_delete_pattern.called

    def test_update_episode_status_cache_invalidation(self, db_session):
        """Test that cache is invalidated when updating episode status."""
        from unittest.mock import patch
        from app.utils.cache import cache

        claim = ClaimFactory()
        remittance = RemittanceFactory()
        episode = ClaimEpisodeFactory(claim=claim, remittance=remittance, status=EpisodeStatus.LINKED)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock cache methods to verify they're called
        with patch.object(cache, 'delete') as mock_delete, \
             patch.object(cache, 'delete_pattern') as mock_delete_pattern:
            updated = linker.update_episode_status(episode.id, EpisodeStatus.COMPLETE)
            
            # Verify cache invalidation was called
            assert updated is not None
            assert mock_delete.called
            assert mock_delete_pattern.called

    def test_auto_link_by_patient_and_date_cache_invalidation(self, db_session):
        """Test that cache is invalidated when auto-linking by patient and date."""
        from datetime import timedelta
        from unittest.mock import patch
        from app.utils.cache import cache
        from tests.factories import PayerFactory

        payer = PayerFactory()
        payment_date = datetime.now()
        service_date = payment_date - timedelta(days=10)

        claim = ClaimFactory(payer=payer, service_date=service_date)
        remittance = RemittanceFactory(payer=payer, payment_date=payment_date)
        db_session.add(payer)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        
        # Mock cache methods to verify they're called
        with patch.object(cache, 'delete') as mock_delete, \
             patch.object(cache, 'delete_pattern') as mock_delete_pattern:
            episodes = linker.auto_link_by_patient_and_date(remittance)
            
            # Verify cache invalidation was called for newly created episodes
            assert len(episodes) == 1
            if episodes[0].id:
                assert mock_delete_pattern.called

    def test_auto_link_by_control_number_multiple_claims_existing_episodes(self, db_session):
        """Test auto-linking with multiple claims where some already have episodes."""
        from tests.factories import PayerFactory

        payer = PayerFactory()
        # Use different control numbers since claim_control_number must be unique
        # But remittance can match one of them
        claim1 = ClaimFactory(claim_control_number="CLM001", payer=payer)
        claim2 = ClaimFactory(claim_control_number="CLM002", payer=payer)
        # Remittance matches claim1's control number
        remittance = RemittanceFactory(claim_control_number="CLM001", payer=payer)
        
        # Create existing episode for claim1
        existing_episode = ClaimEpisodeFactory(claim=claim1, remittance=remittance)
        
        db_session.add(payer)
        db_session.add(claim1)
        db_session.add(claim2)
        db_session.add(remittance)
        db_session.add(existing_episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_control_number(remittance)

        # Should return existing episode for claim1 (matching control number)
        # claim2 won't match since it has different control number
        assert len(episodes) == 1
        assert episodes[0].id == existing_episode.id
        assert episodes[0].claim_id == claim1.id

    def test_auto_link_by_patient_and_date_no_new_episodes(self, db_session):
        """Test auto-linking when all claims already have episodes."""
        from datetime import timedelta
        from tests.factories import PayerFactory

        payer = PayerFactory()
        payment_date = datetime.now()
        service_date = payment_date - timedelta(days=10)

        claim = ClaimFactory(payer=payer, service_date=service_date)
        remittance = RemittanceFactory(payer=payer, payment_date=payment_date)
        # Create existing episode
        existing_episode = ClaimEpisodeFactory(claim=claim, remittance=remittance)
        
        db_session.add(payer)
        db_session.add(claim)
        db_session.add(remittance)
        db_session.add(existing_episode)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_patient_and_date(remittance)

        # Should return existing episode, no new ones created
        assert len(episodes) == 1
        assert episodes[0].id == existing_episode.id

