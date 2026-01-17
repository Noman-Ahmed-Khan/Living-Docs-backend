"""Application settings and configuration."""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, computed_field
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
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
    
    # ===========================================
    # DATABASE SETTINGS
    # ===========================================
    DATABASE_URL: Optional[str] = None
    
    # Database Pool Settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    
    # ===========================================
    # SECURITY / AUTH SETTINGS
    # ===========================================
    SECRET_KEY: str = "your-secret-key-here"
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
    
    # ===========================================
    # EMAIL SETTINGS
    # ===========================================
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@livingdocs.com"
    SMTP_FROM_NAME: str = "Living Docs"
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    EMAIL_TEMPLATES_DIR: str = "app/templates/email"
    
    # Google Gemini
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/embedding-001"
    
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
    
    # ===========================================
    # VALIDATORS
    # ===========================================
    
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