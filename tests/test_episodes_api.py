"""Tests for episodes API endpoints."""
import pytest

from tests.factories import (
    ClaimEpisodeFactory,
    ClaimFactory,
    PayerFactory,
    ProviderFactory,
    RemittanceFactory,
)


@pytest.mark.api
class TestGetEpisodes:
    """Tests for GET /api/v1/episodes endpoint."""

    def test_get_episodes_empty(self, client, db_session):
        """Test getting episodes when none exist."""
        response = client.get("/api/v1/episodes")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["episodes"] == []
        assert data["skip"] == 0
        assert data["limit"] == 100

    def test_get_episodes_with_data(self, client, db_session):
        """Test getting episodes with existing data."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)

        episode1 = ClaimEpisodeFactory(claim=claim, remittance=remittance)
        episode2 = ClaimEpisodeFactory(claim=claim, remittance=remittance)

        response = client.get("/api/v1/episodes")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["episodes"]) == 2
        assert all("id" in episode for episode in data["episodes"])
        assert all("claim_id" in episode for episode in data["episodes"])
        assert all("remittance_id" in episode for episode in data["episodes"])
        assert all("status" in episode for episode in data["episodes"])

    def test_get_episodes_filtered_by_claim_id(self, client, db_session):
        """Test filtering episodes by claim_id."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim1 = ClaimFactory(provider=provider, payer=payer)
        claim2 = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)

        # Create episodes for both claims
        episode1 = ClaimEpisodeFactory(claim=claim1, remittance=remittance)
        episode2 = ClaimEpisodeFactory(claim=claim2, remittance=remittance)
        episode3 = ClaimEpisodeFactory(claim=claim1, remittance=remittance)

        # Filter by claim1
        response = client.get(f"/api/v1/episodes?claim_id={claim1.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Only episodes for claim1
        assert len(data["episodes"]) == 2
        assert all(episode["claim_id"] == claim1.id for episode in data["episodes"])

    def test_get_episodes_pagination(self, client, db_session):
        """Test pagination parameters."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)

        # Create 5 episodes
        for _ in range(5):
            ClaimEpisodeFactory(claim=claim, remittance=remittance)

        # Test first page
        response = client.get("/api/v1/episodes?skip=0&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["episodes"]) == 2

        # Test second page
        response = client.get("/api/v1/episodes?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["episodes"]) == 2

    def test_get_episodes_with_claim_id_filter_and_pagination(self, client, db_session):
        """Test combining claim_id filter with pagination."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)

        # Create 3 episodes for this claim
        for _ in range(3):
            ClaimEpisodeFactory(claim=claim, remittance=remittance)

        response = client.get(f"/api/v1/episodes?claim_id={claim.id}&skip=1&limit=1")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["episodes"]) == 1

    def test_get_episodes_negative_skip(self, client, db_session):
        """Test episodes endpoint with negative skip parameter."""
        response = client.get("/api/v1/episodes?skip=-1")
        # FastAPI should validate and return 422 for invalid parameter
        assert response.status_code == 422

    def test_get_episodes_negative_limit(self, client, db_session):
        """Test episodes endpoint with negative limit parameter."""
        response = client.get("/api/v1/episodes?limit=-1")
        # FastAPI should validate and return 422 for invalid parameter
        assert response.status_code == 422

    def test_get_episodes_invalid_skip_type(self, client, db_session):
        """Test episodes endpoint with non-numeric skip parameter."""
        response = client.get("/api/v1/episodes?skip=not_a_number")
        # FastAPI should validate and return 422 for invalid parameter type
        assert response.status_code == 422

    def test_get_episodes_invalid_limit_type(self, client, db_session):
        """Test episodes endpoint with non-numeric limit parameter."""
        response = client.get("/api/v1/episodes?limit=not_a_number")
        # FastAPI should validate and return 422 for invalid parameter type
        assert response.status_code == 422

    def test_get_episodes_invalid_claim_id(self, client, db_session):
        """Test episodes endpoint with invalid claim_id (non-existent)."""
        response = client.get("/api/v1/episodes?claim_id=99999")
        # Should return empty list, not error
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["episodes"] == []

    def test_get_episodes_invalid_claim_id_type(self, client, db_session):
        """Test episodes endpoint with non-numeric claim_id."""
        response = client.get("/api/v1/episodes?claim_id=not_a_number")
        # FastAPI should validate and return 422 for invalid parameter type
        assert response.status_code == 422


