"""SQLAlchemy ORM Chat Models - Infrastructure Layer."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.infrastructure.database.session import Base


class ChatMessageRole(str, PyEnum):
    """Chat message role."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatSessionModel(Base):
    """SQLAlchemy ORM model for chat sessions."""
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_message_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("ProjectModel", back_populates="chat_sessions")
    user = relationship("UserModel")
    messages = relationship(
        "ChatMessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessageModel.created_at.asc()",
    )

    __table_args__ = (
        Index("idx_chat_session_user_project", "user_id", "project_id"),
    )


class ChatMessageModel(Base):
    """SQLAlchemy ORM model for chat messages."""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)

    role = Column(
        Enum(ChatMessageRole, name="chat_message_role"),
        nullable=False,
    )
    content = Column(Text, nullable=False)

    # Optional metadata about the answer
    query_id = Column(UUID(as_uuid=True), nullable=True)       # from QueryResponse.query_id
    answer_metadata = Column(Text, nullable=True)              # JSON blob as text if needed

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSessionModel", back_populates="messages")

    __table_args__ = (
        Index("idx_chat_message_session_created", "session_id", "created_at"),
    )
