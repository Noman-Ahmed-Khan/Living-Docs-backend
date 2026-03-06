"""Project domain exceptions."""

from app.domain.common.exceptions import DomainException


class ProjectError(DomainException):
    """Base exception for project domain."""
    pass


class ProjectNotFoundError(ProjectError):
    """Project not found or access denied."""
    pass


class ProjectArchivedError(ProjectError):
    """Operation not allowed on an archived project."""
    pass


class ProjectNameTooLongError(ProjectError):
    """Project name exceeds maximum length."""
    pass
