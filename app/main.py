from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from app.api import auth, users, projects, documents, query, health, chat
from app.api.middleware.error_handler import (
    domain_exception_handler,
    validation_exception_handler,
    generic_exception_handler
)
from app.container import get_container
from app.api.v1.router import api_v1_router
from app.infrastructure.database.session import engine, Base, SessionLocal
from app.config.settings import settings
from app.domain.common.exceptions import DomainException


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
    container = get_container()
    db = next(container.get_db())
    try:
        user_repo = container.user_repository(db)
        rt_repo = container.refresh_token_repository(db)
        
        # Cleanup deactivated users
        deleted_count = await user_repo.cleanup_deactivated_users()
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} deactivated users")
        
        # Cleanup expired tokens
        expired_tokens = await rt_repo.cleanup_expired_tokens()
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

# Register exception handlers (before middleware)
app.add_exception_handler(DomainException, domain_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API v1 router (aggregated)
app.include_router(api_v1_router)



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