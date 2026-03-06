import logging
import re
from uuid import UUID, uuid4
from typing import List, Optional
from sqlalchemy.orm import Session

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
    
    Orchestrates: Retrieve relevant chunks → Format context → Generate answer → Extract citations
    """
    
    # Pattern for extracting citation IDs from LLM output (e.g., [chunk_id])
    CITATION_PATTERN = re.compile(r'\[([^\]]+)\]')
    
    # RAG prompt template
    SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on provided documents.
Always cite your sources by referencing chunk IDs in square brackets [chunk_id].
If information is not found in the documents, clearly state that.
Keep answers concise and focused on the user's question."""
    
    def __init__(
        self,
        retriever: IRetriever,
        llm_client: ILLMClient,
        retriever_config: RetrieverConfig,
        query_config: QueryConfig
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
            QueryResult with answer and citations
        """
        query_id = uuid4()
        
        try:
            # Validate query
            self._validate_query(question)
            
            logger.info(f"Processing query: {question[:100]}... (query_id={query_id})")
            
            # 1. Retrieve relevant chunks
            try:
                chunks = await self._retriever.retrieve(
                    query=question,
                    namespace=str(project_id),
                    top_k=self._retriever_config.top_k,
                    document_ids=document_ids
                )
            except NoContextFoundError:
                logger.warning(f"No context found for query: {question[:100]}")
                raise
            
            logger.info(f"Retrieved {len(chunks)} chunks for query {query_id}")
            
            # 2. Format context from chunks
            context = self._format_context(chunks)
            
            # 3. Build prompt
            prompt = self._build_prompt(question, context)
            
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
            
            # 5. Extract and build citations
            if self._query_config.include_sources:
                citations = self._build_citations(answer, chunks)
            else:
                citations = []
            
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
                    "model": self._llm_client.model_name,
                    "chunk_count": len(chunks),
                    "retrieval_strategy": self._retriever._strategy.value
                }
            )
            
            logger.info(f"Query {query_id} completed with {len(citations)} citations")
            
            return result
            
        except (InvalidQueryError, NoContextFoundError, QueryError):
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
    
    def _format_context(self, chunks) -> str:
        """Format retrieved chunks into context string for LLM."""
        if not chunks:
            return "No relevant documents found."
        
        context_parts = []
        for i, chunk in enumerate(chunks):
            # Format: [chunk_id] (from: source_file, page: X) text...
            header = f"[{chunk.chunk_id}]"
            if chunk.metadata.source_file:
                header += f" (from: {chunk.metadata.source_file}"
                if chunk.metadata.page:
                    header += f", page: {chunk.metadata.page}"
                header += ")"
            
            context_parts.append(f"{header}\n{chunk.text}")
            
            # Add relevance score as comment for debugging
            if chunk.score:
                context_parts.append(f"// Relevance: {chunk.score:.3f}")
        
        return "\n\n".join(context_parts)
    
    def _build_prompt(self, question: str, context: str) -> str:
        """Build LLM prompt with context and question."""
        return f"""{self.SYSTEM_PROMPT}

<documents>
{context}
</documents>

<question>
{question}
</question>

Answer the question based on the documents provided above. Cite sources using [chunk_id] format."""
    
    def _build_citations(self, answer: str, chunks) -> List[Citation]:
        """
        Extract citations from answer and match with source chunks.
        
        Only include citations that actually appear in the answer.
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
                
                citation = Citation(
                    chunk_id=chunk_id,
                    document_id=chunk.document_id,
                    source_file=chunk.metadata.source_file,
                    text_snippet=snippet,
                    page=chunk.metadata.page,
                    char_start=chunk.metadata.char_start,
                    char_end=chunk.metadata.char_end,
                    relevance_score=chunk.score
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