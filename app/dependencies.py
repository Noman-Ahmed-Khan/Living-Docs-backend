from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Optional
from uuid import UUID

from app.db.session import get_db, SessionLocal
from app.db import crud, models
from app.settings import settings
from app.schemas.auth import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> models.User:
    """Get current authenticated user from access token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id_str is None:
            raise credentials_exception
        
        # Ensure it's an access token, not a refresh token
        if token_type != "access":
            raise credentials_exception
        
        # Convert string to UUID
        try:
            user_id = UUID(user_id_str)
        except ValueError:
            raise credentials_exception
            
        token_data = TokenData(user_id=user_id, token_type=token_type)
        
    except JWTError:
        raise credentials_exception
    
    user = crud.get_user(db, user_id=token_data.user_id)
    
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    return current_user


async def get_current_verified_user(
    current_user: models.User = Depends(get_current_active_user)
) -> models.User:
    """Get current verified user (email verified)"""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email first."
        )
    return current_user


async def get_current_superuser(
    current_user: models.User = Depends(get_current_active_user)
) -> models.User:
    """Get current superuser"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


async def get_optional_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme_optional)
) -> Optional[models.User]:
    """Optionally get current user (for routes that work with or without auth)"""
    if token is None:
        return None
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id_str is None or token_type != "access":
            return None
        
        try:
            user_id = UUID(user_id_str)
        except ValueError:
            return None
        
        user = crud.get_user(db, user_id=user_id)
        if user and user.is_active:
            return user
        return None
        
    except JWTError:
        return None


def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request"""
    return request.headers.get("User-Agent", "unknown")[:200]
