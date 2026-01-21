"""Query-related Pydantic schemas."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class RetrievalStrategy(str, Enum):
    """Available retrieval strategies."""
    SIMILARITY = "similarity"
    MMR = "mmr"
    HYBRID = "hybrid"


class Citation(BaseModel):
    """Represents a citation to a source document chunk."""
    
    chunk_id: str = Field(..., description="Unique identifier for the chunk")
    document_id: Optional[str] = Field(None, description="Parent document ID")
    source_file: str = Field(default="unknown", description="Source filename")
    page: Optional[int] = Field(None, description="Page number (if applicable)")
    char_start: Optional[int] = Field(None, description="Character start position")
    char_end: Optional[int] = Field(None, description="Character end position")
    text_snippet: Optional[str] = Field(None, description="Preview of the cited text")
    relevance_score: Optional[float] = Field(None, description="Relevance score")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chunk_id": "abc123",
                "document_id": "doc456",
                "source_file": "report.pdf",
                "page": 5,
                "char_start": 1000,
                "char_end": 2000,
                "text_snippet": "The quarterly results show..."
            }
        }
    )


class QueryRequest(BaseModel):
    """Request schema for document queries."""
    
    project_id: str = Field(..., description="Project ID to query")
    question: str = Field(
        ..., 
        min_length=1, 
        max_length=2000,
        description="The question to ask"
    )
    document_ids: Optional[List[str]] = Field(
        None,
        description="Filter to specific documents"
    )
    include_all_sources: bool = Field(
        default=False,
        description="Include all retrieved sources in citations"
    )
    retrieval_strategy: RetrievalStrategy = Field(
        default=RetrievalStrategy.MMR,
        description="Retrieval strategy to use"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of chunks to retrieve"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional chat session ID to associate this query with"
    )

class QueryResponse(BaseModel):
    """Response schema for document queries."""
    
    answer: str = Field(..., description="The generated answer")
    citations: List[Citation] = Field(
        default_factory=list,
        description="Citations for the answer"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional response metadata"
    )
    query_id: Optional[str] = Field(None, description="Unique query identifier")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "The key findings include... [abc123]",
                "citations": [
                    {
                        "chunk_id": "abc123",
                        "document_id": "doc456",
                        "source_file": "report.pdf",
                        "page": 5
                    }
                ],
                "metadata": {
                    "retrieval_strategy": "mmr",
                    "documents_retrieved": 5
                }
            }
        }
    )


class SimilarChunksRequest(BaseModel):
    """Request for finding similar chunks."""
    project_id: str
    text: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    document_ids: Optional[List[str]] = None


class SimilarChunksResponse(BaseModel):
    """Response with similar chunks."""
    chunks: List[Citation]
    query_text: str