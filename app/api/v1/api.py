"""
API v1 router configuration.
"""
from fastapi import APIRouter
from app.api.v1 import auth, workflows, executions, integrations, websocket, webhooks, monitoring

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(executions.router, prefix="/executions", tags=["executions"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(monitoring.router, tags=["monitoring"])