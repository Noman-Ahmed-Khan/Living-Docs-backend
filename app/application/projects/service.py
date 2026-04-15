"""Project application service."""

import logging
from typing import Callable, List, Optional
from uuid import UUID

from app.domain.projects.entities import Project, ProjectStatus
from app.domain.projects.interfaces import IProjectRepository
from app.domain.projects.exceptions import ProjectNotFoundError
from .dto import ProjectDTO, ProjectStatsDTO, ProjectWithStatsDTO, ProjectListDTO

logger = logging.getLogger(__name__)


class ProjectService:
    """Orchestrates project CRUD and lifecycle management."""

    def __init__(
        self,
        project_repo: IProjectRepository,
        vector_store_factory: Optional[Callable[[], object]] = None,
    ):
        self._project_repo = project_repo
        self._vector_store_factory = vector_store_factory

    async def create_project(
        self,
        owner_id: UUID,
        name: str,
        description: Optional[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> ProjectDTO:
        """Create a new project."""
        project = Project.create(
            name=name,
            owner_id=owner_id,
            description=description,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        saved = await self._project_repo.save(project)
        logger.info(f"Project created: {saved.id} by owner {owner_id}")
        return self._to_dto(saved)

    async def get_project(self, project_id: UUID, owner_id: UUID) -> ProjectDTO:
        """Get project by ID (ownership enforced)."""
        project = await self._project_repo.get_by_id_and_owner(
            project_id, owner_id
        )
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")
        return self._to_dto(project)

    async def get_project_with_stats(
        self, project_id: UUID, owner_id: UUID
    ) -> ProjectWithStatsDTO:
        """Get project with document statistics."""
        project = await self._project_repo.get_by_id_and_owner(
            project_id, owner_id
        )
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        stats_data = await self._project_repo.get_stats(project_id)
        stats = ProjectStatsDTO(**stats_data)

        return ProjectWithStatsDTO(
            id=project.id,
            name=project.name,
            owner_id=project.owner_id,
            description=project.description,
            status=project.status.value,
            chunk_size=project.chunk_size,
            chunk_overlap=project.chunk_overlap,
            created_at=project.created_at,
            updated_at=project.updated_at,
            stats=stats,
        )

    async def list_projects(
        self,
        owner_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ProjectListDTO:
        """List owner's projects with pagination."""
        skip = (page - 1) * page_size
        domain_status = ProjectStatus(status) if status else None

        projects, total = await self._project_repo.list_by_owner(
            owner_id=owner_id,
            status=domain_status,
            skip=skip,
            limit=page_size,
        )
        pages = (total + page_size - 1) // page_size

        return ProjectListDTO(
            items=[self._to_dto(p) for p in projects],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def update_project(
        self,
        project_id: UUID,
        owner_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> ProjectDTO:
        """Update mutable project fields."""
        project = await self._project_repo.get_by_id_and_owner(
            project_id, owner_id
        )
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        project.update(
            name=name,
            description=description,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        saved = await self._project_repo.save(project)
        return self._to_dto(saved)

    async def archive_project(
        self, project_id: UUID, owner_id: UUID
    ) -> ProjectDTO:
        """Archive a project."""
        project = await self._project_repo.get_by_id_and_owner(
            project_id, owner_id
        )
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        project.archive()
        saved = await self._project_repo.save(project)
        return self._to_dto(saved)

    async def unarchive_project(
        self, project_id: UUID, owner_id: UUID
    ) -> ProjectDTO:
        """Restore an archived project."""
        project = await self._project_repo.get_by_id_and_owner(
            project_id, owner_id
        )
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        project.unarchive()
        saved = await self._project_repo.save(project)
        return self._to_dto(saved)

    async def delete_project(
        self, project_id: UUID, owner_id: UUID
    ) -> None:
        """Delete project, its documents, and vectors from the vector store."""
        project = await self._project_repo.get_by_id_and_owner(
            project_id, owner_id
        )
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        if self._vector_store_factory:
            try:
                vector_store = self._vector_store_factory()
                await vector_store.delete_namespace(str(project_id))
            except Exception as e:
                logger.warning(f"Vector cleanup failed for project {project_id}: {e}")

        await self._project_repo.delete(project)
        logger.info(f"Project {project_id} deleted by owner {owner_id}")

    @staticmethod
    def _to_dto(project: Project) -> ProjectDTO:
        return ProjectDTO(
            id=project.id,
            name=project.name,
            owner_id=project.owner_id,
            description=project.description,
            status=project.status.value,
            chunk_size=project.chunk_size,
            chunk_overlap=project.chunk_overlap,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
