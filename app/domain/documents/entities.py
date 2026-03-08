"""Document domain entities."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
from typing import Optional

from app.domain.common.entity import Entity


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Document(Entity):
    """
    Document entity representing an uploaded file.

    Invariants:
    - filename must be unique within project
    - status transitions: PENDING → PROCESSING → COMPLETED/FAILED
    - chunk_count >= 0
    """

    filename: str = ""
    original_filename: str = ""
    project_id: UUID = field(default_factory=uuid4)
    file_path: str = ""
    status: DocumentStatus = DocumentStatus.PENDING
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    content_type: Optional[str] = None
    chunk_count: int = 0
    page_count: Optional[int] = None
    character_count: Optional[int] = None
    status_message: Optional[str] = None
    processed_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        filename: str,
        original_filename: str,
        project_id: UUID,
        file_path: str,
        file_size: int,
        file_type: str,
        content_type: str
    ) -> "Document":
        """Factory method to create a new document."""
        return cls(
            id=uuid4(),
            created_at=datetime.utcnow(),
            filename=filename,
            original_filename=original_filename,
            project_id=project_id,
            file_path=file_path,
            status=DocumentStatus.PENDING,
            file_size=file_size,
            file_type=file_type,
            content_type=content_type,
            chunk_count=0
        )

    def start_processing(self) -> None:
        """Mark document as processing."""
        if self.status != DocumentStatus.PENDING:
            raise ValueError(f"Cannot start processing document in {self.status} state")
        self.status = DocumentStatus.PROCESSING

    def mark_completed(
        self,
        chunk_count: int,
        page_count: Optional[int] = None,
        character_count: Optional[int] = None
    ) -> None:
        """Mark document as successfully processed."""
        if self.status != DocumentStatus.PROCESSING:
            raise ValueError(f"Cannot complete document in {self.status} state")

        self.status = DocumentStatus.COMPLETED
        self.chunk_count = chunk_count
        self.page_count = page_count
        self.character_count = character_count
        self.processed_at = datetime.utcnow()
        self.status_message = "Document processed successfully"

    def mark_failed(self, error_message: str) -> None:
        """Mark document as failed."""
        self.status = DocumentStatus.FAILED
        self.status_message = error_message

    def reset_for_reingestion(self) -> None:
        """Reset document status to allow re-processing."""
        self.status = DocumentStatus.PENDING
        self.status_message = None
        self.chunk_count = 0
        self.processed_at = None

    @property
    def is_processable(self) -> bool:
        """Check if document can be processed."""
        return self.status == DocumentStatus.PENDING


@dataclass
class Chunk(Entity):
    """
    Chunk entity representing a portion of a document.

    Used for RAG retrieval.
    """

    text: str = ""
    document_id: UUID = field(default_factory=uuid4)
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        text: str,
        document_id: UUID,
        chunk_index: int,
        **metadata
    ) -> "Chunk":
        """Create a chunk with metadata."""
        return cls(
            id=uuid4(),
            created_at=datetime.utcnow(),
            text=text,
            document_id=document_id,
            chunk_index=chunk_index,
            metadata=metadata
        )
