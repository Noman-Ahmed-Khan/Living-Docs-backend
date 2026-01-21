from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from uuid import UUID

from app.db import crud, models
from app.db.session import get_db
from app.schemas import auth as auth_schema
from app.schemas import user as user_schema
from app.utils import security, hashing, email as email_utils
from app.settings import settings
from app.dependencies import (
    get_current_user,
    get_current_active_user,
    get_current_verified_user,
    get_client_ip,
    get_user_agent
)

router = APIRouter()


# Registration

@router.post("/register", response_model=auth_schema.MessageResponse)
async def register(
    user_in: auth_schema.RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    """
    # Check if user already exists
    db_user = crud.get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )
    
    # Create user
    user_create = user_schema.UserCreate(email=user_in.email, password=user_in.password)
    user = crud.create_user(db, user=user_create)
    
    # Create verification token and send email
    if settings.REQUIRE_EMAIL_VERIFICATION:
        verification_token = crud.create_verification_token(db, user_id=user.id)
        background_tasks.add_task(
            email_utils.send_verification_email,
            user.email,
            verification_token.token
        )
        return {"message": "Registration successful. Please check your email to verify your account."}
    
    return {"message": "Registration successful."}


@router.post("/verify-email", response_model=auth_schema.MessageResponse)
async def verify_email(
    data: auth_schema.VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """Verify user's email address using the token sent via email."""
    token = crud.get_verification_token(db, token=data.token)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token."
        )
    
    if token.token_type == "email_change" and token.new_email:
        crud.update_user_email(db, token.user, token.new_email)
        crud.use_verification_token(db, token)
        return {"message": "Email address updated successfully."}
    
    crud.verify_user_email(db, token.user)
    crud.use_verification_token(db, token)
    
    return {"message": "Email verified successfully. You can now log in."}


@router.get("/verify-email")
async def verify_email_get(
    token: str,
    db: Session = Depends(get_db)
):
    """Verify user's email address using the token sent via email (GET version for links)."""
    db_token = crud.get_verification_token(db, token=token)
    
    if not db_token:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=Invalid or expired verification token.")
    
    if db_token.token_type == "email_change" and db_token.new_email:
        crud.update_user_email(db, db_token.user, db_token.new_email)
        crud.use_verification_token(db, db_token)
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?message=Email address updated successfully.")
    
    crud.verify_user_email(db, db_token.user)
    crud.use_verification_token(db, db_token)
    
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?message=Email verified successfully. You can now log in.")


@router.post("/resend-verification", response_model=auth_schema.MessageResponse)
async def resend_verification(
    data: auth_schema.ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Resend verification email."""
    user = crud.get_user_by_email(db, email=data.email)
    
    if not user:
        return {"message": "If an account exists with this email, a verification link has been sent."}
    
    if user.is_verified:
        return {"message": "Email is already verified."}
    
    verification_token = crud.create_verification_token(db, user_id=user.id)
    background_tasks.add_task(
        email_utils.send_verification_email,
        user.email,
        verification_token.token
    )
    
    return {"message": "If an account exists with this email, a verification link has been sent."}


# ============== Login / Logout ==============

@router.post("/login", response_model=auth_schema.Token)
async def login(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    OAuth2 compatible login endpoint.
    """
    user = crud.get_user_by_email(db, email=form_data.username)
    
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not user:
        raise credentials_error
    
    # Check if account is locked
    if crud.is_user_locked(user):
        remaining_time = (user.locked_until - datetime.utcnow()).seconds // 60
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account is temporarily locked. Try again in {remaining_time} minutes."
        )
    
    # Verify password
    if not hashing.verify_password(form_data.password, user.hashed_password):
        crud.increment_failed_login(db, user)
        raise credentials_error
    
    # Reactivate if deactivated
    if not user.is_active:
        crud.activate_user(db, user.id)
    
    # Check if email is verified
    if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in."
        )
    
    # Reset failed login attempts
    crud.reset_failed_login(db, user)
    
    # Create tokens
    tokens = security.create_token_pair(user.id)
    
    # Store refresh token in database
    crud.create_refresh_token(
        db,
        user_id=user.id,
        token=tokens["refresh_token"],
        expires_at=tokens["refresh_expires_at"],
        device_info=get_user_agent(request),
        ip_address=get_client_ip(request)
    )
    
    return auth_schema.Token(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=tokens["expires_in"]
    )


