"""Chat domain exceptions."""

from app.domain.common.exceptions import DomainException


class ChatError(DomainException):
    """Base exception for chat domain."""
    pass


class ChatSessionNotFoundError(ChatError):
    """Chat session not found or access denied."""
    pass


class ChatAccessDeniedError(ChatError):
    """User does not have access to this chat session."""
    pass


class InvalidChatSessionUpdateError(ChatError):
    """Chat session update payload is empty or invalid."""
    pass
