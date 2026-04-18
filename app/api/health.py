"""Health check endpoints."""

from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.container_dependencies import get_db
from app.container import Container, get_container
from app.domain.rag.interfaces import IVectorStore

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Overall API health status")
    version: str = Field(..., description="Application version")
    services: Dict[str, ServiceHealth] = Field(
        ...,
        description="Health status for dependent services"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "services": {
                    "database": {
                        "status": "healthy"
                    },
                    "vectorstore": {
                        "status": "healthy",
                        "total_vectors": 128,
                        "index": "livingdocs"
                    }
                }
            }
        }


class ServiceHealth(BaseModel):
    """Health details for a single dependency."""

    status: str = Field(..., description="Service status")
    error: Optional[str] = Field(None, description="Error details if the service is unhealthy")
    total_vectors: Optional[int] = Field(None, description="Total number of vectors stored")
    index: Optional[str] = Field(None, description="Vector index name")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "total_vectors": 128,
                "index": "livingdocs"
            }
        }


class SimpleStatusResponse(BaseModel):
    """Simple status response used by readiness and liveness checks."""

    status: str = Field(..., description="Current service status")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ready"
            }
        }


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


@router.get("/health/ready", response_model=SimpleStatusResponse, summary="Readiness check")
async def readiness_check():
    """Simple readiness check for load balancers."""
    return SimpleStatusResponse(status="ready")


@router.get("/health/live", response_model=SimpleStatusResponse, summary="Liveness check")
async def liveness_check():
    """Simple liveness check for container orchestration."""
    return SimpleStatusResponse(status="alive")
