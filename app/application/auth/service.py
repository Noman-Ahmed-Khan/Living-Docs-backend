"""Auth application service — registration, login, token management."""

import logging
from typing import List, Optional
from uuid import UUID, uuid4

from app.domain.users.entities import User, RefreshToken
from app.domain.users.interfaces import (
    IUserRepository,
    IRefreshTokenRepository,
    IPasswordHasher,
    ITokenService,
    IEmailService,
)
from app.domain.users.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    EmailNotVerifiedError,
    AccountLockedError,
    AccountDeactivatedError,
    InvalidTokenError,
    TokenRevokedError,
)
from app.domain.users.rules import UserRules
from app.config.settings import settings
from app.infrastructure.database.repositories.user_repository import SQLUserRepository
from app.application.users.dto import TokenResponseDTO, SessionInfoDTO

logger = logging.getLogger(__name__)


class AuthService:
    """Orchestrates all authentication use cases."""

    def __init__(
        self,
        user_repo: SQLUserRepository,           # typed for helper methods
        refresh_token_repo: IRefreshTokenRepository,
        password_hasher: IPasswordHasher,
        token_service: ITokenService,
        email_service: IEmailService,
    ):
        self._user_repo = user_repo
        self._rt_repo = refresh_token_repo
        self._hasher = password_hasher
        self._token_service = token_service
        self._email_service = email_service

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register_user(
        self, email: str, password: str
    ) -> str:
        """
        Register a new user.

        Returns message string indicating next step.
        """
        # Uniqueness check
        existing = await self._user_repo.get_by_email(email)
        if existing:
            raise UserAlreadyExistsError(
                "An account with this email already exists."
            )

        # Hash password (validation already done at API schema level)
        hashed = self._hasher.hash_password(password)
        user = User.create(
            email=email,
            hashed_password=hashed,
            require_verification=settings.REQUIRE_EMAIL_VERIFICATION,
        )
        await self._user_repo.save(user)
        logger.info(f"New user registered: {user.id}")

        if settings.REQUIRE_EMAIL_VERIFICATION:
            token = self._user_repo.create_verification_token(user.id)
            await self._email_service.send_verification_email(
                user.email, token.token
            )
            return (
                "Registration successful. "
                "Please check your email to verify your account."
            )

        return "Registration successful."

    async def verify_email(self, token: str) -> str:
        """
        Verify email using token.

        Returns message string.
        """
        db_token = self._user_repo.get_verification_token(token)
        if not db_token:
            raise InvalidTokenError("Invalid or expired verification token.")

        user = await self._user_repo.get_by_id(db_token.user_id)
        if not user:
            raise InvalidTokenError("User not found.")

        if db_token.token_type == "email_change" and db_token.new_email:
            user.update_email(db_token.new_email)
            user.is_verified = True  # new email is pre-verified
            await self._user_repo.save(user)
            self._user_repo.use_verification_token(db_token)
            return "Email address updated successfully."

        user.verify_email()
        await self._user_repo.save(user)
        self._user_repo.use_verification_token(db_token)
        return "Email verified successfully. You can now log in."

    async def resend_verification(self, email: str) -> str:
        """
        Resend email verification.

        Always returns same message to avoid email enumeration.
        """
        _generic = (
            "If an account exists with this email, a verification link has been sent."
        )
        user = await self._user_repo.get_by_email(email)
        if not user or user.is_verified:
            return _generic

        token = self._user_repo.create_verification_token(user.id)
        await self._email_service.send_verification_email(user.email, token.token)
        return _generic

    # ------------------------------------------------------------------
    # Login / Logout
    # ------------------------------------------------------------------

    async def login(
        self,
        email: str,
        password: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponseDTO:
        """
        Authenticate user and issue token pair.

        Handles lockout, verification checks, and failed-login tracking.
        """
        credentials_error = InvalidCredentialsError(
            "Incorrect email or password"
        )

        user = await self._user_repo.get_by_email(email)
        if not user:
            raise credentials_error

        # Lockout check
        if user.is_locked:
            raise AccountLockedError(
                f"Account is temporarily locked. Try again in a few minutes."
            )

        # Password verification
        if not self._hasher.verify_password(password, user.hashed_password):
            user.record_failed_login(
                max_attempts=settings.MAX_LOGIN_ATTEMPTS,
                lockout_minutes=settings.LOCKOUT_DURATION_MINUTES,
            )
            await self._user_repo.save(user)
            raise credentials_error

        # Reactivate silently if deactivated (matches original behaviour)
        if not user.is_active:
            user.reactivate()

        # Email verification check
        if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
            raise EmailNotVerifiedError(
                "Please verify your email before logging in."
            )

        # Record successful login
        user.record_successful_login()
        await self._user_repo.save(user)

        # Create token pair
        access_token = self._token_service.create_access_token(user.id)
        refresh_str, refresh_expires = self._token_service.create_refresh_token(user.id)

        # Persist refresh token
        rt = RefreshToken.create(
            token=refresh_str,
            user_id=user.id,
            expires_at=refresh_expires,
            family_id=uuid4(),
            device_info=device_info,
            ip_address=ip_address,
        )
        await self._rt_repo.save(rt)

        return TokenResponseDTO(
            access_token=access_token,
            refresh_token=refresh_str,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_token(
        self,
        refresh_token_str: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenResponseDTO:
        """
        Rotate refresh token and issue new token pair.

        Implements token-reuse detection via family_id.
        """
        db_token = await self._rt_repo.get_by_token(refresh_token_str)

        if not db_token:
            raise InvalidTokenError("Invalid refresh token")

        # Token reuse detection
        if db_token.is_revoked:
            await self._rt_repo.revoke_family(db_token.family_id)
            user = await self._user_repo.get_by_id(db_token.user_id)
            if user:
                await self._email_service.send_security_alert(
                    user.email,
                    "Suspicious activity detected: A refresh token was reused. "
                    "All sessions have been logged out for security.",
                )
            raise TokenRevokedError(
                "Token has been revoked. Please log in again."
            )

        if db_token.is_expired:
            raise InvalidTokenError(
                "Refresh token has expired. Please log in again."
            )

        user = await self._user_repo.get_by_id(db_token.user_id)
        if not user:
            raise InvalidTokenError("User not found.")

        # Reactivate silently if deactivated
        if not user.is_active:
            user.reactivate()
            await self._user_repo.save(user)

        # Create new token pair in same family
        access_token = self._token_service.create_access_token(user.id)
        new_refresh_str, new_expires = self._token_service.create_refresh_token(user.id)

        new_rt = RefreshToken.create(
            token=new_refresh_str,
            user_id=user.id,
            expires_at=new_expires,
            family_id=db_token.family_id,  # same family
            device_info=device_info,
            ip_address=ip_address,
        )
        saved = await self._rt_repo.save(new_rt)

        # Revoke old token, linking to replacement
        db_token.revoke(replaced_by=saved.id)
        await self._rt_repo.revoke_token(db_token)

        return TokenResponseDTO(
            access_token=access_token,
            refresh_token=new_refresh_str,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(
        self, user_id: UUID, refresh_token_str: str
    ) -> str:
        """Revoke a single session."""
        db_token = await self._rt_repo.get_by_token(refresh_token_str)
        if db_token and db_token.user_id == user_id:
            await self._rt_repo.revoke_token(db_token)
        return "Successfully logged out"

    async def logout_all(self, user_id: UUID) -> str:
        """Revoke all sessions for the user."""
        count = await self._rt_repo.revoke_all_user_tokens(user_id)
        return f"Successfully logged out from {count} session(s)"

    # ------------------------------------------------------------------
    # Password Management
    # ------------------------------------------------------------------

    async def forgot_password(self, email: str) -> str:
        """Send password reset email (always returns generic message)."""
        _msg = (
            "If an account exists with this email, a password reset link has been sent."
        )
        user = await self._user_repo.get_by_email(email)
        if user and user.is_active:
            token = self._user_repo.create_password_reset_token(user.id)
            await self._email_service.send_password_reset_email(
                user.email, token.token
            )
        return _msg

    async def reset_password(self, token: str, new_password: str) -> str:
        """Reset password using the token from email."""
        db_token = self._user_repo.get_password_reset_token(token)
        if not db_token:
            raise InvalidTokenError("Invalid or expired password reset token.")

        user = await self._user_repo.get_by_id(db_token.user_id)
        if not user:
            raise InvalidTokenError("User not found.")

        new_hash = self._hasher.hash_password(new_password)
        user.change_password(new_hash)
        await self._user_repo.save(user)

        self._user_repo.use_password_reset_token(db_token)
        await self._rt_repo.revoke_all_user_tokens(user.id)

        await self._email_service.send_password_changed_notification(user.email)
        logger.info(f"Password reset for user {user.id}")
        return "Password has been reset successfully. Please log in with your new password."

    # ------------------------------------------------------------------
    # Email Management
    # ------------------------------------------------------------------

    async def request_email_change(
        self, current_user: User, new_email: str, password: str
    ) -> str:
        """Request an email address change (sends verification to new email)."""
        if not self._hasher.verify_password(password, current_user.hashed_password):
            raise InvalidCredentialsError("Password is incorrect")

        existing = await self._user_repo.get_by_email(new_email)
        if existing:
            raise UserAlreadyExistsError("This email is already in use")

        token = self._user_repo.create_verification_token(
            current_user.id,
            token_type="email_change",
            new_email=new_email.lower().strip(),
        )
        await self._email_service.send_email_change_verification(
            new_email, token.token
        )
        return "Verification email sent to your new email address."

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    async def get_sessions(
        self, user_id: UUID, current_ip: Optional[str] = None
    ) -> List[SessionInfoDTO]:
        """Return all active sessions for a user."""
        tokens = await self._rt_repo.get_user_sessions(user_id)
        return [
            SessionInfoDTO(
                id=t.id,
                device_info=t.device_info,
                ip_address=t.ip_address,
                created_at=t.created_at,
                expires_at=t.expires_at,
                is_current=(t.ip_address == current_ip) if current_ip else False,
            )
            for t in tokens
        ]

    async def revoke_session(self, user_id: UUID, session_id: UUID) -> str:
        """Revoke a specific session by its ID."""
        sessions = await self._rt_repo.get_user_sessions(user_id)
        target = next((s for s in sessions if s.id == session_id), None)
        if not target:
            raise InvalidTokenError("Session not found")
        await self._rt_repo.revoke_token(target)
        return "Session revoked successfully"
