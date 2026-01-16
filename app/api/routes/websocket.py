"""WebSocket endpoints for real-time notifications."""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class NotificationType(str, Enum):
    """Types of notifications that can be sent."""

    RISK_SCORE_CALCULATED = "risk_score_calculated"
    CLAIM_PROCESSED = "claim_processed"
    REMITTANCE_PROCESSED = "remittance_processed"
    EPISODE_LINKED = "episode_linked"
    EPISODE_COMPLETED = "episode_completed"
    FILE_PROCESSED = "file_processed"
    FILE_PROGRESS = "file_progress"  # Progress updates for large file processing
    ERROR = "error"
    INFO = "info"


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connection established", total_connections=len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket connection closed", total_connections=len(self.active_connections))

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to a specific connection."""
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            # Client disconnected - expected behavior
            self.disconnect(websocket)
        except RuntimeError as e:
            # Connection closed or in invalid state
            logger.warning("WebSocket connection closed during send", error=str(e))
            self.disconnect(websocket)
        except (ValueError, TypeError) as e:
            # Invalid message format
            logger.error("Invalid message format for WebSocket", error=str(e), exc_info=True)
            self.disconnect(websocket)
        except OSError as e:
            # Network error
            logger.error("Network error sending WebSocket message", error=str(e), exc_info=True)
            self.disconnect(websocket)
        except Exception as e:
            # Unexpected error - log with full context
            logger.error("Unexpected error sending personal WebSocket message", error=str(e), exc_info=True)
            self.disconnect(websocket)
            # Re-raise to prevent silent failures
            raise

    async def broadcast(self, message: dict):
        """Broadcast message to all connections."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                # Client disconnected - expected behavior
                disconnected.append(connection)
            except RuntimeError as e:
                # Connection closed or in invalid state
                logger.warning("WebSocket connection closed during broadcast", error=str(e))
                disconnected.append(connection)
            except (ValueError, TypeError) as e:
                # Invalid message format
                logger.error("Invalid message format for WebSocket broadcast", error=str(e), exc_info=True)
                disconnected.append(connection)
            except OSError as e:
                # Network error
                logger.error("Network error in WebSocket broadcast", error=str(e), exc_info=True)
                disconnected.append(connection)
            except Exception as e:
                # Unexpected error - log with full context but don't fail entire broadcast
                logger.error("Unexpected error in WebSocket broadcast", error=str(e), exc_info=True)
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)

    async def send_notification(
        self,
        notification_type: NotificationType,
        data: Dict[str, Any],
        message: Optional[str] = None,
    ):
        """
        Send a structured notification to all connected clients.
        
        Args:
            notification_type: Type of notification
            data: Notification payload data
            message: Optional human-readable message
        """
        notification = {
            "type": notification_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }
        
        if message:
            notification["message"] = message
        
        await self.broadcast(notification)
        logger.debug(
            "Notification sent",
            notification_type=notification_type.value,
            connections=len(self.active_connections),
        )


manager = ConnectionManager()


@router.websocket("/notifications")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time notifications.
    
    Clients can subscribe to real-time updates for:
    - Risk score calculations
    - Claim processing
    - Remittance processing
    - Episode linking
    
    **Error Handling Strategy:**
    This endpoint uses targeted exception handling to provide specific error recovery:
    - `WebSocketDisconnect`: Normal client disconnection, handled gracefully
    - `json.JSONDecodeError`: Invalid JSON from client, sends error message before disconnect
    - `RuntimeError`: Connection state errors (closed/invalid), attempts to notify client
    - `OSError`: Network/system errors, logs and attempts recovery
    - `ValueError`: Invalid data format, sends error message to client
    - `Exception`: Unexpected errors are logged with full context and re-raised for monitoring
    
    All errors attempt to send an error message to the client before disconnecting,
    except when the connection is already closed. This provides better user experience
    and debugging information.
    """
    await manager.connect(websocket)
    try:
        # Send welcome message
        await manager.send_personal_message(
            {
                "type": "connection",
                "message": "Connected to mARB 2.0 notifications",
                "timestamp": datetime.utcnow().isoformat(),
            },
            websocket,
        )
        
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            
            # Handle client messages (can be extended for filtering/subscriptions)
            try:
                message = json.loads(data)
                
                # Echo back acknowledgment
                await manager.send_personal_message(
                    {
                        "type": "ack",
                        "message": "Received",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    websocket,
                )
            except json.JSONDecodeError as e:
                # If not JSON, send error message
                logger.error("WebSocket JSON decode error", error=str(e), exc_info=True)
                await manager.send_personal_message(
                    {
                        "type": "error",
                        "message": f"Invalid JSON: {str(e)}",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    websocket,
                )
    except WebSocketDisconnect:
        # Client disconnected normally - expected behavior
        manager.disconnect(websocket)
        logger.debug("WebSocket client disconnected")
    except json.JSONDecodeError as e:
        # Invalid JSON from client
        logger.warning("WebSocket JSON decode error", error=str(e), exc_info=True)
        try:
            await manager.send_personal_message(
                {
                    "type": "error",
                    "message": f"Invalid JSON: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                websocket,
            )
        except (WebSocketDisconnect, RuntimeError, OSError):
            # Connection may already be closed
            pass
        manager.disconnect(websocket)
    except RuntimeError as e:
        # Connection state error (closed, invalid state, etc.)
        logger.warning("WebSocket runtime error", error=str(e), exc_info=True)
        try:
            await manager.send_personal_message(
                {
                    "type": "error",
                    "message": "Connection error occurred",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                websocket,
            )
        except (WebSocketDisconnect, RuntimeError, OSError):
            # Connection may already be closed
            pass
        manager.disconnect(websocket)
    except OSError as e:
        # Network/system error
        logger.error("WebSocket network error", error=str(e), exc_info=True)
        try:
            await manager.send_personal_message(
                {
                    "type": "error",
                    "message": "Network error occurred",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                websocket,
            )
        except (WebSocketDisconnect, RuntimeError, OSError):
            # Connection may already be closed
            pass
        manager.disconnect(websocket)
    except ValueError as e:
        # Invalid data format
        logger.error("WebSocket value error", error=str(e), exc_info=True)
        try:
            await manager.send_personal_message(
                {
                    "type": "error",
                    "message": f"Invalid data: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                websocket,
            )
        except (WebSocketDisconnect, RuntimeError, OSError):
            # Connection may already be closed
            pass
        manager.disconnect(websocket)
    except Exception as e:
        # Unexpected error - log with full context and re-raise for monitoring
        logger.error("Unexpected WebSocket error", error=str(e), error_type=type(e).__name__, exc_info=True)
        try:
            await manager.send_personal_message(
                {
                    "type": "error",
                    "message": "Internal server error occurred",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                websocket,
            )
        except (WebSocketDisconnect, RuntimeError, OSError):
            # Connection may already be closed
            pass
        manager.disconnect(websocket)
        # Re-raise unexpected errors to ensure they're caught by application-level error handlers
        raise

