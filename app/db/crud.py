"""Database CRUD operations."""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from uuid import UUID
import secrets
import os

from app.db import models
from app.schemas import user as user_schema
from app.schemas import project as project_schema
from app.schemas import document as document_schema
from app.utils.hashing import get_password_hash
from app.settings import settings


# ============== User CRUD (unchanged - keeping as is) ==============

def get_user(db: Session, user_id: UUID) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: user_schema.UserCreate) -> models.User:
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        is_verified=not settings.REQUIRE_EMAIL_VERIFICATION
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, db_user: models.User, user_update: user_schema.UserUpdate) -> models.User:
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_password(
    db: Session,
    user_id: UUID,
    new_password: str
) -> models.User:
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not db_user:
        raise ValueError("User not found")

    db_user.hashed_password = get_password_hash(new_password)
    db_user.password_changed_at = datetime.utcnow()

    db.commit()
    db.refresh(db_user)
    return db_user

def verify_user_email(db: Session, db_user: models.User) -> models.User:
    db_user.is_verified = True
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_email(db: Session, db_user: models.User, new_email: str) -> models.User:
    db_user.email = new_email
    db_user.is_verified = True
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def deactivate_user(db: Session, user_id: UUID) -> models.User:
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise ValueError("User not found")
    db_user.is_active = False
    db_user.deactivated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_user)
    return db_user


def activate_user(db: Session, user_id: UUID) -> models.User:
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise ValueError("User not found")
    db_user.is_active = True
    db_user.deactivated_at = None
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, db_user: models.User) -> None:
    for project in db_user.projects:
        for doc in project.documents:
            if os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                except Exception:
                    pass
    db.delete(db_user)
    db.commit()


def cleanup_deactivated_users(db: Session) -> int:
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    expired_users = db.query(models.User).filter(
        models.User.is_active == False,
        models.User.deactivated_at <= thirty_days_ago
    ).all()
    count = 0
    for user in expired_users:
        delete_user(db, user)
        count += 1
    return count


def increment_failed_login(db: Session, db_user: models.User) -> models.User:
    db_user.failed_login_attempts += 1
    if db_user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
        db_user.locked_until = datetime.utcnow() + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def reset_failed_login(db: Session, db_user: models.User) -> models.User:
    db_user.failed_login_attempts = 0
    db_user.locked_until = None
    db_user.last_login_at = datetime.utcnow()
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def is_user_locked(db_user: models.User) -> bool:
    if db_user.locked_until is None:
        return False
    return datetime.utcnow() < db_user.locked_until


# ============== Refresh Token CRUD (unchanged) ==============

