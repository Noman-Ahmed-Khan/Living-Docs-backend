"""RAG domain value objects - immutable configuration and data objects."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum

from app.domain.common.value_object import ValueObject


@dataclass(frozen=True)
class BoundingBox(ValueObject):
    """Bounding box coordinates for a document element.
    
    Coordinates are normalized to the page dimensions (0.0 to 1.0)
    or in absolute points depending on the parser output.
    """
    x0: float
    y0: float
    x1: float
    y1: float
    
    def __post_init__(self):
        if self.x0 > self.x1:
            raise ValueError(f"x0 ({self.x0}) must be <= x1 ({self.x1})")
        if self.y0 > self.y1:
            raise ValueError(f"y0 ({self.y0}) must be <= y1 ({self.y1})")
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for storage."""
        return {
            "bbox_x0": self.x0,
            "bbox_y0": self.y0,
            "bbox_x1": self.x1,
            "bbox_y1": self.y1,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["BoundingBox"]:
        """Reconstruct BoundingBox from a flat metadata dict (Pinecone format)."""
        x0 = data.get("bbox_x0")
        y0 = data.get("bbox_y0")
        x1 = data.get("bbox_x1")
        y1 = data.get("bbox_y1")
        if x0 is not None and y0 is not None and x1 is not None and y1 is not None:
            return cls(x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1))
        return None
    
    @classmethod
    def from_coordinates(cls, coordinates: Any) -> Optional["BoundingBox"]:
        """Create BoundingBox from Unstructured coordinates metadata.
        
        Unstructured exposes coordinates as an object with a `points`
        collection, and some callers may already pass a plain dict or list
        of points. We normalize all of those shapes into a bounding box.
        """
        if not coordinates:
            return None
        try:
            if hasattr(coordinates, "to_dict"):
                coordinates = coordinates.to_dict()

            if isinstance(coordinates, dict):
                points = coordinates.get("points")
            elif hasattr(coordinates, "points"):
                points = getattr(coordinates, "points")
            else:
                points = coordinates

            if not points or len(points) < 2:
                return None

            xs = []
            ys = []
            for point in points:
                if point is None:
                    continue
                if hasattr(point, "x") and hasattr(point, "y"):
                    xs.append(float(point.x))
                    ys.append(float(point.y))
                    continue
                xs.append(float(point[0]))
                ys.append(float(point[1]))

            if not xs or not ys:
                return None

            return cls(
                x0=min(xs),
                y0=min(ys),
                x1=max(xs),
                y1=max(ys),
            )
        except (TypeError, IndexError, AttributeError, ValueError):
            return None


@dataclass(frozen=True)
class EmbeddingVector(ValueObject):
    """Represents a document embedding vector."""
    values: List[float]
    model: str
    dimension: int
    
    def __post_init__(self):
        if len(self.values) != self.dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.dimension}, "
                f"got {len(self.values)}"
            )


@dataclass(frozen=True)
class ChunkMetadata(ValueObject):
    """Metadata for a document chunk.
    
    Supports both legacy flat chunks and new parent-child hierarchy
    with bounding box coordinates.
    """
    source_file: str
    char_start: int
    char_end: int
    chunk_index: int
    page: Optional[int] = None
    bbox: Optional[BoundingBox] = None
    parent_id: Optional[str] = None
    chunk_type: str = "child"  # "parent" or "child"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage.
        
        Flattens bbox into top-level keys for Pinecone compatibility and
        omits optional fields with None values, since Pinecone metadata
        does not accept nulls.
        """
        result = {
            "source_file": self.source_file,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "chunk_index": self.chunk_index,
            "chunk_type": self.chunk_type,
        }
        if self.page is not None:
            result["page"] = self.page
        if self.parent_id is not None:
            result["parent_id"] = self.parent_id
        # Flatten bbox into top-level keys
        if self.bbox:
            result.update(self.bbox.to_dict())
        return {key: value for key, value in result.items() if value is not None}


@dataclass(frozen=True)
class RetrieverConfig(ValueObject):
    """Configuration for document retrieval."""
    top_k: int = 5
    score_threshold: float = 0.0
    fetch_k: int = 20  # For MMR
    lambda_mult: float = 0.5  # MMR diversity parameter
    
    def __post_init__(self):
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")
        if not 0 <= self.score_threshold <= 1:
            raise ValueError("score_threshold must be between 0 and 1")


@dataclass(frozen=True)
class QueryConfig(ValueObject):
    """Configuration for query execution."""
    temperature: float = 0.0
    max_tokens: int = 512
    include_sources: bool = True
    stream: bool = False
    
    def __post_init__(self):
        if not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")


@dataclass(frozen=True)
class ChunkerConfig(ValueObject):
    """Configuration for text chunking."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separator: str = "\n\n"
    min_chunk_size: int = 50
    
    def __post_init__(self):
        if self.chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
