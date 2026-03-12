"""Project-related Pydantic schemas."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum
from uuid import UUID

class ProjectStatus(str, Enum):
    """Project status enum."""
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectBase(BaseModel):
    """Base project schema."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Project name (1-255 characters)"
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Project description (optional, max 2000 characters)"
    )


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""
    chunk_size: int = Field(
        default=1000,
        ge=100,
        le=4000,
        description="Chunk size for document splitting (100-4000 chars, default 1000). "
                   "Larger chunks = more context per retrieval."
    )
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        le=1000,
        description="Overlap between chunks (0-1000 chars, default 200). "
                   "Ensures continuity between chunks."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "My Research Project",
                "description": "Documentation for my research",
                "chunk_size": 1000,
                "chunk_overlap": 200
            }
        }


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="New project name"
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="New project description"
    )
    chunk_size: Optional[int] = Field(
        None,
        ge=100,
        le=4000,
        description="New chunk size for future documents"
    )
    chunk_overlap: Optional[int] = Field(
        None,
        ge=0,
        le=1000,
        description="New chunk overlap for future documents"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Updated Project Name",
                "chunk_size": 1500
            }
        }


class ProjectStats(BaseModel):
    """Project statistics."""
    document_count: int = Field(default=0, description="Total documents in project")
    completed_documents: int = Field(default=0, description="Successfully processed documents")
    failed_documents: int = Field(default=0, description="Failed documents")
    pending_documents: int = Field(default=0, description="Documents pending processing")
    processing_documents: int = Field(default=0, description="Currently processing documents")
    total_chunks: int = Field(default=0, description="Total chunks from all documents")
    total_size_bytes: int = Field(default=0, description="Total file size in bytes")

    class Config:
        json_schema_extra = {
            "example": {
                "document_count": 15,
                "completed_documents": 12,
                "failed_documents": 1,
                "pending_documents": 2,
                "processing_documents": 0,
                "total_chunks": 3450,
                "total_size_bytes": 1250000
            }
        }


class Project(ProjectBase):
    """Project response schema."""
    id: UUID = Field(..., description="Project unique identifier")
    owner_id: UUID = Field(..., description="User ID of project owner")
    status: ProjectStatus = Field(..., description="Project status (active/archived)")
    chunk_size: int = Field(..., description="Current chunk size setting")
    chunk_overlap: int = Field(..., description="Current chunk overlap setting")
    created_at: datetime = Field(..., description="Project creation timestamp")
    updated_at: datetime = Field(..., description="Project last update timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "660e8400-e29b-41d4-a716-446655440000",
                "name": "My Research Project",
                "description": "Documentation for my research",
                "owner_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "active",
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "created_at": "2024-03-08T10:00:00Z",
                "updated_at": "2024-03-08T10:00:00Z"
            }
        }
    )


class ProjectWithStats(Project):
    """Project with statistics."""
    stats: ProjectStats = Field(..., description="Project statistics")


class ProjectList(BaseModel):
    """Paginated project list."""
    items: List[Project] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "660e8400-e29b-41d4-a716-446655440000",
                        "name": "My Research Project",
                        "description": "Documentation for my research",
                        "owner_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "active",
                        "chunk_size": 1000,
                        "chunk_overlap": 200,
                        "created_at": "2024-03-08T10:00:00Z",
                        "updated_at": "2024-03-08T10:00:00Z"
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20,
                "pages": 1
            }
        }
    )
