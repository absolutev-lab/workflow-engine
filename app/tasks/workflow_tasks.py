"""
Celery tasks for workflow execution.
"""
import json
import traceback
from datetime import datetime
from typing import Dict, Any, List
from celery import current_task
from sqlalchemy.orm import sessionmaker
from app.celery_app import celery_app
from app.core.database import engine
from app.models import Workflow, Execution, ExecutionLog
from app.models.execution import ExecutionStatus
from app.models.execution_log import LogLevel
import logging

logger = logging.getLogger(__name__)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class WorkflowExecutor:
    """Workflow execution engine."""
    
    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self.db = SessionLocal()
        self.execution = None
        self.workflow = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
    
    def load_execution(self):
        """Load execution and workflow from database."""
        self.execution = self.db.query(Execution).filter(
            Execution.id == self.execution_id
        ).first()
        
        if not self.execution:
            raise ValueError(f"Execution {self.execution_id} not found")
        
        self.workflow = self.db.query(Workflow).filter(
            Workflow.id == self.execution.workflow_id
        ).first()
        
        if not self.workflow:
            raise ValueError(f"Workflow {self.execution.workflow_id} not found")
    
    def log_message(self, level: LogLevel, message: str, metadata: Dict[str, Any] = None):
        """Log execution message."""
        log_entry = ExecutionLog(
            execution_id=self.execution_id,
            level=level,
            message=message,
            log_metadata=metadata or {}
        )
        self.db.add(log_entry)
        self.db.commit()
        
        # Also log to Python logger
        getattr(logger, level.value)(f"Execution {self.execution_id}: {message}")
    
    def update_execution_status(self, status: ExecutionStatus, error_message: str = None):
        """Update execution status."""
        self.execution.status = status
        
        if status == ExecutionStatus.RUNNING:
            self.execution.started_at = datetime.utcnow()
        elif status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
            self.execution.completed_at = datetime.utcnow()
        
        if error_message:
            self.execution.error_message = error_message
        
        self.db.commit()
    
    def execute_node(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single workflow node."""
        node_id = node.get("id")
        node_type = node.get("type")
        node_name = node.get("name", node_id)
        parameters = node.get("parameters", {})
        
        self.log_message(
            LogLevel.INFO,
            f"Executing node: {node_name} ({node_type})",
            {"node_id": node_id, "node_type": node_type}
        )
        
        try:
            # Execute based on node type
            if node_type == "start":
                return self.execute_start_node(node, context)
            elif node_type == "http_request":
                return self.execute_http_request_node(node, context)
            elif node_type == "data_transform":
                return self.execute_data_transform_node(node, context)
            elif node_type == "condition":
                return self.execute_condition_node(node, context)
            elif node_type == "end":
                return self.execute_end_node(node, context)
            else:
                # Generic node execution
                return self.execute_generic_node(node, context)
                
        except Exception as e:
            self.log_message(
                LogLevel.ERROR,
                f"Error executing node {node_name}: {str(e)}",
                {"node_id": node_id, "error": str(e), "traceback": traceback.format_exc()}
            )
            raise
    
    def execute_start_node(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute start node."""
        return {"status": "started", "data": context.get("input_data", {})}
    
    def execute_http_request_node(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HTTP request node."""
        import requests
        
        parameters = node.get("parameters", {})
        method = parameters.get("method", "GET").upper()
        url = parameters.get("url", "")
        headers = parameters.get("headers", {})
        data = parameters.get("data", {})
        
        # Replace variables in URL and data
        url = self.replace_variables(url, context)
        data = self.replace_variables(data, context)
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data if method in ["POST", "PUT", "PATCH"] else None,
                timeout=30
            )
            
            return {
                "status_code": response.status_code,
                "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                "headers": dict(response.headers)
            }
        except Exception as e:
            return {"error": str(e), "status_code": 0}
    
    def execute_data_transform_node(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute data transformation node."""
        parameters = node.get("parameters", {})
        transformation = parameters.get("transformation", "")
        input_data = context.get("data", {})
        
        # Simple transformation logic (can be extended)
        if transformation == "json_extract":
            path = parameters.get("path", "")
            return self.extract_json_path(input_data, path)
        elif transformation == "format_string":
            template = parameters.get("template", "")
            return {"result": self.replace_variables(template, context)}
        else:
            return input_data
    
    def execute_condition_node(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute condition node."""
        parameters = node.get("parameters", {})
        condition = parameters.get("condition", "")
        
        # Simple condition evaluation (can be extended with safe eval)
        try:
            # For now, just return True/False based on simple conditions
            result = self.evaluate_condition(condition, context)
            return {"condition_result": result}
        except Exception as e:
            return {"condition_result": False, "error": str(e)}
    
    def execute_end_node(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute end node."""
        return {"status": "completed", "final_data": context.get("data", {})}
    
    def execute_generic_node(self, node: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute generic node."""
        # Default implementation - just pass through data
        return context.get("data", {})
    
    def replace_variables(self, template: Any, context: Dict[str, Any]) -> Any:
        """Replace variables in template with context values."""
        if isinstance(template, str):
            # Simple variable replacement: {{variable_name}}
            import re
            def replace_var(match):
                var_name = match.group(1)
                return str(context.get(var_name, match.group(0)))
            
            return re.sub(r'\{\{(\w+)\}\}', replace_var, template)
        elif isinstance(template, dict):
            return {k: self.replace_variables(v, context) for k, v in template.items()}
        elif isinstance(template, list):
            return [self.replace_variables(item, context) for item in template]
        else:
            return template
    
    def extract_json_path(self, data: Any, path: str) -> Dict[str, Any]:
        """Extract data from JSON path."""
        try:
            parts = path.split(".")
            result = data
            for part in parts:
                if isinstance(result, dict):
                    result = result.get(part)
                elif isinstance(result, list) and part.isdigit():
                    result = result[int(part)]
                else:
                    return {"error": f"Cannot access path {path}"}
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
    
    def evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate simple conditions."""
        # Very basic condition evaluation - extend as needed
        condition = self.replace_variables(condition, context)
        
        # Simple comparisons
        if " == " in condition:
            left, right = condition.split(" == ", 1)
            return left.strip() == right.strip()
        elif " != " in condition:
            left, right = condition.split(" != ", 1)
            return left.strip() != right.strip()
        elif " > " in condition:
            left, right = condition.split(" > ", 1)
            try:
                return float(left.strip()) > float(right.strip())
            except ValueError:
                return False
        elif " < " in condition:
            left, right = condition.split(" < ", 1)
            try:
                return float(left.strip()) < float(right.strip())
            except ValueError:
                return False
        else:
            # Default to checking if condition string is truthy
            return bool(condition.strip())
    
    def execute_workflow(self) -> Dict[str, Any]:
        """Execute the complete workflow."""
        self.load_execution()
        
        # Update status to running
        self.update_execution_status(ExecutionStatus.RUNNING)
        self.log_message(LogLevel.INFO, "Starting workflow execution")
        
        try:
            definition = self.workflow.definition
            nodes = definition.get("nodes", [])
            connections = definition.get("connections", [])
            
            # Build execution graph
            execution_order = self.build_execution_order(nodes, connections)
            
            # Execute nodes in order
            context = {
                "input_data": self.execution.input_data,
                "workflow_id": str(self.workflow.id),
                "execution_id": str(self.execution.id)
            }
            
            output_data = {}
            
            for node_id in execution_order:
                node = next((n for n in nodes if n["id"] == node_id), None)
                if node:
                    result = self.execute_node(node, context)
                    context["data"] = result
                    output_data[node_id] = result
                    
                    # Update task progress
                    progress = (execution_order.index(node_id) + 1) / len(execution_order) * 100
                    current_task.update_state(
                        state="PROGRESS",
                        meta={"progress": progress, "current_node": node.get("name", node_id)}
                    )
            
            # Update execution with results
            self.execution.output_data = output_data
            self.update_execution_status(ExecutionStatus.COMPLETED)
            self.log_message(LogLevel.INFO, "Workflow execution completed successfully")
            
            return output_data
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            self.update_execution_status(ExecutionStatus.FAILED, error_msg)
            self.log_message(LogLevel.ERROR, error_msg, {"traceback": traceback.format_exc()})
            raise
    
    def build_execution_order(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> List[str]:
        """Build execution order from workflow definition."""
        # Simple topological sort
        from collections import defaultdict, deque
        
        # Build adjacency list
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        
        # Initialize all nodes
        for node in nodes:
            node_id = node["id"]
            in_degree[node_id] = 0
        
        # Build graph from connections
        for connection in connections:
            source = connection["source"]
            target = connection["target"]
            graph[source].append(target)
            in_degree[target] += 1
        
        # Topological sort
        queue = deque([node_id for node_id in in_degree if in_degree[node_id] == 0])
        result = []
        
        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            
            for neighbor in graph[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # If result doesn't contain all nodes, there might be a cycle
        if len(result) != len(nodes):
            # Fallback to original order
            result = [node["id"] for node in nodes]
        
        return result


@celery_app.task(bind=True)
def execute_workflow_task(self, execution_id: str):
    """Celery task to execute a workflow."""
    try:
        with WorkflowExecutor(execution_id) as executor:
            result = executor.execute_workflow()
            return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"Workflow execution failed: {str(e)}")
        return {"status": "failed", "error": str(e)}


@celery_app.task
def process_webhook_task(webhook_id: str, payload: Dict[str, Any]):
    """Celery task to process webhook."""
    try:
        db = SessionLocal()
        
        # Find workflows that should be triggered by this webhook
        # This is a simplified implementation
        logger.info(f"Processing webhook {webhook_id} with payload: {payload}")
        
        # Here you would implement webhook processing logic
        # For now, just log the webhook
        
        db.close()
        return {"status": "processed", "webhook_id": webhook_id}
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        return {"status": "failed", "error": str(e)}