import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Living Docs"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"  # Change in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database
    DATABASE_URL: str = "sqlite:///./living_docs.db"
    
    # Google Gemini
    GOOGLE_API_KEY: str
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/embedding-001"
    
    # Pinecone
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str
    PINECONE_ENVIRONMENT: str = "gcp-starter"
    
    # Storage
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 50
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