@router.post("/refresh", response_model=auth_schema.Token)
async def refresh_token(
    request: Request,
    data: auth_schema.RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token with token rotation.
    """
    db_token = crud.get_refresh_token(db, token=data.refresh_token)
    
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Token reuse detection
    if db_token.is_revoked:
        crud.revoke_token_family(db, db_token.family_id)
        
        email_utils.send_security_alert_email(
            db_token.user.email,
            "Suspicious activity detected: A refresh token was reused. All sessions have been logged out for security."
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again."
        )
    
    # Check expiry
    if db_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again."
        )
    
    # Reactivate if deactivated
    user = db_token.user
    if not user.is_active:
        crud.activate_user(db, user.id)
    
    # Create new token pair
    new_tokens = security.create_token_pair(user.id)
    
    # Store new refresh token
    new_db_token = crud.create_refresh_token(
        db,
        user_id=user.id,
        token=new_tokens["refresh_token"],
        expires_at=new_tokens["refresh_expires_at"],
        device_info=get_user_agent(request),
        ip_address=get_client_ip(request),
        family_id=db_token.family_id
    )
    
    # Revoke old token
    crud.revoke_refresh_token(db, db_token, replaced_by=new_db_token.id)
    
    return auth_schema.Token(
        access_token=new_tokens["access_token"],
        refresh_token=new_tokens["refresh_token"],
        token_type=new_tokens["token_type"],
        expires_in=new_tokens["expires_in"]
    )


@router.post("/logout", response_model=auth_schema.MessageResponse)
async def logout(
    data: auth_schema.RefreshTokenRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Logout and invalidate the refresh token."""
    db_token = crud.get_refresh_token(db, token=data.refresh_token)
    
    if db_token and db_token.user_id == current_user.id:
        crud.revoke_refresh_token(db, db_token)
    
    return {"message": "Successfully logged out"}


@router.post("/logout-all", response_model=auth_schema.MessageResponse)
async def logout_all_sessions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Logout from all devices/sessions."""
    revoked_count = crud.revoke_all_user_tokens(db, current_user.id)
    return {"message": f"Successfully logged out from {revoked_count} session(s)"}


# ============== Password Management ==============

@router.post("/forgot-password", response_model=auth_schema.MessageResponse)
async def forgot_password(
    data: auth_schema.ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Request password reset email."""
    user = crud.get_user_by_email(db, email=data.email)
    
    if user and user.is_active:
        reset_token = crud.create_password_reset_token(db, user_id=user.id)
        background_tasks.add_task(
            email_utils.send_password_reset_email,
            user.email,
            reset_token.token
        )
    
    return {"message": "If an account exists with this email, a password reset link has been sent."}


@router.post("/reset-password", response_model=auth_schema.MessageResponse)
async def reset_password(
    data: auth_schema.ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Reset password using the token from email."""
    token = crud.get_password_reset_token(db, token=data.token)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token."
        )
    
    user = token.user
    crud.update_user_password(db, user.id, data.new_password)
    crud.use_password_reset_token(db, token)
    crud.revoke_all_user_tokens(db, user.id)
    
    background_tasks.add_task(
        email_utils.send_password_changed_email,
        user.email
    )
    
    return {"message": "Password has been reset successfully. Please log in with your new password."}


@router.get("/reset-password")
async def reset_password_get(
    token: str,
    db: Session = Depends(get_db)
):
    """Verify reset token and redirect to frontend reset password form."""
    db_token = crud.get_password_reset_token(db, token=token)
    
    if not db_token:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/forgot-password?error=Invalid or expired password reset token.")
    
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/reset-password?token={token}")


@router.post("/change-password", response_model=auth_schema.MessageResponse)
async def change_password(
    data: auth_schema.ChangePasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Change password while logged in."""
    if not hashing.verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    if hashing.verify_password(data.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    crud.update_user_password(db, current_user.id, data.new_password)
    crud.revoke_all_user_tokens(db, current_user.id)
    
    background_tasks.add_task(
        email_utils.send_password_changed_email,
        current_user.email
    )
    
    return {"message": "Password changed successfully. Please log in again."}


# ============== Email Management ==============

@router.post("/change-email", response_model=auth_schema.MessageResponse)
async def request_email_change(
    data: auth_schema.ChangeEmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_verified_user)
):
    """Request to change email address."""
    if not hashing.verify_password(data.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect"
        )
    
    existing_user = crud.get_user_by_email(db, email=data.new_email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email is already in use"
        )
    
    verification_token = crud.create_verification_token(
        db,
        user_id=current_user.id,
        token_type="email_change",
        new_email=data.new_email
    )
    
    background_tasks.add_task(
        email_utils.send_email_change_verification,
        data.new_email,
        verification_token.token
    )
    
    return {"message": "Verification email sent to your new email address."}


# ============== Session Management ==============

@router.get("/sessions", response_model=auth_schema.SessionList)
async def get_active_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get all active sessions for the current user."""
    sessions = crud.get_user_active_sessions(db, current_user.id)
    current_ip = get_client_ip(request)
    
    session_list = []
    for session in sessions:
        session_info = auth_schema.SessionInfo(
            id=session.id,
            device_info=session.device_info,
            ip_address=session.ip_address,
            created_at=session.created_at,
            expires_at=session.expires_at,
            is_current=(session.ip_address == current_ip)
        )
        session_list.append(session_info)
    
    return auth_schema.SessionList(sessions=session_list, total=len(session_list))


@router.delete("/sessions/{session_id}", response_model=auth_schema.MessageResponse)
async def revoke_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Revoke a specific session."""
    sessions = crud.get_user_active_sessions(db, current_user.id)
    target_session = next((s for s in sessions if s.id == session_id), None)
    
    if not target_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    crud.revoke_refresh_token(db, target_session)
    
    return {"message": "Session revoked successfully"}


# ============== Auth Status ==============

@router.get("/status", response_model=auth_schema.AuthStatus)
async def get_auth_status(
    current_user: models.User = Depends(get_current_user)
):
    """Get current authentication status."""
    return auth_schema.AuthStatus(
        is_authenticated=True,
        is_verified=current_user.is_verified,
        email=current_user.email,
        user_id=current_user.id
    )