"""Authentication API routes."""

from typing import Any
from fastapi import APIRouter, Depends, status, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from uuid import UUID

from app.api.schemas import auth as auth_schema
from app.config.settings import settings
from app.api.container_dependencies import (
    get_auth_service,
    get_user_service,
    get_current_user,
    get_current_active_user,
    get_current_verified_user,
    get_client_ip,
    get_user_agent,
)
from app.application.auth.service import AuthService
from app.application.users.service import UserService
from app.domain.users.entities import User

router = APIRouter()


# ----------------------------------------------------------------
# Registration
# ----------------------------------------------------------------

@router.post("/register", response_model=auth_schema.MessageResponse)
async def register(
    user_in: auth_schema.RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Register a new user account."""
    message = await auth_service.register_user(
        email=user_in.email, 
        password=user_in.password
    )
    return {"message": message}


@router.post("/verify-email", response_model=auth_schema.MessageResponse)
async def verify_email(
    data: auth_schema.VerifyEmailRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Verify user's email address using the token sent via email."""
    message = await auth_service.verify_email(token=data.token)
    return {"message": message}


@router.get("/verify-email")
async def verify_email_get(
    token: str,
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Verify user's email address using the token sent via email (GET version for links)."""
    try:
        message = await auth_service.verify_email(token=token)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?message={message}"
        )
    except Exception as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={str(e)}"
        )


@router.post("/resend-verification", response_model=auth_schema.MessageResponse)
async def resend_verification(
    data: auth_schema.ResendVerificationRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Resend verification email."""
    message = await auth_service.resend_verification(email=data.email)
    return {"message": message}


# ----------------------------------------------------------------
# Login / Logout
# ----------------------------------------------------------------

@router.post("/login", response_model=auth_schema.Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """OAuth2 compatible login endpoint."""
    token_pair = await auth_service.login(
        email=form_data.username,
        password=form_data.password,
        device_info=get_user_agent(request),
        ip_address=get_client_ip(request)
    )
    
    return auth_schema.Token(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
        expires_in=token_pair.expires_in
    )


@router.post("/refresh", response_model=auth_schema.Token)
async def refresh_token(
    request: Request,
    data: auth_schema.RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Refresh access token using refresh token with token rotation."""
    token_pair = await auth_service.refresh_token(
        refresh_token_str=data.refresh_token,
        device_info=get_user_agent(request),
        ip_address=get_client_ip(request)
    )
    
    return auth_schema.Token(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
        expires_in=token_pair.expires_in
    )


@router.post("/logout", response_model=auth_schema.MessageResponse)
async def logout(
    data: auth_schema.RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Logout and invalidate the refresh token."""
    message = await auth_service.logout(
        user_id=current_user.id, 
        refresh_token_str=data.refresh_token
    )
    return {"message": message}


@router.post("/logout-all", response_model=auth_schema.MessageResponse)
async def logout_all_sessions(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Logout from all devices/sessions."""
    message = await auth_service.logout_all(user_id=current_user.id)
    return {"message": message}


# ----------------------------------------------------------------
# Password Management
# ----------------------------------------------------------------

@router.post("/forgot-password", response_model=auth_schema.MessageResponse)
async def forgot_password(
    data: auth_schema.ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Request password reset email."""
    message = await auth_service.forgot_password(email=data.email)
    return {"message": message}


@router.post("/reset-password", response_model=auth_schema.MessageResponse)
async def reset_password(
    data: auth_schema.ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Reset password using the token from email."""
    message = await auth_service.reset_password(
        token=data.token, 
        new_password=data.new_password
    )
    return {"message": message}


@router.get("/reset-password")
async def reset_password_get(token: str) -> Any:
    """Verify reset token and redirect to frontend reset password form."""
    # We do the redirect directly since we don't have a specific ResetRequest object here
    # The frontend will call the POST /reset-password later
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/reset-password?token={token}"
    )


@router.post("/change-password", response_model=auth_schema.MessageResponse)
async def change_password(
    data: auth_schema.ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Change password while logged in."""
    # Auth service needs current_user (entity) and password strings
    # We use UserService for changing password as per our new design
    # Actually, AuthService has change_password in the original plan? 
    # Plan said: `change_password()` in AuthService and UserService.
    # In my implementation, UserService handles it. Let's use AuthService for consistency in auth.py
    # but AuthService doesn't have change_password implemented in the plan?
    # Wait, I implemented UserService.change_password.
    
    # I'll add change_password to AuthService too or just use UserService here.
    # Let's check AuthService implementation I just did.
    # It has request_email_change, logout, etc.
    # Actually, UserService.change_password is already there. Let's use it.
    from app.api.container_dependencies import get_user_service
    from app.application.users.service import UserService
    pass
    
@router.post("/change-password", response_model=auth_schema.MessageResponse)
async def change_password_route(
    data: auth_schema.ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service)
) -> Any:
    """Change password while logged in."""
    await user_service.change_password(
        current_user=current_user,
        current_password=data.current_password,
        new_password=data.new_password
    )
    return {"message": "Password changed successfully. Please log in again."}


# ----------------------------------------------------------------
# Email Management
# ----------------------------------------------------------------

@router.post("/change-email", response_model=auth_schema.MessageResponse)
async def request_email_change(
    data: auth_schema.ChangeEmailRequest,
    current_user: User = Depends(get_current_verified_user),
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Request to change email address."""
    message = await auth_service.request_email_change(
        current_user=current_user,
        new_email=data.new_email,
        password=data.password
    )
    return {"message": message}


# ----------------------------------------------------------------
# Session Management
# ----------------------------------------------------------------

@router.get("/sessions", response_model=auth_schema.SessionList)
async def get_active_sessions(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Get all active sessions for the current user."""
    sessions = await auth_service.get_sessions(
        user_id=current_user.id,
        current_ip=get_client_ip(request)
    )
    
    session_list = [
        auth_schema.SessionInfo(
            id=s.id,
            device_info=s.device_info,
            ip_address=s.ip_address,
            created_at=s.created_at,
            expires_at=s.expires_at,
            is_current=s.is_current
        )
        for s in sessions
    ]
    
    return auth_schema.SessionList(sessions=session_list, total=len(session_list))


@router.delete("/sessions/{session_id}", response_model=auth_schema.MessageResponse)
async def revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service)
) -> Any:
    """Revoke a specific session."""
    message = await auth_service.revoke_session(
        user_id=current_user.id,
        session_id=session_id
    )
    return {"message": message}


# ----------------------------------------------------------------
# Auth Status
# ----------------------------------------------------------------

@router.get("/status", response_model=auth_schema.AuthStatus)
async def get_auth_status(
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get current authentication status."""
    return auth_schema.AuthStatus(
        is_authenticated=True,
        is_verified=current_user.is_verified,
        email=current_user.email,
        user_id=current_user.id
    )
