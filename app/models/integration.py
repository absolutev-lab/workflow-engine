"""
Integration model for external service integrations.
"""
from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
import enum
from app.core.database import Base


class IntegrationStatus(str, enum.Enum):
    """Integration status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class Integration(Base):
    """Integration model for external service integrations."""
    
    __tablename__ = "integrations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_name = Column(String(100), nullable=False)
    service_url = Column(String(500))
    credentials = Column(JSONB)
    configuration = Column(JSONB)
    status = Column(Enum(IntegrationStatus), default=IntegrationStatus.INACTIVE, nullable=False)
    last_sync = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Integration(id={self.id}, service={self.service_name}, status={self.status})>"