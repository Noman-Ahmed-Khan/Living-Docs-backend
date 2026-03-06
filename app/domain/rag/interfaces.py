"""RAG domain interfaces (ports) - contracts for infrastructure implementations."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID

from app.domain.documents.entities import Chunk
from .entities import RetrievedChunk
from .value_objects import EmbeddingVector, ChunkMetadata


class IChunker(ABC):
    """Interface for text chunking strategies."""

    @abstractmethod
    async def chunk(
        self,
        file_data: bytes,
        filename: str,
        document_id: UUID
    ) -> List[Chunk]:
        """
        Split a document into chunks.

        Args:
            file_data: Raw file bytes
            filename: Original filename (for format detection)
            document_id: Document identifier

        Returns:
            List of Chunk entities with metadata
        """
        pass


class IEmbedder(ABC):
    """Interface for text embedding generation."""

    @abstractmethod
    async def embed_text(self, text: str) -> EmbeddingVector:
        """
        Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            EmbeddingVector with values and metadata
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[EmbeddingVector]:
        """
        Generate embeddings for multiple texts (batched for efficiency).

        Args:
            texts: List of input texts

        Returns:
            List of EmbeddingVectors in same order
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding dimension."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the embedding model."""
        pass


class IVectorStore(ABC):
    """Interface for vector database operations."""

    @abstractmethod
    async def add_chunks(
        self,
        chunks: List[Chunk],
        embeddings: List[EmbeddingVector],
        namespace: str
    ) -> None:
        """
        Store chunks with embeddings in vector database.

        Args:
            chunks: Document chunks
            embeddings: Corresponding embeddings
            namespace: Project namespace for isolation
        """
        pass

    @abstractmethod
    async def delete_by_document(
        self,
        document_id: UUID,
        namespace: str
    ) -> None:
        """
        Delete all chunks for a document.

        Args:
            document_id: Document identifier
            namespace: Project namespace
        """
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: EmbeddingVector,
        namespace: str,
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        """
        Search for similar chunks.

        Args:
            query_embedding: Query vector
            namespace: Project namespace
            top_k: Number of results
            filter_dict: Metadata filters (e.g., {"document_id": "..."})

        Returns:
            List of retrieved chunks with relevance scores
        """
        pass

    @abstractmethod
    async def delete_namespace(self, namespace: str) -> None:
        """
        Delete all vectors in a namespace (project deletion).

        Args:
            namespace: Project namespace
        """
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get vector store statistics for health monitoring.
        """
        pass


class IRetriever(ABC):
    """Interface for document retrieval with various strategies."""

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        namespace: str,
        top_k: int = 5,
        document_ids: Optional[List[UUID]] = None
    ) -> List[RetrievedChunk]:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: User question
            namespace: Project namespace
            top_k: Number of chunks to retrieve
            document_ids: Optional filter for specific documents

        Returns:
            List of retrieved chunks with relevance scores
        """
        pass


class ILLMClient(ABC):
    """Interface for Language Model interaction."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        stream: bool = False
    ) -> str:
        """
        Generate text completion.

        Args:
            prompt: Input prompt with context and instructions
            temperature: Sampling temperature (0 = deterministic)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream response

        Returns:
            Generated text response
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the LLM model."""
        pass
