"""User application service — manages user profile, password, account."""

import logging
from typing import List, Optional
from uuid import UUID

from app.domain.users.entities import User
from app.domain.users.interfaces import (
    IUserRepository,
    IRefreshTokenRepository,
    IPasswordHasher,
)
from app.domain.users.exceptions import (
    UserNotFoundError,
    InvalidCredentialsError,
    InvalidPasswordError,
    PermissionDeniedError,
)
from app.domain.users.rules import UserRules
from .dto import UserDTO, SessionInfoDTO

logger = logging.getLogger(__name__)


class UserService:
    """Manages user profile and account operations."""

    def __init__(
        self,
        user_repo: IUserRepository,
        refresh_token_repo: IRefreshTokenRepository,
        password_hasher: IPasswordHasher,
    ):
        self._user_repo = user_repo
        self._rt_repo = refresh_token_repo
        self._hasher = password_hasher

    async def get_user(self, user_id: UUID) -> UserDTO:
        """Get user details by ID."""
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")
        return self._to_dto(user)

    async def change_password(
        self,
        current_user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        """
        Change user password while logged in.

        Validates current password, ensures new != current,
        then revokes all sessions (security best practice).
        """
        if not self._hasher.verify_password(
            current_password, current_user.hashed_password
        ):
            raise InvalidCredentialsError("Current password is incorrect")

        if self._hasher.verify_password(
            new_password, current_user.hashed_password
        ):
            raise InvalidPasswordError(
                "New password must be different from current password"
            )

        try:
            UserRules.validate_password(new_password)
        except ValueError as e:
            raise InvalidPasswordError(str(e))

        new_hash = self._hasher.hash_password(new_password)
        current_user.change_password(new_hash)
        await self._user_repo.save(current_user)
        await self._rt_repo.revoke_all_user_tokens(current_user.id)
        logger.info(f"Password changed for user {current_user.id}")

    async def deactivate_account(
        self,
        current_user: User,
        password: str,
    ) -> None:
        """Soft-delete the account (requires password confirmation)."""
        if not self._hasher.verify_password(password, current_user.hashed_password):
            raise InvalidCredentialsError("Incorrect password")

        await self._rt_repo.revoke_all_user_tokens(current_user.id)
        current_user.deactivate()
        await self._user_repo.save(current_user)
        logger.info(f"Account deactivated for user {current_user.id}")

    async def activate_account(self, current_user: User) -> None:
        """Reactivate a deactivated account."""
        if current_user.is_active:
            return
        current_user.reactivate()
        await self._user_repo.save(current_user)

    async def delete_account(
        self,
        current_user: User,
        password: str,
        confirmation: str,
    ) -> None:
        """Permanently delete account. Requires password + 'DELETE' confirmation."""
        if not self._hasher.verify_password(password, current_user.hashed_password):
            raise InvalidCredentialsError("Incorrect password")

        if confirmation != "DELETE":
            raise PermissionDeniedError(
                "Please type 'DELETE' to confirm account deletion"
            )

        await self._user_repo.delete(current_user.id)
        logger.info(f"Account permanently deleted for user {current_user.id}")

    async def list_sessions(self, user_id: UUID) -> List[SessionInfoDTO]:
        """List all active sessions for a user."""
        tokens = await self._rt_repo.get_user_sessions(user_id)
        return [
            SessionInfoDTO(
                id=t.id,
                device_info=t.device_info,
                ip_address=t.ip_address,
                created_at=t.created_at,
                expires_at=t.expires_at,
            )
            for t in tokens
        ]

    async def revoke_session(
        self, user_id: UUID, session_id: UUID
    ) -> None:
        """Revoke a specific session by its token ID."""
        sessions = await self._rt_repo.get_user_sessions(user_id)
        target = next((s for s in sessions if s.id == session_id), None)
        if not target:
            from app.domain.users.exceptions import InvalidTokenError
            raise InvalidTokenError("Session not found")
        await self._rt_repo.revoke_token(target)

    async def logout_all(self, user_id: UUID) -> int:
        """Revoke all sessions for the user."""
        count = await self._rt_repo.revoke_all_user_tokens(user_id)
        logger.info(f"Logged out {count} session(s) for user {user_id}")
        return count

    def get_security_info(self, user: User) -> dict:
        """Return security metadata for a user."""
        return {
            "email": user.email,
            "is_verified": user.is_verified,
            "password_changed_at": user.password_changed_at,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "failed_login_attempts": user.failed_login_attempts,
            "is_locked": user.is_locked,
        }

    @staticmethod
    def validate_password(password: str) -> None:
        """Validate password meets policy. Raises InvalidPasswordError."""
        try:
            UserRules.validate_password(password)
        except ValueError as e:
            raise InvalidPasswordError(str(e))

    async def update_profile(
        self,
        current_user: User,
        user_update: any # user_schema.UserUpdate
    ) -> UserDTO:
        """Update user profile (full_name)."""
        if hasattr(user_update, "full_name") and user_update.full_name is not None:
            current_user.full_name = user_update.full_name
        
        saved = await self._user_repo.save(current_user)
        logger.info(f"Profile updated for user {current_user.id}")
        return self._to_dto(saved)

    @staticmethod
    def _to_dto(user: User) -> UserDTO:
        return UserDTO(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
            password_changed_at=user.password_changed_at,
            failed_login_attempts=user.failed_login_attempts,
        )
