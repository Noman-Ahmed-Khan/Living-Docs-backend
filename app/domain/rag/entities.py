"""RAG domain entities."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from app.domain.common.entity import Entity
from .value_objects import ChunkMetadata, EmbeddingVector, BoundingBox


@dataclass
class QueryRequest(Entity):
    """Represents a user query request."""
    
    # All fields must have defaults because Entity has defaults
    question: str = ""
    project_id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    document_ids: Optional[List[UUID]] = None
    session_id: Optional[UUID] = None
    
    def __post_init__(self):
        super().__post_init__() if hasattr(super(), '__post_init__') else None
        if not self.question or len(self.question.strip()) == 0:
            raise ValueError("Question cannot be empty")
        if len(self.question) > 2000:
            raise ValueError("Question too long (max 2000 characters)")


@dataclass
class Citation:
    """Citation linking answer to source chunk."""
    
    # This doesn't inherit from Entity, so required fields are OK
    chunk_id: str
    document_id: UUID
    source_file: str
    text_snippet: str
    page: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    relevance_score: Optional[float] = None
    bbox: Optional[Dict[str, float]] = None  # {x0, y0, x1, y1} for API
    parent_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": str(self.document_id),
            "source_file": self.source_file,
            "text_snippet": self.text_snippet,
            "page": self.page,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "relevance_score": self.relevance_score,
            "bbox": self.bbox,
            "parent_id": self.parent_id,
        }


@dataclass
class QueryResult(Entity):
    """Result of a RAG query."""
    
    # All fields must have defaults because Entity has defaults
    query_id: UUID = field(default_factory=uuid4)
    question: str = ""
    answer: str = ""
    citations: List[Citation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_citations(self) -> bool:
        """Check if result has citations."""
        return len(self.citations) > 0
    
    def add_citation(self, citation: Citation) -> None:
        """Add a citation to the result."""
        self.citations.append(citation)


@dataclass
class RetrievedChunk:
    """A chunk retrieved from vector store.
    
    Extended to support parent-child hierarchy and bounding box coordinates.
    """
    
    # This doesn't inherit from Entity, so required fields are OK
    chunk_id: str
    text: str
    document_id: UUID
    metadata: ChunkMetadata
    score: float
    embedding: Optional[EmbeddingVector] = None
    # Parent-child hierarchy fields
    parent_id: Optional[str] = None
    chunk_type: str = "child"
    bbox: Optional[BoundingBox] = None
    parent_bbox: Optional[BoundingBox] = None
    parent_text: Optional[str] = None  # Resolved parent context
    
    def to_context_string(self) -> str:
        """Format chunk for LLM context.
        
        If parent_text is available, use it for richer context.
        Otherwise fall back to the child chunk text.
        """
        context_text = self.parent_text if self.parent_text else self.text
        header = f"[{self.chunk_id}]"
        if self.metadata.source_file:
            header += f" (Source: {self.metadata.source_file}"
            if self.metadata.page:
                header += f", Page: {self.metadata.page}"
            header += ")"
        return f"{header}\n{context_text}"


@dataclass
class ParentChunk:
    """A parent chunk representing a paragraph or section.
    
    Used during ingestion to group child chunks and provide
    LLM context during retrieval.
    """
    id: str
    text: str
    document_id: UUID
    page: Optional[int] = None
    bbox: Optional[BoundingBox] = None
    chunk_index: int = 0
    source_file: str = ""


@dataclass
class ChildChunk:
    """A child chunk representing a single sentence.
    
    Used for embedding and similarity search. Links back to
    its parent for context resolution.
    """
    id: str
    text: str
    document_id: UUID
    parent_id: str
    page: Optional[int] = None
    bbox: Optional[BoundingBox] = None
    chunk_index: int = 0
    source_file: str = ""
    char_start: int = 0
    char_end: int = 0
