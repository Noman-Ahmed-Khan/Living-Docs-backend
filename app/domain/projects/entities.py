"""Project domain entities."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4
from typing import Optional

from app.domain.common.entity import Entity


class ProjectStatus(str, Enum):
    """Project lifecycle status."""
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class Project(Entity):
    """
    Project domain entity.

    Business Rules:
    - Projects belong to exactly one owner
    - Archived projects are read-only for document operations
    - chunk_size / chunk_overlap are RAG configuration for the project
    """

    name: str = ""
    owner_id: UUID = field(default_factory=uuid4)
    status: ProjectStatus = ProjectStatus.ACTIVE
    description: Optional[str] = None
    chunk_size: int = 1000
    chunk_overlap: int = 200

    @classmethod
    def create(
        cls,
        name: str,
        owner_id: UUID,
        description: Optional[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> "Project":
        """Factory method — create a new active project."""
        return cls(
            id=uuid4(),
            name=name.strip(),
            owner_id=owner_id,
            description=description,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            status=ProjectStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
        )

    def archive(self) -> None:
        """Archive the project (make read-only)."""
        self.status = ProjectStatus.ARCHIVED

    def unarchive(self) -> None:
        """Restore an archived project to active."""
        self.status = ProjectStatus.ACTIVE

    def update(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> None:
        """Update mutable project fields."""
        if name is not None:
            self.name = name.strip()
        if description is not None:
            self.description = description
        if chunk_size is not None:
            self.chunk_size = chunk_size
        if chunk_overlap is not None:
            self.chunk_overlap = chunk_overlap

    @property
    def is_active(self) -> bool:
        return self.status == ProjectStatus.ACTIVE

    @property
    def is_archived(self) -> bool:
        return self.status == ProjectStatus.ARCHIVED

