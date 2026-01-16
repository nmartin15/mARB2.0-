"""Tests for WebSocket API endpoints."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.api
class TestWebSocketEndpoint:
    """Tests for WebSocket /ws/notifications endpoint."""

    def test_websocket_connection(self, client):
        """Test WebSocket connection can be established."""
        with client.websocket_connect("/ws/notifications") as websocket:
            # Connection should be established
            assert websocket is not None
            # Should receive welcome message
            welcome = websocket.receive_json()
            assert welcome["type"] == "connection"
            assert "Connected to mARB 2.0 notifications" in welcome["message"]

    def test_websocket_receives_ack(self, client):
        """Test WebSocket receives acknowledgment message."""
        with client.websocket_connect("/ws/notifications") as websocket:
            # Receive welcome message first
            welcome = websocket.receive_json()
            assert welcome["type"] == "connection"

            # Send a message
            websocket.send_text("test message")

            # Receive acknowledgment
            data = websocket.receive_json()
            assert data["type"] == "ack"
            assert data["message"] == "Received"

    def test_websocket_multiple_messages(self, client):
        """Test WebSocket can handle multiple messages."""
        with client.websocket_connect("/ws/notifications") as websocket:
            # Receive welcome message first
            welcome = websocket.receive_json()
            assert welcome["type"] == "connection"

            # Send multiple messages
            for i in range(3):
                websocket.send_text(f"message {i}")
                data = websocket.receive_json()
                assert data["type"] == "ack"
                assert data["message"] == "Received"

    def test_websocket_disconnect(self, client):
        """Test WebSocket disconnects properly."""
        with client.websocket_connect("/ws/notifications") as websocket:
            welcome = websocket.receive_json()
            websocket.send_text("test")
            websocket.receive_json()
            # Disconnect by exiting context manager
            # Should not raise any errors

    def test_websocket_json_message(self, client):
        """Test WebSocket can handle JSON-like text messages."""
        with client.websocket_connect("/ws/notifications") as websocket:
            welcome = websocket.receive_json()
            message = json.dumps({"action": "subscribe", "channel": "risk_updates"})
            websocket.send_text(message)

            data = websocket.receive_json()
            assert data["type"] == "ack"

    @pytest.mark.asyncio
    async def test_websocket_connection_manager(self):
        """Test ConnectionManager functionality."""
        from app.api.routes.websocket import ConnectionManager

        manager = ConnectionManager()
        assert len(manager.active_connections) == 0

        # Note: Full WebSocket testing requires actual WebSocket connections
        # This test verifies the manager structure
        assert hasattr(manager, "connect")
        assert hasattr(manager, "disconnect")
        assert hasattr(manager, "send_personal_message")
        assert hasattr(manager, "broadcast")
        assert hasattr(manager, "send_notification")


@pytest.mark.api
class TestWebSocketNotifications:
    """Tests for WebSocket real-time notifications."""

    @pytest.mark.asyncio
    async def test_notification_types(self):
        """Test that all notification types are defined."""
        from app.api.routes.websocket import NotificationType

        assert NotificationType.RISK_SCORE_CALCULATED == "risk_score_calculated"
        assert NotificationType.CLAIM_PROCESSED == "claim_processed"
        assert NotificationType.REMITTANCE_PROCESSED == "remittance_processed"
        assert NotificationType.EPISODE_LINKED == "episode_linked"
        assert NotificationType.EPISODE_COMPLETED == "episode_completed"
        assert NotificationType.FILE_PROCESSED == "file_processed"
        assert NotificationType.ERROR == "error"
        assert NotificationType.INFO == "info"

    async def test_send_notification_structure(self):
        """Test that send_notification creates proper notification structure."""

        from app.api.routes.websocket import ConnectionManager, NotificationType

        manager = ConnectionManager()

        # Mock a WebSocket connection
        mock_websocket = AsyncMock()
        manager.active_connections = [mock_websocket]

        # Send a notification
        await manager.send_notification(
            notification_type=NotificationType.RISK_SCORE_CALCULATED,
            data={"claim_id": 1, "score": 75.5},
            message="Test notification",
        )

        # Verify broadcast was called
        assert mock_websocket.send_json.called

        # Get the call arguments
        call_args = mock_websocket.send_json.call_args[0][0]

        # Verify notification structure
        assert call_args["type"] == "risk_score_calculated"
        assert "timestamp" in call_args
        assert call_args["data"]["claim_id"] == 1
        assert call_args["data"]["score"] == 75.5
        assert call_args["message"] == "Test notification"

    def test_notification_utilities(self):
        """Test notification utility functions exist and are callable."""
        from app.utils.notifications import (
            notify_claim_processed,
            notify_episode_completed,
            notify_episode_linked,
            notify_file_processed,
            notify_remittance_processed,
            notify_risk_score_calculated,
        )

        # Verify all functions exist and are callable
        assert callable(notify_risk_score_calculated)
        assert callable(notify_claim_processed)
        assert callable(notify_remittance_processed)
        assert callable(notify_episode_linked)
        assert callable(notify_episode_completed)
        assert callable(notify_file_processed)

    @pytest.mark.asyncio
    async def test_risk_score_notification(self):
        """Test risk score notification is sent correctly."""
        from app.api.routes.websocket import ConnectionManager, NotificationType

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        manager.active_connections = [mock_websocket]

        await manager.send_notification(
            notification_type=NotificationType.RISK_SCORE_CALCULATED,
            data={
                "claim_id": 123,
                "overall_score": 85.5,
                "risk_level": "high",
                "component_scores": {"coding_risk": 90, "payer_risk": 80},
            },
            message="Risk score calculated for claim 123",
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "risk_score_calculated"
        assert call_args["data"]["claim_id"] == 123
        assert call_args["data"]["overall_score"] == 85.5
        assert call_args["data"]["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_episode_linked_notification(self):
        """Test episode linked notification is sent correctly."""
        from app.api.routes.websocket import ConnectionManager, NotificationType

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        manager.active_connections = [mock_websocket]

        await manager.send_notification(
            notification_type=NotificationType.EPISODE_LINKED,
            data={
                "episode_id": 456,
                "claim_id": 123,
                "remittance_id": 789,
                "status": "linked",
            },
            message="Episode 456 linked successfully",
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "episode_linked"
        assert call_args["data"]["episode_id"] == 456
        assert call_args["data"]["claim_id"] == 123
        assert call_args["data"]["remittance_id"] == 789

    @pytest.mark.asyncio
    async def test_file_processed_notification(self):
        """Test file processed notification is sent correctly."""
        from app.api.routes.websocket import ConnectionManager, NotificationType

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        manager.active_connections = [mock_websocket]

        await manager.send_notification(
            notification_type=NotificationType.FILE_PROCESSED,
            data={
                "filename": "test_837.edi",
                "file_type": "837",
                "status": "success",
                "claims_created": 5,
            },
            message="837 file test_837.edi processed successfully",
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "file_processed"
        assert call_args["data"]["filename"] == "test_837.edi"
        assert call_args["data"]["file_type"] == "837"
        assert call_args["data"]["claims_created"] == 5

    def test_websocket_invalid_json_handling(self, client):
        """Test WebSocket handles invalid JSON gracefully."""
        with client.websocket_connect("/ws/notifications") as websocket:
            welcome = websocket.receive_json()
            assert welcome["type"] == "connection"

            # Send invalid JSON
            websocket.send_text("not valid json {")

            # Should receive error message
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "Invalid JSON" in data["message"]

    def test_websocket_empty_message(self, client):
        """Test WebSocket handles empty messages."""
        with client.websocket_connect("/ws/notifications") as websocket:
            welcome = websocket.receive_json()
            assert welcome["type"] == "connection"

            # Send empty message
            websocket.send_text("")

            # Should receive acknowledgment or error
            data = websocket.receive_json()
            assert data["type"] in ["ack", "error"]

    def test_websocket_large_message(self, client):
        """Test WebSocket handles large messages."""
        with client.websocket_connect("/ws/notifications") as websocket:
            welcome = websocket.receive_json()
            assert welcome["type"] == "connection"

            # Send large JSON message
            large_data = {"data": "x" * 10000}
            message = json.dumps(large_data)
            websocket.send_text(message)

            # Should receive acknowledgment
            data = websocket.receive_json()
            assert data["type"] == "ack"

    def test_websocket_multiple_connections(self, client):
        """Test WebSocket with multiple concurrent connections."""
        with client.websocket_connect("/ws/notifications") as ws1:
            welcome1 = ws1.receive_json()
            assert welcome1["type"] == "connection"

            with client.websocket_connect("/ws/notifications") as ws2:
                welcome2 = ws2.receive_json()
                assert welcome2["type"] == "connection"

                # Both should be able to send/receive
                ws1.send_text("message1")
                ws2.send_text("message2")

                ack1 = ws1.receive_json()
                ack2 = ws2.receive_json()

                assert ack1["type"] == "ack"
                assert ack2["type"] == "ack"

    def test_websocket_connection_manager_disconnect(self):
        """Test ConnectionManager disconnect functionality."""
        from app.api.routes.websocket import ConnectionManager

        manager = ConnectionManager()
        assert len(manager.active_connections) == 0

        # Mock a WebSocket connection
        mock_websocket = MagicMock()
        manager.active_connections = [mock_websocket]

        # Disconnect
        manager.disconnect(mock_websocket)

        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_websocket_notification_without_message(self):
        """Test sending notification without optional message."""
        from app.api.routes.websocket import ConnectionManager, NotificationType

        manager = ConnectionManager()
        mock_websocket = AsyncMock()
        manager.active_connections = [mock_websocket]

        await manager.send_notification(
            notification_type=NotificationType.INFO,
            data={"test": "data"},
            # No message parameter
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "info"
        assert "message" not in call_args or call_args.get("message") is None

    @pytest.mark.asyncio
    async def test_websocket_broadcast_handles_disconnections(self):
        """Test that broadcast handles disconnected clients gracefully."""
        from app.api.routes.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.send_json.side_effect = RuntimeError("Connection closed")
        manager.active_connections = [mock_ws1, mock_ws2]

        # Broadcast should handle the error and remove disconnected client
        await manager.broadcast({"type": "test", "data": "test"})

        # ws1 should have received the message
        assert mock_ws1.send_json.called
        # ws2 should have been removed
        assert len(manager.active_connections) == 1

