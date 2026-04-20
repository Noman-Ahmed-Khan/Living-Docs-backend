"""Document application service."""

import logging
from uuid import UUID, uuid4
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import UploadFile

from app.domain.documents.entities import Document, DocumentStatus
from app.domain.documents.interfaces import IDocumentRepository, IFileStorage
from app.domain.documents.rules import DocumentRules
from app.domain.documents.exceptions import DocumentNotFoundError
from .dto import DocumentUploadDTO, DocumentDetailDTO

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document operations."""

    def __init__(
        self,
        document_repo: IDocumentRepository,
        file_storage: IFileStorage
    ):
        self._document_repo = document_repo
        self._file_storage = file_storage

    async def upload_document(
        self,
        file: UploadFile,
        project_id: UUID,
        user_id: UUID
    ) -> DocumentUploadDTO:
        """
        Upload a document file.

        Args:
            file: The uploaded file
            project_id: Target project
            user_id: User uploading the file

        Returns:
            DocumentUploadDTO with upload result
        """
        # Validate file type
        file_ext = DocumentRules.validate_file_type(file.filename)

        # Read file
        file_data = await file.read()
        file_size = len(file_data)

        # Validate file size
        DocumentRules.validate_file_size(file_size)

        # Generate unique filename
        unique_filename = f"{uuid4()}{file_ext}"

        # Save file to storage
        file_path = await self._file_storage.save(
            file_data=file_data,
            filename=unique_filename,
            project_id=project_id
        )

        # Create document entity
        document = Document.create(
            filename=unique_filename,
            original_filename=file.filename,
            project_id=project_id,
            file_path=file_path,
            file_size=file_size,
            file_type=file_ext,
            content_type=file.content_type or 'application/octet-stream'
        )

        # Save to repository
        document = await self._document_repo.save(document)

        logger.info(f"Document uploaded: {document.id}")

        return DocumentUploadDTO(
            document_id=document.id,
            filename=document.original_filename,
            file_size=document.file_size,
            status=document.status.value,
            message="Document uploaded successfully"
        )

    async def get_document(
        self,
        document_id: UUID,
        project_id: UUID
    ) -> DocumentDetailDTO:
        """Get document details."""
        document = await self._document_repo.get_by_id_and_project(
            document_id=document_id,
            project_id=project_id
        )

        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        return self._to_detail_dto(document)

    async def get_document_by_id(
        self,
        document_id: UUID
    ) -> DocumentDetailDTO:
        """Get document details without project scoping."""
        document = await self._document_repo.get_by_id(document_id)

        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        return self._to_detail_dto(document)

    async def list_documents(
        self,
        project_id: UUID,
        status: Optional[DocumentStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[DocumentDetailDTO], int]:
        """List documents with pagination."""
        skip = (page - 1) * page_size

        documents, total = await self._document_repo.list_by_project(
            project_id=project_id,
            status=status,
            skip=skip,
            limit=page_size
        )

        dto_list = [
            self._to_detail_dto(doc)
            for doc in documents
        ]

        return dto_list, total

    async def delete_document(
        self,
        document_id: UUID,
        project_id: UUID
    ) -> None:
        """Delete a document and its file."""
        document = await self._document_repo.get_by_id_and_project(
            document_id=document_id,
            project_id=project_id
        )

        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        # Delete file from storage
        await self._file_storage.delete(document.file_path)

        # Delete from repository
        await self._document_repo.delete(document_id)

        logger.info(f"Document deleted: {document_id}")

    async def reset_document_for_reingestion(
        self,
        document_id: UUID,
        project_id: UUID
    ) -> DocumentDetailDTO:
        """Reset a document for re-ingestion."""
        document = await self._document_repo.get_by_id_and_project(
            document_id=document_id,
            project_id=project_id
        )

        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        document.reset_for_reingestion()
        saved = await self._document_repo.save(document)

        return self._to_detail_dto(saved)

    @staticmethod
    def _to_detail_dto(document: Document) -> DocumentDetailDTO:
        """Map a domain document into the detailed API DTO."""
        return DocumentDetailDTO(
            id=document.id,
            filename=document.filename,
            original_filename=document.original_filename,
            project_id=document.project_id,
            status=document.status.value,
            file_size=document.file_size,
            chunk_count=document.chunk_count,
            page_count=document.page_count,
            created_at=document.created_at,
            updated_at=document.updated_at,
            processed_at=document.processed_at,
            content_type=document.content_type,
            file_path=document.file_path
        )
