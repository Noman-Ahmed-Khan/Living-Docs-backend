"""JWT + opaque refresh token service — infrastructure implementation.

The existing app uses:
- JWT (HS256) for access tokens
- secrets.token_urlsafe() opaque strings for refresh tokens (stored in DB)

This matches that convention exactly.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from jose import jwt, JWTError

from app.domain.users.interfaces import ITokenService
from app.domain.users.value_objects import TokenPair
from app.config.settings import settings


class JWTTokenService(ITokenService):
    """Token service: JWT access tokens + opaque refresh tokens."""

    def __init__(self):
        self._secret_key = settings.SECRET_KEY
        self._algorithm = settings.ALGORITHM
        self._access_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self._refresh_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS

    def create_access_token(self, user_id: UUID) -> str:
        """Create a short-lived JWT access token."""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._access_expire_minutes
        )
        payload = {
            "sub": str(user_id),
            "type": "access",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def create_refresh_token(self, user_id: UUID) -> Tuple[str, datetime]:
        """
        Create an opaque (non-JWT) refresh token.

        Returns:
            (token_string, expires_at) — token is stored in DB for validation.
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self._refresh_expire_days
        )
        return token, expires_at

    def decode_access_token(self, token: str) -> Optional[dict]:
        """
        Decode and validate a JWT access token.

        Returns payload dict on success, None if invalid or expired.
        """
        try:
            payload = jwt.decode(
                token, self._secret_key, algorithms=[self._algorithm]
            )
            if payload.get("type") != "access":
                return None
            return payload
        except JWTError:
            return None

    def create_token_pair(self, user_id: UUID) -> TokenPair:
        """Create both access + refresh tokens, returning a TokenPair."""
        access_token = self.create_access_token(user_id)
        refresh_token, _ = self.create_refresh_token(user_id)
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self._access_expire_minutes * 60,
        )
