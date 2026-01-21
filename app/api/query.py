"""Query API endpoints for RAG-based document querying."""

import logging
import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import crud, session, models
from app.schemas import query as query_schema
from app.dependencies import get_current_user
from app.rag.query import RAGQueryEngine
from app.rag.exceptions import QueryError
from app.rag.config import RetrieverConfig, RetrievalStrategy, QueryConfig
from app.db.models import ChatMessageRole
from app.schemas import chat as chat_schema

logger = logging.getLogger(__name__)
router = APIRouter()


def get_retrieval_strategy(strategy: query_schema.RetrievalStrategy) -> RetrievalStrategy:
    """Convert schema enum to RAG enum."""
    return RetrievalStrategy(strategy.value)


@router.post(
    "/",
    response_model=query_schema.QueryResponse,
    summary="Query documents"
)
async def query_documents(
    query_in: query_schema.QueryRequest,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Query documents in a project using RAG.
    
    This endpoint:
    1. Retrieves relevant document chunks based on the question
    2. Uses an LLM to generate an answer with citations
    3. Returns the answer with source citations
    
    Parameters:
    - **project_id**: The project to query
    - **question**: Your question (1-2000 characters)
    - **document_ids**: Optional filter to specific documents
    - **retrieval_strategy**: How to retrieve chunks (similarity, mmr, hybrid)
    - **top_k**: Number of chunks to retrieve (1-20)
    """
    # Verify project ownership
    project = crud.get_project(
        db, 
        project_id=UUID(query_in.project_id), 
        owner_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check if project has completed documents
    stats = crud.get_project_stats(db, project_id=UUID(query_in.project_id))
    if stats['completed_documents'] == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No processed documents available in this project. Please upload and wait for processing to complete."
        )
    
    # Validate document_ids if provided
    if query_in.document_ids:
        documents, _ = crud.get_documents_by_project(
            db,
            project_id=UUID(query_in.project_id)
        )
        valid_doc_ids = {str(doc.id) for doc in documents if doc.status == models.DocumentStatus.COMPLETED}
        
        for doc_id in query_in.document_ids:
            if doc_id not in valid_doc_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Document {doc_id} not found or not yet processed"
                )
    
    try:
        # Configure retriever
        retriever_config = RetrieverConfig(
            strategy=get_retrieval_strategy(query_in.retrieval_strategy),
            top_k=query_in.top_k
        )
        
        # Configure query
        query_config = QueryConfig(
            temperature=0.0,
            citation_required=True
        )
        
        # Initialize query engine
        engine = RAGQueryEngine(
            project_id=query_in.project_id,
            query_config=query_config,
            retriever_config=retriever_config
        )
        
        # Execute query
        response = await engine.query(
            question=query_in.question,
            document_ids=query_in.document_ids,
            include_all_sources=query_in.include_all_sources
        )
        
        # Add query ID for tracking
        response.query_id = str(uuid.uuid4())

        # Chat session persistence
        # If session_id is provided, validate that it belongs to this user & project
        session_obj = None
        if query_in.session_id:
            try:
                session_uuid = UUID(query_in.session_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid session_id format",
                )

            session_obj = crud.get_chat_session(
                db=db, session_id=session_uuid, user_id=current_user.id
            )
            if not session_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat session not found",
                )

            # Ensure session belongs to the same project
            if str(session_obj.project_id) != query_in.project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="session_id does not belong to the specified project",
                )

        # If no session provided, you can optionally auto-create one, or leave it.
        # Example: auto-create a session for this query
        if not session_obj:
            session_obj = crud.create_chat_session(
                db=db,
                user_id=current_user.id,
                project_id=UUID(query_in.project_id),
                title=None,
            )

        # Store user question
        crud.create_chat_message(
            db=db,
            session_obj=session_obj,
            role=ChatMessageRole.USER,
            content=query_in.question,
        )

        # Store assistant answer, including query_id and metadata if desired
        from json import dumps as json_dumps
        metadata_json = json_dumps(response.metadata or {}) if response.metadata else None

        crud.create_chat_message(
            db=db,
            session_obj=session_obj,
            role=ChatMessageRole.ASSISTANT,
            content=response.answer,
            query_id=UUID(response.query_id) if response.query_id else None,
            answer_metadata=metadata_json,
        )

        return response
        
    except QueryError as e:
        logger.error(f"Query failed: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {e.message}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error during query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your query"
        )


@router.post(
    "/similar",
    response_model=query_schema.SimilarChunksResponse,
    summary="Find similar chunks"
)
async def find_similar_chunks(
    request: query_schema.SimilarChunksRequest,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Find document chunks similar to the provided text.
    
    This is useful for:
    - Finding related content
    - Checking if similar information exists
    - Exploring document content
    """
    # Verify project ownership
    project = crud.get_project(
        db,
        project_id=UUID(request.project_id),
        owner_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    try:
        from app.rag.retriever import create_retriever
        from app.rag.config import RetrievalStrategy
        
        retriever = create_retriever(
            project_id=request.project_id,
            strategy=RetrievalStrategy.SIMILARITY,
            top_k=request.top_k
        )
        
        result = await retriever.retrieve(
            query=request.text,
            document_ids=request.document_ids
        )
        
        chunks = []
        for i, doc in enumerate(result.documents):
            chunks.append(query_schema.Citation(
                chunk_id=doc.metadata.get('chunk_id', 'unknown'),
                document_id=doc.metadata.get('document_id'),
                source_file=doc.metadata.get('source_file', 'unknown'),
                page=doc.metadata.get('page'),
                char_start=doc.metadata.get('char_start'),
                char_end=doc.metadata.get('char_end'),
                text_snippet=doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content,
                relevance_score=result.scores[i] if i < len(result.scores) else None
            ))
        
        return query_schema.SimilarChunksResponse(
            chunks=chunks,
            query_text=request.text
        )
        
    except Exception as e:
        logger.exception(f"Similar chunks search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find similar chunks"
        )