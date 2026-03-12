"""Query-related Pydantic schemas."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class RetrievalStrategy(str, Enum):
    """Available retrieval strategies for searching documents."""
    SIMILARITY = "similarity"
    MMR = "mmr"  # Maximal Marginal Relevance - diversifies results
    HYBRID = "hybrid"  # Combines similarity and keyword search


class Citation(BaseModel):
    """Represents a citation to a source document chunk with character-level precision."""
    
    chunk_id: str = Field(
        ...,
        description="Unique identifier for the chunk"
    )
    document_id: Optional[str] = Field(
        None,
        description="Parent document ID"
    )
    source_file: str = Field(
        default="unknown",
        description="Source filename"
    )
    page: Optional[int] = Field(
        None,
        description="Page number (for paginated documents like PDFs)"
    )
    char_start: Optional[int] = Field(
        None,
        description="Character position where citation starts in source document"
    )
    char_end: Optional[int] = Field(
        None,
        description="Character position where citation ends in source document"
    )
    text_snippet: Optional[str] = Field(
        None,
        description="Preview text from the cited chunk"
    )
    relevance_score: Optional[float] = Field(
        None,
        description="Relevance score from retrieval (0.0 to 1.0)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chunk_id": "abc123",
                "document_id": "770e8400-e29b-41d4-a716-446655440000",
                "source_file": "report.pdf",
                "page": 5,
                "char_start": 1245,
                "char_end": 1450,
                "text_snippet": "The quarterly results show a 45% increase in user engagement...",
                "relevance_score": 0.92
            }
        }
    )


class QueryRequest(BaseModel):
    """Request schema for RAG-based document queries."""
    
    project_id: str = Field(
        ...,
        description="Project ID to query (UUID)"
    )
    question: str = Field(
        ..., 
        min_length=1, 
        max_length=2000,
        description="The question to ask about the documents"
    )
    document_ids: Optional[List[str]] = Field(
        None,
        description="Optional: Limit query to specific documents (list of UUIDs)"
    )
    include_all_sources: bool = Field(
        default=False,
        description="Include all retrieved sources or only cited ones"
    )
    retrieval_strategy: RetrievalStrategy = Field(
        default=RetrievalStrategy.SIMILARITY,
        description="Strategy for retrieving relevant chunks: similarity, mmr, or hybrid"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of chunks to retrieve for context (1-20)"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional: Associate query with chat session for conversation history"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "660e8400-e29b-41d4-a716-446655440000",
                "question": "What are the key findings from the Q4 report?",
                "document_ids": None,
                "include_all_sources": False,
                "retrieval_strategy": "similarity",
                "top_k": 5,
                "session_id": None
            }
        }


class QueryResponse(BaseModel):
    """Response schema for RAG queries with citations."""
    
    query_id: Optional[str] = Field(
        None,
        description="Unique identifier for this query"
    )
    answer: str = Field(
        ...,
        description="The generated answer to the question, with embedded citation markers"
    )
    citations: List[Citation] = Field(
        default_factory=list,
        description="Source citations supporting the answer with character-level precision"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Performance and processing metadata"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query_id": "880e8400-e29b-41d4-a716-446655440000",
                "answer": "The main findings indicate that user engagement increased by 45% [doc456#abc123] after implementing the new feature. Revenue growth was attributed to improved retention [doc456#def789].",
                "citations": [
                    {
                        "chunk_id": "abc123",
                        "document_id": "770e8400-e29b-41d4-a716-446655440000",
                        "source_file": "report.pdf",
                        "page": 3,
                        "char_start": 1250,
                        "char_end": 1290,
                        "text_snippet": "user engagement increased by 45%",
                        "relevance_score": 0.92
                    }
                ],
                "metadata": {
                    "retrieval_time_ms": 245,
                    "generation_time_ms": 1230,
                    "chunks_retrieved": 5,
                    "chunks_used": 1,
                    "retrieval_strategy": "similarity"
                }
            }
        }
    )


class SimilarChunksRequest(BaseModel):
    """Request to find similar chunks without generating an answer."""
    
    project_id: str = Field(
        ...,
        description="Project ID (UUID)"
    )
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Query text to find similar chunks for"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of similar chunks to return"
    )
    document_ids: Optional[List[str]] = Field(
        None,
        description="Optional: Limit search to specific documents"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "660e8400-e29b-41d4-a716-446655440000",
                "query": "user engagement metrics",
                "top_k": 10,
                "document_ids": None
            }
        }


class SimilarChunksResponse(BaseModel):
    """Response with similar chunks."""
    
    query: str = Field(..., description="The query that was searched")
    chunks: List[Citation] = Field(..., description="Similar chunks ranked by relevance")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "user engagement metrics",
                "chunks": [
                    {
                        "chunk_id": "abc123",
                        "document_id": "770e8400-e29b-41d4-a716-446655440000",
                        "source_file": "report.pdf",
                        "page": 3,
                        "char_start": 1250,
                        "char_end": 1450,
                        "text_snippet": "User engagement increased by 45% compared to previous quarter...",
                        "relevance_score": 0.96
                    }
                ]
            }
        }
