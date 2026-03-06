import os
import uuid
import logging
from typing import List, Optional
from pathlib import Path

from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    UploadFile, 
    File, 
    Form,
    BackgroundTasks,
    Query,
    status
)
from sqlalchemy.orm import Session
from uuid import UUID

from app.infrastructure.database.models import (
    DocumentStatus,
    ProjectModelStatus
)
from app.api.schemas import document as document_schema
from app.api.container_dependencies import (
    get_db,
    get_document_service,
    get_ingestion_service,
    get_project_service,
    get_current_verified_user
)
from app.application.projects.service import ProjectService
from app.application.documents.service import DocumentService
from app.domain.users.entities import User
from app.domain.projects.exceptions import ProjectNotFoundError
from app.domain.documents.exceptions import DocumentNotFoundError
from app.config.settings import settings
from app.infrastructure.tasks.document_processor import process_document_task


logger = logging.getLogger(__name__)
router = APIRouter()


# Allowed file extensions
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.md', '.txt', '.html', '.htm'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post(
    "/upload",
    response_model=document_schema.DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document"
)
async def upload_document(
    background_tasks: BackgroundTasks,
    project_id: UUID = Form(..., description="Project ID to upload to"),
    file: UploadFile = File(..., description="Document file to upload"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
    project_service: ProjectService = Depends(get_project_service),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Upload a document to a project.
    
    Supported file types:
    - PDF (.pdf)
    - Word (.docx, .doc)
    - PowerPoint (.pptx, .ppt)
    - Excel (.xlsx, .xls)
    - Markdown (.md)
    - Text (.txt)
    - HTML (.html, .htm)
    
    The document will be processed asynchronously.
    """
    try:
        # Verify project ownership
        try:
            project = await project_service.get_project(project_id=project_id, owner_id=current_user.id)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        if project.status == ProjectModelStatus.ARCHIVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot upload documents to archived projects"
            )
        
        # Upload via DocumentService
        upload_result = await document_service.upload_document(
            file=file,
            project_id=project_id,
            user_id=current_user.id
        )
        
        # Queue background processing task
        background_tasks.add_task(
            process_document_task,
            document_id=upload_result.document_id,
            project_id=project_id
        )
        
        return document_schema.DocumentUploadResponse(
            document_id=str(upload_result.document_id),
            filename=upload_result.filename,
            message="Document uploaded successfully. Processing started.",
            processing=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to upload document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.post(
    "/upload/bulk",
    response_model=document_schema.BulkUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload multiple documents"
)
async def bulk_upload_documents(
    background_tasks: BackgroundTasks,
    project_id: UUID = Form(...),
    files: List[UploadFile] = File(..., description="Document files to upload"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
    project_service: ProjectService = Depends(get_project_service),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Upload multiple documents to a project at once.
    
    All documents will be processed asynchronously.
    """
    try:
        # Verify project
        try:
            project = await project_service.get_project(project_id=project_id, owner_id=current_user.id)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        if project.status == ProjectModelStatus.ARCHIVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot upload documents to archived projects"
            )
        
        uploaded = []
        failed = []
        
        for file in files:
            try:
                # Upload via service
                upload_result = await document_service.upload_document(
                    file=file,
                    project_id=project_id,
                    user_id=current_user.id
                )
                
                # Queue processing
                background_tasks.add_task(
                    process_document_task,
                    document_id=upload_result.document_id,
                    project_id=project_id
                )
                
                uploaded.append({
                    "document_id": str(upload_result.document_id),
                    "filename": upload_result.filename
                })
                
            except Exception as e:
                failed.append({
                    "filename": file.filename or "unknown",
                    "error": str(e)
                })
        
        return document_schema.BulkUploadResponse(
            uploaded=uploaded,
            failed=failed,
            total_uploaded=len(uploaded),
            total_failed=len(failed)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Bulk upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bulk upload failed"
        )


@router.get(
    "/project/{project_id}",
    response_model=document_schema.DocumentList,
    summary="List project documents"
)
async def list_documents(
    project_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[document_schema.DocumentStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
    project_service: ProjectService = Depends(get_project_service),
    document_service: DocumentService = Depends(get_document_service)
):
    try:
        try:
            project = await project_service.get_project(project_id=project_id, owner_id=current_user.id)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        from app.domain.documents.entities import DocumentStatus as DomainDocumentStatus
        model_status = DomainDocumentStatus(status_filter.value) if status_filter else None
        
        documents, total = await document_service.list_documents(
            project_id=project_id,
            status=model_status,
            page=page,
            page_size=page_size
        )
        
        pages = (total + page_size - 1) // page_size
        
        return document_schema.DocumentList(
            items=documents,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents"
        )


@router.get(
    "/{document_id}",
    response_model=document_schema.DocumentDetail,
    summary="Get document details"
)
async def get_document(
    document_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
    project_service: ProjectService = Depends(get_project_service),
    document_service: DocumentService = Depends(get_document_service)
):
    """Get detailed information about a document."""
    try:
        # Verify project ownership
        try:
            await project_service.get_project(project_id=project_id, owner_id=current_user.id)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        try:
            document = await document_service.get_document(document_id=document_id, project_id=project_id)
        except DocumentNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return document
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document"
        )


@router.get(
    "/{document_id}/status",
    response_model=document_schema.DocumentIngestionStatus,
    summary="Get document processing status"
)
async def get_document_status(
    document_id: UUID,
    project_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
    project_service: ProjectService = Depends(get_project_service),
    document_service: DocumentService = Depends(get_document_service)
):
    """Get the current processing status of a document."""
    try:
        try:
            await project_service.get_project(project_id=project_id, owner_id=current_user.id)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        try:
            document = await document_service.get_document(document_id=document_id, project_id=project_id)
        except DocumentNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return document_schema.DocumentIngestionStatus(
            document_id=str(document.id),
            status=document_schema.DocumentStatus(document.status),
            message=document.status_message if hasattr(document, 'status_message') else None,
            chunks_created=document.chunk_count,
            pages_processed=document.page_count,
            completed_at=document.processed_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document status"
        )


@router.post(
    "/{document_id}/reingest",
    response_model=document_schema.Document,
    summary="Re-ingest document"
)
async def reingest_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    request: document_schema.ReingestionRequest,
    project_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
    project_service: ProjectService = Depends(get_project_service),
    document_service: DocumentService = Depends(get_document_service),
    ingestion_service = Depends(get_ingestion_service)
):
    """
    Re-process a document with new settings.
    
    This will:
    1. Delete existing vectors for this document
    2. Re-chunk the document with new settings (if provided)
    3. Re-embed and store the new chunks
    """
    try:
        try:
            project = await project_service.get_project(project_id=project_id, owner_id=current_user.id)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        if project.status == ProjectModelStatus.ARCHIVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify documents in archived projects"
            )
        
        try:
            document = await document_service.get_document(document_id=document_id, project_id=project_id)
        except DocumentNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Check if already completed and force not set
        if document.status == DocumentStatus.COMPLETED.value and not request.force:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document already processed. Set force=true to reprocess."
            )
        
        # Delete existing vectors
        await ingestion_service.delete_document_vectors(document_id, project_id)
        
        # Reset document status
        await document_service.reset_document_for_reingestion(document_id, project_id)
        
        # Queue re-processing
        background_tasks.add_task(
            process_document_task,
            document_id=document_id,
            project_id=project_id
        )
        
        return await document_service.get_document(document_id=document_id, project_id=project_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reingest document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reingest document"
        )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document"
)
async def delete_document(
    document_id: UUID,
    project_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
    project_service: ProjectService = Depends(get_project_service),
    document_service: DocumentService = Depends(get_document_service),
    ingestion_service = Depends(get_ingestion_service)
):
    """
    Permanently delete a document.
    
    This will:
    - Remove the document file from storage
    - Delete all vectors from the vector database
    - Remove the database record
    """
    try:
        try:
            await project_service.get_project(project_id=project_id, owner_id=current_user.id)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Delete vectors
        await ingestion_service.delete_document_vectors(document_id, project_id)
        
        # Delete document (file and record)
        try:
            await document_service.delete_document(document_id=document_id, project_id=project_id)
        except DocumentNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )


@router.get(
    "/supported-types",
    response_model=List[str],
    summary="Get supported file types"
)
async def get_supported_types():
    """Get list of supported file extensions for upload."""
    return sorted(list(ALLOWED_EXTENSIONS))

