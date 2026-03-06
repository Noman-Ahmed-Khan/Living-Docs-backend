"""Document business rules and validation."""

from pathlib import Path
from .exceptions import UnsupportedFileTypeError, FileTooLargeError

# Constants
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.md', '.txt', '.html', '.htm'}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class DocumentRules:
    """Business rules for document validation."""

    @staticmethod
    def validate_file_type(filename: str) -> str:
        """
        Validate file extension.

        Returns:
            The file extension

        Raises:
            UnsupportedFileTypeError: If file type not allowed
        """
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"File type '{ext}' is not supported",
                details={
                    "extension": ext,
                    "allowed_extensions": list(ALLOWED_EXTENSIONS)
                }
            )
        return ext

    @staticmethod
    def validate_file_size(size_bytes: int) -> None:
        """
        Validate file size.

        Raises:
            FileTooLargeError: If file exceeds maximum size
        """
        if size_bytes > MAX_FILE_SIZE_BYTES:
            raise FileTooLargeError(
                f"File size {size_bytes} bytes exceeds maximum {MAX_FILE_SIZE_BYTES} bytes",
                details={
                    "file_size": size_bytes,
                    "max_size": MAX_FILE_SIZE_BYTES,
                    "max_size_mb": MAX_FILE_SIZE_BYTES / (1024 * 1024)
                }
            )

    @staticmethod
    def validate_filename(filename: str) -> None:
        """Validate filename format."""
        if not filename or len(filename.strip()) == 0:
            raise ValueError("Filename cannot be empty")

        if len(filename) > 255:
            raise ValueError("Filename too long (max 255 characters)")
