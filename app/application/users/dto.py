"""Users application DTOs."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class UserDTO:
    """Data transfer object for a user."""
    id: UUID
    email: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    full_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    failed_login_attempts: int = 0


@dataclass
class TokenResponseDTO:
    """Data transfer object for auth token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800


@dataclass
class SessionInfoDTO:
    """Data transfer object for a session (refresh token info)."""
    id: UUID
    device_info: Optional[str]
    ip_address: Optional[str]
    created_at: Optional[datetime]
    expires_at: datetime
    is_current: bool = False
