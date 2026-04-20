"""Chat application service."""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.domain.chat.interfaces import IChatRepository
from app.domain.chat.exceptions import ChatSessionNotFoundError, InvalidChatSessionUpdateError
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

    async def update_session(
        self,
        session_id: UUID,
        user_id: UUID,
        updates: Dict[str, Any],
    ) -> ChatSessionDTO:
        """Update a chat session title or active state."""
        if not updates:
            raise InvalidChatSessionUpdateError(
                "At least one session field must be provided"
            )

        session = await self._chat_repo.get_session(session_id, user_id)
        if not session:
            raise ChatSessionNotFoundError(f"Chat session {session_id} not found")

        if "title" in updates:
            session.title = updates["title"]
        if "is_active" in updates:
            if updates["is_active"] is None:
                raise InvalidChatSessionUpdateError(
                    "is_active must be true or false"
                )
            session.is_active = updates["is_active"]

        updated = await self._chat_repo.update_session(session)
        if not updated:
            raise ChatSessionNotFoundError(f"Chat session {session_id} not found")

        logger.info(
            "Chat session %s updated by user %s",
            session_id,
            user_id,
        )
        return self._session_to_dto(updated)

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
            message_count=getattr(session, "message_count", 0),
        )

    @staticmethod
    def _message_to_dto(message) -> ChatMessageDTO:
        citations = None
        if message.answer_metadata:
            try:
                metadata = json.loads(message.answer_metadata)
                citations = metadata.get("citations")
            except (TypeError, ValueError):
                citations = None

        return ChatMessageDTO(
            id=message.id,
            session_id=message.session_id,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
            query_id=message.query_id,
            answer_metadata=message.answer_metadata,
            citations=citations,
        )
