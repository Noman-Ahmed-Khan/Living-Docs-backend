"""Data Transfer Objects for RAG query operations."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime


@dataclass
class CitationDTO:
    """Citation linking answer to source chunk."""
    chunk_id: str
    document_id: str
    source_file: str
    text_snippet: str
    page: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    relevance_score: Optional[float] = None


@dataclass
class QueryRequestDTO:
    """Request for RAG query."""
    question: str
    project_id: str
    user_id: str
    document_ids: Optional[List[str]] = None
    session_id: Optional[str] = None


@dataclass
class QueryResponseDTO:
    """Response for RAG query."""
    query_id: str
    question: str
    answer: str
    citations: List[CitationDTO] = field(default_factory=list)
    model: str = ""
    chunk_count: int = 0
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
