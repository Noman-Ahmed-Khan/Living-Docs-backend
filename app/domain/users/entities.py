"""User domain entities."""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from uuid import UUID, uuid4
from typing import Optional

from app.domain.common.entity import Entity


class UserRole(str, Enum):
    """User roles."""
    USER = "user"
    ADMIN = "admin"
    SUPERUSER = "superuser"


@dataclass
class User(Entity):
    """
    User domain entity.

    Business Rules:
    - Email must be unique
    - Must be verified before certain actions
    - Can be deactivated (soft delete)
    - Failed logins trigger account lockout
    """

    # All fields must have defaults because Entity has defaults
    email: str = ""
    hashed_password: str = ""
    full_name: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    is_superuser: bool = False
    role: UserRole = UserRole.USER

    # Security tracking
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        email: str,
        hashed_password: str,
        full_name: Optional[str] = None,
        require_verification: bool = True
    ) -> "User":
        """Factory method to create a new user."""
        return cls(
            id=uuid4(),
            email=email.lower().strip(),
            hashed_password=hashed_password,
            full_name=full_name,
            is_active=True,
            is_verified=not require_verification,
            created_at=datetime.now(timezone.utc),
            password_changed_at=datetime.now(timezone.utc)
        )

    def verify_email(self) -> None:
        """Mark email as verified."""
        self.is_verified = True

    def update_email(self, new_email: str) -> None:
        """Update email address (requires re-verification)."""
        self.email = new_email.lower().strip()
        self.is_verified = False

    def change_password(self, new_hashed_password: str) -> None:
        """Change user password and reset security state."""
        self.hashed_password = new_hashed_password
        self.password_changed_at = datetime.now(timezone.utc)
        self.failed_login_attempts = 0
        self.locked_until = None

    def record_successful_login(self) -> None:
        """Record successful login."""
        self.last_login_at = datetime.now(timezone.utc)
        self.failed_login_attempts = 0
        self.locked_until = None

    def record_failed_login(
        self,
        max_attempts: int = 5,
        lockout_minutes: int = 15
    ) -> None:
        """Record failed login attempt and lock if threshold reached."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)

    def deactivate(self) -> None:
        """Deactivate user account (soft delete)."""
        self.is_active = False
        self.deactivated_at = datetime.now(timezone.utc)

    def reactivate(self) -> None:
        """Reactivate user account."""
        self.is_active = True
        self.deactivated_at = None

    def promote_to_admin(self) -> None:
        """Promote user to admin role."""
        self.role = UserRole.ADMIN

    def promote_to_superuser(self) -> None:
        """Promote user to superuser."""
        self.is_superuser = True
        self.role = UserRole.SUPERUSER

    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until

    @property
    def can_login(self) -> bool:
        """Check if user can log in."""
        return self.is_active and not self.is_locked


@dataclass
class RefreshToken(Entity):
    """
    Refresh token for maintaining sessions.

    Business Rules:
    - Belongs to single user
    - Has expiration
    - Can be revoked
    - Token rotation for security (family_id groups reuse-detection)
    """

    # All fields must have defaults because Entity has defaults
    token: str = ""
    user_id: UUID = field(default_factory=uuid4)
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    family_id: UUID = field(default_factory=uuid4)
    is_revoked: bool = False
    revoked_at: Optional[datetime] = None
    replaced_by: Optional[UUID] = None
    device_info: Optional[str] = None
    ip_address: Optional[str] = None

    @classmethod
    def create(
        cls,
        token: str,
        user_id: UUID,
        expires_at: datetime,
        family_id: UUID,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> "RefreshToken":
        """Create a new refresh token."""
        return cls(
            id=uuid4(),
            token=token,
            user_id=user_id,
            expires_at=expires_at,
            family_id=family_id,
            device_info=device_info,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc)
        )

    def revoke(self, replaced_by: Optional[UUID] = None) -> None:
        """Revoke this token."""
        self.is_revoked = True
        self.revoked_at = datetime.now(timezone.utc)
        self.replaced_by = replaced_by

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        # Normalize to aware datetime for comparison
        if expires.tzinfo is None:
            from datetime import timezone as tz
            expires = expires.replace(tzinfo=tz.utc)
        return now > expires

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not revoked and not expired)."""
        return not self.is_revoked and not self.is_expired
