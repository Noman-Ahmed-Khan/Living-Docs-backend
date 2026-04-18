"""Document application layer DTOs."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Optional


@dataclass
class DocumentUploadDTO:
    """DTO for document upload result."""
    document_id: UUID
    filename: str
    file_size: int
    status: str
    message: str


@dataclass
class IngestionResultDTO:
    """DTO for ingestion result."""
    document_id: UUID
    success: bool
    chunk_count: int
    message: str
    error: Optional[str] = None


@dataclass
class DocumentDetailDTO:
    """DTO for document details."""
    id: UUID
    filename: str
    original_filename: str
    project_id: UUID
    status: str
    file_size: Optional[int]
    chunk_count: int
    page_count: Optional[int]
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime]
    file_path: str
