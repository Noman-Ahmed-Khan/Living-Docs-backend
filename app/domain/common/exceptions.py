"""Base domain exceptions."""


class DomainException(Exception):
    """Base exception for all domain errors."""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
