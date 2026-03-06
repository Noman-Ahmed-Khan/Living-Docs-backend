"""Chat domain entities."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4
from typing import Optional, List

from app.domain.common.entity import Entity


class MessageRole(str, Enum):
    """Chat message role."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ChatMessage(Entity):
    """A single message within a chat session."""

    session_id: UUID
    role: MessageRole
    content: str
    query_id: Optional[UUID] = None
    answer_metadata: Optional[str] = None

    @classmethod
    def create(
        cls,
        session_id: UUID,
        role: MessageRole,
        content: str,
        query_id: Optional[UUID] = None,
        answer_metadata: Optional[str] = None,
    ) -> "ChatMessage":
        """Factory method to create a chat message."""
        return cls(
            id=uuid4(),
            session_id=session_id,
            role=role,
            content=content,
            query_id=query_id,
            answer_metadata=answer_metadata,
            created_at=datetime.now(timezone.utc),
        )


@dataclass
class ChatSession(Entity):
    """
    A chat session grouping messages for a user+project pair.

    Business Rules:
    - Belongs to one user and one project
    - title is optional and auto-generated / user-provided
    - Deactivated sessions are hidden from list views
    """

    project_id: UUID
    user_id: UUID
    title: Optional[str] = None
    is_active: bool = True
    last_message_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        project_id: UUID,
        user_id: UUID,
        title: Optional[str] = None,
    ) -> "ChatSession":
        """Factory method to create a new chat session."""
        return cls(
            id=uuid4(),
            project_id=project_id,
            user_id=user_id,
            title=title,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

    def deactivate(self) -> None:
        """Soft-delete / hide the session."""
        self.is_active = False

    def record_message(self) -> None:
        """Update last_message_at timestamp."""
        self.last_message_at = datetime.now(timezone.utc)
