"""User domain value objects."""

import re
from dataclasses import dataclass

from app.domain.common.value_object import ValueObject


@dataclass(frozen=True)
class Email(ValueObject):
    """Email address value object with validation."""

    value: str

    def __post_init__(self):
        """Validate email format."""
        if not self.value or not self.value.strip():
            raise ValueError("Email cannot be empty")

        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, self.value):
            raise ValueError(f"Invalid email format: {self.value}")

        # Normalize in-place via object.__setattr__ (frozen dataclass)
        object.__setattr__(self, 'value', self.value.lower().strip())

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Password(ValueObject):
    """
    Plain-text password value object with configurable validation rules.

    Never persisted — only used during validation and hashing.
    """

    value: str
    min_length: int = 8
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    require_special: bool = False

    def __post_init__(self):
        """Validate password meets requirements."""
        if not self.value:
            raise ValueError("Password cannot be empty")

        if len(self.value) < self.min_length:
            raise ValueError(
                f"Password must be at least {self.min_length} characters"
            )

        if self.require_uppercase and not any(c.isupper() for c in self.value):
            raise ValueError(
                "Password must contain at least one uppercase letter"
            )

        if self.require_lowercase and not any(c.islower() for c in self.value):
            raise ValueError(
                "Password must contain at least one lowercase letter"
            )

        if self.require_digit and not any(c.isdigit() for c in self.value):
            raise ValueError("Password must contain at least one digit")

        if self.require_special:
            special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?')
            if not any(c in special_chars for c in self.value):
                raise ValueError(
                    "Password must contain at least one special character"
                )

    def __str__(self) -> str:
        return "***REDACTED***"  # Never log plain passwords

    def __repr__(self) -> str:
        return "Password(***)"


@dataclass(frozen=True)
class HashedPassword(ValueObject):
    """Hashed password value object."""

    value: str

    def __post_init__(self):
        """Validate hash is non-empty."""
        if not self.value or len(self.value) < 20:
            raise ValueError("Invalid password hash")

    def __str__(self) -> str:
        return "***HASH***"

    def __repr__(self) -> str:
        return "HashedPassword(***)"


@dataclass(frozen=True)
class TokenPair(ValueObject):
    """Access and refresh token pair returned after authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # seconds (30 minutes default)
