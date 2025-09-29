"""Workflow service for managing workflow operations."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.models import Workflow, Execution, ExecutionStatus, User
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from datetime import datetime, timedelta
import uuid
import json


class WorkflowService:
    """Service for workflow management and validation."""
    
    # Basic workflow definition schema
    WORKFLOW_SCHEMA = {
        "type": "object",
        "properties": {
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string"},
                        "name": {"type": "string"},
                        "parameters": {"type": "object"},
                        "position": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"}
                            }
                        }
                    },
                    "required": ["id", "type", "name"]
                }
            },
            "connections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "sourceOutput": {"type": "string"},
                        "targetInput": {"type": "string"}
                    },
                    "required": ["source", "target"]
                }
            },
            "settings": {
                "type": "object",
                "properties": {
                    "executionOrder": {"type": "string", "enum": ["v0", "v1"]},
                    "saveManualExecutions": {"type": "boolean"},
                    "callerPolicy": {"type": "string"}
                }
            }
        },
        "required": ["nodes"]
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_workflow_definition(self, definition: Dict[str, Any]) -> bool:
        """Validate workflow definition against schema."""
        # Basic validation - check required fields
        if not isinstance(definition, dict):
            raise ValueError("Workflow definition must be a dictionary")
        
        if "nodes" not in definition:
            raise ValueError("Workflow definition must contain 'nodes'")
        
        if not isinstance(definition["nodes"], list):
            raise ValueError("Workflow 'nodes' must be a list")
        
        return True
    
    def create_workflow(
        self, 
        name: str, 
        definition: Dict[str, Any], 
        user_id: str,
        description: Optional[str] = None
    ) -> Workflow:
        """Create a new workflow with validation."""
        # Validate definition
        self.validate_workflow_definition(definition)
        
        # Check for duplicate names for this user
        existing = self.db.query(Workflow).filter(
            Workflow.user_id == user_id,
            Workflow.name == name
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow with this name already exists"
            )
        
        # Create workflow
        workflow = Workflow(
            name=name,
            description=description,
            definition=definition,
            user_id=user_id,
            status=WorkflowStatus.DRAFT
        )
        
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        
        return workflow
    
    def update_workflow(
        self, 
        workflow_id: str, 
        user_id: str,
        **updates
    ) -> Workflow:
        """Update workflow with validation."""
        workflow = self.db.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.user_id == user_id
        ).first()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        # Validate definition if provided
        if "definition" in updates:
            self.validate_workflow_definition(updates["definition"])
        
        # Check name uniqueness if name is being updated
        if "name" in updates and updates["name"] != workflow.name:
            existing = self.db.query(Workflow).filter(
                Workflow.user_id == user_id,
                Workflow.name == updates["name"],
                Workflow.id != workflow_id
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Workflow with this name already exists"
                )
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(workflow, key):
                setattr(workflow, key, value)
        
        workflow.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(workflow)
        
        return workflow
    
    def activate_workflow(self, workflow_id: str, user_id: str) -> Workflow:
        """Activate a workflow for execution."""
        workflow = self.db.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.user_id == user_id
        ).first()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        # Validate workflow before activation
        self.validate_workflow_definition(workflow.definition)
        
        workflow.status = WorkflowStatus.ACTIVE
        workflow.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(workflow)
        
        return workflow
    
    def deactivate_workflow(self, workflow_id: str, user_id: str) -> Workflow:
        """Deactivate a workflow."""
        workflow = self.db.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.user_id == user_id
        ).first()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        workflow.status = WorkflowStatus.INACTIVE
        workflow.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(workflow)
        
        return workflow
    
    def get_workflow_executions(
        self, 
        workflow_id: str, 
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Execution]:
        """Get workflow execution history."""
        workflow = self.db.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.user_id == user_id
        ).first()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        executions = self.db.query(Execution).filter(
            Execution.workflow_id == workflow_id
        ).order_by(Execution.created_at.desc()).offset(offset).limit(limit).all()
        
        return executions
    
    def can_execute_workflow(self, workflow_id: str, user_id: str) -> bool:
        """Check if workflow can be executed."""
        workflow = self.db.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.user_id == user_id
        ).first()
        
        if not workflow:
            return False
        
        return workflow.status == WorkflowStatus.ACTIVE
    
    def get_workflow_statistics(self, workflow_id: str, user_id: str) -> Dict[str, Any]:
        """Get workflow execution statistics."""
        workflow = self.db.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.user_id == user_id
        ).first()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        # Get execution counts by status
        total_executions = self.db.query(Execution).filter(
            Execution.workflow_id == workflow_id
        ).count()
        
        successful_executions = self.db.query(Execution).filter(
            Execution.workflow_id == workflow_id,
            Execution.status == ExecutionStatus.COMPLETED
        ).count()
        
        failed_executions = self.db.query(Execution).filter(
            Execution.workflow_id == workflow_id,
            Execution.status == ExecutionStatus.FAILED
        ).count()
        
        running_executions = self.db.query(Execution).filter(
            Execution.workflow_id == workflow_id,
            Execution.status.in_([ExecutionStatus.PENDING, ExecutionStatus.RUNNING])
        ).count()
        
        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "running_executions": running_executions,
            "success_rate": successful_executions / total_executions if total_executions > 0 else 0
        }