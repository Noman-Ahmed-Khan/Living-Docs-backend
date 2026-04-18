from uuid import uuid4

from app.domain.documents.entities import Chunk
from app.application.query.query_service import QueryService
from app.domain.rag.entities import RetrievedChunk
from app.domain.rag.value_objects import BoundingBox, ChunkMetadata
from app.domain.rag.value_objects import QueryConfig, RetrieverConfig
from app.infrastructure.rag.vectorstores.pinecone_store import PineconeVectorStore


def test_chunk_metadata_to_dict_omits_optional_none_fields():
    metadata = ChunkMetadata(
        source_file="report.pdf",
        char_start=10,
        char_end=42,
        chunk_index=3,
    )

    assert metadata.to_dict() == {
        "source_file": "report.pdf",
        "char_start": 10,
        "char_end": 42,
        "chunk_index": 3,
        "chunk_type": "child",
    }


def test_chunk_metadata_to_dict_flattens_bbox_values():
    metadata = ChunkMetadata(
        source_file="report.pdf",
        page=4,
        char_start=10,
        char_end=42,
        chunk_index=3,
        bbox=BoundingBox(x0=1.0, y0=2.0, x1=3.0, y1=4.0),
        parent_id="parent-1",
        chunk_type="parent",
    )

    assert metadata.to_dict() == {
        "source_file": "report.pdf",
        "page": 4,
        "char_start": 10,
        "char_end": 42,
        "chunk_index": 3,
        "parent_id": "parent-1",
        "chunk_type": "parent",
        "bbox_x0": 1.0,
        "bbox_y0": 2.0,
        "bbox_x1": 3.0,
        "bbox_y1": 4.0,
    }


def test_pinecone_chunk_metadata_strips_none_values():
    document_id = uuid4()
    chunk = Chunk.create(
        text="Example text.",
        document_id=document_id,
        chunk_index=7,
        source_file="report.pdf",
        page=None,
        parent_id=None,
        bbox_x0=None,
        bbox_y0=None,
        bbox_x1=None,
        bbox_y1=None,
    )

    metadata = PineconeVectorStore._chunk_to_metadata(chunk)

    assert metadata == {
        "text": "Example text.",
        "document_id": str(document_id),
        "chunk_id": str(chunk.id),
        "chunk_index": 7,
        "source_file": "report.pdf",
        "char_start": 0,
        "char_end": 0,
        "chunk_type": "child",
    }
    assert all(value is not None for value in metadata.values())


class _FakeCoordinates:
    def __init__(self, points):
        self.points = points


class _FakeCoordinatesWithToDict:
    def __init__(self, points):
        self._points = points

    def to_dict(self):
        return {"points": self._points}


def test_bounding_box_from_coordinates_accepts_points_attribute():
    bbox = BoundingBox.from_coordinates(
        _FakeCoordinates(
            [
                (10.0, 20.0),
                (10.0, 60.0),
                (80.0, 60.0),
                (80.0, 20.0),
            ]
        )
    )

    assert bbox == BoundingBox(x0=10.0, y0=20.0, x1=80.0, y1=60.0)


def test_bounding_box_from_coordinates_accepts_to_dict_shape():
    bbox = BoundingBox.from_coordinates(
        _FakeCoordinatesWithToDict(
            [
                (5.0, 15.0),
                (5.0, 25.0),
                (35.0, 25.0),
                (35.0, 15.0),
            ]
        )
    )

    assert bbox == BoundingBox(x0=5.0, y0=15.0, x1=35.0, y1=25.0)


def test_query_service_uses_parent_bbox_when_child_bbox_missing():
    class _DummyRetriever:
        _strategy = type("Strategy", (), {"value": "similarity"})()

    class _DummyLLM:
        model_name = "dummy-model"

    service = QueryService(
        retriever=_DummyRetriever(),
        llm_client=_DummyLLM(),
        retriever_config=RetrieverConfig(),
        query_config=QueryConfig(),
    )

    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        text="Relevant sentence.",
        document_id=uuid4(),
        metadata=ChunkMetadata(
            source_file="report.pdf",
            page=1,
            char_start=10,
            char_end=28,
            chunk_index=0,
        ),
        score=0.87,
        bbox=None,
        parent_bbox=BoundingBox(x0=12.0, y0=34.0, x1=56.0, y1=78.0),
    )

    citations = service._build_citations("Answer [chunk-1]", [chunk])

    assert len(citations) == 1
    assert citations[0].bbox == {
        "x0": 12.0,
        "y0": 34.0,
        "x1": 56.0,
        "y1": 78.0,
    }
