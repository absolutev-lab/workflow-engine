"""
Webhook management endpoints for dynamic webhook handling.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.models import User, Webhook, Workflow
from app.tasks.workflow_tasks import process_webhook_task
from app.websocket.events import events
from pydantic import BaseModel
from datetime import datetime
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)


class WebhookCreate(BaseModel):
    """Webhook creation schema."""
    workflow_id: str
    url_path: str
    method: str = "POST"
    headers: Optional[Dict[str, str]] = None


class WebhookUpdate(BaseModel):
    """Webhook update schema."""
    url_path: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    """Webhook response schema."""
    id: str
    workflow_id: str
    url_path: str
    method: str
    headers: Dict[str, str]
    is_active: bool
    created_at: str
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[WebhookResponse])
def list_webhooks(
    workflow_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all webhooks, optionally filtered by workflow."""
    query = db.query(Webhook)
    
    if workflow_id:
        # Verify user has access to the workflow
        workflow = db.query(Workflow).filter(
            Workflow.id == workflow_id,
            Workflow.created_by == str(current_user.id)
        ).first()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        query = query.filter(Webhook.workflow_id == workflow_id)
    else:
        # Only show webhooks for user's workflows
        user_workflow_ids = db.query(Workflow.id).filter(
            Workflow.created_by == str(current_user.id)
        ).subquery()
        query = query.filter(Webhook.workflow_id.in_(user_workflow_ids))
    
    webhooks = query.all()
    return webhooks


@router.post("/", response_model=WebhookResponse)
def create_webhook(
    webhook_data: WebhookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new webhook."""
    # Verify user owns the workflow
    workflow = db.query(Workflow).filter(
        Workflow.id == webhook_data.workflow_id,
        Workflow.created_by == str(current_user.id)
    ).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Check if webhook path already exists
    existing_webhook = db.query(Webhook).filter(
        Webhook.url_path == webhook_data.url_path,
        Webhook.method == webhook_data.method
    ).first()
    
    if existing_webhook:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook with this path and method already exists"
        )
    
    # Create webhook
    webhook = Webhook(
        id=str(uuid.uuid4()),
        workflow_id=webhook_data.workflow_id,
        url_path=webhook_data.url_path,
        method=webhook_data.method.upper(),
        headers=webhook_data.headers or {},
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    
    logger.info(f"Created webhook {webhook.id} for workflow {webhook_data.workflow_id}")
    return webhook


@router.get("/{webhook_id}", response_model=WebhookResponse)
def get_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific webhook."""
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )
    
    # Verify user owns the workflow
    workflow = db.query(Workflow).filter(
        Workflow.id == webhook.workflow_id,
        Workflow.created_by == str(current_user.id)
    ).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return webhook


@router.put("/{webhook_id}", response_model=WebhookResponse)
def update_webhook(
    webhook_id: str,
    webhook_data: WebhookUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update a webhook."""
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )
    
    # Verify user owns the workflow
    workflow = db.query(Workflow).filter(
        Workflow.id == webhook.workflow_id,
        Workflow.created_by == str(current_user.id)
    ).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Update webhook fields
    if webhook_data.url_path is not None:
        webhook.url_path = webhook_data.url_path
    if webhook_data.method is not None:
        webhook.method = webhook_data.method.upper()
    if webhook_data.headers is not None:
        webhook.headers = webhook_data.headers
    if webhook_data.is_active is not None:
        webhook.is_active = webhook_data.is_active
    
    db.commit()
    db.refresh(webhook)
    
    logger.info(f"Updated webhook {webhook_id}")
    return webhook


@router.delete("/{webhook_id}")
def delete_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a webhook."""
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found"
        )
    
    # Verify user owns the workflow
    workflow = db.query(Workflow).filter(
        Workflow.id == webhook.workflow_id,
        Workflow.created_by == str(current_user.id)
    ).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    db.delete(webhook)
    db.commit()
    
    logger.info(f"Deleted webhook {webhook_id}")
    return {"message": "Webhook deleted successfully"}


# Dynamic webhook handler
@router.api_route("/trigger/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def handle_webhook(
    path: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle incoming webhook requests dynamically."""
    method = request.method
    
    # Find matching webhook
    webhook = db.query(Webhook).filter(
        Webhook.url_path == path,
        Webhook.method == method,
        Webhook.is_active == True
    ).first()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint not found"
        )
    
    try:
        # Get request data
        headers = dict(request.headers)
        query_params = dict(request.query_params)
        
        # Get body data
        body = None
        content_type = headers.get("content-type", "")
        
        if method in ["POST", "PUT", "PATCH"]:
            if "application/json" in content_type:
                try:
                    body = await request.json()
                except:
                    body = {}
            elif "application/x-www-form-urlencoded" in content_type:
                form_data = await request.form()
                body = dict(form_data)
            else:
                body_bytes = await request.body()
                body = body_bytes.decode("utf-8") if body_bytes else ""
        
        # Prepare webhook payload
        webhook_payload = {
            "webhook_id": webhook.id,
            "workflow_id": webhook.workflow_id,
            "method": method,
            "url_path": path,
            "headers": headers,
            "query_params": query_params,
            "body": body,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Queue webhook processing task
        task = process_webhook_task.delay(webhook_payload)
        
        # Broadcast webhook received event
        await events.webhook_received({
            "id": webhook.id,
            "workflow_id": webhook.workflow_id,
            "method": method,
            "url_path": path,
            "payload": webhook_payload
        })
        
        logger.info(f"Webhook {webhook.id} triggered for workflow {webhook.workflow_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Webhook received and queued for processing",
                "webhook_id": webhook.id,
                "task_id": task.id
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing webhook {webhook.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )