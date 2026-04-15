"""Health check endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.container_dependencies import get_db
from app.container import Container, get_container
from app.domain.rag.interfaces import IVectorStore

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    services: Dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    """
    Check health of all services.

    Returns status of:
    - Database connection
    - Vector store connection
    - Overall system status
    """
    services = {}
    overall_healthy = True

    # Check database
    try:
        db.execute(text("SELECT 1"))
        services["database"] = {"status": "healthy"}
    except Exception as e:
        services["database"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Check vector store
    try:
        vector_store: IVectorStore = container.vector_store()
        stats = await vector_store.get_stats()
        services["vectorstore"] = {
            "status": "healthy",
            "total_vectors": stats.get("total_vector_count", 0),
            "index": stats.get("index_name"),
        }
    except Exception as e:
        services["vectorstore"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    return HealthResponse(
        status="healthy" if overall_healthy else "degraded",
        version="1.0.0",
        services=services,
    )


@router.get("/health/ready")
async def readiness_check():
    """Simple readiness check for load balancers."""
    return {"status": "ready"}


@router.get("/health/live")
async def liveness_check():
    """Simple liveness check for container orchestration."""
    return {"status": "alive"}
