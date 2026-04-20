"""Chat API routes."""

from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status

from app.api.schemas import chat as chat_schema
from app.api.container_dependencies import (
    get_chat_service,
    get_current_active_user,
)
from app.application.chat.service import ChatService
from app.domain.users.entities import User

router = APIRouter()


@router.get(
    "/sessions",
    response_model=List[chat_schema.ChatSessionSummary],
    summary="List chat sessions for current user",
)
async def list_sessions(
    project_id: Optional[UUID] = Query(
        default=None, description="Optional filter by project"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    chat_service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """List chat sessions for current user."""
    return await chat_service.list_sessions(
        user_id=current_user.id,
        project_id=project_id,
        skip=skip,
        limit=limit
    )


@router.post(
    "/sessions",
    response_model=chat_schema.ChatSessionSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
async def create_session(
    session_in: chat_schema.ChatSessionCreate,
    chat_service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create a new chat session (verifies project ownership)."""
    return await chat_service.create_session(
        user_id=current_user.id,
        project_id=session_in.project_id,
        title=session_in.title
    )


@router.patch(
    "/sessions/{session_id}",
    response_model=chat_schema.ChatSessionSummary,
    summary="Update a chat session",
)
async def update_session(
    session_id: UUID,
    session_in: chat_schema.ChatSessionUpdate,
    chat_service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Update a chat session title or active state."""
    return await chat_service.update_session(
        session_id=session_id,
        user_id=current_user.id,
        updates=session_in.model_dump(exclude_unset=True),
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session",
    responses={204: {"description": "Chat session deleted successfully"}},
)

async def delete_session(
    session_id: UUID,
    chat_service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Delete a chat session."""
    await chat_service.delete_session(
        session_id=session_id, 
        user_id=current_user.id
    )
    return None


@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[chat_schema.ChatMessageRead],
    summary="Get all messages for a chat session",
)
async def get_session_messages(
    session_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    chat_service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get all messages for a chat session (ownership enforced)."""
    return await chat_service.get_messages(
        session_id=session_id,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
