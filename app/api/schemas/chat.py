from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator


class ChatSessionBase(BaseModel):
    """Base chat session schema."""
    project_id: UUID = Field(
        ...,
        description="Project ID this chat session belongs to"
    )
    title: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional human-readable title for the session"
    )


class ChatSessionCreate(ChatSessionBase):
    """Schema for creating a new chat session."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "660e8400-e29b-41d4-a716-446655440000",
                "title": "Research Discussion",
            }
        }
    )


class ChatSessionUpdate(BaseModel):
    """Schema for updating a chat session."""
    title: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional new title for the session"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Whether the session should be active"
    )

    @model_validator(mode="after")
    def validate_payload(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Research Discussion",
                "is_active": True
            }
        }
    )


class ChatSessionSummary(BaseModel):
    """Summary information for a chat session."""
    id: UUID = Field(..., description="Session unique identifier")
    project_id: UUID = Field(..., description="Parent project ID")
    title: Optional[str] = Field(None, description="Session title")
    is_active: bool = Field(default=True, description="Whether session is active")
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_message_at: Optional[datetime] = Field(None, description="Last message timestamp")
    message_count: int = Field(default=0, description="Total messages in session")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "990e8400-e29b-41d4-a716-446655440000",
                "project_id": "660e8400-e29b-41d4-a716-446655440000",
                "title": "Research Discussion",
                "is_active": True,
                "created_at": "2024-03-08T10:00:00Z",
                "updated_at": "2024-03-08T15:30:00Z",
                "last_message_at": "2024-03-08T15:30:00Z",
                "message_count": 12
            }
        }
    )


class ChatMessageBase(BaseModel):
    """Base chat message schema."""
    role: str = Field(
        ...,
        description="Message role: 'user' for user messages, 'assistant' for AI responses"
    )
    content: str = Field(
        ...,
        description="Message content"
    )


class ChatMessageRead(ChatMessageBase):
    """Chat message response schema."""
    id: UUID = Field(..., description="Message unique identifier")
    session_id: UUID = Field(..., description="Parent session ID")
    created_at: datetime = Field(..., description="Message timestamp")
    citations: Optional[List[dict]] = Field(
        None,
        description="Citations if this is an assistant message with RAG results"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "aa0e8400-e29b-41d4-a716-446655440000",
                "session_id": "990e8400-e29b-41d4-a716-446655440000",
                "role": "user",
                "content": "What are the main findings?",
                "created_at": "2024-03-08T14:30:00Z"
            }
        }
    )


class ChatSessionWithMessages(ChatSessionSummary):
    """Chat session including all messages."""
    messages: List[ChatMessageRead] = Field(
        default_factory=list,
        description="All messages in this session"
    )
