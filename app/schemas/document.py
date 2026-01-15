"""Document-related Pydantic schemas."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentBase(BaseModel):
    """Base document schema."""
    filename: str = Field(..., description="Document filename")


class DocumentCreate(BaseModel):
    """Internal schema for creating a document."""
    filename: str
    original_filename: str
    project_id: str
    file_path: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    content_type: Optional[str] = None


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""
    status: Optional[DocumentStatus] = None
    status_message: Optional[str] = None
    chunk_count: Optional[int] = None
    page_count: Optional[int] = None
    character_count: Optional[int] = None
    processed_at: Optional[datetime] = None


class Document(BaseModel):
    """Document response schema."""
    id: str
    filename: str
    original_filename: str
    project_id: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    status: DocumentStatus
    status_message: Optional[str] = None
    chunk_count: int = 0
    page_count: Optional[int] = None
    character_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentDetail(Document):
    """Detailed document information."""
    content_type: Optional[str] = None
    file_path: str


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""
    document: Document
    message: str = "Document uploaded successfully"
    processing: bool = True


class DocumentList(BaseModel):
    """Paginated document list."""
    items: List[Document]
    total: int
    page: int
    page_size: int
    pages: int


class DocumentIngestionStatus(BaseModel):
    """Document ingestion status details."""
    document_id: str
    status: DocumentStatus
    message: Optional[str] = None
    progress: Optional[float] = None  # 0.0 to 1.0
    chunks_created: int = 0
    pages_processed: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BulkUploadResponse(BaseModel):
    """Response for bulk upload."""
    uploaded: List[Document]
    failed: List[Dict[str, str]]
    total_uploaded: int
    total_failed: int


class ReingestionRequest(BaseModel):
    """Request to re-ingest a document."""
    chunk_size: Optional[int] = Field(None, ge=100, le=4000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000)
    force: bool = Field(default=False, description="Force re-ingestion even if completed")