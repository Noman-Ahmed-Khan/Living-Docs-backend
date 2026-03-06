"""LangChain-based chunker implementation."""

import logging
import tempfile
from typing import List
from uuid import UUID
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredHTMLLoader
)

from app.domain.rag.interfaces import IChunker
from app.domain.rag.exceptions import ChunkingError
from app.domain.documents.exceptions import UnsupportedFileTypeError
from app.domain.documents.entities import Chunk
from app.domain.rag.value_objects import ChunkMetadata

logger = logging.getLogger(__name__)


class LangChainChunker(IChunker):
    """Chunker using LangChain's RecursiveCharacterTextSplitter with offset tracking."""
    
    SUPPORTED_FORMATS = {
        '.pdf': PyPDFLoader,
        '.docx': Docx2txtLoader,
        '.doc': Docx2txtLoader,
        '.txt': TextLoader,
        '.md': TextLoader,
        '.html': UnstructuredHTMLLoader,
        '.htm': UnstructuredHTMLLoader
    }
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 50
    ):
        """
        Initialize chunker with configuration.
        
        Args:
            chunk_size: Size of each chunk
            chunk_overlap: Overlap between chunks
            min_chunk_size: Minimum chunk size to keep
        """
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._min_chunk_size = min_chunk_size
        
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len
        )
        
        logger.info(
            f"Initialized LangChain chunker "
            f"(size={chunk_size}, overlap={chunk_overlap})"
        )
    
    async def chunk(
        self,
        file_data: bytes,
        filename: str,
        document_id: UUID
    ) -> List[Chunk]:
        """Chunk a document using LangChain loaders and splitters."""
        try:
            # Determine file type
            ext = Path(filename).suffix.lower()
            if ext not in self.SUPPORTED_FORMATS:
                raise UnsupportedFileTypeError(
                    f"File type {ext} not supported for chunking"
                )
            
            # Load document
            langchain_docs = await self._load_document(file_data, ext)
            
            if not langchain_docs:
                logger.warning(f"No content loaded from {filename}")
                return []
            
            # Split into chunks
            langchain_chunks = self._splitter.split_documents(langchain_docs)
            
            # Convert to domain Chunk entities with tracking
            chunks = []
            char_offset = 0
            
            for idx, lc_chunk in enumerate(langchain_chunks):
                text = lc_chunk.page_content
                
                # Skip small chunks
                if len(text.strip()) < self._min_chunk_size:
                    continue
                
                # Extract metadata
                metadata_dict = lc_chunk.metadata or {}
                
                # Create ChunkMetadata value object
                chunk_metadata = ChunkMetadata(
                    source_file=filename,
                    page=metadata_dict.get('page'),
                    char_start=char_offset,
                    char_end=char_offset + len(text),
                    chunk_index=idx
                )
                
                # Create domain Chunk entity
                chunk = Chunk.create(
                    text=text,
                    document_id=document_id,
                    chunk_index=idx,
                    **chunk_metadata.to_dict()
                )
                chunks.append(chunk)
                char_offset += len(text)
            
            logger.info(
                f"Chunked document {filename} into {len(chunks)} chunks "
                f"from {len(langchain_chunks)} raw chunks "
                f"(size={self._chunk_size}, overlap={self._chunk_overlap})"
            )
            
            return chunks
            
        except UnsupportedFileTypeError:
            raise
        except Exception as e:
            logger.error(f"Chunking failed for {filename}: {e}", exc_info=True)
            raise ChunkingError(
                f"Failed to chunk document: {str(e)}",
                details={"filename": filename, "error": str(e)}
            )
    
    async def _load_document(self, file_data: bytes, ext: str):
        """Load document using appropriate LangChain loader."""
        loader_class = self.SUPPORTED_FORMATS.get(ext)
        if not loader_class:
            raise UnsupportedFileTypeError(f"Unsupported file type: {ext}")
        
        # Write to temp file (LangChain loaders need file paths)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name
        
        try:
            loader = loader_class(tmp_path)
            docs = loader.load()
            logger.debug(f"Loaded {len(docs)} documents from {ext}")
            return docs
        finally:
            # Clean up temp file
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")
