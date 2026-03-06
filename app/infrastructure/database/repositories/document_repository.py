"""SQLAlchemy implementation of document repository."""

from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.domain.documents.entities import Document, DocumentStatus
from app.domain.documents.interfaces import IDocumentRepository
from app.infrastructure.database.models.document import DocumentModel, DocumentStatus as DocumentStatusEnum


class SQLDocumentRepository(IDocumentRepository):
    """Document repository using SQLAlchemy."""

    def __init__(self, session: Session):
        self._session = session

    async def save(self, document: Document) -> Document:
        """Save a document entity."""
        # Check if exists
        db_doc = self._session.query(DocumentModel).filter(
            DocumentModel.id == document.id
        ).first()

        if db_doc:
            # Update existing
            self._update_model_from_entity(db_doc, document)
        else:
            # Create new
            db_doc = self._entity_to_model(document)
            self._session.add(db_doc)

        self._session.commit()
        self._session.refresh(db_doc)

        return self._model_to_entity(db_doc)

    async def get_by_id(self, document_id: UUID) -> Optional[Document]:
        """Get document by ID."""
        db_doc = self._session.query(DocumentModel).filter(
            DocumentModel.id == document_id
        ).first()

        return self._model_to_entity(db_doc) if db_doc else None

    async def get_by_id_and_project(
        self,
        document_id: UUID,
        project_id: UUID
    ) -> Optional[Document]:
        """Get document by ID and project."""
        db_doc = self._session.query(DocumentModel).filter(
            and_(
                DocumentModel.id == document_id,
                DocumentModel.project_id == project_id
            )
        ).first()

        return self._model_to_entity(db_doc) if db_doc else None

    async def list_by_project(
        self,
        project_id: UUID,
        status: Optional[DocumentStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Document], int]:
        """List documents with pagination."""
        query = self._session.query(DocumentModel).filter(
            DocumentModel.project_id == project_id
        )

        if status:
            query = query.filter(DocumentModel.status == status.value)

        total = query.count()

        db_docs = query.order_by(
            DocumentModel.created_at.desc()
        ).offset(skip).limit(limit).all()

        documents = [self._model_to_entity(db_doc) for db_doc in db_docs]

        return documents, total

    async def delete(self, document_id: UUID) -> None:
        """Delete a document."""
        self._session.query(DocumentModel).filter(
            DocumentModel.id == document_id
        ).delete()
        self._session.commit()

    async def get_pending_documents(self, limit: int = 10) -> List[Document]:
        """Get pending documents for processing."""
        db_docs = self._session.query(DocumentModel).filter(
            DocumentModel.status == DocumentStatusEnum.PENDING.value
        ).order_by(DocumentModel.created_at.asc()).limit(limit).all()

        return [self._model_to_entity(db_doc) for db_doc in db_docs]

    # Conversion methods

    @staticmethod
    def _entity_to_model(entity: Document) -> DocumentModel:
        """Convert domain entity to ORM model."""
        return DocumentModel(
            id=entity.id,
            filename=entity.filename,
            original_filename=entity.original_filename,
            project_id=entity.project_id,
            file_path=entity.file_path,
            file_size=entity.file_size,
            file_type=entity.file_type,
            content_type=entity.content_type,
            status=entity.status.value,
            status_message=entity.status_message,
            chunk_count=entity.chunk_count,
            page_count=entity.page_count,
            character_count=entity.character_count,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            processed_at=entity.processed_at
        )

    @staticmethod
    def _model_to_entity(model: DocumentModel) -> Document:
        """Convert ORM model to domain entity."""
        return Document(
            id=model.id,
            filename=model.filename,
            original_filename=model.original_filename,
            project_id=model.project_id,
            file_path=model.file_path,
            file_size=model.file_size,
            file_type=model.file_type,
            content_type=model.content_type,
            status=DocumentStatus(model.status),
            status_message=model.status_message,
            chunk_count=model.chunk_count,
            page_count=model.page_count,
            character_count=model.character_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
            processed_at=model.processed_at
        )

    @staticmethod
    def _update_model_from_entity(model: DocumentModel, entity: Document) -> None:
        """Update ORM model fields from entity."""
        model.status = entity.status.value
        model.status_message = entity.status_message
        model.chunk_count = entity.chunk_count
        model.page_count = entity.page_count
        model.character_count = entity.character_count
        model.processed_at = entity.processed_at
        model.updated_at = entity.updated_at
