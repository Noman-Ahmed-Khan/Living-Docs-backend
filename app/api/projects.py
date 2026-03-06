"""Project management API endpoints."""

from typing import Any, Optional
from fastapi import APIRouter, Depends, Query, status
from uuid import UUID

from app.api.schemas import project as project_schema
from app.api.container_dependencies import (
    get_project_service,
    get_current_active_user,
)
from app.application.projects.service import ProjectService
from app.domain.users.entities import User

router = APIRouter()


@router.post(
    "/",
    response_model=project_schema.Project,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project"
)
async def create_project(
    project_in: project_schema.ProjectCreate,
    project_service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Create a new project for document management."""
    project = await project_service.create_project(
        owner_id=current_user.id,
        name=project_in.name,
        description=project_in.description,
        chunk_size=project_in.chunk_size,
        chunk_overlap=project_in.chunk_overlap
    )
    return project


@router.get(
    "/",
    response_model=project_schema.ProjectList,
    summary="List all projects"
)
async def list_projects(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[project_schema.ProjectStatus] = Query(None, description="Filter by status"),
    project_service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """List all projects for the current user with pagination."""
    return await project_service.list_projects(
        owner_id=current_user.id,
        status=status.value if status else None,
        page=page,
        page_size=page_size
    )


@router.get(
    "/{project_id}",
    response_model=project_schema.Project,
    summary="Get project details"
)
async def get_project(
    project_id: UUID,
    project_service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Get details of a specific project."""
    return await project_service.get_project(
        project_id=project_id, 
        owner_id=current_user.id
    )


@router.get(
    "/{project_id}/stats",
    # response_model=project_schema.ProjectWithStats, # commented out as DTO structure might differ slightly from schema but usually matches
    summary="Get project with statistics"
)
async def get_project_with_stats(
    project_id: UUID,
    project_service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Get project details with document statistics."""
    return await project_service.get_project_with_stats(
        project_id=project_id, 
        owner_id=current_user.id
    )


@router.patch(
    "/{project_id}",
    response_model=project_schema.Project,
    summary="Update project"
)
async def update_project(
    project_id: UUID,
    project_update: project_schema.ProjectUpdate,
    project_service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Update project settings."""
    return await project_service.update_project(
        project_id=project_id,
        owner_id=current_user.id,
        name=project_update.name,
        description=project_update.description,
        chunk_size=project_update.chunk_size,
        chunk_overlap=project_update.chunk_overlap
    )


@router.post(
    "/{project_id}/archive",
    response_model=project_schema.Project,
    summary="Archive project"
)
async def archive_project(
    project_id: UUID,
    project_service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Archive a project. Archived projects are read-only."""
    return await project_service.archive_project(
        project_id=project_id, 
        owner_id=current_user.id
    )


@router.post(
    "/{project_id}/unarchive",
    response_model=project_schema.Project,
    summary="Unarchive project"
)
async def unarchive_project(
    project_id: UUID,
    project_service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Restore an archived project to active status."""
    return await project_service.unarchive_project(
        project_id=project_id, 
        owner_id=current_user.id
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project"
)
async def delete_project(
    project_id: UUID,
    project_service: ProjectService = Depends(get_project_service),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Permanently delete a project and all its documents."""
    await project_service.delete_project(
        project_id=project_id, 
        owner_id=current_user.id
    )
    return None
