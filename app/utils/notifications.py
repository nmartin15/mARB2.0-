"""Utility functions for sending WebSocket notifications."""
from typing import Dict, Any, Optional
import asyncio
import threading
from app.api.routes.websocket import manager, NotificationType
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Global event loop and thread for synchronous contexts
_sync_event_loop = None
_sync_thread = None
_loop_lock = threading.Lock()


def _start_background_loop(loop: asyncio.AbstractEventLoop):
    """Start an event loop in a background thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def get_sync_event_loop():
    """Get or create a shared event loop for synchronous contexts."""
    global _sync_event_loop, _sync_thread
    
    # First, try to get the running loop (if we're in an async context)
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        pass
    
    # No running loop, create/use a background thread loop
    with _loop_lock:
        if _sync_event_loop is None:
            _sync_event_loop = asyncio.new_event_loop()
            _sync_thread = threading.Thread(
                target=_start_background_loop,
                args=(_sync_event_loop,),
                daemon=True,
                name="NotificationEventLoop",
            )
            _sync_thread.start()
        elif not _sync_event_loop.is_running():
            # Loop exists but stopped, restart it
            _sync_thread = threading.Thread(
                target=_start_background_loop,
                args=(_sync_event_loop,),
                daemon=True,
                name="NotificationEventLoop",
            )
            _sync_thread.start()
    
    return _sync_event_loop


async def _send_notification(notification_type: NotificationType, data: Dict[str, Any], message: str):
    """Reusable function to send the notification."""
    try:
        await manager.send_notification(notification_type=notification_type, data=data, message=message)
    except Exception as e:
        logger.warning(
            "Failed to send notification",
            notification_type=notification_type.value,
            error=str(e),
            data=data,
        )


def _run_sync(coro):
    """
    Runs an async coroutine in a synchronous context using a shared event loop.
    
    This function handles both async and sync contexts:
    - If called from an async context, schedules the coroutine in the current loop
    - If called from a sync context, uses a shared background thread event loop
    
    Args:
        coro: The coroutine to execute
    """
    if not asyncio.iscoroutine(coro):
        logger.error("Attempted to run a non-coroutine", coro=coro)
        return
    
    try:
        # Try to get the running loop (if we're in an async context)
        loop = asyncio.get_running_loop()
        # Schedule the coroutine in the running loop (fire and forget)
        asyncio.create_task(coro)
    except RuntimeError:
        # No running loop, use the shared sync loop in background thread
        loop = get_sync_event_loop()
        # Schedule coroutine in the background thread's event loop (fire and forget)
        # This is safe because the loop is running in a daemon thread
        asyncio.run_coroutine_threadsafe(coro, loop)


def notify_risk_score_calculated(claim_id: int, risk_score: Dict[str, Any]):
    """
    Send notification when a risk score is calculated.
    Works in both sync and async contexts.
    
    Args:
        claim_id: ID of the claim
        risk_score: Risk score data dictionary
    """
    data = {
        "claim_id": claim_id,
        "overall_score": risk_score.get("overall_score"),
        "risk_level": risk_score.get("risk_level"),
        "component_scores": risk_score.get("component_scores", {}),
    }
    message = f"Risk score calculated for claim {claim_id}"
    _run_sync(_send_notification(NotificationType.RISK_SCORE_CALCULATED, data, message))


def notify_claim_processed(claim_id: int, claim_data: Dict[str, Any]):
    """
    Send notification when a claim is processed.
    Works in both sync and async contexts.
    
    Args:
        claim_id: ID of the claim
        claim_data: Claim data dictionary
    """
    data = {
        "claim_id": claim_id,
        "claim_control_number": claim_data.get("claim_control_number"),
        "status": claim_data.get("status"),
    }
    message = f"Claim {claim_id} processed successfully"
    _run_sync(_send_notification(NotificationType.CLAIM_PROCESSED, data, message))


def notify_remittance_processed(remittance_id: int, remittance_data: Dict[str, Any]):
    """
    Send notification when a remittance is processed.
    Works in both sync and async contexts.
    
    Args:
        remittance_id: ID of the remittance
        remittance_data: Remittance data dictionary
    """
    data = {
        "remittance_id": remittance_id,
        "claim_control_number": remittance_data.get("claim_control_number"),
        "payment_amount": remittance_data.get("payment_amount"),
        "status": remittance_data.get("status"),
    }
    message = f"Remittance {remittance_id} processed successfully"
    _run_sync(_send_notification(NotificationType.REMITTANCE_PROCESSED, data, message))


def notify_episode_linked(episode_id: int, episode_data: Dict[str, Any]):
    """
    Send notification when an episode is linked.
    Works in both sync and async contexts.
    
    Args:
        episode_id: ID of the episode
        episode_data: Episode data dictionary
    """
    data = {
        "episode_id": episode_id,
        "claim_id": episode_data.get("claim_id"),
        "remittance_id": episode_data.get("remittance_id"),
        "status": episode_data.get("status"),
    }
    message = f"Episode {episode_id} linked successfully"
    _run_sync(_send_notification(NotificationType.EPISODE_LINKED, data, message))


def notify_episode_completed(episode_id: int, episode_data: Dict[str, Any]):
    """
    Send notification when an episode is completed.
    Works in both sync and async contexts.
    
    Args:
        episode_id: ID of the episode
        episode_data: Episode data dictionary
    """
    data = {
        "episode_id": episode_id,
        "claim_id": episode_data.get("claim_id"),
        "remittance_id": episode_data.get("remittance_id"),
    }
    message = f"Episode {episode_id} completed"
    _run_sync(_send_notification(NotificationType.EPISODE_COMPLETED, data, message))


def notify_file_processed(filename: str, file_type: str, result: Dict[str, Any]):
    """
    Send notification when a file is processed.
    Works in both sync and async contexts.
    
    Args:
        filename: Name of the processed file
        file_type: Type of file (837 or 835)
        result: Processing result dictionary
    """
    data = {
        "filename": filename,
        "file_type": file_type,
        "status": result.get("status"),
        "claims_created": result.get("claims_created", 0),
        "remittances_created": result.get("remittances_created", 0),
    }
    message = f"{file_type.upper()} file {filename} processed successfully"
    _run_sync(_send_notification(NotificationType.FILE_PROCESSED, data, message))


def notify_file_progress(
    filename: str,
    file_type: str,
    task_id: str,
    stage: str,
    progress: float,
    current: int,
    total: int,
    message: Optional[str] = None,
):
    """
    Send progress notification for file processing.
    Works in both sync and async contexts.
    
    Args:
        filename: Name of the file being processed
        file_type: Type of file (837 or 835)
        task_id: Celery task ID
        stage: Current processing stage
        progress: Progress percentage (0.0 to 1.0)
        current: Current item number
        total: Total items to process
        message: Optional custom message
    """
    data = {
        "filename": filename,
        "file_type": file_type,
        "task_id": task_id,
        "stage": stage,  # "uploading", "parsing", "processing", "saving"
        "progress": progress,  # 0.0 to 1.0
        "current": current,
        "total": total,
    }
    message = message or f"Processing {filename}: {stage} ({progress:.1%})"
    _run_sync(_send_notification(NotificationType.FILE_PROGRESS, data, message))

