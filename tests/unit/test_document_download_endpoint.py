from datetime import datetime
from types import SimpleNamespace
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import documents
from app.api.container_dependencies import (
    get_current_verified_user,
    get_document_service,
    get_project_service,
)
from app.application.documents.dto import DocumentDetailDTO


ROOT_DIR = Path(__file__).resolve().parents[2]


class _FakeDocumentService:
    def __init__(self, document: DocumentDetailDTO):
        self._document = document

    async def get_document_by_id(self, document_id):
        return self._document


class _FakeProjectService:
    async def get_project(self, project_id, owner_id):
        return SimpleNamespace(id=project_id, owner_id=owner_id)


def _build_app(document: DocumentDetailDTO, owner_id):
    app = FastAPI()
    app.include_router(documents.router, prefix="/api/v1/documents")
    app.dependency_overrides[get_current_verified_user] = lambda: SimpleNamespace(
        id=owner_id
    )
    app.dependency_overrides[get_document_service] = lambda: _FakeDocumentService(
        document
    )
    app.dependency_overrides[get_project_service] = lambda: _FakeProjectService()
    return app


def test_document_download_returns_file_response():
    owner_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    file_path = ROOT_DIR / f"download-test-{document_id}.pdf"
    file_bytes = b"%PDF-1.4 test file"

    try:
        file_path.write_bytes(file_bytes)

        document = DocumentDetailDTO(
            id=document_id,
            filename="stored-file.pdf",
            original_filename="report.pdf",
            project_id=project_id,
            status="completed",
            file_size=len(file_bytes),
            chunk_count=1,
            page_count=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
            content_type="application/pdf",
            file_path=str(file_path),
        )

        app = _build_app(document=document, owner_id=owner_id)
        client = TestClient(app)

        response = client.get(f"/api/v1/documents/{document_id}/download")

        assert response.status_code == 200
        assert response.content == file_bytes
        assert response.headers["content-type"].startswith("application/pdf")
        assert "report.pdf" in response.headers["content-disposition"]
    finally:
        if file_path.exists():
            file_path.unlink()


def test_document_download_path_is_exposed_in_openapi():
    owner_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()

    document = DocumentDetailDTO(
        id=document_id,
        filename="stored-file.pdf",
        original_filename="report.pdf",
        project_id=project_id,
        status="completed",
        file_size=4,
        chunk_count=1,
        page_count=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        processed_at=datetime.utcnow(),
        content_type="application/pdf",
        file_path=str(ROOT_DIR / "ignored.pdf"),
    )

    app = _build_app(document=document, owner_id=owner_id)

    schema = app.openapi()

    assert "/api/v1/documents/{document_id}/download" in schema["paths"]
