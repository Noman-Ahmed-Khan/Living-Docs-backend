"""Base entity class for domain objects with identity."""

from dataclasses import dataclass
from uuid import UUID
from datetime import datetime
from typing import Optional


@dataclass
class Entity:
    """Base class for entities (objects with identity)."""

    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)
