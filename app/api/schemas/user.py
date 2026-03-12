from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
import re


class UserBase(BaseModel):
    """Base user model."""
    email: EmailStr = Field(..., description="User's email address")


class UserCreate(UserBase):
    """User creation request."""
    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters with uppercase, lowercase, digit, and special character"
    )
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserUpdate(BaseModel):
    """User profile update request."""
    email: Optional[EmailStr] = Field(
        None,
        description="New email address (use /auth/change-email endpoint)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "email": "newemail@example.com"
            }
        }


class PasswordReset(BaseModel):
    """Password reset request."""
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (8+ chars with uppercase, lowercase, digit)"
    )
    
    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v


class User(UserBase):
    """User profile response."""
    id: UUID = Field(..., description="User's unique identifier")
    is_active: bool = Field(..., description="Whether the account is active")
    is_verified: bool = Field(..., description="Whether email is verified")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "user@example.com",
                "is_active": True,
                "is_verified": True,
                "created_at": "2024-03-01T10:00:00Z",
                "last_login_at": "2024-03-08T14:20:00Z"
            }
        }


class UserProfile(User):
    """Complete user profile with additional fields."""
    updated_at: datetime = Field(..., description="Last profile update timestamp")
    password_changed_at: datetime = Field(..., description="Last password change timestamp")

    class Config:
        from_attributes = True


class DeleteAccountRequest(BaseModel):
    """Request to permanently delete user account."""
    password: str = Field(..., description="Current password for verification")
    confirmation: str = Field(
        ...,
        pattern="^DELETE$",
        description="Type 'DELETE' exactly to confirm account deletion"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "password": "SecurePass123!",
                "confirmation": "DELETE"
            }
        }
