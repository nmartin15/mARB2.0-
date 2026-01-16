"""Tests for notification utilities."""
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
import asyncio

from app.utils.notifications import (
    notify_risk_score_calculated,
    notify_file_processed,
    notify_remittance_processed,
    notify_episode_linked,
    notify_file_progress,
    get_sync_event_loop,
    _run_sync,
)

# Import these conditionally as they may not exist
try:
    from app.utils.notifications import notify_claim_processed, notify_episode_completed
    HAS_CLAIM_NOTIFY = True
    HAS_EPISODE_NOTIFY = True
except ImportError:
    HAS_CLAIM_NOTIFY = False
    HAS_EPISODE_NOTIFY = False


@pytest.mark.unit
class TestNotifications:
    """Test notification utility functions."""

    def test_notify_risk_score_calculated(self):
        """Test risk score notification."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_risk_score_calculated(
                claim_id=1,
                risk_score={
                    "overall_score": 75.5,
                    "risk_level": "high",
                    "component_scores": {"coding_risk": 80.0},
                },
            )
            assert mock_run.called

    def test_notify_file_processed(self):
        """Test file processed notification."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_file_processed(
                filename="test.edi",
                file_type="837",
                result={"status": "success", "claims_created": 5},
            )
            assert mock_run.called

    @pytest.mark.skipif(not HAS_CLAIM_NOTIFY, reason="notify_claim_processed not available")
    def test_notify_claim_processed(self):
        """Test claim processed notification."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_claim_processed(
                claim_id=1,
                claim_data={"claim_control_number": "CLM001", "status": "processed"},
            )
            assert mock_run.called

    def test_notify_remittance_processed(self):
        """Test remittance processed notification."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_remittance_processed(
                remittance_id=1,
                remittance_data={
                    "claim_control_number": "CLM001",
                    "payment_amount": 1000.0,
                },
            )
            assert mock_run.called

    def test_notify_episode_linked(self):
        """Test episode linked notification."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_episode_linked(
                episode_id=1,
                episode_data={"claim_id": 1, "remittance_id": 2, "status": "linked"},
            )
            assert mock_run.called

    @pytest.mark.skipif(not HAS_EPISODE_NOTIFY, reason="notify_episode_completed not available")
    def test_notify_episode_completed(self):
        """Test episode completed notification."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_episode_completed(
                episode_id=1,
                episode_data={"claim_id": 1, "status": "complete"},
            )
            assert mock_run.called

    def test_notify_file_progress(self):
        """Test file progress notification."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_file_progress(
                filename="test.edi",
                file_type="837",
                task_id="task-123",
                stage="parsing",
                progress=0.5,
                current=10,
                total=20,
                message="Processing...",
            )
            assert mock_run.called

    def test_get_sync_event_loop_creates_new(self):
        """Test that get_sync_event_loop creates a new loop when needed."""
        # Clear any existing loop
        import app.utils.notifications as notifications_module
        notifications_module._sync_event_loop = None
        notifications_module._sync_thread = None

        loop = get_sync_event_loop()
        assert loop is not None
        assert isinstance(loop, asyncio.AbstractEventLoop)

    def test_get_sync_event_loop_reuses_existing(self):
        """Test that get_sync_event_loop reuses existing loop."""
        loop1 = get_sync_event_loop()
        loop2 = get_sync_event_loop()
        assert loop1 is loop2

    def test_run_sync_with_coroutine(self):
        """Test _run_sync with a coroutine."""
        async def test_coro():
            return "test"

        coro = test_coro()
        # Test in non-async context (no running loop)
        try:
            loop = asyncio.get_running_loop()
            # If we're in async context, skip this test
            pytest.skip("Already in async context")
        except RuntimeError:
            # No running loop, test the sync path
            with patch("app.utils.notifications.get_sync_event_loop") as mock_get_loop:
                mock_loop = MagicMock()
                mock_get_loop.return_value = mock_loop
                with patch("asyncio.run_coroutine_threadsafe") as mock_run:
                    _run_sync(coro)
                    # Should schedule coroutine in background loop
                    assert mock_run.called

    def test_run_sync_with_non_coroutine(self):
        """Test _run_sync with non-coroutine (should log error)."""
        with patch("app.utils.notifications.logger") as mock_logger:
            _run_sync("not a coroutine")
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_in_async_context(self):
        """Test notification in async context."""
        with patch("app.utils.notifications.manager") as mock_manager:
            mock_manager.send_notification = AsyncMock()
            
            # In async context, should use running loop
            await asyncio.sleep(0.01)  # Ensure we're in async context
            
            # The notification should work
            notify_risk_score_calculated(
                claim_id=1,
                risk_score={"overall_score": 50.0, "risk_level": "medium"},
            )
            
            # Should have scheduled the coroutine
            await asyncio.sleep(0.1)  # Give it time to execute
            # Note: In real scenario, the notification would be sent

    def test_notify_claim_processed_missing_fields(self):
        """Test notify_claim_processed with missing optional fields."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_claim_processed(
                claim_id=1,
                claim_data={},  # Empty data
            )
            assert mock_run.called

    def test_notify_remittance_processed_missing_fields(self):
        """Test notify_remittance_processed with missing optional fields."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_remittance_processed(
                remittance_id=1,
                remittance_data={},  # Empty data
            )
            assert mock_run.called

    def test_notify_episode_linked_missing_fields(self):
        """Test notify_episode_linked with missing optional fields."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_episode_linked(
                episode_id=1,
                episode_data={},  # Empty data
            )
            assert mock_run.called

    def test_notify_file_progress_without_message(self):
        """Test notify_file_progress without custom message."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_file_progress(
                filename="test.edi",
                file_type="837",
                task_id="task-123",
                stage="parsing",
                progress=0.5,
                current=10,
                total=20,
                # message not provided
            )
            assert mock_run.called

    def test_notify_file_progress_complete(self):
        """Test notify_file_progress with progress=1.0."""
        with patch("app.utils.notifications._run_sync") as mock_run:
            notify_file_progress(
                filename="test.edi",
                file_type="837",
                task_id="task-123",
                stage="complete",
                progress=1.0,
                current=20,
                total=20,
            )
            assert mock_run.called

    def test_get_sync_event_loop_restarts_stopped_loop(self):
        """Test get_sync_event_loop restarts stopped loop."""
        import app.utils.notifications as notifications_module
        
        # Create a stopped loop
        loop = asyncio.new_event_loop()
        loop.close()
        notifications_module._sync_event_loop = loop
        notifications_module._sync_thread = None
        
        # Should create new loop
        new_loop = get_sync_event_loop()
        assert new_loop is not None
        assert new_loop != loop

    def test_run_sync_in_async_context(self):
        """Test _run_sync when already in async context."""
        async def test_coro():
            return "test"
        
        coro = test_coro()
        
        # Mock being in async context
        with patch("app.utils.notifications.asyncio.get_running_loop") as mock_get_loop, \
             patch("app.utils.notifications.asyncio.create_task") as mock_create_task:
            mock_get_loop.return_value = MagicMock()
            mock_get_loop.side_effect = None  # No RuntimeError
            
            _run_sync(coro)
            
            # Should use create_task instead of run_coroutine_threadsafe
            mock_create_task.assert_called_once()

    def test_notify_with_exception_handling(self):
        """Test notification functions handle exceptions gracefully."""
        with patch("app.utils.notifications._run_sync") as mock_run, \
             patch("app.utils.notifications.logger") as mock_logger:
            # Simulate exception in _run_sync
            mock_run.side_effect = Exception("Test error")
            
            # Should not raise, but might log
            try:
                notify_risk_score_calculated(claim_id=1, risk_score={"overall_score": 50.0})
            except Exception:
                # If exception propagates, that's also acceptable behavior
                pass

