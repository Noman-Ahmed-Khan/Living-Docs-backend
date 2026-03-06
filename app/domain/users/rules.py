"""User domain business rules."""

from .entities import User
from .value_objects import Password


class UserRules:
    """Business rules and constants for the user domain."""

    # Password policy
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = False

    # Account lockout
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15

    # Account retention after deactivation
    DEACTIVATION_RETENTION_DAYS = 30

    @staticmethod
    def validate_password(password_str: str) -> None:
        """
        Validate password meets policy.

        Raises:
            ValueError: if password does not meet requirements.
        """
        Password(
            value=password_str,
            min_length=UserRules.MIN_PASSWORD_LENGTH,
            require_uppercase=UserRules.REQUIRE_UPPERCASE,
            require_lowercase=UserRules.REQUIRE_LOWERCASE,
            require_digit=UserRules.REQUIRE_DIGIT,
            require_special=UserRules.REQUIRE_SPECIAL,
        )

    @staticmethod
    def can_user_login(user: User) -> tuple[bool, str]:
        """
        Check if user is allowed to log in.

        Returns:
            (True, "") if allowed, (False, reason) otherwise.
        """
        if not user.is_active:
            return False, "Account is deactivated"

        if user.is_locked:
            return False, f"Account is locked until {user.locked_until}"

        return True, ""

    @staticmethod
    def requires_verification(user: User) -> bool:
        """Check if user requires email verification for restricted actions."""
        return not user.is_verified
