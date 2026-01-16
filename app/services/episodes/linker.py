"""Link claims to remittances to create episodes."""
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.database import Claim, Remittance, ClaimEpisode, EpisodeStatus
from app.utils.logger import get_logger
from app.utils.notifications import notify_episode_linked, notify_episode_completed
from app.utils.cache import cache, episode_cache_key, count_cache_key

logger = get_logger(__name__)


class EpisodeLinker:
    """
    Links claims to remittances to create and manage claim episodes.

    This class provides methods for linking claims and remittances,
    automatically linking them based on various criteria, updating episode
    statuses, and retrieving episode information.
    """

    def __init__(self, db: Session):
        self.db = db

    def link_claim_to_remittance(
        self, claim_id: int, remittance_id: int
    ) -> Optional[ClaimEpisode]:
        """
        Link a claim to a remittance. Optimized with error handling.
        
        Args:
            claim_id: The ID of the claim to link
            remittance_id: The ID of the remittance to link
            
        Returns:
            ClaimEpisode instance if successful, None otherwise
            
        Raises:
            Exception: If database operations fail
        """
        try:
            # Optimize: Use single query with join to fetch both objects efficiently
            from sqlalchemy.orm import joinedload
            
            # Fetch claim and remittance in separate queries (simpler and clearer)
            # Could be optimized further with a single query if needed
            claim = self.db.query(Claim).filter(Claim.id == claim_id).first()
            if not claim:
                logger.warning("Claim not found", claim_id=claim_id)
                return None

            remittance = self.db.query(Remittance).filter(Remittance.id == remittance_id).first()
            if not remittance:
                logger.warning("Remittance not found", remittance_id=remittance_id)
                return None

            # Check if episode already exists - eager load relationships to avoid N+1
            from sqlalchemy.orm import joinedload
            
            existing = (
                self.db.query(ClaimEpisode)
                .options(
                    joinedload(ClaimEpisode.claim),
                    joinedload(ClaimEpisode.remittance)
                )
                .filter(
                    ClaimEpisode.claim_id == claim_id,
                    ClaimEpisode.remittance_id == remittance_id,
                )
                .first()
            )

            if existing:
                logger.info("Episode already exists", episode_id=existing.id)
                return existing

            # Create new episode
            episode = ClaimEpisode(
                claim_id=claim_id,
                remittance_id=remittance_id,
                status=EpisodeStatus.LINKED,
                linked_at=datetime.now(),
                payment_amount=remittance.payment_amount,
                denial_count=len(remittance.denial_reasons or []),
                adjustment_count=len(remittance.adjustment_reasons or []),
            )

            self.db.add(episode)
            try:
                self.db.flush()
            except Exception as flush_error:
                logger.error(
                    "Failed to flush episode to database",
                    error=str(flush_error),
                    claim_id=claim_id,
                    remittance_id=remittance_id,
                    exc_info=True,
                )
                raise
            
            logger.info("Episode created", episode_id=episode.id, claim_id=claim_id, remittance_id=remittance_id)

            # Invalidate cache for the new episode and related caches
            # IMPORTANT: Must invalidate cache when episodes are created/modified
            # to ensure cache consistency across all callers (API routes, Celery tasks, etc.)
            cache_key = episode_cache_key(episode.id)
            cache.delete(cache_key)
            cache.delete_pattern(f"episode:{episode.id}*")
            cache.delete_pattern("count:episode*")

            # Send WebSocket notification (non-blocking)
            try:
                notify_episode_linked(
                    episode.id,
                    {
                        "claim_id": claim_id,
                        "remittance_id": remittance_id,
                        "status": episode.status.value,
                    },
                )
            except Exception as e:
                logger.warning("Failed to send episode linked notification", error=str(e), episode_id=episode.id)

            return episode
        except Exception as e:
            logger.error(
                "Failed to link claim to remittance",
                error=str(e),
                claim_id=claim_id,
                remittance_id=remittance_id,
                exc_info=True,
            )
            raise

    def auto_link_by_control_number(self, remittance: Remittance) -> List[ClaimEpisode]:
        """
        Automatically link remittance to claim(s) by control number. 
        Optimized with batch operations and error handling.
        
        Args:
            remittance: The remittance to link to claims
            
        Returns:
            List of ClaimEpisode instances that were created or already existed
            
        Raises:
            Exception: If database operations fail
        """
        try:
            if not remittance.claim_control_number:
                logger.warning("Remittance has no claim control number", remittance_id=remittance.id)
                return []

            # Find matching claims
            claims = (
                self.db.query(Claim)
                .filter(Claim.claim_control_number == remittance.claim_control_number)
                .all()
            )

            if not claims:
                logger.warning(
                    "No matching claims found",
                    claim_control_number=remittance.claim_control_number,
                )
                return []

            # Optimize: Batch check for existing episodes instead of individual queries
            # Eager load relationships to avoid N+1 queries if relationships are accessed
            from sqlalchemy.orm import joinedload
            
            claim_ids = [claim.id for claim in claims]
            existing_episodes = (
                self.db.query(ClaimEpisode)
                .options(
                    joinedload(ClaimEpisode.claim),
                    joinedload(ClaimEpisode.remittance)
                )
                .filter(
                    ClaimEpisode.claim_id.in_(claim_ids),
                    ClaimEpisode.remittance_id == remittance.id,
                )
                .all()
            )
            existing_episodes_dict = {ep.claim_id: ep for ep in existing_episodes}

            # Create episodes for claims that don't already have one
            new_episodes = []
            for claim in claims:
                if claim.id in existing_episodes_dict:
                    # Use existing episode
                    existing = existing_episodes_dict[claim.id]
                    new_episodes.append(existing)
                else:
                    # Create new episode (optimized: batch create)
                    episode = ClaimEpisode(
                        claim_id=claim.id,
                        remittance_id=remittance.id,
                        status=EpisodeStatus.LINKED,
                        linked_at=datetime.now(),
                        payment_amount=remittance.payment_amount,
                        denial_count=len(remittance.denial_reasons or []),
                        adjustment_count=len(remittance.adjustment_reasons or []),
                    )
                    self.db.add(episode)
                    new_episodes.append(episode)

            # Batch flush instead of individual flushes
            try:
                self.db.flush()
            except Exception as flush_error:
                logger.error(
                    "Failed to flush episodes to database",
                    error=str(flush_error),
                    remittance_id=remittance.id,
                    episode_count=len(new_episodes),
                    exc_info=True,
                )
                raise

            # Invalidate cache for all newly created episodes
            # IMPORTANT: Must invalidate cache when episodes are created/modified
            # to ensure cache consistency across all callers (API routes, Celery tasks, etc.)
            for episode in new_episodes:
                if episode.id:  # Only invalidate for newly created episodes
                    cache_key = episode_cache_key(episode.id)
                    cache.delete(cache_key)
                    cache.delete_pattern(f"episode:{episode.id}*")
            
            # Invalidate count caches for episodes (both filtered and unfiltered)
            cache.delete_pattern("count:episode*")

            # Send notifications in batch (non-blocking)
            for episode in new_episodes:
                if episode.id:  # Only notify for newly created episodes
                    try:
                        notify_episode_linked(
                            episode.id,
                            {
                                "claim_id": episode.claim_id,
                                "remittance_id": episode.remittance_id,
                                "status": episode.status.value,
                            },
                        )
                    except Exception as e:
                        logger.warning("Failed to send episode linked notification", error=str(e), episode_id=episode.id)

            logger.info(
                "Auto-linked remittance to claims",
                remittance_id=remittance.id,
                episode_count=len(new_episodes),
            )

            return new_episodes
        except Exception as e:
            logger.error(
                "Failed to auto-link by control number",
                error=str(e),
                remittance_id=remittance.id if remittance else None,
                exc_info=True,
            )
            raise

    def get_episodes_for_claim(self, claim_id: int) -> List[ClaimEpisode]:
        """
        Get all episodes for a claim. Optimized with eager loading.
        
        Args:
            claim_id: The ID of the claim to get episodes for
            
        Returns:
            List of ClaimEpisode instances, ordered by creation date (newest first)
        """
        try:
            from sqlalchemy.orm import joinedload
            
            # Eager load remittance to avoid N+1 queries if remittance data is accessed
            episodes = (
                self.db.query(ClaimEpisode)
                .options(joinedload(ClaimEpisode.remittance))
                .filter(ClaimEpisode.claim_id == claim_id)
                .order_by(ClaimEpisode.created_at.desc())
                .all()
            )
            return episodes
        except Exception as e:
            logger.error(
                "Failed to get episodes for claim",
                error=str(e),
                claim_id=claim_id,
                exc_info=True,
            )
            raise

    def get_unlinked_claims(self, limit: int = 100) -> List[Claim]:
        """
        Get claims that haven't been linked to remittances. Optimized query.
        
        Args:
            limit: Maximum number of claims to return (default: 100)
            
        Returns:
            List of Claim instances that have no associated episodes
        """
        try:
            # Optimize: Use NOT EXISTS subquery for better performance than outer join
            from sqlalchemy import not_
            
            subquery = (
                self.db.query(ClaimEpisode)
                .filter(ClaimEpisode.claim_id == Claim.id)
                .exists()
            )
            
            claims = (
                self.db.query(Claim)
                .filter(not_(subquery))
                .limit(limit)
                .all()
            )
            return claims
        except Exception as e:
            logger.error(
                "Failed to get unlinked claims",
                error=str(e),
                limit=limit,
                exc_info=True,
            )
            raise

    def update_episode_status(
        self, episode_id: int, status: EpisodeStatus
    ) -> Optional[ClaimEpisode]:
        """
        Update the status of an episode. Includes error handling.
        
        Args:
            episode_id: The ID of the episode to update
            status: The new status to set
            
        Returns:
            ClaimEpisode instance if found and updated, None otherwise
            
        Raises:
            Exception: If database operations fail
        """
        try:
            # Eager load relationships to avoid N+1 queries if relationships are accessed
            from sqlalchemy.orm import joinedload
            
            episode = (
                self.db.query(ClaimEpisode)
                .options(
                    joinedload(ClaimEpisode.claim),
                    joinedload(ClaimEpisode.remittance)
                )
                .filter(ClaimEpisode.id == episode_id)
                .first()
            )

            if not episode:
                logger.warning("Episode not found", episode_id=episode_id)
                return None

            episode.status = status
            if status == EpisodeStatus.COMPLETE:
                episode.linked_at = episode.linked_at or datetime.now()

            try:
                self.db.flush()
            except Exception as flush_error:
                logger.error(
                    "Failed to flush episode status update to database",
                    error=str(flush_error),
                    episode_id=episode_id,
                    status=status.value,
                    exc_info=True,
                )
                raise
            
            logger.info("Episode status updated", episode_id=episode_id, status=status.value)

            # Invalidate cache for this episode
            # IMPORTANT: Must use the same cache key function as get_episode endpoint
            # to ensure cache consistency. If episode_cache_key is modified to include
            # additional parameters (e.g., user_id), this invalidation must be updated
            # to match, or use pattern-based invalidation.
            cache_key = episode_cache_key(episode_id)
            cache.delete(cache_key)
            
            # Also invalidate any pattern-based variations (defensive measure)
            # This ensures we catch any cache keys that might have been created with
            # additional parameters or variations
            cache.delete_pattern(f"episode:{episode_id}*")
            
            # Invalidate count caches for episodes (both filtered and unfiltered)
            # This ensures count queries reflect the updated episodes
            cache.delete_pattern("count:episode*")

            # Send WebSocket notification if episode is completed (non-blocking)
            if status == EpisodeStatus.COMPLETE:
                try:
                    notify_episode_completed(
                        episode_id,
                        {
                            "claim_id": episode.claim_id,
                            "remittance_id": episode.remittance_id,
                        },
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to send episode completed notification",
                        error=str(e),
                        episode_id=episode_id,
                    )

            return episode
        except Exception as e:
            logger.error(
                "Failed to update episode status",
                error=str(e),
                episode_id=episode_id,
                status=status.value,
                exc_info=True,
            )
            raise

    def mark_episode_complete(self, episode_id: int) -> Optional[ClaimEpisode]:
        """Mark an episode as complete."""
        return self.update_episode_status(episode_id, EpisodeStatus.COMPLETE)

    def auto_link_by_patient_and_date(
        self, remittance: Remittance, days_tolerance: int = 30
    ) -> List[ClaimEpisode]:
        """
        Automatically link remittance to claim(s) by patient ID and date range.
        
        This is a fallback when control number matching fails.
        Optimized with batch operations and error handling.
        
        Args:
            remittance: The remittance to link to claims
            days_tolerance: Number of days before/after payment date to search (default: 30)
            
        Returns:
            List of ClaimEpisode instances that were created
            
        Raises:
            Exception: If database operations fail
        """
        try:
            if not remittance.payer_id:
                logger.warning("Remittance has no payer ID", remittance_id=remittance.id)
                return []

            # Try to find claims by patient and date range
            # Note: This requires patient_id on both Claim and Remittance
            # For now, we'll use a simplified approach matching by payer and date
            
            from datetime import timedelta

            if not remittance.payment_date:
                logger.warning("Remittance has no payment date", remittance_id=remittance.id)
                return []

            date_start = remittance.payment_date - timedelta(days=days_tolerance)
            date_end = remittance.payment_date + timedelta(days=days_tolerance)

            # Find claims for the same payer within date range
            claims = (
                self.db.query(Claim)
                .filter(
                    Claim.payer_id == remittance.payer_id,
                    Claim.service_date >= date_start,
                    Claim.service_date <= date_end,
                )
                .all()
            )

            if not claims:
                logger.info(
                    "No matching claims found by patient/date",
                    remittance_id=remittance.id,
                    payer_id=remittance.payer_id,
                )
                return []

            # Optimize: Batch check for existing episodes instead of querying in loop
            # Eager load relationships to avoid N+1 queries if relationships are accessed
            from sqlalchemy.orm import joinedload
            
            claim_ids = [claim.id for claim in claims]
            existing_episodes = (
                self.db.query(ClaimEpisode)
                .options(
                    joinedload(ClaimEpisode.claim),
                    joinedload(ClaimEpisode.remittance)
                )
                .filter(
                    ClaimEpisode.claim_id.in_(claim_ids),
                    ClaimEpisode.remittance_id == remittance.id,
                )
                .all()
            )
            # Use dictionary for O(1) lookups and to return existing episodes
            existing_episodes_dict = {ep.claim_id: ep for ep in existing_episodes}

            # Create episodes for claims that don't already have one
            all_episodes = []
            newly_created_episodes = []
            for claim in claims:
                if claim.id in existing_episodes_dict:
                    # Use existing episode
                    existing = existing_episodes_dict[claim.id]
                    all_episodes.append(existing)
                else:
                    # Create new episode (optimized: batch create)
                    episode = ClaimEpisode(
                        claim_id=claim.id,
                        remittance_id=remittance.id,
                        status=EpisodeStatus.LINKED,
                        linked_at=datetime.now(),
                        payment_amount=remittance.payment_amount,
                        denial_count=len(remittance.denial_reasons or []),
                        adjustment_count=len(remittance.adjustment_reasons or []),
                    )
                    self.db.add(episode)
                    all_episodes.append(episode)
                    newly_created_episodes.append(episode)

            # Batch flush instead of individual flushes
            if newly_created_episodes:
                try:
                    self.db.flush()
                except Exception as flush_error:
                    logger.error(
                        "Failed to flush episodes to database",
                        error=str(flush_error),
                        remittance_id=remittance.id,
                        episode_count=len(newly_created_episodes),
                        exc_info=True,
                    )
                    raise

                # Invalidate cache for all newly created episodes
                # IMPORTANT: Must invalidate cache when episodes are created/modified
                # to ensure cache consistency across all callers (API routes, Celery tasks, etc.)
                for episode in newly_created_episodes:
                    if episode.id:  # Only invalidate for newly created episodes
                        cache_key = episode_cache_key(episode.id)
                        cache.delete(cache_key)
                        cache.delete_pattern(f"episode:{episode.id}*")
                
                # Invalidate count caches for episodes (both filtered and unfiltered)
                cache.delete_pattern("count:episode*")

                # Send notifications in batch (non-blocking) - only for newly created episodes
                for episode in newly_created_episodes:
                    if episode.id:  # Only notify for newly created episodes
                        try:
                            notify_episode_linked(
                                episode.id,
                                {
                                    "claim_id": episode.claim_id,
                                    "remittance_id": episode.remittance_id,
                                    "status": episode.status.value,
                                },
                            )
                        except Exception as e:
                            logger.warning("Failed to send episode linked notification", error=str(e), episode_id=episode.id)

            logger.info(
                "Auto-linked remittance to claims by patient/date",
                remittance_id=remittance.id,
                episode_count=len(all_episodes),
                newly_created_count=len(newly_created_episodes),
            )

            return all_episodes
        except Exception as e:
            logger.error(
                "Failed to auto-link by patient and date",
                error=str(e),
                remittance_id=remittance.id if remittance else None,
                exc_info=True,
            )
            raise

    def complete_episode_if_ready(self, episode_id: int) -> Optional[ClaimEpisode]:
        """
        Mark episode as COMPLETE if remittance processing is finished.
        
        An episode is ready to be marked complete when:
        - It has a remittance
        - The remittance has been fully processed (status is PROCESSED)
        
        Optimized with eager loading to avoid N+1 queries by fetching the remittance
        in the same query as the episode.
        
        Args:
            episode_id: The ID of the episode to check and potentially complete
            
        Returns:
            ClaimEpisode instance if found, None otherwise. Returns the episode
            unchanged if it's already complete or if remittance is not yet processed.
        """
        # Optimize: Use eager loading to fetch remittance in same query
        from sqlalchemy.orm import joinedload
        from app.models.database import RemittanceStatus

        episode = (
            self.db.query(ClaimEpisode)
            .options(joinedload(ClaimEpisode.remittance))
            .filter(ClaimEpisode.id == episode_id)
            .first()
        )

        if not episode:
            logger.warning("Episode not found", episode_id=episode_id)
            return None

        if episode.status == EpisodeStatus.COMPLETE:
            return episode

        if not episode.remittance:
            logger.warning("Episode has no remittance", episode_id=episode_id)
            return episode

        # Check if remittance is fully processed
        if episode.remittance.status == RemittanceStatus.PROCESSED:
            return self.mark_episode_complete(episode_id)

        return episode

