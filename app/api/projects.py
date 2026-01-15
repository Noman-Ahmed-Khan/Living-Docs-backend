"""Project management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.db import crud, session, models
from app.schemas import project as project_schema
from app.dependencies import get_current_user
from app.services.ingestion import get_ingestion_service


router = APIRouter()


@router.post(
    "/",
    response_model=project_schema.Project,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project"
)
def create_project(
    project_in: project_schema.ProjectCreate,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Create a new project for document management.
    
    - **name**: Project name (required)
    - **description**: Optional project description
    - **chunk_size**: Size of text chunks for RAG (default: 1000)
    - **chunk_overlap**: Overlap between chunks (default: 200)
    """
    return crud.create_project(db, project=project_in, owner_id=current_user.id)


@router.get(
    "/",
    response_model=project_schema.ProjectList,
    summary="List all projects"
)
def list_projects(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[project_schema.ProjectStatus] = Query(None, description="Filter by status"),
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    List all projects for the current user with pagination.
    """
    skip = (page - 1) * page_size
    
    # Convert schema enum to model enum if provided
    model_status = None
    if status:
        model_status = models.ProjectStatus(status.value)
    
    projects, total = crud.get_projects(
        db, 
        owner_id=current_user.id,
        status=model_status,
        skip=skip,
        limit=page_size
    )
    
    pages = (total + page_size - 1) // page_size
    
    return project_schema.ProjectList(
        items=projects,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.get(
    "/{project_id}",
    response_model=project_schema.Project,
    summary="Get project details"
)
def get_project(
    project_id: UUID,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get details of a specific project."""
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


@router.get(
    "/{project_id}/stats",
    response_model=project_schema.ProjectWithStats,
    summary="Get project with statistics"
)
def get_project_with_stats(
    project_id: UUID,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get project details with document statistics."""
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    stats_data = crud.get_project_stats(db, project_id=project_id)
    stats = project_schema.ProjectStats(**stats_data)
    
    return project_schema.ProjectWithStats(
        id=str(project.id),
        name=project.name,
        description=project.description,
        owner_id=str(project.owner_id),
        status=project_schema.ProjectStatus(project.status.value),
        chunk_size=project.chunk_size,
        chunk_overlap=project.chunk_overlap,
        created_at=project.created_at,
        updated_at=project.updated_at,
        stats=stats
    )


@router.patch(
    "/{project_id}",
    response_model=project_schema.Project,
    summary="Update project"
)
def update_project(
    project_id: UUID,
    project_update: project_schema.ProjectUpdate,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update project settings.
    
    Note: Changing chunk_size or chunk_overlap will not affect existing documents.
    Use the re-ingest endpoint to reprocess documents with new settings.
    """
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return crud.update_project(db, project, project_update)


@router.post(
    "/{project_id}/archive",
    response_model=project_schema.Project,
    summary="Archive project"
)
def archive_project(
    project_id: UUID,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Archive a project. Archived projects are read-only."""
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return crud.archive_project(db, project)


@router.post(
    "/{project_id}/unarchive",
    response_model=project_schema.Project,
    summary="Unarchive project"
)
def unarchive_project(
    project_id: UUID,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Restore an archived project to active status."""
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return crud.unarchive_project(db, project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project"
)
def delete_project(
    project_id: UUID,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Permanently delete a project and all its documents.
    
    This action:
    - Deletes all document files from storage
    - Removes all vectors from the vector database
    - Deletes all database records
    
    This action cannot be undone.
    """
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Delete vectors from vector store
    ingestion_service = get_ingestion_service()
    ingestion_service.delete_project_vectors(project_id)
    
    # Delete project (cascades to documents)
    crud.delete_project(db, project)
    
    return None