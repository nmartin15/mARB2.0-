"""Tests for episode linking functionality.

This module tests the episode linking service which connects claims to remittances
to create claim episodes. Episodes represent the complete lifecycle of a claim
from submission through payment/denial.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.database import ClaimEpisode, EpisodeStatus
from app.services.episodes.linker import EpisodeLinker
from tests.factories import ClaimFactory, RemittanceFactory


@pytest.mark.unit
class TestEpisodeLinking:
    """Tests for episode linking operations."""

    def test_auto_link_by_control_number_success(self, db_session: Session):
        """Test automatic linking by matching claim control number."""
        claim = ClaimFactory(claim_control_number="CLM12345")
        remittance = RemittanceFactory(claim_control_number="CLM12345")
        db_session.add_all([claim, remittance])
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_control_number(remittance)

        assert len(episodes) >= 1
        assert episodes[0].claim_id == claim.id
        assert episodes[0].remittance_id == remittance.id
        assert episodes[0].status == EpisodeStatus.LINKED

    def test_auto_link_by_control_number_no_match(self, db_session: Session):
        """Test linking when no matching control number exists."""
        remittance = RemittanceFactory(claim_control_number="NOMATCH123")
        db_session.add(remittance)
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_control_number(remittance)

        assert len(episodes) == 0

    def test_auto_link_by_patient_and_date(self, db_session: Session):
        """Test automatic linking by patient information and service date."""
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
        db_session.add_all([payer, claim, remittance])
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episodes = linker.auto_link_by_patient_and_date(remittance)

        # Should match by payer and date
        assert isinstance(episodes, list)
        assert len(episodes) == 1
        assert episodes[0].claim_id == claim.id
        assert episodes[0].remittance_id == remittance.id

    def test_link_creates_episode_with_correct_status(self, db_session: Session):
        """Test that linking creates episode with correct initial status."""
        claim = ClaimFactory(claim_control_number="CLM999")
        remittance = RemittanceFactory(
            claim_control_number="CLM999",
            payment_amount=Decimal("1500.00"),
        )
        db_session.add_all([claim, remittance])
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episode = linker.link_claim_to_remittance(claim.id, remittance.id)

        assert episode is not None
        assert episode.status == EpisodeStatus.LINKED
        assert episode.payment_amount == Decimal("1500.00")
        assert episode.claim_id == claim.id
        assert episode.remittance_id == remittance.id

    def test_link_prevents_duplicate_episodes(self, db_session: Session):
        """Test that linking the same claim-remittance pair twice doesn't create duplicates."""
        claim = ClaimFactory(claim_control_number="CLM888")
        remittance = RemittanceFactory(claim_control_number="CLM888")
        db_session.add_all([claim, remittance])
        db_session.commit()

        linker = EpisodeLinker(db_session)
        episode1 = linker.link_claim_to_remittance(claim.id, remittance.id)
        episode2 = linker.link_claim_to_remittance(claim.id, remittance.id)

        assert episode1 is not None
        assert episode2 is not None
        assert episode1.id == episode2.id  # Should return same episode
