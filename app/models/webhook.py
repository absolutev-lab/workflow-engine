"""
Webhook model for webhook management.
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class Webhook(Base):
    """Webhook model for webhook management."""
    
    __tablename__ = "webhooks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    url_path = Column(String(255), unique=True, nullable=False, index=True)
    method = Column(String(10), default="POST", nullable=False)
    headers = Column(JSONB)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    workflow = relationship("Workflow", back_populates="webhooks")
    
    def __repr__(self):
        return f"<Webhook(id={self.id}, workflow_id={self.workflow_id}, path={self.url_path})>"