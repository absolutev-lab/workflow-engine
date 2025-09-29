"""
Workflow execution endpoints.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.models import User, Workflow, Execution
from app.services.workflow_service import WorkflowService
from pydantic import BaseModel

router = APIRouter()


class ExecutionRequest(BaseModel):
    """Execution request schema."""
    input_data: Optional[Dict[str, Any]] = {}


class ExecutionResponse(BaseModel):
    """Execution response schema."""
    id: str
    workflow_id: str
    status: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    
    class Config:
        from_attributes = True


@router.post("/{workflow_id}/execute", response_model=ExecutionResponse)
async def execute_workflow(
    workflow_id: str,
    execution_request: ExecutionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Execute a workflow."""
    from app.tasks.workflow_tasks import execute_workflow_task
    
    workflow_service = WorkflowService(db)
    
    # Check if workflow can be executed
    if not workflow_service.can_execute_workflow(workflow_id, str(current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow cannot be executed. Check if it's active."
        )
    
    # Create execution record
    execution = Execution(
        workflow_id=workflow_id,
        input_data=execution_request.input_data,
        status="PENDING"
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    # Queue execution task with Celery
    task = execute_workflow_task.delay(str(execution.id))
    
    # Store Celery task ID for tracking
    execution.execution_metadata = {"celery_task_id": task.id}
    db.commit()
    
    return execution


@router.get("/{workflow_id}/executions", response_model=List[ExecutionResponse])
def get_workflow_executions(
    workflow_id: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get workflow execution history."""
    workflow_service = WorkflowService(db)
    executions = workflow_service.get_workflow_executions(
        workflow_id, str(current_user.id), limit, skip
    )
    return executions


@router.get("/{workflow_id}/statistics")
def get_workflow_statistics(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get workflow execution statistics."""
    workflow_service = WorkflowService(db)
    return workflow_service.get_workflow_statistics(workflow_id, str(current_user.id))


@router.post("/{workflow_id}/activate", response_model=Dict[str, str])
def activate_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Activate a workflow for execution."""
    workflow_service = WorkflowService(db)
    workflow = workflow_service.activate_workflow(workflow_id, str(current_user.id))
    return {"message": f"Workflow '{workflow.name}' activated successfully"}


@router.post("/{workflow_id}/deactivate", response_model=Dict[str, str])
def deactivate_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Deactivate a workflow."""
    workflow_service = WorkflowService(db)
    workflow = workflow_service.deactivate_workflow(workflow_id, str(current_user.id))
    return {"message": f"Workflow '{workflow.name}' deactivated successfully"}