"""Project-related Pydantic schemas."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ProjectStatus(str, Enum):
    """Project status enum."""
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectBase(BaseModel):
    """Base project schema."""
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=2000, description="Project description")


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""
    chunk_size: int = Field(default=1000, ge=100, le=4000, description="Chunk size for documents")
    chunk_overlap: int = Field(default=200, ge=0, le=1000, description="Chunk overlap size")


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[ProjectStatus] = None
    chunk_size: Optional[int] = Field(None, ge=100, le=4000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000)


class ProjectStats(BaseModel):
    """Project statistics."""
    document_count: int = Field(default=0, description="Total documents")
    completed_documents: int = Field(default=0, description="Successfully processed documents")
    failed_documents: int = Field(default=0, description="Failed documents")
    pending_documents: int = Field(default=0, description="Pending documents")
    total_chunks: int = Field(default=0, description="Total chunks across all documents")
    total_size_bytes: int = Field(default=0, description="Total file size in bytes")


class Project(ProjectBase):
    """Project response schema."""
    id: str
    owner_id: str
    status: ProjectStatus
    chunk_size: int
    chunk_overlap: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectWithStats(Project):
    """Project with statistics."""
    stats: ProjectStats


class ProjectList(BaseModel):
    """Paginated project list."""
    items: List[Project]
    total: int
    page: int
    page_size: int
    pages: int