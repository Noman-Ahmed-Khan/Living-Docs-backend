"""Projects application DTOs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from uuid import UUID


@dataclass
class ProjectDTO:
    """Data transfer object for a project."""
    id: UUID
    name: str
    owner_id: UUID
    status: str
    chunk_size: int
    chunk_overlap: int
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ProjectStatsDTO:
    """Data transfer object for project statistics."""
    document_count: int = 0
    completed_documents: int = 0
    failed_documents: int = 0
    pending_documents: int = 0
    total_chunks: int = 0
    total_size_bytes: int = 0


@dataclass
class ProjectWithStatsDTO:
    """Project DTO enriched with statistics."""
    id: UUID
    name: str
    owner_id: UUID
    status: str
    chunk_size: int
    chunk_overlap: int
    stats: ProjectStatsDTO
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ProjectListDTO:
    """Paginated list of projects."""
    items: List[ProjectDTO]
    total: int
    page: int
    page_size: int
    pages: int
