from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ChatSessionBase(BaseModel):
    project_id: UUID = Field(..., description="Project this chat belongs to")
    title: Optional[str] = Field(
        None, max_length=255, description="Optional human-readable title for the session"
    )


class ChatSessionCreate(ChatSessionBase):
    pass


class ChatSessionSummary(BaseModel):
    id: UUID
    project_id: UUID
    title: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ChatMessageBase(BaseModel):
    role: str  # 'user', 'assistant', 'system'
    content: str


class ChatMessageRead(ChatMessageBase):
    id: UUID
    session_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionWithMessages(ChatSessionSummary):
    messages: List[ChatMessageRead] = []