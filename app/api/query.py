"""Query API endpoints - thin layer delegating to QueryService."""

import logging
from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.container_dependencies import get_query_service, get_db, get_project_service, get_document_service, get_current_verified_user
from app.api.schemas import query as query_schema
from app.infrastructure.database.models import DocumentStatus
from app.domain.projects.entities import ProjectStatus 
from app.application.query.query_service import QueryService
from app.application.projects.service import ProjectService
from app.application.documents.service import DocumentService
from app.domain.rag.exceptions import (
    InvalidQueryError,
    NoContextFoundError,
    QueryError
)
from app.domain.projects.exceptions import ProjectNotFoundError
from app.domain.users.entities import User


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/",
    response_model=query_schema.QueryResponse,
    summary="Query documents",
    responses={
        200: {"description": "Successful query with answer and citations"},
        400: {"description": "Invalid query or no processed documents"},
        404: {"description": "Project not found or no relevant context"},
        500: {"description": "Query processing failed"}
    }
)
async def query_documents(
    query_in: query_schema.QueryRequest,
    query_service: QueryService = Depends(get_query_service),
    project_service: ProjectService = Depends(get_project_service),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    """
    Query documents in a project using RAG.
    
    This endpoint:
    1. Validates project ownership and document status
    2. Executes RAG query via QueryService
    3. Returns answer with source citations
    """
    # Verify project ownership and status
    try:
        project = await project_service.get_project(
            project_id=UUID(query_in.project_id),
            owner_id=current_user.id
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if project.status ==  ProjectStatus.ARCHIVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot query archived projects"
        )
    
    # Check if project has completed documents
    project_with_stats = await project_service.get_project_with_stats(
        project_id=UUID(query_in.project_id),
        owner_id=current_user.id
    )
    if project_with_stats.stats.completed_documents == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No processed documents available in this project. Please upload and wait for processing to complete."
        )
    
    # Validate document_ids if provided
    if query_in.document_ids:
        documents, _ = await document_service.list_documents(
            project_id=UUID(query_in.project_id)
        )
        valid_doc_ids = {str(doc.id) for doc in documents if doc.status == DocumentStatus.COMPLETED.value}
        
        for doc_id in query_in.document_ids:
            if doc_id not in valid_doc_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Document {doc_id} not found or not yet processed"
                )
    
    try:
        # Execute query via service (all business logic delegated)
        result = await query_service.query(
            question=query_in.question,
            project_id=UUID(query_in.project_id),
            user_id=current_user.id,
            document_ids=[UUID(doc_id) for doc_id in query_in.document_ids] if query_in.document_ids else None,
            session_id=UUID(query_in.session_id) if query_in.session_id else None,
            retrieval_strategy=query_in.retrieval_strategy,
            top_k=query_in.top_k,
            include_all_sources=query_in.include_all_sources,
            db=db
        )
        
        # Convert domain entity to API response
        return query_schema.QueryResponse(
            query_id=str(result.query_id),
            answer=result.answer,
            citations=[
                query_schema.Citation(
                    chunk_id=c.chunk_id,
                    document_id=str(c.document_id),
                    source_file=c.source_file,
                    text_snippet=c.text_snippet,
                    page=c.page,
                    char_start=c.char_start,
                    char_end=c.char_end,
                    relevance_score=c.relevance_score
                )
                for c in result.citations
            ],
            metadata=result.metadata
        )
        
    except (InvalidQueryError, NoContextFoundError, QueryError):
        # Let middleware handle domain exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in query endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your query"
        )


@router.post(
    "/similar",
    response_model=query_schema.SimilarChunksResponse,
    summary="Find similar chunks",
    responses={
        200: {"description": "Similar chunks found"},
        400: {"description": "Invalid input"},
        404: {"description": "Project not found or no similar chunks"}
    }
)
async def find_similar_chunks(
    request: query_schema.SimilarChunksRequest,
    query_service: QueryService = Depends(get_query_service),
    project_service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
):
    """
    Find document chunks similar to provided text.
    
    Useful for:
    - Finding related content without generating an answer
    - Checking if similar information exists
    - Exploring document content
    """
    # Verify project ownership
    try:
        project = await project_service.get_project(
            project_id=UUID(request.project_id),
            owner_id=current_user.id
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    try:
        # Execute similar search via service
        chunks = await query_service.find_similar(
            text=request.text,
            project_id=UUID(request.project_id),
            user_id=current_user.id,
            document_ids=[UUID(doc_id) for doc_id in request.document_ids] if request.document_ids else None,
            top_k=request.top_k,
            db=db
        )
        
        return query_schema.SimilarChunksResponse(
            query_text=request.text,
            chunks=[
                query_schema.Citation(
                    chunk_id=c.chunk_id,
                    document_id=str(c.document_id),
                    source_file=c.metadata.source_file if hasattr(c.metadata, 'source_file') else c.metadata.get('source_file', 'unknown'),
                    text_snippet=c.text[:300] + "..." if len(c.text) > 300 else c.text,
                    page=c.metadata.page if hasattr(c.metadata, 'page') else c.metadata.get('page'),
                    char_start=c.metadata.char_start if hasattr(c.metadata, 'char_start') else c.metadata.get('char_start'),
                    char_end=c.metadata.char_end if hasattr(c.metadata, 'char_end') else c.metadata.get('char_end'),
                    relevance_score=c.score if hasattr(c, 'score') else None
                )
                for c in chunks
            ]
        )
        
    except (NoContextFoundError, QueryError):
        raise
    except Exception as e:
        logger.error(f"Similar chunks search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find similar chunks"
        )
