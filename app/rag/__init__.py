"""RAG Pipeline Package for Living Docs Backend."""

from .config import (
    RAGConfig,
    ChunkerConfig,
    RetrieverConfig,
    QueryConfig,
    ChunkingStrategy,
    RetrievalStrategy,
)
from .exceptions import (
    RAGException,
    DocumentLoadError,
    ChunkingError,
    EmbeddingError,
    VectorStoreError,
    QueryError,
    UnsupportedFileTypeError,
)
from .normalizers import TextNormalizer, MetadataNormalizer
from .chunker import (
    BaseChunker,
    FixedSizeChunker,
    RecursiveChunker,
    SentenceChunker,
    ChunkerFactory,
    create_chunker,
)
from .embeddings import (
    EmbeddingService,
    get_embedding_service,
    get_embeddings,
)
from .loaders import DocumentLoader
from .vectorstore import (
    VectorStoreManager,
    get_vectorstore_manager,
    get_vectorstore,
)
from .retriever import (
    DocumentRetriever,
    RetrievalResult,
    create_retriever,
)
from .prompts import (
    RAG_CHAT_PROMPT,
    RAG_PROMPT,
    get_prompt,
)
from .query import (
    RAGQueryEngine,
    QueryEngineFactory,
    CitationExtractor,
    query_documents,
)


__all__ = [
    # Config
    "RAGConfig",
    "ChunkerConfig",
    "RetrieverConfig",
    "QueryConfig",
    "ChunkingStrategy",
    "RetrievalStrategy",
    # Exceptions
    "RAGException",
    "DocumentLoadError",
    "ChunkingError",
    "EmbeddingError",
    "VectorStoreError",
    "QueryError",
    "UnsupportedFileTypeError",
    # Normalizers
    "TextNormalizer",
    "MetadataNormalizer",
    # Chunking
    "BaseChunker",
    "FixedSizeChunker",
    "RecursiveChunker",
    "SentenceChunker",
    "ChunkerFactory",
    "create_chunker",
    # Embeddings
    "EmbeddingService",
    "get_embedding_service",
    "get_embeddings",
    # Document Loading
    "DocumentLoader",
    # Vector Store
    "VectorStoreManager",
    "get_vectorstore_manager",
    "get_vectorstore",
    # Retrieval
    "DocumentRetriever",
    "RetrievalResult",
    "create_retriever",
    # Prompts
    "RAG_CHAT_PROMPT",
    "RAG_PROMPT",
    "get_prompt",
    # Query
    "RAGQueryEngine",
    "QueryEngineFactory",
    "CitationExtractor",
    "query_documents",
]