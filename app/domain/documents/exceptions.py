"""Document domain exceptions."""

from app.domain.common.exceptions import DomainException


class DocumentError(DomainException):
    """Base exception for document domain."""
    pass


class DocumentNotFoundError(DocumentError):
    """Document not found."""
    pass


class UnsupportedFileTypeError(DocumentError):
    """File type is not supported."""
    pass


class FileTooLargeError(DocumentError):
    """File exceeds maximum allowed size."""
    pass


class DocumentProcessingError(DocumentError):
    """Error during document processing."""
    pass


class InvalidDocumentStateError(DocumentError):
    """Invalid state transition attempted."""
    pass
