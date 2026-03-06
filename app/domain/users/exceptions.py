"""User domain exceptions."""

from app.domain.common.exceptions import DomainException


class UserError(DomainException):
    """Base exception for user domain."""
    pass


class UserNotFoundError(UserError):
    """User not found."""
    pass


class UserAlreadyExistsError(UserError):
    """User with this email already exists."""
    pass


class InvalidCredentialsError(UserError):
    """Invalid email or password."""
    pass


class EmailNotVerifiedError(UserError):
    """Email address not verified."""
    pass


class AccountLockedError(UserError):
    """Account is locked due to failed login attempts."""
    pass


class AccountDeactivatedError(UserError):
    """Account has been deactivated."""
    pass


class InvalidPasswordError(UserError):
    """Password does not meet requirements."""
    pass


class InvalidEmailError(UserError):
    """Invalid email format."""
    pass


class TokenExpiredError(UserError):
    """Token has expired."""
    pass


class InvalidTokenError(UserError):
    """Token is invalid or not found."""
    pass


class TokenRevokedError(UserError):
    """Token has been revoked."""
    pass


class PermissionDeniedError(UserError):
    """User does not have permission for this action."""
    pass
