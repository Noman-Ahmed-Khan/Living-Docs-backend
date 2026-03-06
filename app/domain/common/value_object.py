"""Base value object class for immutable domain values."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject:
    """Base class for value objects (immutable, compared by value)."""
    pass
