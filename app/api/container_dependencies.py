"""FastAPI dependency injection points using the DI container."""

from typing import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.container import Container, get_container
from app.config.settings import settings

# Application services
from app.application.documents.service import DocumentService
from app.application.documents.ingestion_service import IngestionService
from app.application.query.query_service import QueryService
from app.application.auth.service import AuthService
from app.application.users.service import UserService
from app.application.projects.service import ProjectService
from app.application.chat.service import ChatService

# Domain interfaces
from app.domain.rag.interfaces import IVectorStore

# Domain entities
from app.domain.users.entities import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False
)


# Database session

def get_db(
    container: Container = Depends(get_container),
) -> Generator[Session, None, None]:
    """Database session dependency."""
    yield from container.get_db()


# Document services

def get_document_service(
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
) -> DocumentService:
    return container.document_service(db)


def get_ingestion_service(
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
) -> IngestionService:
    return container.ingestion_service(db)


def get_query_service(
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
) -> QueryService:
    return container.query_service(db)


def get_vector_store(
    container: Container = Depends(get_container),
) -> IVectorStore:
    return container.vector_store()


# Auth & User services

def get_auth_service(
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
) -> AuthService:
    return container.auth_service(db)


def get_user_service(
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
) -> UserService:
    return container.user_service(db)


# Project service

def get_project_service(
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
) -> ProjectService:
    return container.project_service(db)


# Chat service

def get_chat_service(
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
) -> ChatService:
    return container.chat_service(db)


# Current user dependencies (resolve User domain entity from JWT)

async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
    container: Container = Depends(get_container),
) -> User:
    """Decode JWT and return current User domain entity."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_service = container._token_service
    payload = token_service.decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user_repo = container.user_repository(db)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure user account is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Ensure user has verified their email."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email first.",
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Ensure user is a superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


# Request utility dependencies

def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request."""
    return request.headers.get("User-Agent", "unknown")[:200]
