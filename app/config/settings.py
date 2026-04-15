"""Unified application settings and configuration."""

import os
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, computed_field


# RAG CONFIGURATION ENUMS AND DATACLASSES

class ChunkingStrategy(str, Enum):
    """Available chunking strategies."""
    FIXED_SIZE = "fixed_size"
    RECURSIVE = "recursive"
    SEMANTIC = "semantic"
    SENTENCE = "sentence"


class RetrievalStrategy(str, Enum):
    """Available retrieval strategies."""
    SIMILARITY = "similarity"
    MMR = "mmr"  # Maximal Marginal Relevance
    HYBRID = "hybrid"


@dataclass
class ChunkerConfig:
    """Configuration for document chunking."""
    strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE
    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_size: int = 100
    separators: List[str] = field(default_factory=lambda: [
        "\n\n\n",
        "\n\n",
        "\n",
        ". ",
        "! ",
        "? ",
        "; ",
        ", ",
        " ",
        ""
    ])
    preserve_paragraphs: bool = True


@dataclass
class RetrieverConfig:
    """Configuration for document retrieval."""
    strategy: RetrievalStrategy = RetrievalStrategy.MMR
    top_k: int = 5
    score_threshold: float = 0.5
    fetch_k: int = 20
    lambda_mult: float = 0.3  # Lambda for MMR (Maximal Marginal Relevance)
    mmr_diversity: float = 0.3  # Lambda for MMR
    rerank_enabled: bool = True
    max_rerank_candidates: int = 20


@dataclass
class QueryConfig:
    """Configuration for query processing."""
    temperature: float = 0.0
    max_tokens: int = 2048
    include_sources: bool = True
    citation_required: bool = True
    fallback_response: str = "I don't have enough information in the provided documents to answer this question."


@dataclass
class RAGConfig:
    """Master configuration for RAG pipeline."""
    chunker_config: ChunkerConfig = field(default_factory=ChunkerConfig)
    retriever_config: RetrieverConfig = field(default_factory=RetrieverConfig)
    query_config: QueryConfig = field(default_factory=QueryConfig)
    retrieval_strategy: str = "mmr"


# MAIN SETTINGS CLASS

