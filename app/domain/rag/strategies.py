"""RAG strategy enums - defines available algorithms."""

from enum import Enum


class RetrievalStrategy(str, Enum):
    """Strategy for retrieving relevant chunks."""
    SIMILARITY = "similarity"  # Cosine similarity search
    MMR = "mmr"                # Maximal Marginal Relevance (diversity)
    HYBRID = "hybrid"          # Combination of multiple strategies


class ChunkingStrategy(str, Enum):
    """Strategy for splitting documents into chunks."""
    RECURSIVE = "recursive"         # Split on multiple delimiters
    CHARACTER = "character"         # Fixed character count
    SEMANTIC = "semantic"           # Semantic boundary detection (future)
    TOKEN = "token"                 # Token count based (future)
