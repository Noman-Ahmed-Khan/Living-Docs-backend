"""Document ingestion service."""

import logging
import os
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import crud, models
from app.rag.loaders import DocumentLoader
from app.rag.chunker import create_chunker
from app.rag.vectorstore import get_vectorstore_manager
from app.rag.config import ChunkingStrategy
from app.rag.exceptions import (
    DocumentLoadError,
    ChunkingError,
    VectorStoreError,
    UnsupportedFileTypeError,
)
from app.rag.config import ChunkerConfig


logger = logging.getLogger(__name__)


class IngestionService:
    """
    Service for handling document ingestion pipeline.
    
    Manages the complete flow: load -> chunk -> embed -> store
    """
    
    def __init__(self):
        self.loader = DocumentLoader()
        self.vectorstore_manager = get_vectorstore_manager()
    
    def ingest_document(
        self,
        db: Session,
        document_id: UUID,
        project_id: UUID,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> Tuple[bool, str, int]:
        """
        Ingest a document into the RAG system.
        
        Args:
            db: Database session
            document_id: Document ID to ingest
            project_id: Project ID (namespace)
            chunk_size: Size of chunks
            chunk_overlap: Overlap between chunks
            
        Returns:
            Tuple of (success, message, chunk_count)
        """
        # Get document
        db_document = crud.get_document_by_id(db, document_id)
        if not db_document:
            return False, "Document not found", 0
        
        file_path = db_document.file_path
        
        # Update status to processing
        crud.update_document_status(
            db, db_document,
            status=models.DocumentStatus.PROCESSING,
            message="Processing document..."
        )
        
        try:
            # 1. Load document
            logger.info(f"Loading document: {file_path}")
            raw_docs = self.loader.load(file_path)
            
            if not raw_docs:
                crud.update_document_status(
                    db, db_document,
                    status=models.DocumentStatus.FAILED,
                    message="No content extracted from document"
                )
                return False, "No content extracted from document", 0
            
            # Calculate total characters
            total_chars = sum(len(doc.page_content) for doc in raw_docs)
            page_count = len(raw_docs)
            
            # 2. Chunk documents
            logger.info(f"Chunking document with size={chunk_size}, overlap={chunk_overlap}")
            chunker = create_chunker(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                strategy=ChunkingStrategy.RECURSIVE
            )
            chunks = chunker.split_documents(raw_docs, document_id=str(document_id))
            
            if not chunks:
                crud.update_document_status(
                    db, db_document,
                    status=models.DocumentStatus.FAILED,
                    message="No chunks created from document"
                )
                return False, "No chunks created", 0
            
            chunk_count = len(chunks)
            logger.info(f"Created {chunk_count} chunks")
            
            # 3. Add source metadata
            for chunk in chunks:
                chunk.metadata["source"] = db_document.original_filename
                chunk.metadata["source_file"] = db_document.original_filename
            
            # 4. Store in vector database
            logger.info(f"Storing chunks in vector database for project: {project_id}")
            self.vectorstore_manager.add_documents(
                documents=chunks,
                namespace=str(project_id)
            )
            
            # 5. Update document status
            crud.update_document_status(
                db, db_document,
                status=models.DocumentStatus.COMPLETED,
                message="Document processed successfully",
                chunk_count=chunk_count,
                page_count=page_count,
                character_count=total_chars
            )
            
            logger.info(f"Document {document_id} ingested successfully with {chunk_count} chunks")
            return True, "Document processed successfully", chunk_count
            
        except UnsupportedFileTypeError as e:
            error_msg = f"Unsupported file type: {str(e)}"
            logger.error(error_msg)
            crud.update_document_status(
                db, db_document,
                status=models.DocumentStatus.FAILED,
                message=error_msg
            )
            return False, error_msg, 0
            
        except DocumentLoadError as e:
            error_msg = f"Failed to load document: {str(e)}"
            logger.error(error_msg)
            crud.update_document_status(
                db, db_document,
                status=models.DocumentStatus.FAILED,
                message=error_msg
            )
            return False, error_msg, 0
            
        except ChunkingError as e:
            error_msg = f"Failed to chunk document: {str(e)}"
            logger.error(error_msg)
            crud.update_document_status(
                db, db_document,
                status=models.DocumentStatus.FAILED,
                message=error_msg
            )
            return False, error_msg, 0
            
        except VectorStoreError as e:
            error_msg = f"Failed to store in vector database: {str(e)}"
            logger.error(error_msg)
            crud.update_document_status(
                db, db_document,
                status=models.DocumentStatus.FAILED,
                message=error_msg
            )
            return False, error_msg, 0
            
        except Exception as e:
            error_msg = f"Unexpected error during ingestion: {str(e)}"
            logger.exception(error_msg)
            crud.update_document_status(
                db, db_document,
                status=models.DocumentStatus.FAILED,
                message=error_msg
            )
            return False, error_msg, 0
    
    def delete_document_vectors(
        self,
        document_id: UUID,
        project_id: UUID
    ) -> bool:
        """Delete vectors for a document from the vector store."""
        try:
            self.vectorstore_manager.delete_by_document_id(
                document_id=str(document_id),
                namespace=str(project_id)
            )
            logger.info(f"Deleted vectors for document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vectors for document {document_id}: {e}")
            return False
    
    def delete_project_vectors(self, project_id: UUID) -> bool:
        """Delete all vectors for a project."""
        try:
            self.vectorstore_manager.delete_namespace(str(project_id))
            logger.info(f"Deleted all vectors for project {project_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vectors for project {project_id}: {e}")
            return False


# Singleton instance
_ingestion_service: Optional[IngestionService] = None


def get_ingestion_service() -> IngestionService:
    """Get or create ingestion service singleton."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service