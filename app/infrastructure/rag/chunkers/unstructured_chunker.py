"""Layout-aware chunker using Unstructured for parsing and sentence-level splitting."""

import logging
import re
import tempfile
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4
from pathlib import Path

from app.domain.rag.interfaces import IChunker
from app.domain.rag.exceptions import ChunkingError
from app.domain.documents.exceptions import UnsupportedFileTypeError
from app.domain.documents.entities import Chunk
from app.domain.rag.value_objects import ChunkMetadata, BoundingBox

logger = logging.getLogger(__name__)

# Sentence boundary regex — splits on . ! ? followed by whitespace
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')

# Minimum sentence length to avoid micro-fragments
_MIN_SENTENCE_LEN = 20


class UnstructuredLayoutChunker(IChunker):
    """Layout-aware chunker that produces parent-child chunk hierarchies.

    For PDFs:
        Uses Unstructured's partition_pdf with strategy="fast" to extract
        elements with layout metadata (element type, page number, bounding
        box coordinates).

    For other formats:
        Uses Unstructured's generic partition function which handles
        .docx, .pptx, .xlsx, .html, .md, .txt, etc.

    After extraction, elements are grouped into parent chunks (paragraphs /
    sections) and split into child chunks (sentences).  Each child retains
    a parent_id, page number, and approximated bounding box.
    """

    SUPPORTED_FORMATS = {
        '.pdf', '.docx', '.doc', '.pptx', '.ppt',
        '.xlsx', '.xls', '.txt', '.md', '.html', '.htm',
    }

    # Element types that carry meaningful text content
    _TEXT_ELEMENT_TYPES = {
        'NarrativeText', 'ListItem', 'Title', 'UncategorizedText',
        'FigureCaption', 'Address', 'EmailAddress', 'Header', 'Footer',
        'Table', 'Text',
    }

    def __init__(
        self,
        min_parent_length: int = 60,
        min_sentence_length: int = _MIN_SENTENCE_LEN,
        max_parent_elements: int = 5,
    ):
        """
        Args:
            min_parent_length: Minimum character length for a parent chunk.
            min_sentence_length: Minimum character length for a child sentence.
            max_parent_elements: Maximum consecutive elements to merge into
                one parent chunk.
        """
        self._min_parent_length = min_parent_length
        self._min_sentence_length = min_sentence_length
        self._max_parent_elements = max_parent_elements
        logger.info(
            "Initialized UnstructuredLayoutChunker "
            f"(min_parent={min_parent_length}, min_sentence={min_sentence_length})"
        )

    # IChunker interface

    async def chunk(
        self,
        file_data: bytes,
        filename: str,
        document_id: UUID,
    ) -> List[Chunk]:
        """Parse a document and return parent + child Chunk entities."""
        try:
            ext = Path(filename).suffix.lower()
            if ext not in self.SUPPORTED_FORMATS:
                raise UnsupportedFileTypeError(
                    f"File type {ext} not supported for chunking"
                )

            # 1. Parse document into raw elements via Unstructured
            elements = await self._parse_document(file_data, filename, ext)

            if not elements:
                logger.warning(f"No content extracted from {filename}")
                return []

            # 2. Group elements into parent chunks
            parents = self._group_into_parents(elements, filename, document_id)

            if not parents:
                logger.warning(f"No parent chunks created from {filename}")
                return []

            # 3. Split parents into child sentences and build Chunk list
            all_chunks = self._build_parent_child_chunks(
                parents, filename, document_id
            )

            parent_count = sum(
                1 for c in all_chunks if c.metadata.get("chunk_type") == "parent"
            )
            child_count = len(all_chunks) - parent_count
            logger.info(
                f"Chunked {filename} into {parent_count} parents + "
                f"{child_count} children = {len(all_chunks)} total chunks"
            )
            return all_chunks

        except UnsupportedFileTypeError:
            raise
        except Exception as e:
            logger.error(f"Chunking failed for {filename}: {e}", exc_info=True)
            raise ChunkingError(
                f"Failed to chunk document: {str(e)}",
                details={"filename": filename, "error": str(e)},
            )

    # Parsing

    async def _parse_document(
        self, file_data: bytes, filename: str, ext: str
    ) -> List[Any]:
        """Parse document bytes into Unstructured elements."""
        # Write to temp file (Unstructured needs file paths)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name

        try:
            if ext == '.pdf':
                return self._parse_pdf(tmp_path)
            else:
                return self._parse_generic(tmp_path)
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")

    def _parse_pdf(self, file_path: str) -> List[Any]:
        """Parse PDF using Unstructured with fast strategy (no OCR)."""
        try:
            from unstructured.partition.pdf import partition_pdf
            elements = partition_pdf(
                filename=file_path,
                strategy="fast",
                infer_table_structure=True,
                include_page_breaks=True,
            )
            logger.debug(f"Parsed PDF: {len(elements)} elements extracted")
            return elements
        except ImportError:
            logger.warning(
                "unstructured[pdf] not available, falling back to generic partition"
            )
            return self._parse_generic(file_path)

    def _parse_generic(self, file_path: str) -> List[Any]:
        """Parse non-PDF document using Unstructured's auto-detection."""
        from unstructured.partition.auto import partition
        elements = partition(filename=file_path)
        logger.debug(f"Parsed document: {len(elements)} elements extracted")
        return elements

    # Grouping into parent chunks

    def _group_into_parents(
        self,
        elements: List[Any],
        filename: str,
        document_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Group consecutive text elements into parent chunks.

        A new parent starts when:
        - A Title element is encountered
        - The page number changes
        - max_parent_elements consecutive elements have been merged
        """
        parents: List[Dict[str, Any]] = []
        current_texts: List[str] = []
        current_page: Optional[int] = None
        current_bbox_points: List[Tuple[float, float, float, float]] = []
        element_count = 0

        def _flush():
            nonlocal current_texts, current_page, current_bbox_points, element_count
            if not current_texts:
                return
            merged_text = "\n".join(current_texts).strip()
            if len(merged_text) < self._min_parent_length:
                # Too small to be a standalone parent – skip or merge later
                if parents:
                    # Append to previous parent
                    parents[-1]["text"] += "\n" + merged_text
                    current_texts = []
                    current_bbox_points = []
                    element_count = 0
                    return

            # Compute merged bounding box
            bbox = None
            if current_bbox_points:
                bbox = BoundingBox(
                    x0=min(b[0] for b in current_bbox_points),
                    y0=min(b[1] for b in current_bbox_points),
                    x1=max(b[2] for b in current_bbox_points),
                    y1=max(b[3] for b in current_bbox_points),
                )

            parents.append({
                "id": str(uuid4()),
                "text": merged_text,
                "page": current_page,
                "bbox": bbox,
            })
            current_texts = []
            current_bbox_points = []
            element_count = 0

        for el in elements:
            el_type = type(el).__name__
            # Skip non-text elements
            if el_type not in self._TEXT_ELEMENT_TYPES:
                continue

            text = str(el).strip()
            if not text:
                continue

            # Extract page number
            page = None
            if hasattr(el, 'metadata'):
                page = getattr(el.metadata, 'page_number', None)

            # Extract bounding box
            el_bbox = None
            if hasattr(el, 'metadata') and hasattr(el.metadata, 'coordinates'):
                bb = BoundingBox.from_coordinates(el.metadata.coordinates)
                if bb:
                    el_bbox = (bb.x0, bb.y0, bb.x1, bb.y1)

            # Decide whether to start a new parent
            start_new = False
            if el_type == 'Title':
                start_new = True
            elif page is not None and current_page is not None and page != current_page:
                start_new = True
            elif element_count >= self._max_parent_elements:
                start_new = True

            if start_new and current_texts:
                _flush()

            current_texts.append(text)
            current_page = page
            if el_bbox:
                current_bbox_points.append(el_bbox)
            element_count += 1

        # Flush remaining
        _flush()
        return parents

    # Splitting parents into children

    def _build_parent_child_chunks(
        self,
        parents: List[Dict[str, Any]],
        filename: str,
        document_id: UUID,
    ) -> List[Chunk]:
        """Create parent Chunk entities and their child sentence Chunks."""
        all_chunks: List[Chunk] = []
        global_child_idx = 0
        global_char_offset = 0

        for parent_idx, parent in enumerate(parents):
            parent_id = parent["id"]
            parent_text = parent["text"]
            parent_page = parent.get("page")
            parent_bbox: Optional[BoundingBox] = parent.get("bbox")

            # -- Parent chunk --
            parent_metadata = ChunkMetadata(
                source_file=filename,
                page=parent_page,
                char_start=global_char_offset,
                char_end=global_char_offset + len(parent_text),
                chunk_index=parent_idx,
                bbox=parent_bbox,
                parent_id=None,  # Parents have no parent
                chunk_type="parent",
            )

            parent_chunk = Chunk(
                id=UUID(parent_id) if self._is_valid_uuid(parent_id) else uuid4(),
                created_at=None,
                text=parent_text,
                document_id=document_id,
                chunk_index=parent_idx,
                metadata=parent_metadata.to_dict(),
            )
            # Override id to match parent_id string for linkage
            parent_chunk_id_str = str(parent_chunk.id)
            all_chunks.append(parent_chunk)

            # -- Child chunks (sentences) --
            sentences = self._split_into_sentences(parent_text)
            sentence_char_offset = 0

            for sent in sentences:
                sent_stripped = sent.strip()
                if len(sent_stripped) < self._min_sentence_length:
                    sentence_char_offset += len(sent)
                    continue

                # Approximate child bounding box from parent bbox
                child_bbox = self._approximate_sentence_bbox(
                    parent_bbox, parent_text, sentence_char_offset, len(sent_stripped)
                )

                child_metadata = ChunkMetadata(
                    source_file=filename,
                    page=parent_page,
                    char_start=global_char_offset + sentence_char_offset,
                    char_end=global_char_offset + sentence_char_offset + len(sent_stripped),
                    chunk_index=global_child_idx,
                    bbox=child_bbox,
                    parent_id=parent_chunk_id_str,
                    chunk_type="child",
                )

                child_chunk = Chunk(
                    id=uuid4(),
                    created_at=None,
                    text=sent_stripped,
                    document_id=document_id,
                    chunk_index=global_child_idx,
                    metadata=child_metadata.to_dict(),
                )
                all_chunks.append(child_chunk)
                global_child_idx += 1
                sentence_char_offset += len(sent)

            global_char_offset += len(parent_text)

        return all_chunks

    # Helpers

    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        """Split text into sentences using regex boundary detection."""
        if not text.strip():
            return []
        parts = _SENTENCE_RE.split(text)
        # Rejoin very short fragments with the previous sentence
        merged: List[str] = []
        for part in parts:
            if merged and len(part.strip()) < _MIN_SENTENCE_LEN:
                merged[-1] = merged[-1] + " " + part
            else:
                merged.append(part)
        return merged

    @staticmethod
    def _approximate_sentence_bbox(
        parent_bbox: Optional[BoundingBox],
        parent_text: str,
        char_offset: int,
        char_length: int,
    ) -> Optional[BoundingBox]:
        """Estimate a sentence bounding box from its parent's bbox.

        Uses a simple proportional vertical mapping: the sentence's vertical
        position within the parent bbox is proportional to its character offset
        within the parent text.  The horizontal extent is kept the same as the
        parent (full line width).
        """
        if not parent_bbox or not parent_text:
            return None

        total_len = len(parent_text)
        if total_len == 0:
            return parent_bbox

        # Vertical proportional mapping
        frac_start = char_offset / total_len
        frac_end = min((char_offset + char_length) / total_len, 1.0)

        height = parent_bbox.y1 - parent_bbox.y0
        y0 = parent_bbox.y0 + height * frac_start
        y1 = parent_bbox.y0 + height * frac_end

        return BoundingBox(
            x0=parent_bbox.x0,
            y0=y0,
            x1=parent_bbox.x1,
            y1=y1,
        )

    @staticmethod
    def _is_valid_uuid(s: str) -> bool:
        try:
            UUID(s)
            return True
        except (ValueError, AttributeError):
            return False
