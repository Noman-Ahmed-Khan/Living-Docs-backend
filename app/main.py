from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from app.api import auth, users, projects, documents, query, health
from app.db.session import engine, Base, SessionLocal
from app.db import crud
from app.settings import settings


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Create database tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting up Living Docs API...")
    db = SessionLocal()
    try:
        # Cleanup deactivated users
        deleted_count = crud.cleanup_deactivated_users(db)
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} deactivated users")
        
        # Cleanup expired tokens
        expired_tokens = crud.cleanup_expired_tokens(db)
        if expired_tokens > 0:
            logger.info(f"Cleaned up {expired_tokens} expired tokens")
    except Exception as e:
        logger.error(f"Startup cleanup failed: {e}")
    finally:
        db.close()
    
    logger.info("Living Docs API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Living Docs API...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-powered document intelligence system with RAG capabilities",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(
    auth.router, 
    prefix=f"{settings.API_V1_STR}/auth", 
    tags=["auth"]
)
app.include_router(
    users.router, 
    prefix=f"{settings.API_V1_STR}/users", 
    tags=["users"]
)
app.include_router(
    projects.router, 
    prefix=f"{settings.API_V1_STR}/projects", 
    tags=["projects"]
)
app.include_router(
    documents.router, 
    prefix=f"{settings.API_V1_STR}/documents", 
    tags=["documents"]
)
app.include_router(
    query.router, 
    prefix=f"{settings.API_V1_STR}/query", 
    tags=["query"]
)
app.include_router(
    health.router, 
    prefix="/health", 
    tags=["health"]
)


@app.get("/test-upload", response_class=HTMLResponse)
async def get_test_upload():
    """Endpoint for testing document uploads."""
    template_path = Path("app/templates/test_upload.html")
    if not template_path.exists():
        return HTMLResponse(content="Template not found", status_code=404)
    return template_path.read_text()


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Welcome to Living Docs API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }