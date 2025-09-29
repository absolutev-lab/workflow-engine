"""
Monitoring and metrics collection for the workflow engine.
"""
import time
import psutil
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.core.database import get_db
from app.models import Workflow, Execution, User, ExecutionLog
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


class SystemMonitor:
    """System monitoring and metrics collection."""
    
    def __init__(self):
        self.start_time = datetime.utcnow()
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used = memory.used
            memory_total = memory.total
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_used = disk.used
            disk_total = disk.total
            
            # Network metrics (if available)
            network = psutil.net_io_counters()
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count
                },
                "memory": {
                    "percent": memory_percent,
                    "used_bytes": memory_used,
                    "total_bytes": memory_total,
                    "available_bytes": memory.available
                },
                "disk": {
                    "percent": disk_percent,
                    "used_bytes": disk_used,
                    "total_bytes": disk_total,
                    "free_bytes": disk.free
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                }
            }
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {"error": str(e)}
    
    def get_database_metrics(self, db: Session) -> Dict[str, Any]:
        """Get database metrics."""
        try:
            # Connection pool info
            pool = db.bind.pool
            pool_size = pool.size()
            checked_in = pool.checkedin()
            checked_out = pool.checkedout()
            overflow = pool.overflow()
            
            # Table counts
            user_count = db.query(func.count(User.id)).scalar()
            workflow_count = db.query(func.count(Workflow.id)).scalar()
            execution_count = db.query(func.count(Execution.id)).scalar()
            log_count = db.query(func.count(ExecutionLog.id)).scalar()
            
            # Recent activity (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_executions = db.query(func.count(Execution.id)).filter(
                Execution.created_at >= yesterday
            ).scalar()
            
            # Database size (PostgreSQL specific)
            try:
                db_size_result = db.execute(text(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                )).scalar()
            except:
                db_size_result = "Unknown"
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "connection_pool": {
                    "size": pool_size,
                    "checked_in": checked_in,
                    "checked_out": checked_out,
                    "overflow": overflow
                },
                "table_counts": {
                    "users": user_count,
                    "workflows": workflow_count,
                    "executions": execution_count,
                    "logs": log_count
                },
                "recent_activity": {
                    "executions_24h": recent_executions
                },
                "database_size": db_size_result
            }
        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
            return {"error": str(e)}
    
    def get_celery_metrics(self) -> Dict[str, Any]:
        """Get Celery task queue metrics."""
        try:
            # Get Celery inspect instance
            inspect = celery_app.control.inspect()
            
            # Active tasks
            active_tasks = inspect.active()
            
            # Scheduled tasks
            scheduled_tasks = inspect.scheduled()
            
            # Reserved tasks
            reserved_tasks = inspect.reserved()
            
            # Worker stats
            stats = inspect.stats()
            
            # Queue lengths (Redis specific)
            try:
                from celery.backends.redis import RedisBackend
                if isinstance(celery_app.backend, RedisBackend):
                    redis_client = celery_app.backend.client
                    queue_lengths = {}
                    for queue in ['celery', 'workflow_execution', 'webhook_processing']:
                        length = redis_client.llen(queue)
                        queue_lengths[queue] = length
                else:
                    queue_lengths = {}
            except:
                queue_lengths = {}
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "active_tasks": active_tasks,
                "scheduled_tasks": scheduled_tasks,
                "reserved_tasks": reserved_tasks,
                "worker_stats": stats,
                "queue_lengths": queue_lengths
            }
        except Exception as e:
            logger.error(f"Error collecting Celery metrics: {e}")
            return {"error": str(e)}
    
    def get_application_metrics(self, db: Session) -> Dict[str, Any]:
        """Get application-specific metrics."""
        try:
            # Workflow status distribution
            workflow_status_query = db.query(
                Workflow.status,
                func.count(Workflow.id).label('count')
            ).group_by(Workflow.status).all()
            
            workflow_status = {status: count for status, count in workflow_status_query}
            
            # Execution status distribution
            execution_status_query = db.query(
                Execution.status,
                func.count(Execution.id).label('count')
            ).group_by(Execution.status).all()
            
            execution_status = {status.value: count for status, count in execution_status_query}
            
            # Recent execution performance
            recent_executions = db.query(Execution).filter(
                Execution.completed_at.isnot(None),
                Execution.started_at.isnot(None),
                Execution.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).all()
            
            if recent_executions:
                durations = []
                for execution in recent_executions:
                    if execution.started_at and execution.completed_at:
                        duration = (execution.completed_at - execution.started_at).total_seconds()
                        durations.append(duration)
                
                if durations:
                    avg_duration = sum(durations) / len(durations)
                    min_duration = min(durations)
                    max_duration = max(durations)
                else:
                    avg_duration = min_duration = max_duration = 0
            else:
                avg_duration = min_duration = max_duration = 0
            
            # Error rate (last 24 hours)
            total_executions_24h = db.query(func.count(Execution.id)).filter(
                Execution.created_at >= datetime.utcnow() - timedelta(days=1)
            ).scalar()
            
            failed_executions_24h = db.query(func.count(Execution.id)).filter(
                Execution.created_at >= datetime.utcnow() - timedelta(days=1),
                Execution.status == 'FAILED'
            ).scalar()
            
            error_rate = (failed_executions_24h / total_executions_24h * 100) if total_executions_24h > 0 else 0
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "workflow_status_distribution": workflow_status,
                "execution_status_distribution": execution_status,
                "execution_performance": {
                    "avg_duration_seconds": avg_duration,
                    "min_duration_seconds": min_duration,
                    "max_duration_seconds": max_duration,
                    "sample_size": len(recent_executions)
                },
                "error_metrics": {
                    "error_rate_24h_percent": error_rate,
                    "total_executions_24h": total_executions_24h,
                    "failed_executions_24h": failed_executions_24h
                }
            }
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
            return {"error": str(e)}
    
    def get_health_status(self, db: Session) -> Dict[str, Any]:
        """Get overall health status."""
        try:
            health_checks = {}
            overall_status = "healthy"
            
            # Database health
            try:
                db.execute(text("SELECT 1")).scalar()
                health_checks["database"] = {"status": "healthy", "message": "Database connection OK"}
            except Exception as e:
                health_checks["database"] = {"status": "unhealthy", "message": f"Database error: {e}"}
                overall_status = "unhealthy"
            
            # Redis/Celery health
            try:
                inspect = celery_app.control.inspect()
                stats = inspect.stats()
                if stats:
                    health_checks["celery"] = {"status": "healthy", "message": "Celery workers responding"}
                else:
                    health_checks["celery"] = {"status": "degraded", "message": "No Celery workers found"}
                    if overall_status == "healthy":
                        overall_status = "degraded"
            except Exception as e:
                health_checks["celery"] = {"status": "unhealthy", "message": f"Celery error: {e}"}
                overall_status = "unhealthy"
            
            # System resources health
            try:
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                if memory.percent > 90:
                    health_checks["memory"] = {"status": "critical", "message": f"High memory usage: {memory.percent}%"}
                    overall_status = "unhealthy"
                elif memory.percent > 80:
                    health_checks["memory"] = {"status": "warning", "message": f"Memory usage: {memory.percent}%"}
                    if overall_status == "healthy":
                        overall_status = "degraded"
                else:
                    health_checks["memory"] = {"status": "healthy", "message": f"Memory usage: {memory.percent}%"}
                
                if disk.percent > 90:
                    health_checks["disk"] = {"status": "critical", "message": f"High disk usage: {disk.percent}%"}
                    overall_status = "unhealthy"
                elif disk.percent > 80:
                    health_checks["disk"] = {"status": "warning", "message": f"Disk usage: {disk.percent}%"}
                    if overall_status == "healthy":
                        overall_status = "degraded"
                else:
                    health_checks["disk"] = {"status": "healthy", "message": f"Disk usage: {disk.percent}%"}
                    
            except Exception as e:
                health_checks["system"] = {"status": "unknown", "message": f"System check error: {e}"}
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_status": overall_status,
                "checks": health_checks,
                "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds()
            }
        except Exception as e:
            logger.error(f"Error performing health check: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_status": "unhealthy",
                "error": str(e)
            }


# Global monitor instance
monitor = SystemMonitor()