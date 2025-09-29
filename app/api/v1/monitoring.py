"""
Monitoring and health check endpoints.
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_active_user, get_admin_user
from app.models import User
from app.core.monitoring import monitor

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Public health check endpoint."""
    health_status = monitor.get_health_status(db)
    
    # Return appropriate HTTP status based on health
    if health_status["overall_status"] == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )
    elif health_status["overall_status"] == "degraded":
        # Still return 200 but with degraded status
        pass
    
    return health_status


@router.get("/metrics/system")
def get_system_metrics(
    current_user: User = Depends(get_admin_user)
):
    """Get system resource metrics (admin only)."""
    return monitor.get_system_metrics()


@router.get("/metrics/database")
def get_database_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get database metrics (admin only)."""
    return monitor.get_database_metrics(db)


@router.get("/metrics/celery")
def get_celery_metrics(
    current_user: User = Depends(get_admin_user)
):
    """Get Celery task queue metrics (admin only)."""
    return monitor.get_celery_metrics()


@router.get("/metrics/application")
def get_application_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get application-specific metrics (admin only)."""
    return monitor.get_application_metrics(db)


@router.get("/metrics/all")
def get_all_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get all metrics in one response (admin only)."""
    try:
        return {
            "system": monitor.get_system_metrics(),
            "database": monitor.get_database_metrics(db),
            "celery": monitor.get_celery_metrics(),
            "application": monitor.get_application_metrics(db),
            "health": monitor.get_health_status(db)
        }
    except Exception as e:
        logger.error(f"Error collecting all metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to collect metrics"
        )


@router.get("/status")
def get_status(
    current_user: User = Depends(get_current_active_user)
):
    """Get basic status information for authenticated users."""
    try:
        from datetime import datetime
        return {
            "status": "running",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "user": {
                "id": str(current_user.id),
                "email": current_user.email,
                "role": current_user.role.value
            }
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get status"
        )