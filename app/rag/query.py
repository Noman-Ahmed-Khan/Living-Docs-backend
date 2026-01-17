"""RAG Query Engine using LangChain Expression Language (LCEL) with Hugging Face."""

import re
import logging
import uuid
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.documents import Document

from app.settings import settings
from app.schemas.query import QueryResponse, Citation
from .prompts import RAG_CHAT_PROMPT, get_prompt
from .retriever import DocumentRetriever, create_retriever
from .config import QueryConfig, RetrieverConfig, RetrievalStrategy
from .exceptions import QueryError


logger = logging.getLogger(__name__)


@dataclass
class QueryContext:
    """Context information for a query."""
    query: str
    documents: List[Document] = field(default_factory=list)
    formatted_context: str = ""
    cited_chunk_ids: Set[str] = field(default_factory=set)


class CitationExtractor:
    """Extracts and validates citations from LLM responses."""
    
    CITATION_PATTERN = re.compile(r'\[([^\]]+)\]')
    
    @classmethod
    def extract_cited_ids(cls, text: str) -> Set[str]:
        """Extract all citation IDs from text."""
        matches = cls.CITATION_PATTERN.findall(text)
        return {match.strip() for match in matches if match.strip()}
    
    @classmethod
    def build_citations(
        cls,
        response: str,
        documents: List[Document]
    ) -> List[Citation]:
        """
        Build citation objects for chunks actually referenced in response.
        
        Args:
            response: The LLM response text
            documents: Retrieved documents
            
        Returns:
            List of Citation objects for referenced chunks
        """
        cited_ids = cls.extract_cited_ids(response)
        
        # Build lookup map
        chunk_map = {
            doc.metadata.get('chunk_id'): doc
            for doc in documents
        }
        
        citations = []
        for chunk_id in cited_ids:
            if chunk_id in chunk_map:
                doc = chunk_map[chunk_id]
                metadata = doc.metadata
                
                citations.append(Citation(
                    chunk_id=chunk_id,
                    document_id=metadata.get('document_id'),
                    source_file=metadata.get('source_file', 'unknown'),
                    page=metadata.get('page'),
                    char_start=metadata.get('char_start'),
                    char_end=metadata.get('char_end'),
                    text_snippet=doc.page_content[:200] + "..." 
                        if len(doc.page_content) > 200 
                        else doc.page_content
                ))
        
        return citations
    
    @classmethod
    def get_all_potential_citations(
        cls,
        documents: List[Document]
    ) -> List[Citation]:
        """Build citations for all retrieved documents."""
        return [
            Citation(
                chunk_id=doc.metadata.get('chunk_id'),
                document_id=doc.metadata.get('document_id'),
                source_file=doc.metadata.get('source_file', 'unknown'),
                page=doc.metadata.get('page'),
                char_start=doc.metadata.get('char_start'),
                char_end=doc.metadata.get('char_end'),
                text_snippet=doc.page_content[:200] + "..."
                    if len(doc.page_content) > 200
                    else doc.page_content
            )
            for doc in documents
        ]


