"""
Organization — a club, school, or group that hosts tournaments.
OrgMember — links users to organizations with roles.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    org_id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    logo_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    members = relationship("OrgMember", back_populates="organization")
    tournaments = relationship("Tournament", back_populates="organization")


class OrgMember(Base):
    """Links a user to an organization with a role."""
    __tablename__ = "org_members"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="admin")  # admin | scorer | viewer

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_org_user"),
    )

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="organizations")
