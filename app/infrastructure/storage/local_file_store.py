"""Local filesystem storage implementation."""

import os
import aiofiles
from pathlib import Path
from uuid import UUID
from typing import Optional

from app.domain.documents.interfaces import IFileStorage


class LocalFileStore(IFileStorage):
    """Local filesystem implementation of file storage."""

    def __init__(self, base_path: str):
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    async def save(
        self,
        file_data: bytes,
        filename: str,
        project_id: UUID
    ) -> str:
        """Save file to local filesystem."""
        # Create project directory
        project_dir = self._base_path / str(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        file_path = project_dir / filename

        # Write file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_data)

        return str(file_path)

    async def read(self, file_path: str) -> bytes:
        """Read file from filesystem."""
        async with aiofiles.open(file_path, 'rb') as f:
            return await f.read()

    async def delete(self, file_path: str) -> None:
        """Delete file from filesystem."""
        path = Path(file_path)
        if path.exists():
            path.unlink()

    async def exists(self, file_path: str) -> bool:
        """Check if file exists."""
        return Path(file_path).exists()
