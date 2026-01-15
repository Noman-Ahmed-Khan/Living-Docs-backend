"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Dict, Any

from app.db.session import get_db
from app.rag import get_vectorstore_manager
from app.settings import settings


router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    services: Dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
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
        manager = get_vectorstore_manager()
        stats = manager.get_stats()
        services["vectorstore"] = {
            "status": "healthy",
            "total_vectors": stats.get("total_vector_count", 0)
        }
    except Exception as e:
        services["vectorstore"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    return HealthResponse(
        status="healthy" if overall_healthy else "degraded",
        version="1.0.0",
        services=services
    )


@router.get("/health/ready")
async def readiness_check():
    """Simple readiness check for load balancers."""
    return {"status": "ready"}


@router.get("/health/live")
async def liveness_check():
    """Simple liveness check for container orchestration."""
    return {"status": "alive"}