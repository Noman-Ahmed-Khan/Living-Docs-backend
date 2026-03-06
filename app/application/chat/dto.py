"""Chat application DTOs."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from uuid import UUID


@dataclass
class ChatMessageDTO:
    """Data transfer object for a chat message."""
    id: UUID
    session_id: UUID
    role: str
    content: str
    created_at: Optional[datetime] = None
    query_id: Optional[UUID] = None
    answer_metadata: Optional[str] = None


@dataclass
class ChatSessionDTO:
    """Data transfer object for a chat session."""
    id: UUID
    project_id: UUID
    user_id: UUID
    title: Optional[str]
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
