"""
Schemas for tournament members and invite links.
"""
from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, Field


class InviteCreate(BaseModel):
    role: Literal["admin", "staff"] = "staff"
    expires_in_days: int = Field(default=7, ge=1, le=30)


class InviteOut(BaseModel):
    invite_id: int
    token: str
    role: str
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    use_count: int = 0


class MemberOut(BaseModel):
    user_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    role: str                       # "admin" | "staff"
    source: Literal["org", "invite"]
    created_at: Optional[datetime] = None


class MembersResponse(BaseModel):
    members: List[MemberOut]
    invites: List[InviteOut]


class MemberRoleUpdate(BaseModel):
    role: Literal["admin", "staff"]
