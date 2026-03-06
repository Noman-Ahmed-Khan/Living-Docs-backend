"""User domain interfaces (ports)."""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime

from .entities import User, RefreshToken
from .value_objects import Email, Password, HashedPassword, TokenPair


class IUserRepository(ABC):
    """Repository interface for user persistence."""

    @abstractmethod
    async def save(self, user: User) -> User:
        """Save user (create or update)."""
        pass

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address (plain string for convenience)."""
        pass

    @abstractmethod
    async def delete(self, user_id: UUID) -> None:
        """Delete user permanently."""
        pass

    @abstractmethod
    async def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> Tuple[List[User], int]:
        """List users with pagination."""
        pass


class IPasswordHasher(ABC):
    """Interface for password hashing operations."""

    @abstractmethod
    def hash_password(self, plain_password: str) -> str:
        """Hash a plain password, return hash string."""
        pass

    @abstractmethod
    def verify_password(self, plain_password: str, hashed: str) -> bool:
        """Verify plain password against stored hash."""
        pass


class ITokenService(ABC):
    """Interface for token creation operations."""

    @abstractmethod
    def create_access_token(self, user_id: UUID) -> str:
        """Create a signed JWT access token."""
        pass

    @abstractmethod
    def create_refresh_token(self, user_id: UUID) -> Tuple[str, datetime]:
        """
        Create an opaque refresh token.

        Returns:
            Tuple of (token_string, expires_at)
        """
        pass

    @abstractmethod
    def decode_access_token(self, token: str) -> Optional[dict]:
        """
        Decode and validate JWT access token.

        Returns:
            Payload dict on success, None if invalid/expired.
        """
        pass

    @abstractmethod
    def create_token_pair(self, user_id: UUID) -> TokenPair:
        """Create access + refresh token value object."""
        pass


class IRefreshTokenRepository(ABC):
    """Repository for refresh token management."""

    @abstractmethod
    async def save(self, token: RefreshToken) -> RefreshToken:
        """Save refresh token."""
        pass

    @abstractmethod
    async def get_by_token(self, token: str) -> Optional[RefreshToken]:
        """Get refresh token by token string (regardless of revocation)."""
        pass

    @abstractmethod
    async def get_active_by_token(self, token: str) -> Optional[RefreshToken]:
        """Get a non-revoked, non-expired refresh token."""
        pass

    @abstractmethod
    async def revoke_token(self, token: RefreshToken) -> None:
        """Mark token as revoked."""
        pass

    @abstractmethod
    async def revoke_family(self, family_id: UUID) -> int:
        """Revoke all tokens in a family (token reuse detected)."""
        pass

    @abstractmethod
    async def revoke_all_user_tokens(self, user_id: UUID) -> int:
        """Revoke all tokens for a user (logout-all / password change)."""
        pass

    @abstractmethod
    async def get_user_sessions(self, user_id: UUID) -> List[RefreshToken]:
        """Get all active (non-revoked, non-expired) sessions for a user."""
        pass

    @abstractmethod
    async def cleanup_expired_tokens(self) -> int:
        """Delete expired tokens, return count removed."""
        pass


class IEmailService(ABC):
    """Interface for transactional email operations."""

    @abstractmethod
    async def send_verification_email(self, email: str, token: str) -> None:
        """Send email verification link."""
        pass

    @abstractmethod
    async def send_password_reset_email(self, email: str, token: str) -> None:
        """Send password reset link."""
        pass

    @abstractmethod
    async def send_password_changed_notification(self, email: str) -> None:
        """Send password change notification."""
        pass

    @abstractmethod
    async def send_email_change_verification(
        self,
        new_email: str,
        token: str
    ) -> None:
        """Send email change verification to new address."""
        pass

    @abstractmethod
    async def send_account_deleted_notification(self, email: str) -> None:
        """Send account deletion confirmation."""
        pass

    @abstractmethod
    async def send_security_alert(self, email: str, message: str) -> None:
        """Send security alert email."""
        pass
