"""User API routes."""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.api.schemas import user as user_schema
from app.api.container_dependencies import (
    get_user_service,
    get_current_user,
    get_current_active_user,
    get_current_verified_user,
)
from app.application.users.service import UserService
from app.domain.users.entities import User

router = APIRouter()


@router.get("/me", response_model=user_schema.UserProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Get the current user's profile."""
    return current_user


@router.patch("/me", response_model=user_schema.User)
async def update_user_profile(
    user_update: user_schema.UserUpdate,
    current_user: User = Depends(get_current_verified_user),
    user_service: UserService = Depends(get_user_service)
) -> Any:
    """Update the current user's profile (except email and password)."""
    if user_update.email:
        raise HTTPException(
            status_code=400,
            detail="Use the /auth/change-email endpoint to change email"
        )
    
    updated_user = await user_service.update_profile(current_user, user_update)
    return updated_user


@router.post("/me/deactivate")
async def deactivate_account(
    password_confirm: user_schema.DeleteAccountRequest,
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service)
) -> Any:
    """Deactivate the current user's account (soft delete)."""
    await user_service.deactivate_account(
        current_user=current_user,
        password=password_confirm.password
    )
    return {"message": "Account deactivated successfully"}


@router.post("/me/activate")
async def activate_account(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
) -> Any:
    """Reactivate the current user's account."""
    if current_user.is_active:
        return {"message": "Account is already active"}
    
    await user_service.activate_account(current_user)
    return {"message": "Account reactivated successfully"}


@router.delete("/me")
async def delete_account(
    password_confirm: user_schema.DeleteAccountRequest,
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service)
) -> Any:
    """Permanently delete the current user's account and all associated data."""
    await user_service.delete_account(
        current_user=current_user,
        password=password_confirm.password,
        confirmation=password_confirm.confirmation
    )
    return {"message": "Account and all associated data deleted successfully"}


@router.get("/me/security-info")
async def get_security_info(
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service)
) -> Any:
    """Get security-related information for the current user."""
    return user_service.get_security_info(current_user)