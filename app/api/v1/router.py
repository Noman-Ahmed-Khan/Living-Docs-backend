"""API v1 router - aggregates all v1 endpoints."""

from fastapi import APIRouter

from app.api import (
    auth,
    users,
    projects,
    documents,
    query,
    chat,
    health
)

# Create v1 router
api_v1_router = APIRouter(prefix="/api/v1")

# Include all sub-routers
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(users.router, prefix="/users", tags=["users"])
api_v1_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_v1_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_v1_router.include_router(query.router, prefix="/query", tags=["query"])
api_v1_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_v1_router.include_router(health.router, tags=["health"])
