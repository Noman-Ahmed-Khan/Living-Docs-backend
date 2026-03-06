"""RAG domain exceptions."""

from app.domain.common.exceptions import DomainException


class RAGError(DomainException):
    """Base exception for RAG domain."""
    pass


class ChunkingError(RAGError):
    """Error during document chunking."""
    pass


class EmbeddingError(RAGError):
    """Error generating embeddings."""
    pass


class VectorStoreError(RAGError):
    """Error with vector database operations."""
    pass


class RetrievalError(RAGError):
    """Error during document retrieval."""
    pass


class LLMError(RAGError):
    """Error from language model."""
    pass


class QueryError(RAGError):
    """Error processing query."""
    pass


class InvalidQueryError(RAGError):
    """Query validation failed."""
    pass


class NoContextFoundError(RAGError):
    """No relevant context found for query."""
    pass
