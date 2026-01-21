import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import session as db_session, crud, models
from app.schemas import chat as chat_schema
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/sessions",
    response_model=List[chat_schema.ChatSessionSummary],
    summary="List chat sessions for current user",
)
def list_sessions(
    project_id: Optional[UUID] = Query(
        default=None, description="Optional filter by project"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(db_session.get_db),
    current_user: models.User = Depends(get_current_user),
):
    sessions, _ = crud.list_chat_sessions(
        db=db,
        user_id=current_user.id,
        project_id=project_id,
        skip=skip,
        limit=limit,
    )
    return sessions


@router.post(
    "/sessions",
    response_model=chat_schema.ChatSessionSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
def create_session(
    session_in: chat_schema.ChatSessionCreate,
    db: Session = Depends(db_session.get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Verify project ownership
    project = crud.get_project(
        db, project_id=session_in.project_id, owner_id=current_user.id
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    new_session = crud.create_chat_session(
        db=db,
        user_id=current_user.id,
        project_id=session_in.project_id,
        title=session_in.title,
    )
    return new_session


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session",
)
def delete_session(
    session_id: UUID,
    db: Session = Depends(db_session.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session_obj = crud.get_chat_session(
        db, session_id=session_id, user_id=current_user.id
    )
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    crud.delete_chat_session(db, session_obj)
    return


@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[chat_schema.ChatMessageRead],
    summary="Get all messages for a chat session",
)
def get_session_messages(
    session_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(db_session.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session_obj = crud.get_chat_session(
        db, session_id=session_id, user_id=current_user.id
    )
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    messages = crud.list_chat_messages(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return messages