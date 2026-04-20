import json
import logging
import re
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

from app.domain.chat.entities import MessageRole
from app.domain.chat.exceptions import ChatAccessDeniedError, ChatSessionNotFoundError
from app.domain.chat.interfaces import IChatRepository
from app.domain.rag.interfaces import IRetriever, ILLMClient
from app.domain.rag.entities import QueryRequest, QueryResult, Citation
from app.domain.rag.exceptions import (
    QueryError, InvalidQueryError, NoContextFoundError, LLMError
)
from app.domain.rag.value_objects import RetrieverConfig, QueryConfig

logger = logging.getLogger(__name__)


class QueryService:
    """
    Service for processing RAG queries.

    Orchestrates: Retrieve child chunks → Resolve parent context →
                  Format context → Generate answer → Extract citations w/ bbox
    """

    # Pattern for extracting citation IDs from LLM output (e.g., [chunk_id])
    CITATION_PATTERN = re.compile(r'\[([^\]]+)\]')

    # RAG prompt template
    SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on provided documents.
Use the conversation history only to understand follow-up questions and references.
Do not treat prior chat messages as factual evidence when the documents provide direct evidence.
Always cite your sources by referencing chunk IDs in square brackets [chunk_id].
If information is not found in the documents, clearly state that.
Keep answers concise and focused on the user's question."""
    CHAT_HISTORY_MESSAGE_LIMIT = 8
    CHAT_HISTORY_SNIPPET_LIMIT = 800

    def __init__(
        self,
        retriever: IRetriever,
        llm_client: ILLMClient,
        retriever_config: RetrieverConfig,
        query_config: QueryConfig,
        chat_repo: Optional[IChatRepository] = None,
    ):
        """
        Initialize query service.

        Args:
            retriever: Document retriever
            llm_client: Language model client
            retriever_config: Retrieval configuration
            query_config: Query execution configuration
        """
        self._retriever = retriever
        self._llm_client = llm_client
        self._retriever_config = retriever_config
        self._query_config = query_config
        self._chat_repo = chat_repo

    async def query(
        self,
        question: str,
        project_id: UUID,
        user_id: UUID,
        document_ids: Optional[List[UUID]] = None,
        session_id: Optional[UUID] = None,
        retrieval_strategy: Optional[str] = None,
        top_k: Optional[int] = None,
        include_all_sources: bool = False,
        db: Optional[Session] = None
    ) -> QueryResult:
        """
        Process a user query end-to-end.

        Args:
            question: User question
            project_id: Project namespace
            user_id: User making the query
            document_ids: Optional document filter
            session_id: Optional conversation session

        Returns:
            QueryResult with answer and citations (including bbox data)
        """
        query_id = uuid4()

        try:
            # Validate query
            self._validate_query(question)

            logger.info(f"Processing query: {question[:100]}... (query_id={query_id})")

            chat_session = None
            chat_history = []
            if session_id:
                if self._chat_repo is None:
                    logger.warning(
                        "Chat session %s supplied but no chat repository is configured; "
                        "continuing without session history",
                        session_id,
                    )
                else:
                    chat_session = await self._resolve_chat_session(
                        session_id=session_id,
                        project_id=project_id,
                        user_id=user_id,
                    )
                    chat_history = await self._chat_repo.list_recent_messages(
                        session_id=session_id,
                        user_id=user_id,
                        limit=self.CHAT_HISTORY_MESSAGE_LIMIT,
                    )

            chat_history_context = self._format_chat_history(chat_history)
            retrieval_query = self._build_retrieval_query(question, chat_history_context)

            # 1. Retrieve relevant child chunks (with parent context resolved)
            try:
                chunks = await self._retriever.retrieve(
                    query=retrieval_query,
                    namespace=str(project_id),
                    top_k=self._retriever_config.top_k,
                    document_ids=document_ids
                )
            except NoContextFoundError:
                logger.warning(f"No context found for query: {question[:100]}")
                raise

            logger.info(f"Retrieved {len(chunks)} chunks for query {query_id}")

            # 2. Format context from chunks (uses parent text when available)
            context = self._format_context(chunks)

            # 3. Build prompt
            prompt = self._build_prompt(question, context, chat_history_context)

            # 4. Generate answer with LLM
            try:
                answer = await self._llm_client.generate(
                    prompt=prompt,
                    temperature=self._query_config.temperature,
                    max_tokens=self._query_config.max_tokens,
                    stream=self._query_config.stream
                )
            except LLMError as e:
                logger.error(f"LLM generation failed: {e}")
                raise QueryError(
                    "Failed to generate answer",
                    details={"error": str(e)}
                )

            logger.info(f"Generated answer for query {query_id}")

            # 5. Extract and build citations with bbox data
            if self._query_config.include_sources:
                citations = self._build_citations(answer, chunks)
            else:
                citations = []

            if chat_session and self._chat_repo:
                await self._store_chat_exchange(
                    session=chat_session,
                    question=question,
                    answer=answer,
                    query_id=query_id,
                    citations=citations,
                    session_id=session_id,
                    project_id=project_id,
                    user_id=user_id,
                    history_message_count=len(chat_history),
                )

            # 6. Create result entity
            result = QueryResult(
                id=query_id,
                query_id=query_id,
                question=question,
                answer=answer,
                citations=citations,
                metadata={
                    "project_id": str(project_id),
                    "user_id": str(user_id),
                    "session_id": str(session_id) if session_id else None,
                    "chat_history_messages": len(chat_history),
                    "chat_context_used": bool(chat_history_context),
                    "model": self._llm_client.model_name,
                    "chunk_count": len(chunks),
                    "retrieval_strategy": self._retriever._strategy.value
                }
            )

            logger.info(f"Query {query_id} completed with {len(citations)} citations")

            return result

        except (
            InvalidQueryError,
            NoContextFoundError,
            QueryError,
            ChatSessionNotFoundError,
            ChatAccessDeniedError,
        ):
            raise
        except Exception as e:
            logger.error(f"Query processing failed: {e}", exc_info=True)
            raise QueryError(
                "Failed to process query",
                details={"error": str(e), "query": question[:100]}
            )

    def _validate_query(self, question: str) -> None:
        """Validate query before processing."""
        if not question or len(question.strip()) == 0:
            raise InvalidQueryError("Question cannot be empty")

        if len(question) > 2000:
            raise InvalidQueryError("Question too long (max 2000 characters)")

    async def _resolve_chat_session(
        self,
        session_id: UUID,
        project_id: UUID,
        user_id: UUID,
    ):
        """Load and validate the chat session for the current request."""
        if self._chat_repo is None:
            return None

        session = await self._chat_repo.get_session(session_id, user_id)
        if not session:
            raise ChatSessionNotFoundError(f"Chat session {session_id} not found")

        if session.project_id != project_id:
            raise ChatAccessDeniedError(
                f"Chat session {session_id} does not belong to project {project_id}"
            )

        if not session.is_active:
            raise ChatAccessDeniedError(
                f"Chat session {session_id} is not active"
            )

        return session

    def _build_retrieval_query(self, question: str, chat_history: str) -> str:
        """Compose a retrieval query that is aware of chat history."""
        if not chat_history:
            return question

        return f"""Conversation history:
{chat_history}

Current question:
{question}"""

    def _format_chat_history(self, messages) -> str:
        """Format prior chat messages for prompt and retrieval use."""
        if not messages:
            return ""

        formatted_messages = []
        for message in messages:
            role = message.role.value if hasattr(message.role, "value") else str(message.role)
            content = self._truncate_text(message.content)
            formatted_messages.append(f"{role}: {content}")

        return "\n".join(formatted_messages)

    def _truncate_text(self, text: str) -> str:
        """Keep chat history snippets short enough for prompt reuse."""
        if len(text) <= self.CHAT_HISTORY_SNIPPET_LIMIT:
            return text
        return text[: self.CHAT_HISTORY_SNIPPET_LIMIT - 3] + "..."

    def _format_context(self, chunks) -> str:
        """Format retrieved chunks into context string for LLM.

        Uses parent_text (paragraph-level context) when available,
        falling back to child chunk text for isolated sentences.
        """
        if not chunks:
            return "No relevant documents found."

        context_parts = []
        seen_parents = set()

        for i, chunk in enumerate(chunks):
            # Prefer parent text for richer LLM context
            context_text = chunk.parent_text if chunk.parent_text else chunk.text

            # Deduplicate: if multiple children share the same parent,
            # only include the parent text once
            dedup_key = chunk.parent_id if chunk.parent_id else chunk.chunk_id
            if dedup_key in seen_parents:
                continue
            seen_parents.add(dedup_key)

            # Format: [chunk_id] (from: source_file, page: X) text...
            header = f"[{chunk.chunk_id}]"
            if chunk.metadata.source_file:
                header += f" (from: {chunk.metadata.source_file}"
                if chunk.metadata.page:
                    header += f", page: {chunk.metadata.page}"
                header += ")"

            context_parts.append(f"{header}\n{context_text}")

            # Add relevance score as comment for debugging
            if chunk.score:
                context_parts.append(f"// Relevance: {chunk.score:.3f}")

        return "\n\n".join(context_parts)

    def _build_prompt(self, question: str, context: str, chat_history: str = "") -> str:
        """Build LLM prompt with context and question."""
        history_section = ""
        if chat_history:
            history_section = f"""

<conversation_history>
{chat_history}
</conversation_history>"""

        return f"""{self.SYSTEM_PROMPT}{history_section}

<documents>
{context}
</documents>

<question>
{question}
</question>

Answer the question based on the documents provided above. Cite sources using [chunk_id] format."""

    async def _store_chat_exchange(
        self,
        session,
        question: str,
        answer: str,
        query_id: UUID,
        citations: List[Citation],
        session_id: Optional[UUID],
        project_id: UUID,
        user_id: UUID,
        history_message_count: int,
    ) -> None:
        """Persist the current turn in the chat session."""
        if self._chat_repo is None:
            return

        answer_metadata = json.dumps(
            {
                "query_id": str(query_id),
                "session_id": str(session_id) if session_id else None,
                "project_id": str(project_id),
                "user_id": str(user_id),
                "chat_history_messages": history_message_count,
                "citations": [citation.to_dict() for citation in citations],
            }
        )

        # Store both sides of the exchange so future turns can reuse the same session context.
        try:
            await self._chat_repo.add_message(
                session=session,
                role=MessageRole.USER,
                content=question,
                query_id=query_id,
            )
            await self._chat_repo.add_message(
                session=session,
                role=MessageRole.ASSISTANT,
                content=answer,
                query_id=query_id,
                answer_metadata=answer_metadata,
            )
        except Exception as exc:
            logger.warning(
                "Failed to persist chat exchange for session %s: %s",
                session_id,
                exc,
                exc_info=True,
            )

    def _build_citations(self, answer: str, chunks) -> List[Citation]:
        """
        Extract citations from answer and match with source chunks.

        Includes bbox coordinates for each citation to enable
        frontend PDF highlighting.
        """
        # Extract cited chunk IDs from answer
        cited_ids = set(self.CITATION_PATTERN.findall(answer))

        # Build lookup map: chunk_id -> chunk
        chunk_map = {str(chunk.chunk_id): chunk for chunk in chunks}

        # Build citations for referenced chunks
        citations = []
        for chunk_id in cited_ids:
            if chunk_id in chunk_map:
                chunk = chunk_map[chunk_id]

                # Extract snippet (first 200 chars)
                snippet = chunk.text[:200]
                if len(chunk.text) > 200:
                    snippet += "..."

                # Build bbox dict for API response
                bbox_dict = None
                effective_bbox = chunk.bbox or chunk.parent_bbox
                if effective_bbox:
                    bbox_dict = {
                        "x0": effective_bbox.x0,
                        "y0": effective_bbox.y0,
                        "x1": effective_bbox.x1,
                        "y1": effective_bbox.y1,
                    }

                citation = Citation(
                    chunk_id=chunk_id,
                    document_id=chunk.document_id,
                    source_file=chunk.metadata.source_file,
                    text_snippet=snippet,
                    page=chunk.metadata.page,
                    char_start=chunk.metadata.char_start,
                    char_end=chunk.metadata.char_end,
                    relevance_score=chunk.score,
                    bbox=bbox_dict,
                    parent_id=chunk.parent_id,
                )
                citations.append(citation)

        logger.debug(f"Extracted {len(citations)} citations from answer")

        return citations

    async def find_similar(
        self,
        text: str,
        project_id: UUID,
        user_id: UUID,
        document_ids: Optional[List[UUID]] = None,
        top_k: int = 5,
        db: Optional[Session] = None
    ):
        """
        Find chunks similar to provided text (without LLM generation).

        Args:
            text: Text to find similar chunks for
            project_id: Project to search in
            user_id: User making the request
            document_ids: Optional filter for specific documents
            top_k: Number of chunks to retrieve
            db: Database session (optional, for future auth checks)

        Returns:
            List of retrieved chunks with scores
        """
        # Validate input
        self._validate_query(text)

        logger.info(f"Finding similar chunks in project {project_id} for text: {text[:100]}")

        try:
            # Retrieve similar chunks
            chunks = await self._retriever.retrieve(
                query=text,
                namespace=str(project_id),
                top_k=top_k,
                document_ids=[str(did) for did in document_ids] if document_ids else None
            )

            if not chunks:
                raise NoContextFoundError(
                    "No similar chunks found for the provided text",
                    details={"project_id": str(project_id), "text_length": len(text)}
                )

            logger.info(f"Found {len(chunks)} similar chunks in project {project_id}")

            return chunks

        except NoContextFoundError:
            raise
        except Exception as e:
            logger.error(f"Similar chunks search failed: {e}", exc_info=True)
            raise NoContextFoundError(
                "Failed to find similar chunks",
                details={"error": str(e)}
            )
