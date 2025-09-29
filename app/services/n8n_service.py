"""
n8n integration service for workflow synchronization and API integration.
"""
import json
import requests
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.core.config import settings
from app.models import Integration, Workflow, User
from app.models.integration import IntegrationStatus
import logging

logger = logging.getLogger(__name__)


class N8nService:
    """Service for n8n integration and workflow synchronization."""
    
    def __init__(self, db: Session):
        self.db = db
        self.n8n_url = settings.N8N_URL
        self.n8n_api_key = settings.N8N_API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "X-N8N-API-KEY": self.n8n_api_key
        } if self.n8n_api_key else {"Content-Type": "application/json"}
    
    def test_connection(self) -> bool:
        """Test connection to n8n instance."""
        try:
            response = requests.get(
                f"{self.n8n_url}/api/v1/workflows",
                headers=self.headers,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to connect to n8n: {str(e)}")
            return False
    
    def create_integration(self, user_id: str) -> Integration:
        """Create n8n integration record."""
        # Test connection first
        if not self.test_connection():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot connect to n8n instance"
            )
        
        # Check if integration already exists
        existing = self.db.query(Integration).filter(
            Integration.service_name == "n8n"
        ).first()
        
        if existing:
            return existing
        
        integration = Integration(
            service_name="n8n",
            service_url=self.n8n_url,
            credentials={"api_key": self.n8n_api_key} if self.n8n_api_key else {},
            configuration={
                "webhook_base_url": settings.WEBHOOK_BASE_URL,
                "sync_enabled": True
            },
            status=IntegrationStatus.ACTIVE
        )
        
        self.db.add(integration)
        self.db.commit()
        self.db.refresh(integration)
        
        return integration
    
    def sync_workflows_from_n8n(self, user_id: str) -> List[Dict[str, Any]]:
        """Sync workflows from n8n to local database."""
        try:
            # Get workflows from n8n
            response = requests.get(
                f"{self.n8n_url}/api/v1/workflows",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to fetch workflows from n8n: {response.text}"
                )
            
            n8n_workflows = response.json().get("data", [])
            synced_workflows = []
            
            for n8n_workflow in n8n_workflows:
                # Convert n8n workflow to our format
                local_workflow = self.convert_n8n_workflow(n8n_workflow, user_id)
                synced_workflows.append(local_workflow)
            
            return synced_workflows
            
        except Exception as e:
            logger.error(f"Failed to sync workflows from n8n: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Workflow sync failed: {str(e)}"
            )
    
    def convert_n8n_workflow(self, n8n_workflow: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Convert n8n workflow format to local format."""
        workflow_id = n8n_workflow.get("id")
        name = n8n_workflow.get("name", f"n8n_workflow_{workflow_id}")
        
        # Check if workflow already exists
        existing = self.db.query(Workflow).filter(
            Workflow.name == name,
            Workflow.user_id == user_id
        ).first()
        
        if existing:
            # Update existing workflow
            existing.definition = self.convert_n8n_definition(n8n_workflow)
            self.db.commit()
            return {
                "id": str(existing.id),
                "name": existing.name,
                "status": "updated",
                "n8n_id": workflow_id
            }
        else:
            # Create new workflow
            workflow = Workflow(
                name=name,
                description=f"Synced from n8n (ID: {workflow_id})",
                definition=self.convert_n8n_definition(n8n_workflow),
                user_id=user_id
            )
            self.db.add(workflow)
            self.db.commit()
            self.db.refresh(workflow)
            
            return {
                "id": str(workflow.id),
                "name": workflow.name,
                "status": "created",
                "n8n_id": workflow_id
            }
    
    def convert_n8n_definition(self, n8n_workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Convert n8n workflow definition to our format."""
        nodes = n8n_workflow.get("nodes", [])
        connections = n8n_workflow.get("connections", {})
        
        # Convert nodes
        converted_nodes = []
        for node in nodes:
            converted_node = {
                "id": node.get("name", node.get("id")),
                "type": self.map_n8n_node_type(node.get("type", "")),
                "name": node.get("name", ""),
                "parameters": node.get("parameters", {}),
                "position": node.get("position", [0, 0])
            }
            converted_nodes.append(converted_node)
        
        # Convert connections
        converted_connections = []
        for source_node, targets in connections.items():
            for output_index, target_list in targets.items():
                for target in target_list:
                    converted_connections.append({
                        "source": source_node,
                        "target": target.get("node"),
                        "sourceOutput": output_index,
                        "targetInput": str(target.get("type", "main"))
                    })
        
        return {
            "nodes": converted_nodes,
            "connections": converted_connections,
            "settings": n8n_workflow.get("settings", {}),
            "n8n_metadata": {
                "original_id": n8n_workflow.get("id"),
                "version": n8n_workflow.get("versionId"),
                "created_at": n8n_workflow.get("createdAt"),
                "updated_at": n8n_workflow.get("updatedAt")
            }
        }
    
    def map_n8n_node_type(self, n8n_type: str) -> str:
        """Map n8n node types to our internal types."""
        type_mapping = {
            "n8n-nodes-base.start": "start",
            "n8n-nodes-base.httpRequest": "http_request",
            "n8n-nodes-base.webhook": "webhook",
            "n8n-nodes-base.set": "data_transform",
            "n8n-nodes-base.if": "condition",
            "n8n-nodes-base.function": "function",
            "n8n-nodes-base.code": "code",
            "n8n-nodes-base.merge": "merge",
            "n8n-nodes-base.split": "split",
            "n8n-nodes-base.wait": "wait",
            "n8n-nodes-base.schedule": "schedule"
        }
        
        return type_mapping.get(n8n_type, "generic")
    
    def export_workflow_to_n8n(self, workflow_id: str, user_id: str) -> Dict[str, Any]:
        """Export local workflow to n8n format."""
        workflow = self.db.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.user_id == user_id
        ).first()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        # Convert to n8n format
        n8n_workflow = self.convert_to_n8n_format(workflow)
        
        try:
            # Create workflow in n8n
            response = requests.post(
                f"{self.n8n_url}/api/v1/workflows",
                headers=self.headers,
                json=n8n_workflow,
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to create workflow in n8n: {response.text}"
                )
            
            n8n_response = response.json()
            
            return {
                "status": "exported",
                "n8n_id": n8n_response.get("data", {}).get("id"),
                "n8n_url": f"{self.n8n_url}/workflow/{n8n_response.get('data', {}).get('id')}"
            }
            
        except Exception as e:
            logger.error(f"Failed to export workflow to n8n: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Export failed: {str(e)}"
            )
    
    def convert_to_n8n_format(self, workflow: Workflow) -> Dict[str, Any]:
        """Convert local workflow to n8n format."""
        definition = workflow.definition
        nodes = definition.get("nodes", [])
        connections = definition.get("connections", [])
        
        # Convert nodes to n8n format
        n8n_nodes = []
        for node in nodes:
            n8n_node = {
                "name": node.get("id"),
                "type": self.map_to_n8n_node_type(node.get("type", "")),
                "position": node.get("position", [0, 0]),
                "parameters": node.get("parameters", {})
            }
            n8n_nodes.append(n8n_node)
        
        # Convert connections to n8n format
        n8n_connections = {}
        for connection in connections:
            source = connection.get("source")
            target = connection.get("target")
            source_output = connection.get("sourceOutput", "main")
            target_input = connection.get("targetInput", "0")
            
            if source not in n8n_connections:
                n8n_connections[source] = {}
            
            if source_output not in n8n_connections[source]:
                n8n_connections[source][source_output] = []
            
            n8n_connections[source][source_output].append({
                "node": target,
                "type": "main",
                "index": int(target_input) if target_input.isdigit() else 0
            })
        
        return {
            "name": workflow.name,
            "nodes": n8n_nodes,
            "connections": n8n_connections,
            "settings": definition.get("settings", {}),
            "active": workflow.status == "ACTIVE"
        }
    
    def map_to_n8n_node_type(self, internal_type: str) -> str:
        """Map internal node types to n8n types."""
        reverse_mapping = {
            "start": "n8n-nodes-base.start",
            "http_request": "n8n-nodes-base.httpRequest",
            "webhook": "n8n-nodes-base.webhook",
            "data_transform": "n8n-nodes-base.set",
            "condition": "n8n-nodes-base.if",
            "function": "n8n-nodes-base.function",
            "code": "n8n-nodes-base.code",
            "merge": "n8n-nodes-base.merge",
            "split": "n8n-nodes-base.split",
            "wait": "n8n-nodes-base.wait",
            "schedule": "n8n-nodes-base.schedule"
        }
        
        return reverse_mapping.get(internal_type, "n8n-nodes-base.function")
    
    def create_webhook_in_n8n(self, workflow_id: str, webhook_path: str) -> Dict[str, Any]:
        """Create a webhook node in n8n workflow."""
        try:
            webhook_node = {
                "name": f"Webhook_{workflow_id}",
                "type": "n8n-nodes-base.webhook",
                "parameters": {
                    "path": webhook_path,
                    "httpMethod": "POST",
                    "responseMode": "onReceived"
                },
                "position": [0, 0]
            }
            
            return {
                "status": "created",
                "webhook_node": webhook_node,
                "webhook_url": f"{settings.WEBHOOK_BASE_URL}/webhook/{webhook_path}"
            }
            
        except Exception as e:
            logger.error(f"Failed to create webhook in n8n: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Webhook creation failed: {str(e)}"
            )
    
    def get_n8n_executions(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get execution history from n8n."""
        try:
            response = requests.get(
                f"{self.n8n_url}/api/v1/executions",
                headers=self.headers,
                params={"workflowId": workflow_id},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get("data", [])
            else:
                logger.warning(f"Failed to get n8n executions: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get n8n executions: {str(e)}")
            return []