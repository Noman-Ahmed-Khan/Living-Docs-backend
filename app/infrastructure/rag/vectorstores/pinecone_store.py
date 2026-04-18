"""Pinecone vector store implementation with parent-child and bbox support."""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from pinecone import Pinecone
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain.rag.interfaces import IVectorStore
from app.domain.rag.exceptions import VectorStoreError
from app.domain.documents.entities import Chunk
from app.domain.rag.entities import RetrievedChunk
from app.domain.rag.value_objects import EmbeddingVector, ChunkMetadata, BoundingBox
from app.config.settings import settings

logger = logging.getLogger(__name__)


class PineconeVectorStore(IVectorStore):
    """Vector store using Pinecone with retry logic and error handling.

    Supports parent-child chunk hierarchy and bounding box metadata.
    """

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
            try:
                stats = self._index.describe_index_stats()
                namespaces = list(stats.namespaces.keys()) if stats.namespaces else []
                total_vectors = stats.total_vector_count if hasattr(stats, 'total_vector_count') else 0

                logger.info(
                    f"Connected to Pinecone index: {self._index_name} "
                    f"(total_vectors: {total_vectors}, namespaces: {namespaces})"
                )
            except AttributeError:
                logger.info(f"Connected to Pinecone index: {self._index_name}")

        except Exception as e:
            logger.error(f"Failed to connect to Pinecone: {e}", exc_info=True)
            raise VectorStoreError(
                f"Failed to initialize Pinecone: {str(e)}",
                details={"index_name": self._index_name, "error": str(e)}
            )

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _drop_none_values(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Remove metadata entries that Pinecone cannot store."""
        return {key: value for key, value in metadata.items() if value is not None}

    @staticmethod
    def _chunk_to_metadata(chunk: Chunk) -> Dict[str, Any]:
        """Build Pinecone metadata dict from a Chunk entity.

        Reads from chunk.metadata dict (populated by the chunker)
        and falls back gracefully for legacy chunks.
        """
        meta = chunk.metadata if isinstance(chunk.metadata, dict) else {}
        result = {
            "text": chunk.text,
            "document_id": str(chunk.document_id),
            "chunk_id": str(chunk.id),
            "chunk_index": chunk.chunk_index,
            "source_file": meta.get("source_file", "unknown"),
            "char_start": meta.get("char_start", 0),
            "char_end": meta.get("char_end", 0),
            "page": meta.get("page"),
            # Parent-child hierarchy
            "parent_id": meta.get("parent_id"),
            "chunk_type": meta.get("chunk_type", "child"),
            # Bounding box (flat keys for Pinecone)
            "bbox_x0": meta.get("bbox_x0"),
            "bbox_y0": meta.get("bbox_y0"),
            "bbox_x1": meta.get("bbox_x1"),
            "bbox_y1": meta.get("bbox_y1"),
        }
        return PineconeVectorStore._drop_none_values(result)

    @staticmethod
    def _metadata_to_chunk_metadata(metadata: Dict[str, Any]) -> ChunkMetadata:
        """Reconstruct ChunkMetadata value object from stored Pinecone metadata."""
        bbox = BoundingBox.from_dict(metadata)
        return ChunkMetadata(
            source_file=metadata.get('source_file', 'unknown'),
            page=metadata.get('page'),
            char_start=metadata.get('char_start', 0),
            char_end=metadata.get('char_end', 0),
            chunk_index=metadata.get('chunk_index', 0),
            bbox=bbox,
            parent_id=metadata.get('parent_id'),
            chunk_type=metadata.get('chunk_type', 'child'),
        )

    @staticmethod
    def _metadata_to_retrieved_chunk(
        match_id: str,
        metadata: Dict[str, Any],
        score: float = 0.0,
    ) -> RetrievedChunk:
        """Build a RetrievedChunk from Pinecone match data."""
        chunk_metadata = PineconeVectorStore._metadata_to_chunk_metadata(metadata)
        bbox = BoundingBox.from_dict(metadata)

        return RetrievedChunk(
            chunk_id=str(match_id),
            text=metadata.get('text', ''),
            document_id=UUID(metadata.get('document_id')),
            metadata=chunk_metadata,
            score=score,
            parent_id=metadata.get('parent_id'),
            chunk_type=metadata.get('chunk_type', 'child'),
            bbox=bbox,
        )

    # ------------------------------------------------------------------
    # IVectorStore implementation
    # ------------------------------------------------------------------

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
                    "metadata": self._chunk_to_metadata(chunk),
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
        """Search for similar chunks in Pinecone.

        By default only searches child chunks (chunk_type == 'child')
        unless the filter explicitly overrides chunk_type.
        """
        try:
            # Ensure we only search child chunks for semantic retrieval
            effective_filter = dict(filter_dict) if filter_dict else {}
            if "chunk_type" not in effective_filter:
                effective_filter["chunk_type"] = "child"

            results = self._index.query(
                vector=query_embedding.values,
                top_k=top_k,
                namespace=namespace,
                filter=effective_filter if effective_filter else None,
                include_metadata=True
            )

            chunks = []
            for match in results.matches:
                metadata = match.metadata or {}
                chunk = self._metadata_to_retrieved_chunk(
                    match_id=match.id,
                    metadata=metadata,
                    score=match.score,
                )
                chunks.append(chunk)

            logger.info(
                f"Retrieved {len(chunks)} chunks from Pinecone "
                f"(namespace={namespace}, top_k={top_k}, "
                f"filters={effective_filter})"
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
    async def fetch_by_ids(
        self,
        ids: List[str],
        namespace: str
    ) -> List[RetrievedChunk]:
        """Fetch specific chunks by their vector IDs.

        Used to resolve parent chunks for context reconstruction
        after child-chunk retrieval.
        """
        if not ids:
            return []

        try:
            result = self._index.fetch(ids=ids, namespace=namespace)
            chunks = []
            for vec_id, vec_data in (result.vectors or {}).items():
                metadata = vec_data.metadata or {} if hasattr(vec_data, 'metadata') else {}
                chunk = self._metadata_to_retrieved_chunk(
                    match_id=vec_id,
                    metadata=metadata,
                    score=1.0,  # Fetched by ID, not similarity
                )
                chunks.append(chunk)

            logger.info(
                f"Fetched {len(chunks)}/{len(ids)} chunks by ID "
                f"(namespace={namespace})"
            )
            return chunks

        except Exception as e:
            logger.error(f"Pinecone fetch_by_ids failed: {e}", exc_info=True)
            raise VectorStoreError(
                f"Failed to fetch chunks by ID: {str(e)}",
                details={"ids_count": len(ids), "namespace": namespace, "error": str(e)}
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
