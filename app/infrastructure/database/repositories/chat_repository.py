"""SQLAlchemy chat repository implementation."""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.domain.chat.entities import ChatSession, ChatMessage, MessageRole
from app.domain.chat.interfaces import IChatRepository
from app.infrastructure.database.models.chat import (
    ChatSessionModel,
    ChatMessageModel,
    ChatMessageRole,
)

logger = logging.getLogger(__name__)


class SQLChatRepository(IChatRepository):
    """Chat repository backed by SQLAlchemy."""

    def __init__(self, session: Session):
        self._session = session

    async def create_session(
        self,
        user_id: UUID,
        project_id: UUID,
        title: Optional[str] = None,
    ) -> ChatSession:
        """Create and persist a new chat session."""
        db_session = ChatSessionModel(
            user_id=user_id,
            project_id=project_id,
            title=title,
            is_active=True,
        )
        self._session.add(db_session)
        self._session.commit()
        self._session.refresh(db_session)
        return self._session_to_entity(db_session)

    async def get_session(
        self, session_id: UUID, user_id: UUID
    ) -> Optional[ChatSession]:
        """Get session by ID ensuring it belongs to the user."""
        db = (
            self._session.query(ChatSessionModel)
            .filter(
                and_(
                    ChatSessionModel.id == session_id,
                    ChatSessionModel.user_id == user_id,
                )
            )
            .first()
        )
        return self._session_to_entity(db) if db else None

    async def list_sessions(
        self,
        user_id: UUID,
        project_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[ChatSession], int]:
        """List user's sessions, optionally filtered by project."""
        query = self._session.query(ChatSessionModel).filter(
            ChatSessionModel.user_id == user_id
        )
        if project_id:
            query = query.filter(ChatSessionModel.project_id == project_id)

        total = query.count()
        rows = (
            query.order_by(
                ChatSessionModel.last_message_at.desc().nullslast(),
                ChatSessionModel.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [self._session_to_entity(r) for r in rows], total

    async def delete_session(self, session: ChatSession) -> None:
        """Permanently delete a session and all its messages."""
        db = (
            self._session.query(ChatSessionModel)
            .filter(ChatSessionModel.id == session.id)
            .first()
        )
        if db:
            self._session.delete(db)
            self._session.commit()

    async def add_message(
        self,
        session: ChatSession,
        role: MessageRole,
        content: str,
        query_id: Optional[UUID] = None,
        answer_metadata: Optional[str] = None,
    ) -> ChatMessage:
        """Add a message to a session and update last_message_at."""
        db_msg = ChatMessageModel(
            session_id=session.id,
            role=ChatMessageRole(role.value),
            content=content,
            query_id=query_id,
            answer_metadata=answer_metadata,
        )
        self._session.add(db_msg)

        # Update session timestamp
        db_session = (
            self._session.query(ChatSessionModel)
            .filter(ChatSessionModel.id == session.id)
            .first()
        )
        if db_session:
            db_session.last_message_at = datetime.now(timezone.utc)
            self._session.add(db_session)

        self._session.commit()
        self._session.refresh(db_msg)
        return self._message_to_entity(db_msg)

    async def list_messages(
        self,
        session_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 200,
    ) -> List[ChatMessage]:
        """List messages for a session (verifies ownership via user_id)."""
        db_session = await self.get_session(session_id, user_id)
        if not db_session:
            return []

        rows = (
            self._session.query(ChatMessageModel)
            .filter(ChatMessageModel.session_id == session_id)
            .order_by(ChatMessageModel.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [self._message_to_entity(r) for r in rows]

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _session_to_entity(model: ChatSessionModel) -> ChatSession:
        return ChatSession(
            id=model.id,
            project_id=model.project_id,
            user_id=model.user_id,
            title=model.title,
            is_active=model.is_active,
            last_message_at=model.last_message_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _message_to_entity(model: ChatMessageModel) -> ChatMessage:
        return ChatMessage(
            id=model.id,
            session_id=model.session_id,
            role=MessageRole(model.role.value),
            content=model.content,
            query_id=model.query_id,
            answer_metadata=model.answer_metadata,
            created_at=model.created_at,
        )
