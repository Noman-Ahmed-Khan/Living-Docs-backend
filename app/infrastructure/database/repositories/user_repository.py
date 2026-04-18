"""SQLAlchemy user & refresh-token repository implementations."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.domain.users.entities import User, UserRole, RefreshToken
from app.domain.users.interfaces import IUserRepository, IRefreshTokenRepository
from app.infrastructure.database.models.user import (
    UserModel,
    RefreshTokenModel,
    VerificationTokenModel,
    PasswordResetTokenModel,
)
from app.config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User Repository
# ---------------------------------------------------------------------------

class SQLUserRepository(IUserRepository):
    """User repository backed by SQLAlchemy + PostgreSQL."""

    def __init__(self, session: Session):
        self._session = session

    async def save(self, user: User) -> User:
        """Create or update a user."""
        db_user = (
            self._session.query(UserModel)
            .filter(UserModel.id == user.id)
            .first()
        )

        if db_user:
            self._update_model(db_user, user)
        else:
            db_user = self._to_model(user)
            self._session.add(db_user)

        self._session.commit()
        self._session.refresh(db_user)
        return self._to_entity(db_user)

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Fetch user by primary key."""
        db_user = (
            self._session.query(UserModel)
            .filter(UserModel.id == user_id)
            .first()
        )
        return self._to_entity(db_user) if db_user else None

    async def get_by_email(self, email: str) -> Optional[User]:
        """Fetch user by email (case-insensitive)."""
        db_user = (
            self._session.query(UserModel)
            .filter(UserModel.email == email.lower().strip())
            .first()
        )
        return self._to_entity(db_user) if db_user else None

    async def delete(self, user_id: UUID) -> None:
        """Permanently delete a user (cascades via DB)."""
        # Remove associated files via the ORM relationships first
        db_user = (
            self._session.query(UserModel)
            .filter(UserModel.id == user_id)
            .first()
        )
        if db_user:
            import os
            for project in db_user.projects:
                for doc in project.documents:
                    if os.path.exists(doc.file_path):
                        try:
                            os.remove(doc.file_path)
                        except Exception:
                            pass
            self._session.delete(db_user)
            self._session.commit()

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[User], int]:
        """List users with optional active filter and pagination."""
        query = self._session.query(UserModel)
        if is_active is not None:
            query = query.filter(UserModel.is_active == is_active)
        total = query.count()
        rows = query.offset(skip).limit(limit).all()
        return [self._to_entity(r) for r in rows], total

    # ------------------------------------------------------------------
    # Token helpers (used by AuthService for verification / password reset)
    # These are thin wrappers — the tokens are *infrastructure* concerns,
    # not domain entities, so we expose helpers directly on the repo.
    # ------------------------------------------------------------------

    def create_verification_token(
        self, user_id: UUID, token_type: str = "email_verification",
        new_email: Optional[str] = None
    ) -> VerificationTokenModel:
        """Invalidate old tokens of same type and create a fresh one."""
        self._session.query(VerificationTokenModel).filter(
            and_(
                VerificationTokenModel.user_id == user_id,
                VerificationTokenModel.token_type == token_type,
                VerificationTokenModel.is_used == False,
            )
        ).update({"is_used": True})

        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.VERIFICATION_TOKEN_EXPIRE_HOURS
        )
        token = VerificationTokenModel(
            user_id=user_id,
            token=secrets.token_urlsafe(32),
            token_type=token_type,
            new_email=new_email,
            expires_at=expires_at,
        )
        self._session.add(token)
        self._session.commit()
        self._session.refresh(token)
        return token

    def get_verification_token(
        self, token: str
    ) -> Optional[VerificationTokenModel]:
        """Return a valid (unused, non-expired) verification token."""
        return (
            self._session.query(VerificationTokenModel)
            .filter(
                and_(
                    VerificationTokenModel.token == token,
                    VerificationTokenModel.is_used == False,
                    VerificationTokenModel.expires_at > datetime.now(timezone.utc),
                )
            )
            .first()
        )

    def use_verification_token(
        self, token: VerificationTokenModel
    ) -> None:
        """Mark a token as used."""
        token.is_used = True
        token.used_at = datetime.now(timezone.utc)
        self._session.add(token)
        self._session.commit()

    def create_password_reset_token(
        self, user_id: UUID
    ) -> PasswordResetTokenModel:
        """Invalidate old reset tokens and create a fresh one."""
        self._session.query(PasswordResetTokenModel).filter(
            and_(
                PasswordResetTokenModel.user_id == user_id,
                PasswordResetTokenModel.is_used == False,
            )
        ).update({"is_used": True})

        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
        )
        token = PasswordResetTokenModel(
            user_id=user_id,
            token=secrets.token_urlsafe(32),
            expires_at=expires_at,
        )
        self._session.add(token)
        self._session.commit()
        self._session.refresh(token)
        return token

    def get_password_reset_token(
        self, token: str
    ) -> Optional[PasswordResetTokenModel]:
        """Return a valid (unused, non-expired) password reset token."""
        return (
            self._session.query(PasswordResetTokenModel)
            .filter(
                and_(
                    PasswordResetTokenModel.token == token,
                    PasswordResetTokenModel.is_used == False,
                    PasswordResetTokenModel.expires_at > datetime.now(timezone.utc),
                )
            )
            .first()
        )

    def use_password_reset_token(
        self, token: PasswordResetTokenModel
    ) -> None:
        """Mark a password reset token as used."""
        token.is_used = True
        token.used_at = datetime.now(timezone.utc)
        self._session.add(token)
        self._session.commit()

    async def cleanup_deactivated_users(self) -> int:
        """Delete users deactivated more than DEACTIVATION_RETENTION_DAYS ago."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        expired = (
            self._session.query(UserModel)
            .filter(
                UserModel.is_active == False,
                UserModel.deactivated_at <= cutoff,
            )
            .all()
        )
        count = 0
        for user in expired:
            await_del = User(
                id=user.id, email=user.email, hashed_password=user.hashed_password
            )
            import os
            for project in user.projects:
                for doc in project.documents:
                    if os.path.exists(doc.file_path):
                        try:
                            os.remove(doc.file_path)
                        except Exception:
                            pass
            self._session.delete(user)
            count += 1
        self._session.commit()
        return count

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        """Convert ORM model → domain entity."""
        # The current user table only stores the superuser flag, so derive
        # the domain role from that persisted value.
        role = UserRole.SUPERUSER if model.is_superuser else UserRole.USER
        return User(
            id=model.id,
            email=model.email,
            hashed_password=model.hashed_password,
            full_name=model.full_name,
            is_active=model.is_active,
            is_verified=model.is_verified,
            is_superuser=model.is_superuser,
            role=role,
            failed_login_attempts=model.failed_login_attempts,
            locked_until=model.locked_until,
            password_changed_at=model.password_changed_at,
            last_login_at=model.last_login_at,
            deactivated_at=model.deactivated_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_model(entity: User) -> UserModel:
        """Convert domain entity → ORM model."""
        return UserModel(
            id=entity.id,
            email=entity.email,
            hashed_password=entity.hashed_password,
            full_name=entity.full_name,
            is_active=entity.is_active,
            is_verified=entity.is_verified,
            is_superuser=entity.is_superuser
            or entity.role == UserRole.SUPERUSER,
            failed_login_attempts=entity.failed_login_attempts,
            locked_until=entity.locked_until,
            password_changed_at=entity.password_changed_at,
            last_login_at=entity.last_login_at,
            deactivated_at=entity.deactivated_at,
            created_at=entity.created_at,
        )

    @staticmethod
    def _update_model(model: UserModel, entity: User) -> None:
        """Update mutable fields of an existing ORM model from entity."""
        model.email = entity.email
        model.hashed_password = entity.hashed_password
        model.full_name = entity.full_name
        model.is_active = entity.is_active
        model.is_verified = entity.is_verified
        model.is_superuser = entity.is_superuser or entity.role == UserRole.SUPERUSER
        model.failed_login_attempts = entity.failed_login_attempts
        model.locked_until = entity.locked_until
        model.password_changed_at = entity.password_changed_at
        model.last_login_at = entity.last_login_at
        model.deactivated_at = entity.deactivated_at


# ---------------------------------------------------------------------------
# Refresh Token Repository
# ---------------------------------------------------------------------------

class SQLRefreshTokenRepository(IRefreshTokenRepository):
    """Refresh token repository backed by SQLAlchemy."""

    def __init__(self, session: Session):
        self._session = session

    async def save(self, token: RefreshToken) -> RefreshToken:
        """Persist a new refresh token."""
        db_token = RefreshTokenModel(
            id=token.id,
            token=token.token,
            user_id=token.user_id,
            expires_at=token.expires_at,
            family_id=token.family_id,
            device_info=token.device_info,
            ip_address=token.ip_address,
            is_revoked=token.is_revoked,
            created_at=token.created_at,
        )
        self._session.add(db_token)
        self._session.commit()
        self._session.refresh(db_token)
        return self._to_entity(db_token)

    async def get_by_token(self, token: str) -> Optional[RefreshToken]:
        """Get any token by string (revoked or not)."""
        db = (
            self._session.query(RefreshTokenModel)
            .filter(RefreshTokenModel.token == token)
            .first()
        )
        return self._to_entity(db) if db else None

    async def get_active_by_token(self, token: str) -> Optional[RefreshToken]:
        """Get a non-revoked, non-expired token."""
        db = (
            self._session.query(RefreshTokenModel)
            .filter(
                and_(
                    RefreshTokenModel.token == token,
                    RefreshTokenModel.is_revoked == False,
                    RefreshTokenModel.expires_at > datetime.now(timezone.utc),
                )
            )
            .first()
        )
        return self._to_entity(db) if db else None

    async def revoke_token(self, token: RefreshToken) -> None:
        """Revoke a specific token."""
        db = (
            self._session.query(RefreshTokenModel)
            .filter(RefreshTokenModel.id == token.id)
            .first()
        )
        if db:
            db.is_revoked = True
            db.revoked_at = datetime.now(timezone.utc)
            db.replaced_by = token.replaced_by
            self._session.commit()

    async def revoke_family(self, family_id: UUID) -> int:
        """Revoke all tokens in a family (reuse detected)."""
        result = (
            self._session.query(RefreshTokenModel)
            .filter(
                and_(
                    RefreshTokenModel.family_id == family_id,
                    RefreshTokenModel.is_revoked == False,
                )
            )
            .update(
                {"is_revoked": True, "revoked_at": datetime.now(timezone.utc)}
            )
        )
        self._session.commit()
        return result

    async def revoke_all_user_tokens(self, user_id: UUID) -> int:
        """Revoke all active tokens for a user."""
        result = (
            self._session.query(RefreshTokenModel)
            .filter(
                and_(
                    RefreshTokenModel.user_id == user_id,
                    RefreshTokenModel.is_revoked == False,
                )
            )
            .update(
                {"is_revoked": True, "revoked_at": datetime.now(timezone.utc)}
            )
        )
        self._session.commit()
        return result

    async def get_user_sessions(self, user_id: UUID) -> List[RefreshToken]:
        """Get all active sessions for a user."""
        rows = (
            self._session.query(RefreshTokenModel)
            .filter(
                and_(
                    RefreshTokenModel.user_id == user_id,
                    RefreshTokenModel.is_revoked == False,
                    RefreshTokenModel.expires_at > datetime.now(timezone.utc),
                )
            )
            .order_by(RefreshTokenModel.created_at.desc())
            .all()
        )
        return [self._to_entity(r) for r in rows]

    async def cleanup_expired_tokens(self) -> int:
        """Delete expired tokens."""
        result = (
            self._session.query(RefreshTokenModel)
            .filter(RefreshTokenModel.expires_at < datetime.now(timezone.utc))
            .delete()
        )
        self._session.commit()
        return result

    # Conversion helpers

    @staticmethod
    def _to_entity(model: RefreshTokenModel) -> RefreshToken:
        return RefreshToken(
            id=model.id,
            token=model.token,
            user_id=model.user_id,
            expires_at=model.expires_at,
            family_id=model.family_id,
            is_revoked=model.is_revoked,
            revoked_at=model.revoked_at,
            replaced_by=model.replaced_by,
            device_info=model.device_info,
            ip_address=model.ip_address,
            created_at=model.created_at,
        )
