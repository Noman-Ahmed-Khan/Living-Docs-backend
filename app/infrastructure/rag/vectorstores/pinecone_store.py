"""Pinecone vector store implementation with proper error handling."""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from pinecone import Pinecone
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain.rag.interfaces import IVectorStore
from app.domain.rag.exceptions import VectorStoreError
from app.domain.documents.entities import Chunk
from app.domain.rag.entities import RetrievedChunk
from app.domain.rag.value_objects import EmbeddingVector, ChunkMetadata
from app.config.settings import settings

logger = logging.getLogger(__name__)


class PineconeVectorStore(IVectorStore):
    """Vector store using Pinecone with retry logic and error handling."""
    
    UPSERT_BATCH_SIZE = 100
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None
    ):
        """
        Initialize Pinecone vector store.
        
        Args:
            api_key: Pinecone API key (default from settings)
            index_name: Pinecone index name (default from settings)
        """
        self._api_key = api_key or settings.PINECONE_API_KEY
        self._index_name = index_name or settings.PINECONE_INDEX_NAME
        
        try:
            logger.info(f"Connecting to Pinecone index: {self._index_name}")
            
            self._client = Pinecone(api_key=self._api_key)
            self._index = self._client.Index(self._index_name)
            
            # Verify connection by getting index stats
            stats = self._index.describe_index_stats()
            logger.info(
                f"Connected to Pinecone index: {self._index_name} "
                f"(namespaces: {list(stats.namespace_names)})"
            )
            
        except Exception as e:
            logger.error(f"Failed to connect to Pinecone: {e}", exc_info=True)
            raise VectorStoreError(
                f"Failed to initialize Pinecone: {str(e)}",
                details={"index_name": self._index_name, "error": str(e)}
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def add_chunks(
        self,
        chunks: List[Chunk],
        embeddings: List[EmbeddingVector],
        namespace: str
    ) -> None:
        """Store chunks with embeddings in Pinecone."""
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunks and embeddings must have same length "
                f"({len(chunks)} vs {len(embeddings)})"
            )
        
        try:
            # Prepare vectors for upsert
            vectors = []
            for chunk, embedding in zip(chunks, embeddings):
                vector_dict = {
                    "id": str(chunk.id),
                    "values": embedding.values,
                    "metadata": {
                        "text": chunk.text,
                        "document_id": str(chunk.document_id),
                        "chunk_id": str(chunk.id),
                        "chunk_index": chunk.chunk_index,
                        "source_file": chunk.source_file,
                        "char_start": chunk.char_start,
                        "char_end": chunk.char_end,
                        "page": chunk.page
                    }
                }
                vectors.append(vector_dict)
            
            # Upsert in batches
            for i in range(0, len(vectors), self.UPSERT_BATCH_SIZE):
                batch = vectors[i:i + self.UPSERT_BATCH_SIZE]
                self._index.upsert(vectors=batch, namespace=namespace)
                logger.debug(f"Upserted batch {i // self.UPSERT_BATCH_SIZE + 1}")
            
            logger.info(
                f"Stored {len(chunks)} chunks in Pinecone "
                f"(namespace={namespace}, batches={len(vectors) // self.UPSERT_BATCH_SIZE + 1})"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to store chunks in Pinecone: {e}",
                exc_info=True
            )
            raise VectorStoreError(
                f"Failed to store chunks: {str(e)}",
                details={
                    "namespace": namespace,
                    "chunk_count": len(chunks),
                    "error": str(e)
                }
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def search(
        self,
        query_embedding: EmbeddingVector,
        namespace: str,
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        """Search for similar chunks in Pinecone."""
        try:
            results = self._index.query(
                vector=query_embedding.values,
                top_k=top_k,
                namespace=namespace,
                filter=filter_dict,
                include_metadata=True
            )
            
            chunks = []
            for match in results.matches:
                metadata = match.metadata or {}
                
                # Reconstruct ChunkMetadata from stored metadata
                chunk_metadata = ChunkMetadata(
                    source_file=metadata.get('source_file', 'unknown'),
                    page=metadata.get('page'),
                    char_start=metadata.get('char_start', 0),
                    char_end=metadata.get('char_end', 0),
                    chunk_index=metadata.get('chunk_index', 0)
                )
                
                # Create RetrievedChunk entity
                chunk = RetrievedChunk(
                    chunk_id=str(match.id),
                    text=metadata.get('text', ''),
                    document_id=UUID(metadata.get('document_id')),
                    metadata=chunk_metadata,
                    score=match.score
                )
                chunks.append(chunk)
            
            logger.info(
                f"Retrieved {len(chunks)} chunks from Pinecone "
                f"(namespace={namespace}, top_k={top_k}, filters={filter_dict is not None})"
            )
            
            return chunks
            
        except Exception as e:
            logger.error(
                f"Pinecone search failed: {e}",
                exc_info=True
            )
            raise VectorStoreError(
                f"Failed to search vectors: {str(e)}",
                details={
                    "namespace": namespace,
                    "top_k": top_k,
                    "error": str(e)
                }
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def delete_by_document(
        self,
        document_id: UUID,
        namespace: str
    ) -> None:
        """Delete all chunks for a document."""
        try:
            # Delete by filter - all vectors with matching document_id
            self._index.delete(
                filter={"document_id": str(document_id)},
                namespace=namespace
            )
            
            logger.info(
                f"Deleted all chunks for document {document_id} "
                f"in namespace {namespace}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to delete document chunks: {e}",
                exc_info=True
            )
            raise VectorStoreError(
                f"Failed to delete chunks: {str(e)}",
                details={
                    "document_id": str(document_id),
                    "namespace": namespace,
                    "error": str(e)
                }
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def delete_namespace(self, namespace: str) -> None:
        """Delete all vectors in a namespace."""
        try:
            self._index.delete(delete_all=True, namespace=namespace)
            logger.info(f"Deleted all vectors in namespace: {namespace}")
            
        except Exception as e:
            logger.error(
                f"Failed to delete namespace: {e}",
                exc_info=True
            )
            raise VectorStoreError(
                f"Failed to delete namespace: {str(e)}",
                details={"namespace": namespace, "error": str(e)}
            )

    async def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        try:
            stats = self._index.describe_index_stats()
            return {
                "total_vector_count": stats.total_vector_count,
                "namespaces": list(stats.namespaces.keys()),
                "index_name": self._index_name
            }
        except Exception as e:
            logger.error(f"Failed to get Pinecone stats: {e}")
            raise VectorStoreError(f"Failed to get stats: {str(e)}")
