"""
WebSocket event handlers and message types.
"""
import json
import logging
from typing import Dict, Any
from datetime import datetime
from app.websocket.connection_manager import manager

logger = logging.getLogger(__name__)


class WebSocketEvents:
    """Handles WebSocket events and message broadcasting."""
    
    @staticmethod
    async def workflow_created(workflow_data: Dict[str, Any], user_id: str):
        """Broadcast workflow creation event."""
        message = {
            "type": "workflow_created",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "workflow_id": workflow_data.get("id"),
                "name": workflow_data.get("name"),
                "status": workflow_data.get("status"),
                "created_by": user_id
            }
        }
        
        await manager.send_to_user(message, user_id)
        logger.info(f"Broadcasted workflow creation event for workflow {workflow_data.get('id')}")
    
    @staticmethod
    async def workflow_updated(workflow_data: Dict[str, Any], user_id: str):
        """Broadcast workflow update event."""
        message = {
            "type": "workflow_updated",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "workflow_id": workflow_data.get("id"),
                "name": workflow_data.get("name"),
                "status": workflow_data.get("status"),
                "updated_by": user_id
            }
        }
        
        # Send to workflow subscribers
        await manager.broadcast_to_workflow_subscribers(message, workflow_data.get("id"))
        logger.info(f"Broadcasted workflow update event for workflow {workflow_data.get('id')}")
    
    @staticmethod
    async def workflow_deleted(workflow_id: str, user_id: str):
        """Broadcast workflow deletion event."""
        message = {
            "type": "workflow_deleted",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "workflow_id": workflow_id,
                "deleted_by": user_id
            }
        }
        
        await manager.broadcast_to_workflow_subscribers(message, workflow_id)
        logger.info(f"Broadcasted workflow deletion event for workflow {workflow_id}")
    
    @staticmethod
    async def execution_started(execution_data: Dict[str, Any]):
        """Broadcast execution start event."""
        message = {
            "type": "execution_started",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "execution_id": execution_data.get("id"),
                "workflow_id": execution_data.get("workflow_id"),
                "status": execution_data.get("status"),
                "started_at": execution_data.get("started_at")
            }
        }
        
        # Send to both workflow and execution subscribers
        workflow_id = execution_data.get("workflow_id")
        execution_id = execution_data.get("id")
        
        await manager.broadcast_to_workflow_subscribers(message, workflow_id)
        await manager.broadcast_to_execution_subscribers(message, execution_id)
        logger.info(f"Broadcasted execution start event for execution {execution_id}")
    
    @staticmethod
    async def execution_progress(execution_id: str, workflow_id: str, progress_data: Dict[str, Any]):
        """Broadcast execution progress event."""
        message = {
            "type": "execution_progress",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "execution_id": execution_id,
                "workflow_id": workflow_id,
                "current_node": progress_data.get("current_node"),
                "completed_nodes": progress_data.get("completed_nodes", []),
                "progress_percentage": progress_data.get("progress_percentage", 0),
                "message": progress_data.get("message", "")
            }
        }
        
        await manager.broadcast_to_workflow_subscribers(message, workflow_id)
        await manager.broadcast_to_execution_subscribers(message, execution_id)
        logger.info(f"Broadcasted execution progress for execution {execution_id}")
    
    @staticmethod
    async def execution_completed(execution_data: Dict[str, Any]):
        """Broadcast execution completion event."""
        message = {
            "type": "execution_completed",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "execution_id": execution_data.get("id"),
                "workflow_id": execution_data.get("workflow_id"),
                "status": execution_data.get("status"),
                "started_at": execution_data.get("started_at"),
                "completed_at": execution_data.get("completed_at"),
                "duration": execution_data.get("duration"),
                "output_data": execution_data.get("output_data")
            }
        }
        
        workflow_id = execution_data.get("workflow_id")
        execution_id = execution_data.get("id")
        
        await manager.broadcast_to_workflow_subscribers(message, workflow_id)
        await manager.broadcast_to_execution_subscribers(message, execution_id)
        logger.info(f"Broadcasted execution completion for execution {execution_id}")
    
    @staticmethod
    async def execution_failed(execution_data: Dict[str, Any], error_message: str):
        """Broadcast execution failure event."""
        message = {
            "type": "execution_failed",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "execution_id": execution_data.get("id"),
                "workflow_id": execution_data.get("workflow_id"),
                "status": execution_data.get("status"),
                "error_message": error_message,
                "started_at": execution_data.get("started_at"),
                "failed_at": execution_data.get("completed_at")
            }
        }
        
        workflow_id = execution_data.get("workflow_id")
        execution_id = execution_data.get("id")
        
        await manager.broadcast_to_workflow_subscribers(message, workflow_id)
        await manager.broadcast_to_execution_subscribers(message, execution_id)
        logger.info(f"Broadcasted execution failure for execution {execution_id}")
    
    @staticmethod
    async def webhook_received(webhook_data: Dict[str, Any]):
        """Broadcast webhook received event."""
        message = {
            "type": "webhook_received",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "webhook_id": webhook_data.get("id"),
                "workflow_id": webhook_data.get("workflow_id"),
                "method": webhook_data.get("method"),
                "url_path": webhook_data.get("url_path"),
                "payload_size": len(str(webhook_data.get("payload", {})))
            }
        }
        
        workflow_id = webhook_data.get("workflow_id")
        if workflow_id:
            await manager.broadcast_to_workflow_subscribers(message, workflow_id)
        
        logger.info(f"Broadcasted webhook received event for webhook {webhook_data.get('id')}")
    
    @staticmethod
    async def system_status(status_data: Dict[str, Any]):
        """Broadcast system status update."""
        message = {
            "type": "system_status",
            "timestamp": datetime.utcnow().isoformat(),
            "data": status_data
        }
        
        # Broadcast to all connected users
        for user_id in manager.active_connections.keys():
            await manager.send_to_user(message, user_id)
        
        logger.info("Broadcasted system status update")


# Global events instance
events = WebSocketEvents()