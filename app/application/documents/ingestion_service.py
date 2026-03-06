"""Document ingestion service - orchestrates the RAG pipeline."""

import logging
from uuid import UUID
from typing import List, TYPE_CHECKING

from app.domain.documents.entities import Document, Chunk
from app.domain.documents.interfaces import IDocumentRepository, IFileStorage
from app.domain.documents.exceptions import DocumentNotFoundError, DocumentProcessingError
from .dto import IngestionResultDTO

if TYPE_CHECKING:
    from app.domain.rag.interfaces import IChunker, IEmbedder, IVectorStore

logger = logging.getLogger(__name__)


class IngestionService:
    """
    Orchestrates document ingestion pipeline.

    Flow: Load file → Chunk → Embed → Store in vector DB → Update status
    """

    def __init__(
        self,
        document_repo: IDocumentRepository,
        file_storage: IFileStorage,
        chunker: "IChunker",
        embedder: "IEmbedder",
        vector_store: "IVectorStore"
    ):
        self._document_repo = document_repo
        self._file_storage = file_storage
        self._chunker = chunker
        self._embedder = embedder
        self._vector_store = vector_store

    async def ingest_document(
        self,
        document_id: UUID,
        project_id: UUID
    ) -> IngestionResultDTO:
        """
        Execute full ingestion pipeline for a document.

        Args:
            document_id: Document to ingest
            project_id: Project namespace

        Returns:
            IngestionResultDTO with result
        """
        try:
            # 1. Load document entity
            document = await self._document_repo.get_by_id(document_id)
            if not document:
                raise DocumentNotFoundError(f"Document {document_id} not found")

            # Mark as processing
            document.start_processing()
            await self._document_repo.save(document)

            logger.info(f"Starting ingestion for document {document_id}")

            # 2. Read file from storage
            file_data = await self._file_storage.read(document.file_path)

            # 3. Chunk the document
            chunks = await self._chunker.chunk(
                file_data=file_data,
                filename=document.original_filename,
                document_id=document_id
            )

            logger.info(f"Created {len(chunks)} chunks for document {document_id}")

            # 4. Embed chunks
            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = await self._embedder.embed_batch(chunk_texts)

            # 5. Store in vector database
            await self._vector_store.add_chunks(
                chunks=chunks,
                embeddings=embeddings,
                namespace=str(project_id)
            )

            # 6. Mark as completed
            document.mark_completed(
                chunk_count=len(chunks),
                character_count=sum(len(c.text) for c in chunks)
            )
            await self._document_repo.save(document)

            logger.info(f"Document {document_id} ingestion completed successfully")

            return IngestionResultDTO(
                document_id=document_id,
                success=True,
                chunk_count=len(chunks),
                message="Document ingested successfully"
            )

        except DocumentNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Ingestion failed for document {document_id}: {e}", exc_info=True)

            # Mark as failed
            document = await self._document_repo.get_by_id(document_id)
            if document:
                document.mark_failed(str(e))
                await self._document_repo.save(document)

            return IngestionResultDTO(
                document_id=document_id,
                success=False,
                chunk_count=0,
                message="Ingestion failed",
                error=str(e)
            )

    async def delete_document_vectors(
        self,
        document_id: UUID,
        project_id: UUID
    ) -> None:
        """Delete vectors for a document from vector store."""
        await self._vector_store.delete_by_document(
            document_id=document_id,
            namespace=str(project_id)
        )
        logger.info(f"Deleted vectors for document {document_id}")
