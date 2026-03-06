"""SQLAlchemy project repository implementation."""

import logging
import os
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, case
from sqlalchemy.orm import Session

from app.domain.projects.entities import Project, ProjectStatus
from app.domain.projects.interfaces import IProjectRepository
from app.infrastructure.database.models.project import ProjectModel, ProjectStatus as ModelProjectStatus
from app.infrastructure.database.models.document import DocumentModel, DocumentStatus

logger = logging.getLogger(__name__)


class SQLProjectRepository(IProjectRepository):
    """Project repository backed by SQLAlchemy."""

    def __init__(self, session: Session):
        self._session = session

    async def save(self, project: Project) -> Project:
        """Create or update a project."""
        db_project = (
            self._session.query(ProjectModel)
            .filter(ProjectModel.id == project.id)
            .first()
        )

        if db_project:
            self._update_model(db_project, project)
        else:
            db_project = self._to_model(project)
            self._session.add(db_project)

        self._session.commit()
        self._session.refresh(db_project)
        return self._to_entity(db_project)

    async def get_by_id_and_owner(
        self, project_id: UUID, owner_id: UUID
    ) -> Optional[Project]:
        """Get project ensuring it belongs to the owner."""
        db = (
            self._session.query(ProjectModel)
            .filter(
                and_(
                    ProjectModel.id == project_id,
                    ProjectModel.owner_id == owner_id,
                )
            )
            .first()
        )
        return self._to_entity(db) if db else None

    async def get_by_id(self, project_id: UUID) -> Optional[Project]:
        """Get project by ID (internal use, no ownership check)."""
        db = (
            self._session.query(ProjectModel)
            .filter(ProjectModel.id == project_id)
            .first()
        )
        return self._to_entity(db) if db else None

    async def list_by_owner(
        self,
        owner_id: UUID,
        status: Optional[ProjectStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Project], int]:
        """List owner's projects with optional status filter."""
        query = self._session.query(ProjectModel).filter(
            ProjectModel.owner_id == owner_id
        )
        if status:
            model_status = ModelProjectStatus(status.value)
            query = query.filter(ProjectModel.status == model_status)

        total = query.count()
        rows = (
            query.order_by(ProjectModel.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [self._to_entity(r) for r in rows], total

    async def delete(self, project: Project) -> None:
        """Delete project and its document files."""
        db = (
            self._session.query(ProjectModel)
            .filter(ProjectModel.id == project.id)
            .first()
        )
        if db:
            for doc in db.documents:
                if os.path.exists(doc.file_path):
                    try:
                        os.remove(doc.file_path)
                    except Exception:
                        pass
            self._session.delete(db)
            self._session.commit()

    async def get_stats(self, project_id: UUID) -> dict:
        """Return document statistics for a project."""
        stats = (
            self._session.query(
                func.count(DocumentModel.id).label("document_count"),
                func.sum(
                    case(
                        (DocumentModel.status == DocumentStatus.COMPLETED, 1),
                        else_=0,
                    )
                ).label("completed_documents"),
                func.sum(
                    case(
                        (DocumentModel.status == DocumentStatus.FAILED, 1),
                        else_=0,
                    )
                ).label("failed_documents"),
                func.sum(
                    case(
                        (DocumentModel.status == DocumentStatus.PENDING, 1),
                        else_=0,
                    )
                ).label("pending_documents"),
                func.sum(
                    case(
                        (DocumentModel.status == DocumentStatus.PROCESSING, 1),
                        else_=0,
                    )
                ).label("processing_documents"),
                func.coalesce(func.sum(DocumentModel.chunk_count), 0).label(
                    "total_chunks"
                ),
                func.coalesce(func.sum(DocumentModel.file_size), 0).label(
                    "total_size_bytes"
                ),
            )
            .filter(DocumentModel.project_id == project_id)
            .first()
        )

        return {
            "document_count": stats.document_count or 0,
            "completed_documents": stats.completed_documents or 0,
            "failed_documents": stats.failed_documents or 0,
            "pending_documents": (
                (stats.pending_documents or 0) + (stats.processing_documents or 0)
            ),
            "total_chunks": stats.total_chunks or 0,
            "total_size_bytes": stats.total_size_bytes or 0,
        }

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_entity(model: ProjectModel) -> Project:
        return Project(
            id=model.id,
            name=model.name,
            owner_id=model.owner_id,
            description=model.description,
            status=ProjectStatus(model.status.value),
            chunk_size=model.chunk_size,
            chunk_overlap=model.chunk_overlap,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_model(entity: Project) -> ProjectModel:
        return ProjectModel(
            id=entity.id,
            name=entity.name,
            owner_id=entity.owner_id,
            description=entity.description,
            status=ModelProjectStatus(entity.status.value),
            chunk_size=entity.chunk_size,
            chunk_overlap=entity.chunk_overlap,
            created_at=entity.created_at,
        )

    @staticmethod
    def _update_model(model: ProjectModel, entity: Project) -> None:
        model.name = entity.name
        model.description = entity.description
        model.status = ModelProjectStatus(entity.status.value)
        model.chunk_size = entity.chunk_size
        model.chunk_overlap = entity.chunk_overlap
