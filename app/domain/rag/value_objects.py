"""RAG domain value objects - immutable configuration and data objects."""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum

from app.domain.common.value_object import ValueObject


@dataclass(frozen=True)
class EmbeddingVector(ValueObject):
    """Represents a document embedding vector."""
    values: List[float]
    model: str
    dimension: int
    
    def __post_init__(self):
        if len(self.values) != self.dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.dimension}, "
                f"got {len(self.values)}"
            )


@dataclass(frozen=True)
class ChunkMetadata(ValueObject):
    """Metadata for a document chunk."""
    source_file: str
    char_start: int
    char_end: int
    chunk_index: int
    page: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "source_file": self.source_file,
            "page": self.page,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "chunk_index": self.chunk_index
        }


@dataclass(frozen=True)
class RetrieverConfig(ValueObject):
    """Configuration for document retrieval."""
    top_k: int = 5
    score_threshold: float = 0.0
    fetch_k: int = 20  # For MMR
    lambda_mult: float = 0.5  # MMR diversity parameter
    
    def __post_init__(self):
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")
        if not 0 <= self.score_threshold <= 1:
            raise ValueError("score_threshold must be between 0 and 1")


@dataclass(frozen=True)
class QueryConfig(ValueObject):
    """Configuration for query execution."""
    temperature: float = 0.0
    max_tokens: int = 512
    include_sources: bool = True
    stream: bool = False
    
    def __post_init__(self):
        if not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")


@dataclass(frozen=True)
class ChunkerConfig(ValueObject):
    """Configuration for text chunking."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separator: str = "\n\n"
    min_chunk_size: int = 50
    
    def __post_init__(self):
        if self.chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
