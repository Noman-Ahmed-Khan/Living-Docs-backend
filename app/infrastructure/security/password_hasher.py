"""Bcrypt password hasher — infrastructure implementation."""

from passlib.context import CryptContext

from app.domain.users.interfaces import IPasswordHasher

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class BcryptPasswordHasher(IPasswordHasher):
    """Password hasher using bcrypt via passlib."""

    def hash_password(self, plain_password: str) -> str:
        """Hash a plain password and return the bcrypt hash string."""
        return _pwd_context.hash(plain_password)

    def verify_password(self, plain_password: str, hashed: str) -> bool:
        """Verify a plain password against a stored bcrypt hash."""
        return _pwd_context.verify(plain_password, hashed)
