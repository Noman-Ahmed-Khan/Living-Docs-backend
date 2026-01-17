import os
import uuid
import shutil
import logging
import mimetypes
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

from app.db import crud, session, models
from app.schemas import document as document_schema
from app.dependencies import get_current_user
from app.settings import settings
from app.services.ingestion import get_ingestion_service
from app.rag.loaders import DocumentLoader


logger = logging.getLogger(__name__)
router = APIRouter()


# Allowed file extensions
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.md', '.txt', '.html', '.htm'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def validate_file(file: UploadFile) -> tuple[str, str]:
    """
    Validate uploaded file.
    
    Returns:
        Tuple of (file_extension, content_type)
    """
    # Check filename
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    # Check extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{ext}' is not supported. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Get content type
    content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or 'application/octet-stream'
    
    return ext, content_type


async def save_upload_file(file: UploadFile, destination: Path) -> int:
    """
    Save uploaded file to destination.
    
    Returns:
        File size in bytes
    """
    file_size = 0
    
    with open(destination, "wb") as buffer:
        while chunk := await file.read(8192):  # 8KB chunks
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                # Clean up partial file
                buffer.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024*1024)} MB"
                )
            buffer.write(chunk)
    
    return file_size


def process_document_background(
    db_session_factory,
    document_id: UUID,
    project_id: UUID,
    chunk_size: int,
    chunk_overlap: int
):
    """Background task for document processing."""
    from app.db.session import SessionLocal
    
    db = SessionLocal()
    try:
        ingestion_service = get_ingestion_service()
        ingestion_service.ingest_document(
            db=db,
            document_id=document_id,
            project_id=project_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    finally:
        db.close()


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
    process_immediately: bool = Form(True, description="Process document immediately"),
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
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
    
    The document will be processed asynchronously by default.
    """
    # Verify project ownership
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check project status
    if project.status == models.ProjectStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upload documents to archived projects"
        )
    
    # Validate file
    file_ext, content_type = validate_file(file)
    
    # Create upload directory if needed
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    stored_filename = f"{file_id}{file_ext}"
    file_path = upload_dir / stored_filename
    
    try:
        # Save file
        file_size = await save_upload_file(file, file_path)
        
        # Create document record
        db_doc = crud.create_document(
            db,
            filename=stored_filename,
            original_filename=file.filename,
            project_id=project_id,
            file_path=str(file_path),
            file_size=file_size,
            file_type=file_ext,
            content_type=content_type
        )
        
        # Process document
        if process_immediately:
            background_tasks.add_task(
                process_document_background,
                session.SessionLocal,
                db_doc.id,
                project_id,
                project.chunk_size,
                project.chunk_overlap
            )
        
        return document_schema.DocumentUploadResponse(
            document=db_doc,
            message="Document uploaded successfully. Processing started." if process_immediately else "Document uploaded. Processing pending.",
            processing=process_immediately
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Clean up file on error
        if file_path.exists():
            file_path.unlink(missing_ok=True)
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
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Upload multiple documents to a project at once.
    
    All documents will be processed asynchronously.
    """
    # Verify project
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if project.status == models.ProjectStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upload documents to archived projects"
        )
    
    uploaded = []
    failed = []
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    for file in files:
        try:
            # Validate
            file_ext, content_type = validate_file(file)
            
            # Save
            file_id = str(uuid.uuid4())
            stored_filename = f"{file_id}{file_ext}"
            file_path = upload_dir / stored_filename
            
            file_size = await save_upload_file(file, file_path)
            
            # Create record
            db_doc = crud.create_document(
                db,
                filename=stored_filename,
                original_filename=file.filename,
                project_id=project_id,
                file_path=str(file_path),
                file_size=file_size,
                file_type=file_ext,
                content_type=content_type
            )
            
            # Queue processing
            background_tasks.add_task(
                process_document_background,
                session.SessionLocal,
                db_doc.id,
                project_id,
                project.chunk_size,
                project.chunk_overlap
            )
            
            uploaded.append(db_doc)
            
        except HTTPException as e:
            failed.append({
                "filename": file.filename or "unknown",
                "error": e.detail
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


@router.get(
    "/project/{project_id}",
    response_model=document_schema.DocumentList,
    summary="List project documents"
)
def list_documents(
    project_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[document_schema.DocumentStatus] = None,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List all documents in a project with pagination."""
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    skip = (page - 1) * page_size
    model_status = models.DocumentStatus(status.value) if status else None
    
    documents, total = crud.get_documents_by_project(
        db,
        project_id=project_id,
        status=model_status,
        skip=skip,
        limit=page_size
    )
    
    pages = (total + page_size - 1) // page_size
    
    return document_schema.DocumentList(
        items=documents,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.get(
    "/{document_id}",
    response_model=document_schema.DocumentDetail,
    summary="Get document details"
)
def get_document(
    document_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get detailed information about a document."""
    # Verify project ownership
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    document = crud.get_document(db, document_id=document_id, project_id=project_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return document


@router.get(
    "/{document_id}/status",
    response_model=document_schema.DocumentIngestionStatus,
    summary="Get document processing status"
)
def get_document_status(
    document_id: UUID,
    project_id: UUID = Query(...),
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get the current processing status of a document."""
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    document = crud.get_document(db, document_id=document_id, project_id=project_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return document_schema.DocumentIngestionStatus(
        document_id=str(document.id),
        status=document_schema.DocumentStatus(document.status.value),
        message=document.status_message,
        chunks_created=document.chunk_count,
        pages_processed=document.page_count,
        completed_at=document.processed_at
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
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Re-process a document with new settings.
    
    This will:
    1. Delete existing vectors for this document
    2. Re-chunk the document with new settings (if provided)
    3. Re-embed and store the new chunks
    """
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if project.status == models.ProjectStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify documents in archived projects"
        )
    
    document = crud.get_document(db, document_id=document_id, project_id=project_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check if already completed and force not set
    if document.status == models.DocumentStatus.COMPLETED and not request.force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document already processed. Set force=true to reprocess."
        )
    
    # Delete existing vectors
    ingestion_service = get_ingestion_service()
    ingestion_service.delete_document_vectors(document_id, project_id)
    
    # Reset document status
    crud.reset_document_for_reingestion(db, document)
    
    # Use provided settings or project defaults
    chunk_size = request.chunk_size or project.chunk_size
    chunk_overlap = request.chunk_overlap or project.chunk_overlap
    
    # Queue re-processing
    background_tasks.add_task(
        process_document_background,
        session.SessionLocal,
        document_id,
        project_id,
        chunk_size,
        chunk_overlap
    )
    
    # Refresh document
    db.refresh(document)
    
    return document


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document"
)
def delete_document(
    document_id: UUID,
    project_id: UUID = Query(...),
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Permanently delete a document.
    
    This will:
    - Remove the document file from storage
    - Delete all vectors from the vector database
    - Remove the database record
    """
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    document = crud.get_document(db, document_id=document_id, project_id=project_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Delete vectors
    ingestion_service = get_ingestion_service()
    ingestion_service.delete_document_vectors(document_id, project_id)
    
    # Delete document (file and record)
    crud.delete_document(db, document)
    
    return None


@router.get(
    "/supported-types",
    response_model=List[str],
    summary="Get supported file types"
)
def get_supported_types():
    """Get list of supported file extensions for upload."""
    return sorted(list(ALLOWED_EXTENSIONS))