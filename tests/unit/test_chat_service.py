import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.chat.service import ChatService
from app.domain.chat.entities import ChatSession
from app.domain.chat.exceptions import InvalidChatSessionUpdateError


class _DummyProjectRepo:
    def __init__(self, project):
        self._project = project

    async def get_by_id_and_owner(self, project_id, owner_id):
        if self._project.id == project_id and self._project.owner_id == owner_id:
            return self._project
        return None


class _DummyChatRepo:
    def __init__(self, sessions=None):
        self.sessions = {session.id: session for session in (sessions or [])}
        self.update_calls = []

    async def create_session(self, user_id, project_id, title=None):
        session = ChatSession.create(
            project_id=project_id,
            user_id=user_id,
            title=title,
        )
        self.sessions[session.id] = session
        return session

    async def get_session(self, session_id, user_id):
        session = self.sessions.get(session_id)
        if session and session.user_id == user_id:
            return session
        return None

    async def list_sessions(self, user_id, project_id=None, skip=0, limit=100):
        sessions = [
            session
            for session in self.sessions.values()
            if session.user_id == user_id
            and session.is_active
            and (project_id is None or session.project_id == project_id)
        ]
        sessions.sort(
            key=lambda session: (
                session.last_message_at or session.created_at,
                session.created_at,
            ),
            reverse=True,
        )
        total = len(sessions)
        return sessions[skip : skip + limit], total

    async def update_session(self, session):
        self.sessions[session.id] = session
        self.update_calls.append(session)
        return session

    async def delete_session(self, session):
        self.sessions.pop(session.id, None)

    async def add_message(self, *args, **kwargs):
        raise NotImplementedError

    async def list_messages(self, *args, **kwargs):
        raise NotImplementedError

    async def list_recent_messages(self, *args, **kwargs):
        raise NotImplementedError


def test_chat_service_list_sessions_includes_message_count_and_hides_inactive():
    project_id = uuid4()
    user_id = uuid4()
    active_session = ChatSession.create(
        project_id=project_id,
        user_id=user_id,
        title="Active",
    )
    active_session.message_count = 4
    inactive_session = ChatSession.create(
        project_id=project_id,
        user_id=user_id,
        title="Archived",
    )
    inactive_session.message_count = 9
    inactive_session.is_active = False

    chat_repo = _DummyChatRepo([active_session, inactive_session])
    service = ChatService(
        chat_repo=chat_repo,
        project_repo=_DummyProjectRepo(SimpleNamespace(id=project_id, owner_id=user_id)),
    )

    sessions = asyncio.run(service.list_sessions(user_id=user_id))

    assert len(sessions) == 1
    assert sessions[0].title == "Active"
    assert sessions[0].message_count == 4


def test_chat_service_update_session_renames_and_archives_session():
    project_id = uuid4()
    user_id = uuid4()
    session = ChatSession.create(
        project_id=project_id,
        user_id=user_id,
        title="Old title",
    )
    session.message_count = 2

    chat_repo = _DummyChatRepo([session])
    service = ChatService(
        chat_repo=chat_repo,
        project_repo=_DummyProjectRepo(SimpleNamespace(id=project_id, owner_id=user_id)),
    )

    updated = asyncio.run(
        service.update_session(
            session_id=session.id,
            user_id=user_id,
            updates={"title": "New title", "is_active": False},
        )
    )

    assert updated.title == "New title"
    assert updated.is_active is False
    assert updated.message_count == 2
    assert chat_repo.sessions[session.id].title == "New title"
    assert chat_repo.sessions[session.id].is_active is False
    assert len(chat_repo.update_calls) == 1


def test_chat_service_update_session_rejects_empty_payload():
    project_id = uuid4()
    user_id = uuid4()
    session = ChatSession.create(
        project_id=project_id,
        user_id=user_id,
        title="Old title",
    )

    chat_repo = _DummyChatRepo([session])
    service = ChatService(
        chat_repo=chat_repo,
        project_repo=_DummyProjectRepo(SimpleNamespace(id=project_id, owner_id=user_id)),
    )

    with pytest.raises(InvalidChatSessionUpdateError):
        asyncio.run(
            service.update_session(
                session_id=session.id,
                user_id=user_id,
                updates={},
            )
        )
