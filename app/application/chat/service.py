"""Chat application service."""

import logging
from typing import List, Optional
from uuid import UUID

from app.domain.chat.interfaces import IChatRepository
from app.domain.chat.exceptions import ChatSessionNotFoundError
from app.domain.chat.entities import MessageRole
from app.domain.projects.interfaces import IProjectRepository
from app.domain.projects.exceptions import ProjectNotFoundError
from .dto import ChatSessionDTO, ChatMessageDTO

logger = logging.getLogger(__name__)


class ChatService:
    """Orchestrates chat session and message operations."""

    def __init__(
        self,
        chat_repo: IChatRepository,
        project_repo: IProjectRepository,
    ):
        self._chat_repo = chat_repo
        self._project_repo = project_repo

    async def create_session(
        self,
        user_id: UUID,
        project_id: UUID,
        title: Optional[str] = None,
    ) -> ChatSessionDTO:
        """Create a new chat session (verifies project ownership)."""
        project = await self._project_repo.get_by_id_and_owner(
            project_id, user_id
        )
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        session = await self._chat_repo.create_session(
            user_id=user_id,
            project_id=project_id,
            title=title,
        )
        logger.info(f"Chat session created: {session.id}")
        return self._session_to_dto(session)

    async def list_sessions(
        self,
        user_id: UUID,
        project_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ChatSessionDTO]:
        """List chat sessions for a user."""
        sessions, _ = await self._chat_repo.list_sessions(
            user_id=user_id,
            project_id=project_id,
            skip=skip,
            limit=limit,
        )
        return [self._session_to_dto(s) for s in sessions]

    async def delete_session(
        self, session_id: UUID, user_id: UUID
    ) -> None:
        """Delete a chat session."""
        session = await self._chat_repo.get_session(session_id, user_id)
        if not session:
            raise ChatSessionNotFoundError(f"Chat session {session_id} not found")

        await self._chat_repo.delete_session(session)
        logger.info(f"Chat session {session_id} deleted by user {user_id}")

    async def get_messages(
        self,
        session_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 200,
    ) -> List[ChatMessageDTO]:
        """Get messages for a session (ownership enforced)."""
        session = await self._chat_repo.get_session(session_id, user_id)
        if not session:
            raise ChatSessionNotFoundError(f"Chat session {session_id} not found")

        messages = await self._chat_repo.list_messages(
            session_id=session_id,
            user_id=user_id,
            skip=skip,
            limit=limit,
        )
        return [self._message_to_dto(m) for m in messages]

    @staticmethod
    def _session_to_dto(session) -> ChatSessionDTO:
        return ChatSessionDTO(
            id=session.id,
            project_id=session.project_id,
            user_id=session.user_id,
            title=session.title,
            is_active=session.is_active,
            created_at=session.created_at,
            updated_at=session.updated_at,
            last_message_at=session.last_message_at,
        )

    @staticmethod
    def _message_to_dto(message) -> ChatMessageDTO:
        return ChatMessageDTO(
            id=message.id,
            session_id=message.session_id,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
            query_id=message.query_id,
            answer_metadata=message.answer_metadata,
        )
