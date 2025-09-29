"""
Trigger model for workflow triggers.
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class Trigger(Base):
    """Trigger model for workflow triggers."""
    
    __tablename__ = "triggers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    trigger_type = Column(String(50), nullable=False)
    configuration = Column(JSONB, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    workflow = relationship("Workflow", back_populates="triggers")
    
    def __repr__(self):
        return f"<Trigger(id={self.id}, workflow_id={self.workflow_id}, type={self.trigger_type})>"