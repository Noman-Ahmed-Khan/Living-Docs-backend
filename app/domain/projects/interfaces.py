"""Project domain interfaces (ports)."""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID

from .entities import Project, ProjectStatus


class IProjectRepository(ABC):
    """Repository interface for project persistence."""

    @abstractmethod
    async def save(self, project: Project) -> Project:
        """Create or update a project."""
        pass

    @abstractmethod
    async def get_by_id_and_owner(
        self, project_id: UUID, owner_id: UUID
    ) -> Optional[Project]:
        """Get project ensuring it belongs to the given owner."""
        pass

    @abstractmethod
    async def get_by_id(self, project_id: UUID) -> Optional[Project]:
        """Get project by ID regardless of owner (for internal use)."""
        pass

    @abstractmethod
    async def list_by_owner(
        self,
        owner_id: UUID,
        status: Optional[ProjectStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Project], int]:
        """List owner's projects with optional status filter."""
        pass

    @abstractmethod
    async def delete(self, project: Project) -> None:
        """Delete project and all associated document files."""
        pass

    @abstractmethod
    async def get_stats(self, project_id: UUID) -> dict:
        """Return document statistics for a project."""
        pass
