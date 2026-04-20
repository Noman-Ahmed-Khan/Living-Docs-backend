import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.query.query_service import QueryService
from app.domain.chat.entities import ChatMessage, ChatSession, MessageRole
from app.domain.chat.exceptions import ChatAccessDeniedError
from app.domain.rag.entities import RetrievedChunk
from app.domain.rag.value_objects import ChunkMetadata, QueryConfig, RetrieverConfig
from app.domain.rag.value_objects import BoundingBox


class _DummyRetriever:
    def __init__(self, chunks):
        self._strategy = SimpleNamespace(value="similarity")
        self._chunks = chunks
        self.last_query = None
        self.last_namespace = None

    async def retrieve(self, query, namespace, top_k=5, document_ids=None):
        self.last_query = query
        self.last_namespace = namespace
        self.last_top_k = top_k
        self.last_document_ids = document_ids
        return self._chunks


class _DummyLLM:
    model_name = "dummy-model"

    def __init__(self, answer: str):
        self._answer = answer
        self.last_prompt = None

    async def generate(self, prompt, temperature=0.0, max_tokens=512, stream=False):
        self.last_prompt = prompt
        return self._answer


class _DummyChatRepo:
    def __init__(self, session, history_messages):
        self._session = session
        self._history_messages = history_messages
        self.last_limit = None
        self.saved_messages = []

    async def get_session(self, session_id, user_id):
        if session_id == self._session.id and user_id == self._session.user_id:
            return self._session
        return None

    async def list_recent_messages(self, session_id, user_id, limit=20):
        self.last_limit = limit
        if session_id != self._session.id or user_id != self._session.user_id:
            return []
        return list(self._history_messages[-limit:])

    async def add_message(self, session, role, content, query_id=None, answer_metadata=None):
        message = {
            "session_id": session.id,
            "role": role.value if hasattr(role, "value") else str(role),
            "content": content,
            "query_id": query_id,
            "answer_metadata": answer_metadata,
        }
        self.saved_messages.append(message)
        return ChatMessage.create(
            session_id=session.id,
            role=role,
            content=content,
            query_id=query_id,
            answer_metadata=answer_metadata,
        )


def _make_service(chat_repo):
    retriever = _DummyRetriever(
        [
            RetrievedChunk(
                chunk_id="chunk-1",
                text="The document mentions delayed deployment risks.",
                document_id=uuid4(),
                metadata=ChunkMetadata(
                    source_file="report.pdf",
                    char_start=0,
                    char_end=47,
                    chunk_index=0,
                ),
                score=0.93,
                bbox=BoundingBox(x0=10.0, y0=20.0, x1=60.0, y1=80.0),
            )
        ]
    )
    llm = _DummyLLM("The risks are delayed deployment [chunk-1].")
    return QueryService(
        retriever=retriever,
        llm_client=llm,
        retriever_config=RetrieverConfig(),
        query_config=QueryConfig(),
        chat_repo=chat_repo,
    ), retriever, llm


def test_query_service_uses_session_history_for_retrieval_and_persists_exchange():
    project_id = uuid4()
    user_id = uuid4()
    session = ChatSession.create(project_id=project_id, user_id=user_id, title="Research")

    history_messages = [
        ChatMessage.create(
            session_id=session.id,
            role=MessageRole.USER,
            content="We were discussing the Q4 report earlier.",
        ),
        ChatMessage.create(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content="The key findings were growth and retention.",
        ),
    ]

    chat_repo = _DummyChatRepo(session, history_messages)
    service, retriever, llm = _make_service(chat_repo)

    result = asyncio.run(
        service.query(
            question="What about the risks?",
            project_id=project_id,
            user_id=user_id,
            session_id=session.id,
        )
    )

    assert chat_repo.last_limit == service.CHAT_HISTORY_MESSAGE_LIMIT
    assert "We were discussing the Q4 report earlier." in retriever.last_query
    assert "What about the risks?" in retriever.last_query
    assert "<conversation_history>" in llm.last_prompt
    assert "The key findings were growth and retention." in llm.last_prompt
    assert len(chat_repo.saved_messages) == 2
    assert chat_repo.saved_messages[0]["role"] == "user"
    assert chat_repo.saved_messages[1]["role"] == "assistant"
    assert chat_repo.saved_messages[0]["query_id"] == result.query_id
    assert chat_repo.saved_messages[1]["query_id"] == result.query_id
    assert result.metadata["session_id"] == str(session.id)
    assert result.metadata["chat_history_messages"] == len(history_messages)
    assert result.metadata["chat_context_used"] is True
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "chunk-1"


def test_query_service_rejects_cross_project_chat_session():
    project_id = uuid4()
    other_project_id = uuid4()
    user_id = uuid4()
    session = ChatSession.create(project_id=other_project_id, user_id=user_id, title="Research")

    chat_repo = _DummyChatRepo(session, [])
    service, _, _ = _make_service(chat_repo)

    with pytest.raises(ChatAccessDeniedError):
        asyncio.run(
            service.query(
                question="What about the risks?",
                project_id=project_id,
                user_id=user_id,
                session_id=session.id,
            )
        )
