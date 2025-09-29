"""
Workflow schemas for API requests and responses.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from app.models.workflow import WorkflowStatus


class WorkflowBase(BaseModel):
    """Base workflow schema."""
    name: str
    description: Optional[str] = None
    definition: Dict[str, Any]


class WorkflowCreate(WorkflowBase):
    """Workflow creation schema."""
    pass


class WorkflowUpdate(BaseModel):
    """Workflow update schema."""
    name: Optional[str] = None
    description: Optional[str] = None
    definition: Optional[Dict[str, Any]] = None
    status: Optional[WorkflowStatus] = None


class WorkflowResponse(WorkflowBase):
    """Workflow response schema."""
    id: str
    user_id: str
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True