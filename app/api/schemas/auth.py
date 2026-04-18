from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class Token(BaseModel):
    """JWT token response for login and refresh endpoints."""
    access_token: str = Field(..., description="JWT access token for API authentication")
    refresh_token: str = Field(..., description="JWT refresh token for obtaining new access tokens")
    token_type: str = Field(default="bearer", description="Token type, always 'bearer'")
    expires_in: int = Field(..., description="Access token expiry time in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        }


class TokenData(BaseModel):
    """Token claims extracted from JWT."""
    user_id: Optional[UUID] = Field(None, description="User ID from token")
    token_type: Optional[str] = Field(None, description="'access' or 'refresh'")


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token."""
    refresh_token: str = Field(..., description="Valid refresh token from login/refresh response")

    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class LoginRequest(BaseModel):
    """Credentials for login."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!"
            }
        }


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters with uppercase, lowercase, digit, and special character"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!"
            }
        }


class VerifyEmailRequest(BaseModel):
    """Email verification request."""
    token: str = Field(..., description="Verification token received in email")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class ResendVerificationRequest(BaseModel):
    """Request to resend verification email."""
    email: EmailStr = Field(..., description="Email address to send verification to")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }


class ForgotPasswordRequest(BaseModel):
    """Password reset request."""
    email: EmailStr = Field(..., description="Email address for password reset")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }


class ResetPasswordRequest(BaseModel):
    """Password reset with token."""
    token: str = Field(..., description="Password reset token from email")
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (8+ chars with uppercase, lowercase, digit, special)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "new_password": "NewSecurePass123!"
            }
        }


class ChangePasswordRequest(BaseModel):
    """Change password for authenticated user."""
    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (8+ chars with uppercase, lowercase, digit, special)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "current_password": "CurrentPass123!",
                "new_password": "NewSecurePass123!"
            }
        }


class ChangeEmailRequest(BaseModel):
    """Change email for authenticated user."""
    new_email: EmailStr = Field(..., description="New email address")
    password: str = Field(..., description="Current password for verification")

    class Config:
        json_schema_extra = {
            "example": {
                "new_email": "newemail@example.com",
                "password": "CurrentPass123!"
            }
        }


class SessionInfo(BaseModel):
    """Information about an authenticated session."""
    id: UUID = Field(..., description="Session ID")
    device_info: Optional[str] = Field(None, description="Device information (User-Agent)")
    ip_address: Optional[str] = Field(None, description="IP address of session")
    created_at: datetime = Field(..., description="Session creation timestamp")
    expires_at: datetime = Field(..., description="Session expiration timestamp")
    is_current: bool = Field(False, description="Whether this is the current session")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "990e8400-e29b-41d4-a716-446655440000",
                "device_info": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "ip_address": "127.0.0.1",
                "created_at": "2024-03-08T14:00:00Z",
                "expires_at": "2024-03-15T14:00:00Z",
                "is_current": True
            }
        }


class SessionList(BaseModel):
    """List of sessions for a user."""
    sessions: list[SessionInfo] = Field(..., description="List of active sessions")
    total: int = Field(..., description="Total number of sessions")

    class Config:
        json_schema_extra = {
            "example": {
                "sessions": [
                    {
                        "id": "990e8400-e29b-41d4-a716-446655440000",
                        "device_info": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "ip_address": "127.0.0.1",
                        "created_at": "2024-03-08T14:00:00Z",
                        "expires_at": "2024-03-15T14:00:00Z",
                        "is_current": True
                    }
                ],
                "total": 1
            }
        }


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str = Field(..., description="Response message")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation completed successfully"
            }
        }


class AuthStatus(BaseModel):
    """Authentication status information."""
    is_authenticated: bool = Field(..., description="Whether user is authenticated")
    is_verified: bool = Field(..., description="Whether user's email is verified")
    email: str = Field(..., description="User's email address")
    user_id: UUID = Field(..., description="User's unique identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "is_authenticated": True,
                "is_verified": True,
                "email": "user@example.com",
                "user_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