def create_refresh_token(
    db: Session,
    user_id: UUID,
    token: str,
    expires_at: datetime,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None,
    family_id: Optional[UUID] = None
) -> models.RefreshToken:
    import uuid as uuid_module
    db_token = models.RefreshToken(
        token=token,
        user_id=user_id,
        expires_at=expires_at,
        device_info=device_info,
        ip_address=ip_address,
        family_id=family_id or uuid_module.uuid4()
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def get_refresh_token(db: Session, token: str) -> Optional[models.RefreshToken]:
    return db.query(models.RefreshToken).filter(
        models.RefreshToken.token == token
    ).first()


def get_active_refresh_token(db: Session, token: str) -> Optional[models.RefreshToken]:
    return db.query(models.RefreshToken).filter(
        and_(
            models.RefreshToken.token == token,
            models.RefreshToken.is_revoked == False,
            models.RefreshToken.expires_at > datetime.utcnow()
        )
    ).first()


def revoke_refresh_token(
    db: Session, 
    db_token: models.RefreshToken, 
    replaced_by: Optional[UUID] = None
) -> models.RefreshToken:
    db_token.is_revoked = True
    db_token.revoked_at = datetime.utcnow()
    db_token.replaced_by = replaced_by
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def revoke_token_family(db: Session, family_id: UUID) -> int:
    result = db.query(models.RefreshToken).filter(
        and_(
            models.RefreshToken.family_id == family_id,
            models.RefreshToken.is_revoked == False
        )
    ).update({
        "is_revoked": True,
        "revoked_at": datetime.utcnow()
    })
    db.commit()
    return result


def revoke_all_user_tokens(db: Session, user_id: UUID) -> int:
    result = db.query(models.RefreshToken).filter(
        and_(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.is_revoked == False
        )
    ).update({
        "is_revoked": True,
        "revoked_at": datetime.utcnow()
    })
    db.commit()
    return result


def get_user_active_sessions(db: Session, user_id: UUID) -> List[models.RefreshToken]:
    return db.query(models.RefreshToken).filter(
        and_(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.is_revoked == False,
            models.RefreshToken.expires_at > datetime.utcnow()
        )
    ).order_by(models.RefreshToken.created_at.desc()).all()


def cleanup_expired_tokens(db: Session) -> int:
    result = db.query(models.RefreshToken).filter(
        models.RefreshToken.expires_at < datetime.utcnow()
    ).delete()
    db.commit()
    return result


# ============== Verification Token CRUD (unchanged) ==============

def create_verification_token(
    db: Session,
    user_id: UUID,
    token_type: str = "email_verification",
    new_email: Optional[str] = None
) -> models.VerificationToken:
    db.query(models.VerificationToken).filter(
        and_(
            models.VerificationToken.user_id == user_id,
            models.VerificationToken.token_type == token_type,
            models.VerificationToken.is_used == False
        )
    ).update({"is_used": True})
    
    expires_at = datetime.utcnow() + timedelta(hours=settings.VERIFICATION_TOKEN_EXPIRE_HOURS)
    db_token = models.VerificationToken(
        user_id=user_id,
        token=secrets.token_urlsafe(32),
        token_type=token_type,
        new_email=new_email,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def get_verification_token(db: Session, token: str) -> Optional[models.VerificationToken]:
    return db.query(models.VerificationToken).filter(
        and_(
            models.VerificationToken.token == token,
            models.VerificationToken.is_used == False,
            models.VerificationToken.expires_at > datetime.utcnow()
        )
    ).first()


def use_verification_token(db: Session, db_token: models.VerificationToken) -> models.VerificationToken:
    db_token.is_used = True
    db_token.used_at = datetime.utcnow()
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


# Password Reset Token CRUD

def create_password_reset_token(db: Session, user_id: UUID) -> models.PasswordResetToken:
    db.query(models.PasswordResetToken).filter(
        and_(
            models.PasswordResetToken.user_id == user_id,
            models.PasswordResetToken.is_used == False
        )
    ).update({"is_used": True})
    
    expires_at = datetime.utcnow() + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    db_token = models.PasswordResetToken(
        user_id=user_id,
        token=secrets.token_urlsafe(32),
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def get_password_reset_token(db: Session, token: str) -> Optional[models.PasswordResetToken]:
    return db.query(models.PasswordResetToken).filter(
        and_(
            models.PasswordResetToken.token == token,
            models.PasswordResetToken.is_used == False,
            models.PasswordResetToken.expires_at > datetime.utcnow()
        )
    ).first()


def use_password_reset_token(db: Session, db_token: models.PasswordResetToken) -> models.PasswordResetToken:
    db_token.is_used = True
    db_token.used_at = datetime.utcnow()
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


# ============== Project CRUD ==============

def create_project(
    db: Session, 
    project: project_schema.ProjectCreate, 
    owner_id: UUID
) -> models.Project:
    """Create a new project."""
    db_project = models.Project(
        **project.model_dump(),
        owner_id=owner_id,
        status=models.ProjectStatus.ACTIVE
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def get_project(
    db: Session, 
    project_id: UUID, 
    owner_id: UUID
) -> Optional[models.Project]:
    """Get a project by ID and owner."""
    return db.query(models.Project).filter(
        and_(
            models.Project.id == project_id,
            models.Project.owner_id == owner_id
        )
    ).first()


def get_projects(
    db: Session, 
    owner_id: UUID,
    status: Optional[models.ProjectStatus] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[models.Project], int]:
    """Get all projects for an owner with pagination."""
    query = db.query(models.Project).filter(models.Project.owner_id == owner_id)
    
    if status:
        query = query.filter(models.Project.status == status)
    
    total = query.count()
    projects = query.order_by(models.Project.created_at.desc()).offset(skip).limit(limit).all()
    
    return projects, total


def update_project(
    db: Session,
    db_project: models.Project,
    project_update: project_schema.ProjectUpdate
) -> models.Project:
    """Update a project."""
    update_data = project_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_project, field, value)
    db_project.updated_at = datetime.utcnow()
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def delete_project(db: Session, db_project: models.Project) -> None:
    """Delete a project and all associated documents."""
    # Clean up document files
    for doc in db_project.documents:
        if os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except Exception:
                pass
    
    db.delete(db_project)
    db.commit()


def get_project_stats(db: Session, project_id: UUID) -> dict:
    """Get statistics for a project."""
    from sqlalchemy import case
    
    stats = db.query(
        func.count(models.Document.id).label('document_count'),
        func.sum(case((models.Document.status == models.DocumentStatus.COMPLETED, 1), else_=0)).label('completed_documents'),
        func.sum(case((models.Document.status == models.DocumentStatus.FAILED, 1), else_=0)).label('failed_documents'),
        func.sum(case((models.Document.status == models.DocumentStatus.PENDING, 1), else_=0)).label('pending_documents'),
        func.sum(case((models.Document.status == models.DocumentStatus.PROCESSING, 1), else_=0)).label('processing_documents'),
        func.coalesce(func.sum(models.Document.chunk_count), 0).label('total_chunks'),
        func.coalesce(func.sum(models.Document.file_size), 0).label('total_size_bytes')
    ).filter(
        models.Document.project_id == project_id
    ).first()
    
    return {
        'document_count': stats.document_count or 0,
        'completed_documents': stats.completed_documents or 0,
        'failed_documents': stats.failed_documents or 0,
        'pending_documents': (stats.pending_documents or 0) + (stats.processing_documents or 0),
        'total_chunks': stats.total_chunks or 0,
        'total_size_bytes': stats.total_size_bytes or 0
    }


def archive_project(db: Session, db_project: models.Project) -> models.Project:
    """Archive a project."""
    db_project.status = models.ProjectStatus.ARCHIVED
    db_project.updated_at = datetime.utcnow()
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def unarchive_project(db: Session, db_project: models.Project) -> models.Project:
    """Unarchive a project."""
    db_project.status = models.ProjectStatus.ACTIVE
    db_project.updated_at = datetime.utcnow()
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


# ============== Document CRUD ==============

def create_document(
    db: Session,
    filename: str,
    original_filename: str,
    project_id: UUID,
    file_path: str,
    file_size: Optional[int] = None,
    file_type: Optional[str] = None,
    content_type: Optional[str] = None
) -> models.Document:
    """Create a new document record."""
    db_document = models.Document(
        filename=filename,
        original_filename=original_filename,
        project_id=project_id,
        file_path=file_path,
        file_size=file_size,
        file_type=file_type,
        content_type=content_type,
        status=models.DocumentStatus.PENDING
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document


def get_document(
    db: Session,
    document_id: UUID,
    project_id: UUID
) -> Optional[models.Document]:
    """Get a document by ID and project."""
    return db.query(models.Document).filter(
        and_(
            models.Document.id == document_id,
            models.Document.project_id == project_id
        )
    ).first()


def get_document_by_id(db: Session, document_id: UUID) -> Optional[models.Document]:
    """Get a document by ID only."""
    return db.query(models.Document).filter(models.Document.id == document_id).first()


def get_documents_by_project(
    db: Session,
    project_id: UUID,
    status: Optional[models.DocumentStatus] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[models.Document], int]:
    """Get all documents for a project with pagination."""
    query = db.query(models.Document).filter(models.Document.project_id == project_id)
    
    if status:
        query = query.filter(models.Document.status == status)
    
    total = query.count()
    documents = query.order_by(models.Document.created_at.desc()).offset(skip).limit(limit).all()
    
    return documents, total


def update_document(
    db: Session,
    db_document: models.Document,
    update_data: dict
) -> models.Document:
    """Update a document."""
    for field, value in update_data.items():
        if hasattr(db_document, field):
            setattr(db_document, field, value)
    db_document.updated_at = datetime.utcnow()
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document


def update_document_status(
    db: Session,
    db_document: models.Document,
    status: models.DocumentStatus,
    message: Optional[str] = None,
    chunk_count: Optional[int] = None,
    page_count: Optional[int] = None,
    character_count: Optional[int] = None
) -> models.Document:
    """Update document processing status."""
    db_document.status = status
    db_document.status_message = message
    db_document.updated_at = datetime.utcnow()
    
    if chunk_count is not None:
        db_document.chunk_count = chunk_count
    if page_count is not None:
        db_document.page_count = page_count
    if character_count is not None:
        db_document.character_count = character_count
    
    if status == models.DocumentStatus.COMPLETED:
        db_document.processed_at = datetime.utcnow()
    
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document


def delete_document(db: Session, db_document: models.Document) -> None:
    """Delete a document and its file."""
    if os.path.exists(db_document.file_path):
        try:
            os.remove(db_document.file_path)
        except Exception:
            pass
    
    db.delete(db_document)
    db.commit()


def get_pending_documents(db: Session, limit: int = 10) -> List[models.Document]:
    """Get pending documents for processing."""
    return db.query(models.Document).filter(
        models.Document.status == models.DocumentStatus.PENDING
    ).order_by(models.Document.created_at.asc()).limit(limit).all()


def get_failed_documents(
    db: Session,
    project_id: UUID,
    since: Optional[datetime] = None
) -> List[models.Document]:
    """Get failed documents for a project."""
    query = db.query(models.Document).filter(
        and_(
            models.Document.project_id == project_id,
            models.Document.status == models.DocumentStatus.FAILED
        )
    )
    
    if since:
        query = query.filter(models.Document.updated_at >= since)
    
    return query.order_by(models.Document.updated_at.desc()).all()


def reset_document_for_reingestion(db: Session, db_document: models.Document) -> models.Document:
    """Reset a document for re-ingestion."""
    db_document.status = models.DocumentStatus.PENDING
    db_document.status_message = None
    db_document.chunk_count = 0
    db_document.processed_at = None
    db_document.updated_at = datetime.utcnow()
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document