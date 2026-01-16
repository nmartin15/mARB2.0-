"""Episode endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, subqueryload
from pydantic import BaseModel

from app.config.database import get_db
from app.config.cache_ttl import get_episode_ttl, get_count_ttl
from app.services.episodes.linker import EpisodeLinker
from app.models.database import EpisodeStatus
from app.utils.errors import NotFoundError
from app.utils.logger import get_logger
from app.utils.cache import cache, episode_cache_key, count_cache_key

router = APIRouter()
logger = get_logger(__name__)


class UpdateEpisodeStatusRequest(BaseModel):
    """Request model for updating episode status."""

    status: str


@router.get("/episodes")
async def get_episodes(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records to return"),
    claim_id: int = Query(default=None, description="Filter by claim ID"),
    db: Session = Depends(get_db),
):
    """
    Get list of claim episodes.
    
    Uses subqueryload to eagerly load claim and remittance relationships,
    preventing N+1 queries when accessing related data. This is especially
    important when claim_id is not provided and we're fetching all episodes,
    as it ensures all related data is loaded in efficient separate queries
    rather than one query per episode.
    """
    from app.models.database import ClaimEpisode
    
    # Use subqueryload instead of joinedload for better performance with large datasets.
    # subqueryload loads related entities in separate queries, which is more efficient
    # than joinedload when dealing with many episodes, as it avoids cartesian product
    # issues and reduces memory usage.
    base_query = db.query(ClaimEpisode)
    
    if claim_id:
        base_query = base_query.filter(ClaimEpisode.claim_id == claim_id)
    
    # Use cached count for better performance (with filter key if applicable)
    count_key = count_cache_key("episode", claim_id=claim_id) if claim_id else count_cache_key("episode")
    cached_count = cache.get(count_key)
    if cached_count is not None:
        total = cached_count
    else:
        # Count without eager loading for better performance
        # Eager loading options don't affect count(), but it's cleaner to count separately
        total = base_query.count()
        cache.set(count_key, total, ttl_seconds=get_count_ttl())
    
    # Apply eager loading and pagination for the actual data query
    query = base_query.options(
        subqueryload(ClaimEpisode.claim),
        subqueryload(ClaimEpisode.remittance)
    )
    episodes = query.offset(skip).limit(limit).all()
    
    return {
        "episodes": [
            {
                "id": episode.id,
                "claim_id": episode.claim_id,
                "remittance_id": episode.remittance_id,
                "status": episode.status.value if episode.status else None,
                "payment_amount": episode.payment_amount,
                "denial_count": episode.denial_count,
                "adjustment_count": episode.adjustment_count,
                "linked_at": episode.linked_at.isoformat() if episode.linked_at else None,
                "created_at": episode.created_at.isoformat() if episode.created_at else None,
            }
            for episode in episodes
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/episodes/{episode_id}")
async def get_episode(episode_id: int, db: Session = Depends(get_db)):
    """Get episode by ID (cached)."""
    from app.models.database import ClaimEpisode
    from app.utils.errors import NotFoundError
    from sqlalchemy.orm import joinedload
    
    # Try cache first
    cache_key = episode_cache_key(episode_id)
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # Eager load relationships to avoid N+1 queries if relationships are accessed later
    episode = (
        db.query(ClaimEpisode)
        .options(
            joinedload(ClaimEpisode.claim),
            joinedload(ClaimEpisode.remittance)
        )
        .filter(ClaimEpisode.id == episode_id)
        .first()
    )
    
    if not episode:
        raise NotFoundError("Episode", str(episode_id))
    
    result = {
        "id": episode.id,
        "claim_id": episode.claim_id,
        "remittance_id": episode.remittance_id,
        "status": episode.status.value if episode.status else None,
        "payment_amount": episode.payment_amount,
        "denial_count": episode.denial_count,
        "adjustment_count": episode.adjustment_count,
        "linked_at": episode.linked_at.isoformat() if episode.linked_at else None,
        "created_at": episode.created_at.isoformat() if episode.created_at else None,
        "updated_at": episode.updated_at.isoformat() if episode.updated_at else None,
    }
    
    # Cache with configured TTL
    cache.set(cache_key, result, ttl_seconds=get_episode_ttl())
    return result


@router.post("/episodes/{episode_id}/link")
async def link_episode_manually(
    episode_id: int,
    claim_id: int = None,
    remittance_id: int = None,
    db: Session = Depends(get_db),
):
    """Manually link a claim to a remittance to create an episode."""
    from app.models.database import ClaimEpisode

    linker = EpisodeLinker(db)

    if not claim_id or not remittance_id:
        raise HTTPException(
            status_code=400, detail="Both claim_id and remittance_id are required"
        )

    episode = linker.link_claim_to_remittance(claim_id, remittance_id)

    if not episode:
        raise HTTPException(
            status_code=404, detail="Failed to link episode. Claim or remittance not found."
        )

    db.commit()

    # Invalidate cache for the new episode and related caches
    # Invalidate the specific episode cache (if it was queried before)
    cache_key = episode_cache_key(episode.id)
    cache.delete(cache_key)
    
    # Invalidate pattern-based variations (defensive measure)
    cache.delete_pattern(f"episode:{episode.id}*")
    
    # Invalidate count caches for episodes (both filtered and unfiltered)
    # This ensures the episodes list endpoint shows the new episode
    cache.delete_pattern("count:episode*")

    return {
        "message": "Episode linked successfully",
        "episode": {
            "id": episode.id,
            "claim_id": episode.claim_id,
            "remittance_id": episode.remittance_id,
            "status": episode.status.value if episode.status else None,
        },
    }


@router.post("/remits/{remittance_id}/link")
async def link_remittance_to_claims(
    remittance_id: int,
    db: Session = Depends(get_db),
):
    """Manually trigger episode linking for a remittance."""
    from app.models.database import Remittance

    remittance = db.query(Remittance).filter(Remittance.id == remittance_id).first()

    if not remittance:
        raise NotFoundError("Remittance", str(remittance_id))

    linker = EpisodeLinker(db)
    episodes = linker.auto_link_by_control_number(remittance)

    # If no matches by control number, try patient/date matching
    if not episodes:
        logger.info("No matches by control number, trying patient/date matching", remittance_id=remittance_id)
        episodes = linker.auto_link_by_patient_and_date(remittance)

    db.commit()

    # Invalidate cache for all newly created episodes and related caches
    # This ensures the episodes list endpoint shows the new episodes
    for episode in episodes:
        # Invalidate the specific episode cache (if it was queried before)
        cache_key = episode_cache_key(episode.id)
        cache.delete(cache_key)
        
        # Invalidate pattern-based variations (defensive measure)
        cache.delete_pattern(f"episode:{episode.id}*")
    
    # Invalidate count caches for episodes (both filtered and unfiltered)
    # This ensures count queries reflect the new episodes
    cache.delete_pattern("count:episode*")

    return {
        "message": "Episode linking completed",
        "remittance_id": remittance_id,
        "episodes_linked": len(episodes),
        "episodes": [
            {
                "id": ep.id,
                "claim_id": ep.claim_id,
                "status": ep.status.value if ep.status else None,
            }
            for ep in episodes
        ],
    }


@router.patch("/episodes/{episode_id}/status")
async def update_episode_status(
    episode_id: int,
    request: UpdateEpisodeStatusRequest,
    db: Session = Depends(get_db),
):
    """
    Update the status of an episode.

    **Request Body:**
    ```json
    {
        "status": "pending" | "active" | "completed" | "denied"
    }
    ```

    **Parameters:**
    - `episode_id` (path): The ID of the episode to update
    - `status` (body): The new status for the episode. Must be one of:
      - `pending`: Episode is pending processing
      - `active`: Episode is actively being processed
      - `completed`: Episode processing is complete
      - `denied`: Episode has been denied

    **Returns:**
    - Updated episode information with new status

    **Errors:**
    - 400: Invalid status value
    - 404: Episode not found
    """
    try:
        status = EpisodeStatus(request.status.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {[s.value for s in EpisodeStatus]}",
        )

    linker = EpisodeLinker(db)
    episode = linker.update_episode_status(episode_id, status)

    if not episode:
        raise NotFoundError("Episode", str(episode_id))

    db.commit()

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
    cache.delete_pattern("count:episode*")

    return {
        "message": "Episode status updated",
        "episode": {
            "id": episode.id,
            "status": episode.status.value,
        },
    }


@router.post("/episodes/{episode_id}/complete")
async def mark_episode_complete(
    episode_id: int,
    db: Session = Depends(get_db),
):
    """Mark an episode as complete."""
    linker = EpisodeLinker(db)
    episode = linker.mark_episode_complete(episode_id)

    if not episode:
        raise NotFoundError("Episode", str(episode_id))

    db.commit()

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
    cache.delete_pattern("count:episode*")

    return {
        "message": "Episode marked as complete",
        "episode": {
            "id": episode.id,
            "status": episode.status.value,
        },
    }



