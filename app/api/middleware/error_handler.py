"""Global error handling middleware."""

import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.domain.common.exceptions import DomainException
from app.domain.documents.exceptions import (
    DocumentError,
    DocumentNotFoundError,
    UnsupportedFileTypeError,
    FileTooLargeError,
    DocumentProcessingError,
    InvalidDocumentStateError
)
from app.domain.rag.exceptions import (
    RAGError,
    ChunkingError,
    EmbeddingError,
    VectorStoreError,
    RetrievalError,
    LLMError,
    QueryError,
    InvalidQueryError,
    NoContextFoundError
)
from app.domain.users.exceptions import (
    UserError,
    UserNotFoundError,
    UserAlreadyExistsError,
    InvalidCredentialsError,
    EmailNotVerifiedError,
    AccountLockedError,
    AccountDeactivatedError,
    InvalidPasswordError,
    InvalidEmailError,
    TokenExpiredError,
    InvalidTokenError,
    TokenRevokedError,
    PermissionDeniedError,
)
from app.domain.projects.exceptions import (
    ProjectError,
    ProjectNotFoundError,
    ProjectArchivedError,
    ProjectNameTooLongError,
)
from app.domain.chat.exceptions import (
    ChatError,
    ChatSessionNotFoundError,
    ChatAccessDeniedError,
    InvalidChatSessionUpdateError,
)

logger = logging.getLogger(__name__)

# Map domain exceptions to HTTP status codes
EXCEPTION_STATUS_MAP = {
    # Document exceptions
    DocumentNotFoundError: status.HTTP_404_NOT_FOUND,
    UnsupportedFileTypeError: status.HTTP_400_BAD_REQUEST,
    FileTooLargeError: status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    DocumentProcessingError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    InvalidDocumentStateError: status.HTTP_400_BAD_REQUEST,
    DocumentError: status.HTTP_400_BAD_REQUEST,
    
    # RAG exceptions
    InvalidQueryError: status.HTTP_400_BAD_REQUEST,
    NoContextFoundError: status.HTTP_404_NOT_FOUND,
    ChunkingError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    EmbeddingError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    VectorStoreError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    RetrievalError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    LLMError: status.HTTP_503_SERVICE_UNAVAILABLE,
    QueryError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    RAGError: status.HTTP_500_INTERNAL_SERVER_ERROR,

    # User / Auth exceptions
    UserNotFoundError: status.HTTP_404_NOT_FOUND,
    UserAlreadyExistsError: status.HTTP_409_CONFLICT,
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    EmailNotVerifiedError: status.HTTP_403_FORBIDDEN,
    AccountLockedError: status.HTTP_403_FORBIDDEN,
    AccountDeactivatedError: status.HTTP_403_FORBIDDEN,
    InvalidPasswordError: status.HTTP_400_BAD_REQUEST,
    InvalidEmailError: status.HTTP_400_BAD_REQUEST,
    TokenExpiredError: status.HTTP_401_UNAUTHORIZED,
    InvalidTokenError: status.HTTP_401_UNAUTHORIZED,
    TokenRevokedError: status.HTTP_401_UNAUTHORIZED,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    UserError: status.HTTP_400_BAD_REQUEST,

    # Project exceptions
    ProjectNotFoundError: status.HTTP_404_NOT_FOUND,
    ProjectArchivedError: status.HTTP_400_BAD_REQUEST,
    ProjectNameTooLongError: status.HTTP_400_BAD_REQUEST,
    ProjectError: status.HTTP_400_BAD_REQUEST,

    # Chat exceptions
    ChatSessionNotFoundError: status.HTTP_404_NOT_FOUND,
    ChatAccessDeniedError: status.HTTP_403_FORBIDDEN,
    InvalidChatSessionUpdateError: status.HTTP_400_BAD_REQUEST,
    ChatError: status.HTTP_400_BAD_REQUEST,
}


async def domain_exception_handler(request: Request, exc: DomainException):
    """Handle domain exceptions and convert to HTTP responses."""
    status_code = EXCEPTION_STATUS_MAP.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.warning(
        f"Domain exception: {exc.__class__.__name__}",
        extra={
            "exception": exc.__class__.__name__,
            "error_message": exc.message,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method,
        }
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    logger.warning(
        "Validation error",
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": exc.errors()
        }
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "details": exc.errors()
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(
        "Unexpected error",
        exc_info=exc,
        extra={
            "path": request.url.path,
            "method": request.method,
        }
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "details": {}
        }
    )
