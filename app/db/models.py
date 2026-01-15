import uuid
import secrets
from enum import Enum as PyEnum
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Boolean, Index, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .session import Base


# Enums

class DocumentStatus(str, PyEnum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectStatus(str, PyEnum):
    """Project status."""
    ACTIVE = "active"
    ARCHIVED = "archived"


# User Models

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Account Status
    is_active = Column(Boolean, default=True, nullable=False)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    
    # Security
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    verification_tokens = relationship("VerificationToken", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Token metadata
    device_info = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    
    # Token lifecycle
    is_revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    # For token rotation - tracks the token family
    family_id = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, index=True)
    replaced_by = Column(UUID(as_uuid=True), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index('idx_refresh_token_user_active', 'user_id', 'is_revoked'),
        Index('idx_refresh_token_expires', 'expires_at'),
    )


class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(255), unique=True, index=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Token type for different verification purposes
    token_type = Column(String(50), default="email_verification", nullable=False)
    new_email = Column(String(255), nullable=True)  # For email change verification
    
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="verification_tokens")

    __table_args__ = (
        Index('idx_verification_token_user_type', 'user_id', 'token_type'),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(255), unique=True, index=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="password_reset_tokens")

# Project Model

class Project(Base):
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
    owner = relationship("User", back_populates="projects")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_project_owner_status', 'owner_id', 'status'),
    )


# Document Model

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(1000), nullable=False)
    
    # File metadata
    file_size = Column(Integer, nullable=True)  # in bytes
    file_type = Column(String(50), nullable=True)  # extension
    content_type = Column(String(100), nullable=True)  # MIME type
    
    # Processing status
    status = Column(
        Enum(DocumentStatus, name="document_status"),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True
    )
    status_message = Column(Text, nullable=True)
    
    # Ingestion metrics
    chunk_count = Column(Integer, default=0, nullable=False)
    page_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)
    
    # Processing timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="documents")

    __table_args__ = (
        Index('idx_document_project_status', 'project_id', 'status'),
    )