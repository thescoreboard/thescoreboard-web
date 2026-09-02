"""
Group — a pool within an event (Group A, Group B, etc.)
EventParticipant — enrollment of a player or team in an event + group assignment.
Standing — running points table for round-robin / group-stage events.
"""
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Group(Base):
    __tablename__ = "groups"

    group_id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.event_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # "Group A", "Pool 1", etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    event = relationship("Event", back_populates="groups")
    participants = relationship("EventParticipant", back_populates="group")
    matches = relationship("Match", back_populates="group")


class EventParticipant(Base):
    """
    Enrolls a player (individual sport) or team (team sport) in an event.
    Exactly one of player_id or team_id will be set, based on event.participant_type.
    """
    __tablename__ = "event_participants"

    ep_id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.event_id", ondelete="CASCADE"), nullable=False, index=True)

    # One of these is set depending on participant_type
    player_id = Column(Integer, ForeignKey("players.player_id", ondelete="CASCADE"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=True, index=True)

    group_id = Column(Integer, ForeignKey("groups.group_id", ondelete="SET NULL"), nullable=True, index=True)
    seed = Column(Integer, nullable=True)
    status = Column(String(50), default="active")  # active | eliminated | withdrawn

    # Payment collection — tracks entry-fee payment for this registration.
    # not_required: tournament has no payment collection configured
    # pending:      screenshot submitted, awaiting organiser review
    # paid:         organiser confirmed payment received
    payment_status         = Column(String(20), nullable=False, default="not_required")
    payment_screenshot_url = Column(String(500), nullable=True)
    payment_submitted_at   = Column(DateTime(timezone=True), nullable=True)
    payment_confirmed_at   = Column(DateTime(timezone=True), nullable=True)
    payment_confirmed_by   = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # A player or team can only be enrolled once per event
        UniqueConstraint("event_id", "player_id", name="uq_event_player"),
        UniqueConstraint("event_id", "team_id", name="uq_event_team"),
        # DI-1: exactly one of player_id / team_id must be set.
        CheckConstraint(
            "(player_id IS NULL) <> (team_id IS NULL)", name="ck_ep_one_side"),
        # DI-2: payment_status is a closed enum.
        CheckConstraint(
            "payment_status IN ('not_required', 'pending', 'paid')",
            name="ck_ep_payment_status"),
    )

    event = relationship("Event", back_populates="participants")
    player = relationship("Player", back_populates="event_participations")
    team = relationship("Team", back_populates="event_participations")
    group = relationship("Group", back_populates="participants")
    payment_confirmed_by_user = relationship("User", foreign_keys=[payment_confirmed_by])


class Standing(Base):
    """
    Running points table row for one participant in a round-robin or group-stage event.
    Recalculated after every completed match.
    """
    __tablename__ = "standings"

    standing_id    = Column(Integer, primary_key=True)
    event_id       = Column(Integer, ForeignKey("events.event_id",   ondelete="CASCADE"), nullable=False, index=True)
    group_id       = Column(Integer, ForeignKey("groups.group_id",   ondelete="CASCADE"), nullable=True,  index=True)
    player_id      = Column(Integer, ForeignKey("players.player_id", ondelete="CASCADE"), nullable=True)
    team_id        = Column(Integer, ForeignKey("teams.team_id",     ondelete="CASCADE"), nullable=True)

    matches_played = Column(Integer, nullable=False, default=0)
    wins           = Column(Integer, nullable=False, default=0)
    losses         = Column(Integer, nullable=False, default=0)
    sets_won       = Column(Integer, nullable=False, default=0)
    sets_lost      = Column(Integer, nullable=False, default=0)
    points_for     = Column(Integer, nullable=False, default=0)
    points_against = Column(Integer, nullable=False, default=0)
    ranking_points = Column(Integer, nullable=False, default=0)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("event_id", "group_id", "player_id", name="uq_standing_player"),
        UniqueConstraint("event_id", "group_id", "team_id",   name="uq_standing_team"),
    )

    event  = relationship("Event")
    player = relationship("Player")
    team   = relationship("Team")
