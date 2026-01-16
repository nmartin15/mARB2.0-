"""Integration tests for count query caching in API routes."""
from fastapi.testclient import TestClient

from app.utils.cache import cache, count_cache_key


class TestCountCachingIntegration:
    """Test count caching in actual API routes."""

    def test_claims_list_uses_cached_count(self, db_session, client: TestClient):
        """Test that claims list endpoint uses cached count."""
        from tests.factories import ClaimFactory

        # Create some test claims
        for _ in range(3):
            claim = ClaimFactory()
            db_session.add(claim)
        db_session.commit()

        # Clear cache first
        count_key = count_cache_key("claim")
        cache.delete(count_key)

        # First request - should query database and cache result
        response = client.get("/api/v1/claims")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "claims" in data
        assert data["total"] >= 3  # At least our test data

        # Verify cache was set
        cached_count = cache.get(count_key)
        assert cached_count is not None
        assert cached_count == data["total"]

    def test_remits_list_uses_cached_count(self, db_session, client: TestClient):
        """Test that remits list endpoint uses cached count."""
        from tests.factories import RemittanceFactory

        # Create some test remittances
        for _ in range(2):
            remittance = RemittanceFactory()
            db_session.add(remittance)
        db_session.commit()

        # Clear cache first
        count_key = count_cache_key("remittance")
        cache.delete(count_key)

        # Make request
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "remits" in data

    def test_episodes_list_uses_cached_count(self, db_session, client: TestClient):
        """Test that episodes list endpoint uses cached count."""
        from tests.factories import ClaimEpisodeFactory

        # Create some test episodes
        for _ in range(4):
            episode = ClaimEpisodeFactory()
            db_session.add(episode)
        db_session.commit()

        # Clear cache first
        count_key = count_cache_key("episode")
        cache.delete(count_key)

        # Make request
        response = client.get("/api/v1/episodes")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "episodes" in data

    def test_episodes_list_with_filter_uses_cached_count(self, db_session, client: TestClient):
        """Test that episodes list with claim_id filter uses cached count."""
        from tests.factories import ClaimEpisodeFactory, ClaimFactory

        # Create a claim
        claim = ClaimFactory()
        db_session.add(claim)
        db_session.flush()

        # Create episodes for this claim
        for _ in range(2):
            episode = ClaimEpisodeFactory(claim=claim)
            db_session.add(episode)
        db_session.commit()

        # Clear cache for filtered count
        count_key = count_cache_key("episode", claim_id=claim.id)
        cache.delete(count_key)

        # Make request with filter
        response = client.get(f"/api/v1/episodes?claim_id={claim.id}")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "episodes" in data
        assert len(data["episodes"]) == 2