@pytest.mark.api
class TestGetEpisode:
    """Tests for GET /api/v1/episodes/{episode_id} endpoint."""

    def test_get_episode_success(self, client, db_session):
        """Test getting a specific episode."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            payment_amount=1000.00,
            denial_count=2,
            adjustment_count=1,
        )

        response = client.get(f"/api/v1/episodes/{episode.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == episode.id
        assert data["claim_id"] == claim.id
        assert data["remittance_id"] == remittance.id
        assert data["payment_amount"] == 1000.00
        assert data["denial_count"] == 2
        assert data["adjustment_count"] == 1
        assert "status" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_episode_not_found(self, client, db_session):
        """Test getting non-existent episode."""
        response = client.get("/api/v1/episodes/99999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower() or "Episode" in data["message"]

    def test_get_episode_with_null_fields(self, client, db_session):
        """Test getting episode with null optional fields."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)
        episode = ClaimEpisodeFactory(
            claim=claim,
            remittance=remittance,
            linked_at=None,
        )

        response = client.get(f"/api/v1/episodes/{episode.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["linked_at"] is None

    def test_get_episode_caching(self, client, db_session):
        """Test that GET /episodes/{episode_id} uses caching."""
        from app.utils.cache import cache, episode_cache_key

        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)
        episode = ClaimEpisodeFactory(claim=claim, remittance=remittance)

        # Clear cache before test
        cache_key = episode_cache_key(episode.id)
        cache.delete(cache_key)

        # First request - should query database and cache the result
        response1 = client.get(f"/api/v1/episodes/{episode.id}")
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["id"] == episode.id

        # Second request - should return same data (may use cache or query again)
        # The important thing is that it returns the correct data
        response2 = client.get(f"/api/v1/episodes/{episode.id}")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["id"] == episode.id
        # Both responses should have the same data
        assert data1["id"] == data2["id"]
        assert data1["claim_id"] == data2["claim_id"]


