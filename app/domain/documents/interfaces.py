"""Document domain interfaces (ports)."""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from uuid import UUID

from .entities import Document, DocumentStatus


class IDocumentRepository(ABC):
    """Repository interface for document persistence."""

    @abstractmethod
    async def save(self, document: Document) -> Document:
        """
        Save a document (create or update).

        Args:
            document: The document entity

        Returns:
            The saved document with updated fields
        """
        pass

    @abstractmethod
    async def get_by_id(self, document_id: UUID) -> Optional[Document]:
        """Get a document by ID."""
        pass

    @abstractmethod
    async def get_by_id_and_project(
        self,
        document_id: UUID,
        project_id: UUID
    ) -> Optional[Document]:
        """Get a document by ID ensuring it belongs to project."""
        pass

    @abstractmethod
    async def list_by_project(
        self,
        project_id: UUID,
        status: Optional[DocumentStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Document], int]:
        """
        List documents in a project with pagination.

        Returns:
            Tuple of (documents, total_count)
        """
        pass

    @abstractmethod
    async def delete(self, document_id: UUID) -> None:
        """Delete a document."""
        pass

    @abstractmethod
    async def get_pending_documents(self, limit: int = 10) -> List[Document]:
        """Get pending documents for background processing."""
        pass


class IFileStorage(ABC):
    """Interface for file storage operations."""

    @abstractmethod
    async def save(
        self,
        file_data: bytes,
        filename: str,
        project_id: UUID
    ) -> str:
        """
        Save a file to storage.

        Args:
            file_data: Raw file bytes
            filename: Original filename
            project_id: Project ID for organization

        Returns:
            The storage path/key
        """
        pass

    @abstractmethod
    async def read(self, file_path: str) -> bytes:
        """Read file contents from storage."""
        pass

    @abstractmethod
    async def delete(self, file_path: str) -> None:
        """Delete a file from storage."""
        pass

    @abstractmethod
    async def exists(self, file_path: str) -> bool:
        """Check if file exists in storage."""
        pass
