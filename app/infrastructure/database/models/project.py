"""SQLAlchemy ORM Project Model - Infrastructure Layer."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Index, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.infrastructure.database.session import Base


class ProjectStatus(str, PyEnum):
    """Project status."""
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectModel(Base):
    """SQLAlchemy ORM model for projects."""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Status
    status = Column(
        Enum(ProjectStatus, name="project_status"),
        default=ProjectStatus.ACTIVE,
        nullable=False
    )

    # Settings (JSON-like storage for RAG config)
    chunk_size = Column(Integer, default=1000, nullable=False)
    chunk_overlap = Column(Integer, default=200, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("UserModel", back_populates="projects")
    documents = relationship("DocumentModel", back_populates="project", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSessionModel", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_project_owner_status', 'owner_id', 'status'),
    )
