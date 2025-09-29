"""
WebSocket connection manager for handling real-time connections.
"""
import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time communication."""
    
    def __init__(self):
        # Store active connections by user ID
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Store connections subscribed to specific workflows
        self.workflow_subscriptions: Dict[str, Set[str]] = {}
        # Store connections subscribed to execution updates
        self.execution_subscriptions: Dict[str, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket")
        
        # Send welcome message
        await self.send_personal_message({
            "type": "connection",
            "status": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Connected to workflow engine"
        }, websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection."""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                
                # Clean up empty user connections
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        
        # Remove from subscriptions
        self._remove_from_subscriptions(user_id, websocket)
        logger.info(f"User {user_id} disconnected from WebSocket")
    
    def _remove_from_subscriptions(self, user_id: str, websocket: WebSocket):
        """Remove websocket from all subscriptions."""
        # Remove from workflow subscriptions
        for workflow_id in list(self.workflow_subscriptions.keys()):
            if user_id in self.workflow_subscriptions[workflow_id]:
                self.workflow_subscriptions[workflow_id].discard(user_id)
                if not self.workflow_subscriptions[workflow_id]:
                    del self.workflow_subscriptions[workflow_id]
        
        # Remove from execution subscriptions
        for execution_id in list(self.execution_subscriptions.keys()):
            if user_id in self.execution_subscriptions[execution_id]:
                self.execution_subscriptions[execution_id].discard(user_id)
                if not self.execution_subscriptions[execution_id]:
                    del self.execution_subscriptions[execution_id]
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def send_to_user(self, message: dict, user_id: str):
        """Send a message to all connections of a specific user."""
        if user_id in self.active_connections:
            disconnected_connections = []
            
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")
                    disconnected_connections.append(connection)
            
            # Remove disconnected connections
            for connection in disconnected_connections:
                self.active_connections[user_id].remove(connection)
    
    async def broadcast_to_workflow_subscribers(self, message: dict, workflow_id: str):
        """Send a message to all users subscribed to a workflow."""
        if workflow_id in self.workflow_subscriptions:
            for user_id in self.workflow_subscriptions[workflow_id]:
                await self.send_to_user(message, user_id)
    
    async def broadcast_to_execution_subscribers(self, message: dict, execution_id: str):
        """Send a message to all users subscribed to an execution."""
        if execution_id in self.execution_subscriptions:
            for user_id in self.execution_subscriptions[execution_id]:
                await self.send_to_user(message, user_id)
    
    def subscribe_to_workflow(self, user_id: str, workflow_id: str):
        """Subscribe a user to workflow updates."""
        if workflow_id not in self.workflow_subscriptions:
            self.workflow_subscriptions[workflow_id] = set()
        
        self.workflow_subscriptions[workflow_id].add(user_id)
        logger.info(f"User {user_id} subscribed to workflow {workflow_id}")
    
    def unsubscribe_from_workflow(self, user_id: str, workflow_id: str):
        """Unsubscribe a user from workflow updates."""
        if workflow_id in self.workflow_subscriptions:
            self.workflow_subscriptions[workflow_id].discard(user_id)
            
            if not self.workflow_subscriptions[workflow_id]:
                del self.workflow_subscriptions[workflow_id]
        
        logger.info(f"User {user_id} unsubscribed from workflow {workflow_id}")
    
    def subscribe_to_execution(self, user_id: str, execution_id: str):
        """Subscribe a user to execution updates."""
        if execution_id not in self.execution_subscriptions:
            self.execution_subscriptions[execution_id] = set()
        
        self.execution_subscriptions[execution_id].add(user_id)
        logger.info(f"User {user_id} subscribed to execution {execution_id}")
    
    def unsubscribe_from_execution(self, user_id: str, execution_id: str):
        """Unsubscribe a user from execution updates."""
        if execution_id in self.execution_subscriptions:
            self.execution_subscriptions[execution_id].discard(user_id)
            
            if not self.execution_subscriptions[execution_id]:
                del self.execution_subscriptions[execution_id]
        
        logger.info(f"User {user_id} unsubscribed from execution {execution_id}")
    
    def get_connection_stats(self) -> dict:
        """Get connection statistics."""
        total_connections = sum(len(connections) for connections in self.active_connections.values())
        
        return {
            "total_connections": total_connections,
            "connected_users": len(self.active_connections),
            "workflow_subscriptions": len(self.workflow_subscriptions),
            "execution_subscriptions": len(self.execution_subscriptions)
        }


# Global connection manager instance
manager = ConnectionManager()