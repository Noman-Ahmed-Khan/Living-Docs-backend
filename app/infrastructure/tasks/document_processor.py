"""Background task for document processing."""

import logging
from uuid import UUID

from app.container import get_container
from app.infrastructure.database.session import SessionLocal

logger = logging.getLogger(__name__)


async def process_document_task(
    document_id: UUID,
    project_id: UUID
) -> None:
    """
    Background task to process a document.
    
    This task is called asynchronously after a document is uploaded.
    It handles:
    1. Chunking the document
    2. Generating embeddings
    3. Storing vectors in the vector database
    
    Args:
        document_id: Document to process
        project_id: Project namespace
    """
    logger.info(f"Starting background processing for document {document_id} in project {project_id}")
    
    # Create new DB session for background task
    db = SessionLocal()
    
    try:
        # Get container and service
        container = get_container()
        ingestion_service = container.ingestion_service(db)
        
        # Execute ingestion pipeline
        result = await ingestion_service.ingest_document(
            document_id=document_id,
            project_id=project_id
        )
        
        if result.success:
            logger.info(
                f"Document {document_id} processed successfully: "
                f"{result.chunk_count} chunks created"
            )
        else:
            logger.error(
                f"Document {document_id} processing failed: {result.message}"
            )
    
    except Exception as e:
        logger.error(
            f"Unexpected error processing document {document_id}: {e}",
            exc_info=True
        )
    
    finally:
        db.close()
