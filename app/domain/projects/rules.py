"""Project domain business rules."""


class ProjectRules:
    """Business rules and constants for the project domain."""

    MAX_NAME_LENGTH = 255
    MAX_DESCRIPTION_LENGTH = 2000
    MIN_CHUNK_SIZE = 100
    MAX_CHUNK_SIZE = 4000
    MIN_CHUNK_OVERLAP = 0
    MAX_CHUNK_OVERLAP = 1000
    DEFAULT_CHUNK_SIZE = 1000
    DEFAULT_CHUNK_OVERLAP = 200

    @staticmethod
    def validate_name(name: str) -> str:
        """Validate and normalize project name."""
        name = name.strip()
        if not name:
            raise ValueError("Project name cannot be empty")
        if len(name) > ProjectRules.MAX_NAME_LENGTH:
            raise ValueError(
                f"Project name cannot exceed {ProjectRules.MAX_NAME_LENGTH} characters"
            )
        return name

    @staticmethod
    def validate_chunk_settings(chunk_size: int, chunk_overlap: int) -> None:
        """Validate RAG chunk configuration."""
        if not (ProjectRules.MIN_CHUNK_SIZE <= chunk_size <= ProjectRules.MAX_CHUNK_SIZE):
            raise ValueError(
                f"chunk_size must be between {ProjectRules.MIN_CHUNK_SIZE} and "
                f"{ProjectRules.MAX_CHUNK_SIZE}"
            )
        if not (ProjectRules.MIN_CHUNK_OVERLAP <= chunk_overlap <= ProjectRules.MAX_CHUNK_OVERLAP):
            raise ValueError(
                f"chunk_overlap must be between {ProjectRules.MIN_CHUNK_OVERLAP} and "
                f"{ProjectRules.MAX_CHUNK_OVERLAP}"
            )
