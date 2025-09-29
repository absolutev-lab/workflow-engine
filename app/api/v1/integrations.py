"""
Integration management endpoints for n8n and other services.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.models import User, Integration
from app.services.n8n_service import N8nService
from pydantic import BaseModel

router = APIRouter()


class IntegrationResponse(BaseModel):
    """Integration response schema."""
    id: str
    service_name: str
    service_url: str
    status: str
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class N8nSyncRequest(BaseModel):
    """n8n sync request schema."""
    sync_direction: str = "from_n8n"  # "from_n8n" or "to_n8n"


@router.get("/", response_model=List[IntegrationResponse])
def list_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all integrations."""
    integrations = db.query(Integration).all()
    return integrations


@router.post("/n8n/connect", response_model=IntegrationResponse)
def connect_n8n(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Connect to n8n instance."""
    n8n_service = N8nService(db)
    integration = n8n_service.create_integration(str(current_user.id))
    return integration


@router.post("/n8n/test")
def test_n8n_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Test n8n connection."""
    n8n_service = N8nService(db)
    is_connected = n8n_service.test_connection()
    
    return {
        "connected": is_connected,
        "message": "Connection successful" if is_connected else "Connection failed"
    }


@router.post("/n8n/sync")
def sync_n8n_workflows(
    sync_request: N8nSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Sync workflows with n8n."""
    n8n_service = N8nService(db)
    
    if sync_request.sync_direction == "from_n8n":
        synced_workflows = n8n_service.sync_workflows_from_n8n(str(current_user.id))
        return {
            "status": "success",
            "direction": "from_n8n",
            "synced_workflows": synced_workflows,
            "count": len(synced_workflows)
        }
    else:
        return {
            "status": "error",
            "message": "Sync direction 'to_n8n' not implemented yet"
        }


@router.post("/n8n/export/{workflow_id}")
def export_workflow_to_n8n(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Export workflow to n8n."""
    n8n_service = N8nService(db)
    result = n8n_service.export_workflow_to_n8n(workflow_id, str(current_user.id))
    return result


@router.get("/n8n/executions/{workflow_id}")
def get_n8n_executions(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get execution history from n8n."""
    n8n_service = N8nService(db)
    executions = n8n_service.get_n8n_executions(workflow_id)
    
    return {
        "workflow_id": workflow_id,
        "executions": executions,
        "count": len(executions)
    }