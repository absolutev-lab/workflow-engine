"""
WebSocket endpoints for real-time communication.
"""
import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User
from app.websocket.connection_manager import manager
from app.websocket.events import events

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)


async def get_user_from_token(token: str, db: Session) -> User:
    """Get user from JWT token for WebSocket authentication."""
    try:
        payload = decode_access_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = None,
    db: Session = Depends(get_db)
):
    """Main WebSocket endpoint for real-time communication."""
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    try:
        # Authenticate user
        user = await get_user_from_token(token, db)
        user_id = str(user.id)
        
        # Connect user
        await manager.connect(websocket, user_id)
        
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                await handle_websocket_message(message, user_id, websocket)
                
        except WebSocketDisconnect:
            manager.disconnect(websocket, user_id)
            logger.info(f"User {user_id} disconnected")
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)


async def handle_websocket_message(message: Dict[str, Any], user_id: str, websocket: WebSocket):
    """Handle incoming WebSocket messages."""
    message_type = message.get("type")
    
    try:
        if message_type == "subscribe_workflow":
            workflow_id = message.get("workflow_id")
            if workflow_id:
                manager.subscribe_to_workflow(user_id, workflow_id)
                await manager.send_personal_message({
                    "type": "subscription_confirmed",
                    "subscription_type": "workflow",
                    "workflow_id": workflow_id,
                    "message": f"Subscribed to workflow {workflow_id}"
                }, websocket)
        
        elif message_type == "unsubscribe_workflow":
            workflow_id = message.get("workflow_id")
            if workflow_id:
                manager.unsubscribe_from_workflow(user_id, workflow_id)
                await manager.send_personal_message({
                    "type": "subscription_cancelled",
                    "subscription_type": "workflow",
                    "workflow_id": workflow_id,
                    "message": f"Unsubscribed from workflow {workflow_id}"
                }, websocket)
        
        elif message_type == "subscribe_execution":
            execution_id = message.get("execution_id")
            if execution_id:
                manager.subscribe_to_execution(user_id, execution_id)
                await manager.send_personal_message({
                    "type": "subscription_confirmed",
                    "subscription_type": "execution",
                    "execution_id": execution_id,
                    "message": f"Subscribed to execution {execution_id}"
                }, websocket)
        
        elif message_type == "unsubscribe_execution":
            execution_id = message.get("execution_id")
            if execution_id:
                manager.unsubscribe_from_execution(user_id, execution_id)
                await manager.send_personal_message({
                    "type": "subscription_cancelled",
                    "subscription_type": "execution",
                    "execution_id": execution_id,
                    "message": f"Unsubscribed from execution {execution_id}"
                }, websocket)
        
        elif message_type == "ping":
            await manager.send_personal_message({
                "type": "pong",
                "timestamp": message.get("timestamp")
            }, websocket)
        
        elif message_type == "get_stats":
            stats = manager.get_connection_stats()
            await manager.send_personal_message({
                "type": "stats",
                "data": stats
            }, websocket)
        
        else:
            await manager.send_personal_message({
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            }, websocket)
            
    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")
        await manager.send_personal_message({
            "type": "error",
            "message": "Failed to process message"
        }, websocket)


@router.get("/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    return manager.get_connection_stats()