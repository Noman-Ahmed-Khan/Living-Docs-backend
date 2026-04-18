"""Document-related Pydantic schemas."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum
from uuid import UUID

class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BulkUploadStatus(str, Enum):
    """Bulk upload result status."""
    SUCCESS = "success"
    FAILED = "failed"


class DocumentBase(BaseModel):
    """Base document schema."""
    filename: str = Field(..., description="Document filename")


class DocumentCreate(BaseModel):
    """Internal schema for creating a document."""
    filename: str
    original_filename: str
    project_id: UUID
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
    id: UUID = Field(..., description="Document unique identifier")
    filename: str = Field(..., description="Display filename")
    original_filename: str = Field(..., description="Original uploaded filename")
    project_id: UUID = Field(..., description="Parent project ID")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    file_type: Optional[str] = Field(None, description="File type/extension")
    status: DocumentStatus = Field(..., description="Processing status")
    status_message: Optional[str] = Field(None, description="Status error message if failed")
    chunk_count: int = Field(default=0, description="Number of chunks created")
    page_count: Optional[int] = Field(None, description="Page count (if applicable)")
    character_count: Optional[int] = Field(None, description="Total character count")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    processed_at: Optional[datetime] = Field(None, description="Processing completion timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440000",
                "filename": "report.pdf",
                "original_filename": "report.pdf",
                "project_id": "660e8400-e29b-41d4-a716-446655440000",
                "file_size": 1024000,
                "file_type": "pdf",
                "status": "completed",
                "chunk_count": 25,
                "character_count": 50000,
                "created_at": "2024-03-08T10:00:00Z",
                "updated_at": "2024-03-08T10:05:00Z",
                "processed_at": "2024-03-08T10:05:00Z"
            }
        }
    )


class DocumentDetail(Document):
    """Detailed document information."""
    content_type: Optional[str] = Field(None, description="MIME content type")
    file_path: str = Field(..., description="Internal file storage path")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440000",
                "filename": "report.pdf",
                "original_filename": "report.pdf",
                "project_id": "660e8400-e29b-41d4-a716-446655440000",
                "file_size": 1024000,
                "file_type": "pdf",
                "status": "completed",
                "status_message": None,
                "chunk_count": 25,
                "page_count": 12,
                "character_count": 50000,
                "created_at": "2024-03-08T10:00:00Z",
                "updated_at": "2024-03-08T10:05:00Z",
                "processed_at": "2024-03-08T10:05:00Z",
                "content_type": "application/pdf",
                "file_path": "./uploads/report.pdf"
            }
        }
    )


class BulkUploadItem(BaseModel):
    """Single document entry in a bulk upload response."""
    document_id: Optional[str] = Field(None, description="Uploaded document ID")
    filename: str = Field(..., description="Document filename")
    status: BulkUploadStatus = Field(..., description="Upload result status")
    error: Optional[str] = Field(None, description="Error message when upload fails")


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""
    document_id: str = Field(..., description="ID of uploaded document")
    filename: str = Field(..., description="Document filename")
    message: str = Field(default="Document uploaded successfully", description="Status message")
    processing: bool = Field(default=True, description="Whether document is being processed")

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "770e8400-e29b-41d4-a716-446655440000",
                "filename": "report.pdf",
                "message": "Document uploaded successfully. Processing started.",
                "processing": True
            }
        }


class DocumentList(BaseModel):
    """Paginated document list."""
    items: List[Document] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "770e8400-e29b-41d4-a716-446655440000",
                        "filename": "report.pdf",
                        "original_filename": "report.pdf",
                        "project_id": "660e8400-e29b-41d4-a716-446655440000",
                        "file_size": 1024000,
                        "file_type": "pdf",
                        "status": "completed",
                        "chunk_count": 25,
                        "character_count": 50000,
                        "created_at": "2024-03-08T10:00:00Z",
                        "updated_at": "2024-03-08T10:05:00Z",
                        "processed_at": "2024-03-08T10:05:00Z"
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20,
                "pages": 1
            }
        }
    )


class DocumentIngestionStatus(BaseModel):
    """Document ingestion status details."""
    document_id: UUID = Field(..., description="Document ID")
    status: DocumentStatus = Field(..., description="Current status")
    message: Optional[str] = Field(None, description="Status message")
    progress: Optional[float] = Field(None, description="Processing progress (0.0-1.0)")
    chunks_created: int = Field(default=0, description="Number of chunks created")
    pages_processed: Optional[int] = Field(None, description="Pages processed so far")
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Processing completion time")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "770e8400-e29b-41d4-a716-446655440000",
                "status": "processing",
                "message": "Document is being processed",
                "progress": 0.45,
                "chunks_created": 12,
                "pages_processed": 8,
                "started_at": "2024-03-08T10:01:00Z",
                "completed_at": None
            }
        }
    )


class BulkUploadResponse(BaseModel):
    """Response for bulk upload."""
    successfully_uploaded: int = Field(..., description="Number of successfully uploaded documents")
    failed_uploads: int = Field(..., description="Number of failed uploads")
    documents: List[BulkUploadItem] = Field(..., description="Details of each upload attempt")
    total_uploaded: int = Field(..., description="Total number of uploaded documents")
    total_failed: int = Field(..., description="Total number of failed documents")

    class Config:
        json_schema_extra = {
            "example": {
                "successfully_uploaded": 2,
                "failed_uploads": 1,
                "documents": [
                    {
                        "document_id": "770e8400-e29b-41d4-a716-446655440001",
                        "filename": "report1.pdf",
                        "status": "success"
                    },
                    {
                        "document_id": "770e8400-e29b-41d4-a716-446655440002",
                        "filename": "report2.pdf",
                        "status": "success"
                    },
                    {
                        "filename": "broken.xlsx",
                        "status": "failed",
                        "error": "File type is not supported"
                    }
                ],
                "total_uploaded": 2,
                "total_failed": 1
            }
        }


class ReingestionRequest(BaseModel):
    """Request to re-ingest a document."""
    chunk_size: Optional[int] = Field(
        None,
        ge=100,
        le=4000,
        description="Optional chunk size override for re-ingestion"
    )
    chunk_overlap: Optional[int] = Field(
        None,
        ge=0,
        le=1000,
        description="Optional chunk overlap override for re-ingestion"
    )
    force: bool = Field(default=False, description="Force re-ingestion even if completed")

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_size": 1200,
                "chunk_overlap": 200,
                "force": False
            }
        }