class RAGQueryEngine:
    """
    Production-ready RAG query engine using LCEL.
    
    Features:
    - Modern LCEL chain composition
    - Configurable retrieval strategies
    - Proper citation extraction
    - Error handling and logging
    """
    
    def __init__(
        self,
        project_id: str,
        query_config: Optional[QueryConfig] = None,
        retriever_config: Optional[RetrieverConfig] = None
    ):
        self.project_id = project_id
        self.query_config = query_config or QueryConfig()
        self.retriever_config = retriever_config or RetrieverConfig()
        
        # Initialize components
        self.retriever = DocumentRetriever(project_id, self.retriever_config)
        self.llm = self._create_llm()
        self.chain = self._build_chain()
    
    def _create_llm(self):
        """Create configured LLM instance."""
        logger.info(f"Initializing Hugging Face LLM with model: {settings.HUGGINGFACE_LLM_MODEL}")
        
        # Base endpoint
        llm_endpoint = HuggingFaceEndpoint(
            repo_id=settings.HUGGINGFACE_LLM_MODEL,
            huggingfacehub_api_token=settings.HUGGINGFACE_API_KEY,
            task="conversational",
            temperature=self.query_config.temperature,
            max_new_tokens=self.query_config.max_tokens,
            timeout=300
        )
        
        # Wrap for chat-style usage (better for instruct models)
        return ChatHuggingFace(llm=llm_endpoint)

    def _build_chain(self):
        """Build the LCEL chain for query processing."""
        prompt = get_prompt("rag")
        
        chain = (
            prompt
            | self.llm
            | StrOutputParser()
        )
        
        return chain
    
    def _format_context(self, documents: List[Document]) -> str:
        """Format retrieved documents as context string."""
        if not documents:
            return "No relevant documents found."
        
        context_parts = []
        for doc in documents:
            chunk_id = doc.metadata.get('chunk_id', 'unknown')
            source = doc.metadata.get('source_file', 'unknown')
            page = doc.metadata.get('page', 'N/A')
            
            header = f"[ID: {chunk_id}] (Source: {source}, Page: {page})"
            context_parts.append(f"{header}\n{doc.page_content}")
        
        return "\n\n---\n\n".join(context_parts)
    
    async def query(
        self,
        question: str,
        document_ids: Optional[List[str]] = None,
        include_all_sources: bool = False
    ) -> QueryResponse:
        """
        Process a query and return response with citations.
        
        Args:
            question: The user's question
            document_ids: Optional filter for specific documents
            include_all_sources: Include all retrieved docs in citations
            
        Returns:
            QueryResponse with answer and citations
        """
        try:
            logger.info(f"Processing query: {question[:100]}...")
            
            # 1. Retrieve relevant documents
            retrieval_result = await self.retriever.retrieve(
                question,
                document_ids=document_ids
            )
            
            documents = retrieval_result.documents
            
            # 2. Handle no results
            if not documents:
                return QueryResponse(
                    answer=self.query_config.fallback_response,
                    citations=[],
                    metadata={
                        "retrieval_strategy": self.retriever_config.strategy.value,
                        "documents_retrieved": 0
                    }
                )
            
            # 3. Format context
            context = self._format_context(documents)
            
            # 4. Generate response
            response = await self.chain.ainvoke({
                "context": context,
                "question": question
            })
            
            # 5. Extract citations
            if include_all_sources:
                citations = CitationExtractor.get_all_potential_citations(documents)
            else:
                citations = CitationExtractor.build_citations(response, documents)
            
            logger.info(
                f"Query completed. Response length: {len(response)}, "
                f"Citations: {len(citations)}"
            )
            
            return QueryResponse(
                answer=response,
                citations=citations,
                metadata={
                    "retrieval_strategy": retrieval_result.strategy.value,
                    "documents_retrieved": len(documents),
                    "scores": retrieval_result.scores[:5] if retrieval_result.scores else [],
                    "model": settings.LLM_MODEL
                }
            )
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            raise QueryError(
                "Failed to process query",
                details={"question": question, "error": str(e)}
            )
    
    async def query_with_sources(
        self,
        question: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Query with full source information.
        
        Returns a dictionary with answer, citations, and source documents.
        """
        result = await self.query(question, include_all_sources=True, **kwargs)
        
        return {
            "answer": result.answer,
            "citations": [c.dict() for c in result.citations],
            "metadata": result.metadata
        }


class QueryEngineFactory:
    """Factory for creating query engines with different configurations."""
    
    @staticmethod
    def create_default(project_id: str) -> RAGQueryEngine:
        """Create a query engine with default settings."""
        return RAGQueryEngine(project_id)
    
    @staticmethod
    def create_precise(project_id: str) -> RAGQueryEngine:
        """Create a query engine optimized for precision."""
        return RAGQueryEngine(
            project_id,
            query_config=QueryConfig(temperature=0.0),
            retriever_config=RetrieverConfig(
                strategy=RetrievalStrategy.SIMILARITY,
                score_threshold=0.7
            )
        )
    
    @staticmethod
    def create_diverse(project_id: str) -> RAGQueryEngine:
        """Create a query engine with diverse results."""
        return RAGQueryEngine(
            project_id,
            query_config=QueryConfig(temperature=0.3),
            retriever_config=RetrieverConfig(
                strategy=RetrievalStrategy.MMR,
                mmr_diversity=0.5,
                top_k=8
            )
        )


# Convenience function for backward compatibility
async def query_documents(
    project_id: str,
    question: str,
    **kwargs
) -> QueryResponse:
    """Simple function to query documents in a project."""
    engine = RAGQueryEngine(project_id)
    return await engine.query(question, **kwargs)