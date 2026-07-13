"""
TournamentMember — per-tournament access grants (admin | staff).
TournamentInvite — shareable, revocable invite links that add members.

Org members of the owning organization are implicit permanent admins
("owners") and never get a TournamentMember row — see
app.utils.tournament_access.get_tournament_role.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base

TOURNAMENT_ROLES = ["admin", "staff"]


class TournamentMember(Base):
    __tablename__ = "tournament_members"

    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="staff")  # admin | staff
    invited_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tournament_id", "user_id", name="uq_tournament_user"),
    )


class TournamentInvite(Base):
    __tablename__ = "tournament_invites"

    invite_id = Column(Integer, primary_key=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.tournament_id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # role granted on accept
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)   # null = no expiry
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    max_uses = Column(Integer, nullable=True)                     # null = unlimited
    use_count = Column(Integer, nullable=False, default=0)