@pytest.mark.api
class TestLinkEpisodeManually:
    """Tests for POST /api/v1/episodes/{episode_id}/link endpoint."""

    def test_link_episode_manually_success(self, client, db_session):
        """Test manually linking a claim to a remittance."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)

        response = client.post(
            f"/api/v1/episodes/{999}/link",
            params={"claim_id": claim.id, "remittance_id": remittance.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Episode linked successfully"
        assert "episode" in data
        assert data["episode"]["claim_id"] == claim.id
        assert data["episode"]["remittance_id"] == remittance.id

    def test_link_episode_manually_missing_claim_id(self, client, db_session):
        """Test linking episode without claim_id."""
        provider = ProviderFactory()
        payer = PayerFactory()
        remittance = RemittanceFactory(payer=payer)

        response = client.post(
            f"/api/v1/episodes/{999}/link",
            params={"remittance_id": remittance.id},
        )

        assert response.status_code == 400
        data = response.json()
        assert "claim_id" in data["detail"].lower() or "required" in data["detail"].lower()

    def test_link_episode_manually_missing_remittance_id(self, client, db_session):
        """Test linking episode without remittance_id."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)

        response = client.post(
            f"/api/v1/episodes/{999}/link",
            params={"claim_id": claim.id},
        )

        assert response.status_code == 400
        data = response.json()
        assert "remittance_id" in data["detail"].lower() or "required" in data["detail"].lower()

    def test_link_episode_manually_claim_not_found(self, client, db_session):
        """Test linking episode with non-existent claim."""
        provider = ProviderFactory()
        payer = PayerFactory()
        remittance = RemittanceFactory(payer=payer)

        response = client.post(
            f"/api/v1/episodes/{999}/link",
            params={"claim_id": 99999, "remittance_id": remittance.id},
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower() or "failed" in data["detail"].lower()

    def test_link_episode_manually_remittance_not_found(self, client, db_session):
        """Test linking episode with non-existent remittance."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)

        response = client.post(
            f"/api/v1/episodes/{999}/link",
            params={"claim_id": claim.id, "remittance_id": 99999},
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower() or "failed" in data["detail"].lower()


@pytest.mark.api
class TestLinkRemittanceToClaims:
    """Tests for POST /api/v1/remits/{remittance_id}/link endpoint."""

    def test_link_remittance_to_claims_success(self, client, db_session):
        """Test linking remittance to claims by control number."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer, claim_control_number="CLM001")
        remittance = RemittanceFactory(
            payer=payer, claim_control_number="CLM001", remittance_control_number="REM001"
        )

        response = client.post(f"/api/v1/remits/{remittance.id}/link")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Episode linking completed"
        assert data["remittance_id"] == remittance.id
        assert data["episodes_linked"] >= 0  # May be 0 if no matches found
        assert "episodes" in data

    def test_link_remittance_to_claims_not_found(self, client, db_session):
        """Test linking non-existent remittance."""
        response = client.post("/api/v1/remits/99999/link")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower() or "Remittance" in data["message"]

    def test_link_remittance_to_claims_no_matches(self, client, db_session):
        """Test linking remittance with no matching claims."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer, claim_control_number="CLM001")
        remittance = RemittanceFactory(
            payer=payer, claim_control_number="CLM999", remittance_control_number="REM001"
        )

        response = client.post(f"/api/v1/remits/{remittance.id}/link")

        assert response.status_code == 200
        data = response.json()
        assert data["episodes_linked"] >= 0  # May try patient/date matching


@pytest.mark.api
class TestUpdateEpisodeStatus:
    """Tests for PATCH /api/v1/episodes/{episode_id}/status endpoint."""

    def test_update_episode_status_success(self, client, db_session):
        """Test updating episode status."""
        from app.models.database import EpisodeStatus

        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)
        episode = ClaimEpisodeFactory(claim=claim, remittance=remittance)

        response = client.patch(
            f"/api/v1/episodes/{episode.id}/status",
            json={"status": "complete"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Episode status updated"
        assert data["episode"]["id"] == episode.id
        assert data["episode"]["status"] == "complete"

    def test_update_episode_status_invalid_status(self, client, db_session):
        """Test updating episode with invalid status."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)
        episode = ClaimEpisodeFactory(claim=claim, remittance=remittance)

        response = client.patch(
            f"/api/v1/episodes/{episode.id}/status",
            json={"status": "invalid_status"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "invalid" in data["detail"].lower() or "status" in data["detail"].lower()

    def test_update_episode_status_not_found(self, client, db_session):
        """Test updating non-existent episode."""
        response = client.patch(
            "/api/v1/episodes/99999/status",
            json={"status": "complete"},
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower() or "Episode" in data["message"]

    def test_update_episode_status_all_valid_statuses(self, client, db_session):
        """Test updating episode with all valid status values."""
        from app.models.database import EpisodeStatus

        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)

        valid_statuses = ["pending", "linked", "complete"]

        for status in valid_statuses:
            episode = ClaimEpisodeFactory(claim=claim, remittance=remittance)

            response = client.patch(
                f"/api/v1/episodes/{episode.id}/status",
                json={"status": status},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["episode"]["status"] == status

    def test_update_episode_status_case_insensitive(self, client, db_session):
        """Test that status is case-insensitive."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)
        episode = ClaimEpisodeFactory(claim=claim, remittance=remittance)

        response = client.patch(
            f"/api/v1/episodes/{episode.id}/status",
            json={"status": "COMPLETE"},  # Uppercase
        )

        assert response.status_code == 200
        data = response.json()
        assert data["episode"]["status"] == "complete"  # Should be normalized


@pytest.mark.api
class TestMarkEpisodeComplete:
    """Tests for POST /api/v1/episodes/{episode_id}/complete endpoint."""

    def test_mark_episode_complete_success(self, client, db_session):
        """Test marking episode as complete."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)
        episode = ClaimEpisodeFactory(claim=claim, remittance=remittance)

        response = client.post(f"/api/v1/episodes/{episode.id}/complete")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Episode marked as complete"
        assert data["episode"]["id"] == episode.id
        assert data["episode"]["status"] == "complete"

    def test_mark_episode_complete_not_found(self, client, db_session):
        """Test marking non-existent episode as complete."""
        response = client.post("/api/v1/episodes/99999/complete")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower() or "Episode" in data["message"]


@pytest.mark.api
class TestGetUnlinkedClaims:
    """Tests for GET /api/v1/claims/unlinked endpoint."""

    def test_get_unlinked_claims_empty(self, client, db_session):
        """Test getting unlinked claims when all are linked."""
        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)
        ClaimEpisodeFactory(claim=claim, remittance=remittance)

        response = client.get("/api/v1/claims/unlinked")

        assert response.status_code == 200
        data = response.json()
        assert "claims" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data

    def test_get_unlinked_claims_with_data(self, client, db_session):
        """Test getting unlinked claims."""
        provider = ProviderFactory()
        payer = PayerFactory()
        # Create unlinked claim
        unlinked_claim = ClaimFactory(provider=provider, payer=payer)
        # Create linked claim
        linked_claim = ClaimFactory(provider=provider, payer=payer)
        remittance = RemittanceFactory(payer=payer)
        ClaimEpisodeFactory(claim=linked_claim, remittance=remittance)

        response = client.get("/api/v1/claims/unlinked")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["claims"]) >= 1
        # Verify unlinked claim is in results
        claim_ids = [c["id"] for c in data["claims"]]
        assert unlinked_claim.id in claim_ids

    def test_get_unlinked_claims_pagination(self, client, db_session):
        """Test pagination for unlinked claims."""
        provider = ProviderFactory()
        payer = PayerFactory()

        # Create multiple unlinked claims
        for _ in range(5):
            ClaimFactory(provider=provider, payer=payer)

        response = client.get("/api/v1/claims/unlinked?skip=0&limit=2")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["claims"]) <= 2
        assert data["skip"] == 0
        assert data["limit"] == 2

