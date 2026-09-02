"""
TugOfWarWeighIn — one team's verified roster + total weight for a match.
TugOfWarPuller  — the 8 weighed-in pullers making up that roster.

Pull results themselves are NOT modeled here: each pull is recorded as a
MatchSet row (set_number = pull_num, winner_position = winning side,
is_complete = True) via the TugOfWar sport engine, so pulls plug into the
same Standing/points machinery every other sport's sets use. Per-pull extras
that don't fit MatchSet's columns (duration, cautions log) live in
Match.live_state["pulls"].
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey,
    UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class TugOfWarWeighIn(Base):
    __tablename__ = "tug_of_war_weighins"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.match_id", ondelete="CASCADE"), nullable=False, index=True)

    # Which side this roster belongs to — mirrors MatchParticipant.position (1 or 2).
    position = Column(Integer, nullable=False)

    total_weight_kg = Column(Float, nullable=False)
    verified_at = Column(DateTime(timezone=True), server_default=func.now())

    caution_count = Column(Integer, nullable=False, default=0)
    substitution_count = Column(Integer, nullable=False, default=0)
    is_disqualified = Column(Boolean, nullable=False, default=False)
    disqualified_reason = Column(String(50), nullable=True)  # "cautions_exceeded", etc.

    __table_args__ = (
        UniqueConstraint("match_id", "position", name="uq_tow_weighin_position"),
        CheckConstraint("position IN (1, 2)", name="ck_tow_weighin_position"),
    )

    match = relationship("Match")
    pullers = relationship(
        "TugOfWarPuller", back_populates="weighin", cascade="all, delete-orphan"
    )


class TugOfWarPuller(Base):
    __tablename__ = "tug_of_war_pullers"

    id = Column(Integer, primary_key=True)
    weighin_id = Column(Integer, ForeignKey("tug_of_war_weighins.id", ondelete="CASCADE"), nullable=False, index=True)
    team_member_id = Column(Integer, ForeignKey("team_members.tm_id", ondelete="SET NULL"), nullable=True, index=True)

    weight_kg = Column(Float, nullable=False)
    position = Column(String(20), nullable=False)      # "anchor" | "puller_1".."puller_7"
    position_order = Column(Integer, nullable=False)   # 1-8, anchor = 8
    weighed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Set when this puller is an injury replacement for someone else.
    substituted_for_team_member_id = Column(
        Integer, ForeignKey("team_members.tm_id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("weighin_id", "position", name="uq_tow_puller_position"),
    )

    weighin = relationship("TugOfWarWeighIn", back_populates="pullers")
    team_member = relationship("TeamMember", foreign_keys=[team_member_id])