class Settings(BaseSettings):
    """
    Unified application settings loaded from environment variables.
    
    This is the single source of truth for all configuration across:
    - API settings
    - Database configuration
    - Authentication & security
    - Email configuration
    - RAG pipeline settings
    - File storage
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # APPLICATION SETTINGS

    PROJECT_NAME: str = "Living Docs"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    ENVIRONMENT: str = Field(default="development")

    # URLs
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # DATABASE SETTINGS

    DATABASE_URL: Optional[str] = None

    # Database Pool Settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # SECURITY / AUTHENTICATION SETTINGS

    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 1

    # Security Policies
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30
    PASSWORD_MIN_LENGTH: int = 8
    REQUIRE_EMAIL_VERIFICATION: bool = False

    # EMAIL SETTINGS

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@livingdocs.com"
    SMTP_FROM_NAME: str = "Living Docs"
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    EMAIL_TEMPLATES_DIR: str = "app/templates/email"

    # HUGGINGFACE (LLM & EMBEDDINGS)

    HUGGINGFACE_API_KEY: Optional[str] = None
    HUGGINGFACE_LLM_MODEL: str = "bigscience/bloom-560m"
    HUGGINGFACE_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # PINECONE VECTOR DATABASE SETTINGS

    PINECONE_API_KEY: Optional[str] = None
    PINECONE_INDEX_NAME: str = "livingdocs"
    PINECONE_ENVIRONMENT: str = "gcp-starter"

    # FILE STORAGE SETTINGS

    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50

    # RAG PIPELINE SETTINGS

    DEFAULT_CHUNK_SIZE: int = Field(default=1000, ge=100, le=4000)
    DEFAULT_CHUNK_OVERLAP: int = Field(default=200, ge=0, le=1000)
    DEFAULT_TOP_K: int = Field(default=5, ge=1, le=20)
    DEFAULT_RETRIEVAL_STRATEGY: str = Field(default="mmr")
    DEFAULT_TEMPERATURE: float = 0.0
    MAX_TOKENS: int = 512

    # COMPUTED PROPERTIES

    @computed_field
    @property
    def EMBEDDING_MODEL(self) -> str:
        """Alias for embedding model (for RAG compatibility)."""
        return self.HUGGINGFACE_EMBEDDING_MODEL

    @computed_field
    @property
    def LLM_MODEL(self) -> str:
        """Alias for LLM model (for RAG compatibility)."""
        return self.HUGGINGFACE_LLM_MODEL

    @computed_field
    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @computed_field
    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse allowed origins into a list."""
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        origins = self.ALLOWED_ORIGINS.strip('"').strip("'")
        return [origin.strip() for origin in origins.split(",") if origin.strip()]

    @computed_field
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == "production"

    @computed_field
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT == "development" or self.DEBUG

    @computed_field
    @property
    def email_enabled(self) -> bool:
        """Check if email is configured."""
        return bool(self.SMTP_USER and self.SMTP_PASSWORD)

    @computed_field
    @property
    def rag_enabled(self) -> bool:
        """Check if RAG is fully configured."""
        return bool(self.HUGGINGFACE_API_KEY and self.PINECONE_API_KEY)

    @computed_field
    @property
    def RAG_CONFIG(self) -> RAGConfig:
        """Get RAG configuration with values from settings."""
        return RAGConfig(
            chunker_config=ChunkerConfig(
                strategy=ChunkingStrategy.RECURSIVE,
                chunk_size=self.DEFAULT_CHUNK_SIZE,
                chunk_overlap=self.DEFAULT_CHUNK_OVERLAP,
            ),
            retriever_config=RetrieverConfig(
                strategy=RetrievalStrategy(self.DEFAULT_RETRIEVAL_STRATEGY),
                top_k=self.DEFAULT_TOP_K,
            ),
            query_config=QueryConfig(
                temperature=self.DEFAULT_TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
            ),
            retrieval_strategy=self.DEFAULT_RETRIEVAL_STRATEGY,
        )

    # VALIDATORS

    @field_validator("DEBUG", mode="before")
    @classmethod
    def validate_debug_flag(cls, value):
        """Accept common shell-style debug values without crashing startup."""
        if isinstance(value, bool):
            return value
        if value is None:
            return False

        normalized = str(value).strip().strip('"').strip("'").lower()
        truthy = {"1", "true", "yes", "on", "debug", "development"}
        falsy = {"0", "false", "no", "off", "release", "prod", "production"}

        if normalized in truthy:
            return True
        if normalized in falsy:
            return False
        return value

    @field_validator("DEFAULT_RETRIEVAL_STRATEGY")
    @classmethod
    def validate_retrieval_strategy(cls, v: str) -> str:
        """Validate retrieval strategy value."""
        v = v.strip('"').strip("'").lower()
        valid_strategies = {"similarity", "mmr", "hybrid"}
        if v not in valid_strategies:
            raise ValueError(f"Invalid retrieval strategy: {v}. Must be one of {valid_strategies}")
        return v

    @field_validator("UPLOAD_DIR")
    @classmethod
    def validate_upload_dir(cls, v: str) -> str:
        """Ensure upload directory path is valid."""
        return os.path.normpath(v)

    def validate_required_for_rag(self) -> List[str]:
        """Validate that all required settings for RAG are configured."""
        missing = []
        if not self.HUGGINGFACE_API_KEY:
            missing.append("HUGGINGFACE_API_KEY")
        if not self.PINECONE_API_KEY:
            missing.append("PINECONE_API_KEY")
        if not self.PINECONE_INDEX_NAME:
            missing.append("PINECONE_INDEX_NAME")
        return missing

    def validate_required_for_email(self) -> List[str]:
        """Validate that all required settings for email are configured."""
        missing = []
        if not self.SMTP_HOST:
            missing.append("SMTP_HOST")
        if not self.SMTP_USER:
            missing.append("SMTP_USER")
        if not self.SMTP_PASSWORD:
            missing.append("SMTP_PASSWORD")
        return missing


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
