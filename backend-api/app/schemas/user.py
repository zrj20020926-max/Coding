from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserPublic(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    nickname: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    is_admin: bool
    solved_count: int
    submission_count: int
    accepted_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: Optional[str] = Field(default=None, min_length=1, max_length=50)
    avatar_url: Optional[str] = Field(default=None, max_length=2000)
    bio: Optional[str] = Field(default=None, max_length=300)
