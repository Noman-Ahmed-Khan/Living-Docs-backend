"""Dependency injection container - composition root."""

from functools import lru_cache
from typing import Generator, Optional

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.infrastructure.database.session import SessionLocal

# Document infrastructure
from app.infrastructure.database.repositories.document_repository import SQLDocumentRepository
from app.infrastructure.storage.local_file_store import LocalFileStore
from app.application.documents.service import DocumentService
from app.application.documents.ingestion_service import IngestionService
from app.application.query.query_service import QueryService

# RAG Infrastructure
# from app.infrastructure.rag.chunkers.langchain_chunker import LangChainChunker
from app.infrastructure.rag.chunkers.unstructured_chunker import UnstructuredLayoutChunker
from app.infrastructure.rag.embeddings.huggingface_embedder import HuggingFaceEmbedder
from app.infrastructure.rag.vectorstores.pinecone_store import PineconeVectorStore
from app.infrastructure.rag.retrievers.document_retriever import create_retriever
from app.infrastructure.rag.llm.huggingface_client import HuggingFaceLLMClient
from app.domain.rag.strategies import RetrievalStrategy
from app.domain.rag.value_objects import RetrieverConfig, QueryConfig

# User infrastructure
from app.infrastructure.database.repositories.user_repository import (
    SQLUserRepository,
    SQLRefreshTokenRepository,
)
from app.infrastructure.security.password_hasher import BcryptPasswordHasher
from app.infrastructure.security.jwt_service import JWTTokenService
from app.infrastructure.email.smtp_email_service import SMTPEmailService

# Application services
from app.application.auth.service import AuthService
from app.application.users.service import UserService

# Project infrastructure
from app.infrastructure.database.repositories.project_repository import SQLProjectRepository
from app.application.projects.service import ProjectService

# Chat infrastructure
from app.infrastructure.database.repositories.chat_repository import SQLChatRepository
from app.application.chat.service import ChatService


class Container:
    """
    Dependency injection container - composition root.

    This is the ONLY place where concrete implementations are instantiated.
    All other code depends on abstractions (interfaces).
    """

    def __init__(self):
        # Document infrastructure
        self._file_storage = LocalFileStore(settings.UPLOAD_DIR)

        # RAG infrastructure
        self._chunker = UnstructuredLayoutChunker(
            min_parent_length=60,
            min_sentence_length=20,
            max_parent_elements=5,
        )
        self._embedder: Optional[HuggingFaceEmbedder] = None
        self._vector_store: Optional[PineconeVectorStore] = None
        self._llm_client: Optional[HuggingFaceLLMClient] = None

        # User / auth infrastructure
        self._password_hasher = BcryptPasswordHasher()
        self._token_service = JWTTokenService()
        self._email_service = SMTPEmailService()

    # Database

    def get_db(self) -> Generator[Session, None, None]:
        """Database session dependency (for FastAPI Depends)."""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Lazy RAG dependencies

    def embedder(self) -> HuggingFaceEmbedder:
        """Create the embedder only when a RAG workflow needs it."""
        if self._embedder is None:
            self._embedder = HuggingFaceEmbedder(
                model_name=settings.HUGGINGFACE_EMBEDDING_MODEL,
                device="cpu",
            )
        return self._embedder

    def vector_store(self) -> PineconeVectorStore:
        """Create the vector store lazily to keep unrelated services stable."""
        if self._vector_store is None:
            self._vector_store = PineconeVectorStore(
                api_key=settings.PINECONE_API_KEY,
                index_name=settings.PINECONE_INDEX_NAME,
            )
        return self._vector_store

    def llm_client(self) -> HuggingFaceLLMClient:
        """Create the LLM client only when query generation is requested."""
        if self._llm_client is None:
            self._llm_client = HuggingFaceLLMClient(
                model_name=settings.HUGGINGFACE_LLM_MODEL,
                api_key=settings.HUGGINGFACE_API_KEY,
                provider=settings.HUGGINGFACE_LLM_PROVIDER,
                temperature=settings.RAG_CONFIG.query_config.temperature,
                max_tokens=settings.RAG_CONFIG.query_config.max_tokens,
            )
        return self._llm_client

    # Document repositories & services

    def document_repository(self, db: Session) -> SQLDocumentRepository:
        return SQLDocumentRepository(db)

    def document_service(self, db: Session) -> DocumentService:
        return DocumentService(
            document_repo=self.document_repository(db),
            file_storage=self._file_storage,
        )

    def ingestion_service(self, db: Session) -> IngestionService:
        return IngestionService(
            document_repo=self.document_repository(db),
            file_storage=self._file_storage,
            chunker=self._chunker,
            embedder=self.embedder(),
            vector_store=self.vector_store(),
        )

    # RAG query service

    def query_service(self) -> QueryService:
        retriever_config = RetrieverConfig(
            top_k=settings.RAG_CONFIG.retriever_config.top_k,
            score_threshold=settings.RAG_CONFIG.retriever_config.score_threshold,
            fetch_k=settings.RAG_CONFIG.retriever_config.fetch_k,
            lambda_mult=settings.RAG_CONFIG.retriever_config.lambda_mult,
        )
        retriever = create_retriever(
            strategy=RetrievalStrategy(settings.RAG_CONFIG.retrieval_strategy),
            embedder=self.embedder(),
            vector_store=self.vector_store(),
            config=retriever_config,
        )
        query_config = QueryConfig(
            temperature=settings.RAG_CONFIG.query_config.temperature,
            max_tokens=settings.RAG_CONFIG.query_config.max_tokens,
            include_sources=True,
            stream=False,
        )
        return QueryService(
            retriever=retriever,
            llm_client=self.llm_client(),
            retriever_config=retriever_config,
            query_config=query_config,
        )

    # User / auth repositories & services

    def user_repository(self, db: Session) -> SQLUserRepository:
        return SQLUserRepository(db)

    def refresh_token_repository(self, db: Session) -> SQLRefreshTokenRepository:
        return SQLRefreshTokenRepository(db)

    def auth_service(self, db: Session) -> AuthService:
        return AuthService(
            user_repo=self.user_repository(db),
            refresh_token_repo=self.refresh_token_repository(db),
            password_hasher=self._password_hasher,
            token_service=self._token_service,
            email_service=self._email_service,
        )

    def user_service(self, db: Session) -> UserService:
        return UserService(
            user_repo=self.user_repository(db),
            refresh_token_repo=self.refresh_token_repository(db),
            password_hasher=self._password_hasher,
        )

    # Project repositories & services

    def project_repository(self, db: Session) -> SQLProjectRepository:
        return SQLProjectRepository(db)

    def project_service(self, db: Session) -> ProjectService:
        return ProjectService(
            project_repo=self.project_repository(db),
            vector_store_factory=self.vector_store,
        )

    # Chat repositories & services

    def chat_repository(self, db: Session) -> SQLChatRepository:
        return SQLChatRepository(db)

    def chat_service(self, db: Session) -> ChatService:
        return ChatService(
            chat_repo=self.chat_repository(db),
            project_repo=self.project_repository(db),
        )


@lru_cache(maxsize=1)
def get_container() -> Container:
    """Get a singleton container instance."""
    return Container()
