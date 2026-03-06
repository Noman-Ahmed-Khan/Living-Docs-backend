"""Chat domain interfaces (ports)."""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID

from .entities import ChatSession, ChatMessage, MessageRole


class IChatRepository(ABC):
    """Repository interface for chat persistence."""

    @abstractmethod
    async def create_session(
        self,
        user_id: UUID,
        project_id: UUID,
        title: Optional[str] = None,
    ) -> ChatSession:
        """Create and persist a new chat session."""
        pass

    @abstractmethod
    async def get_session(
        self, session_id: UUID, user_id: UUID
    ) -> Optional[ChatSession]:
        """Get session by ID ensuring it belongs to user."""
        pass

    @abstractmethod
    async def list_sessions(
        self,
        user_id: UUID,
        project_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[ChatSession], int]:
        """List user's sessions, optionally filtered by project."""
        pass

    @abstractmethod
    async def delete_session(self, session: ChatSession) -> None:
        """Permanently delete a session and all its messages."""
        pass

    @abstractmethod
    async def add_message(
        self,
        session: ChatSession,
        role: MessageRole,
        content: str,
        query_id: Optional[UUID] = None,
        answer_metadata: Optional[str] = None,
    ) -> ChatMessage:
        """Add a message to a session and update last_message_at."""
        pass

    @abstractmethod
    async def list_messages(
        self,
        session_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 200,
    ) -> List[ChatMessage]:
        """List messages for a session (ownership check via user_id)."""
        pass
