"""
ThrowBallLineup — per-match court roster for a Throw Ball team.

Each team fields 7 players on court plus up to 5 bench players, drawn from
the team's TeamMember roster. This table tracks who is currently on court
and their rotation slot (1-9) so substitutions and the "no sub while in the
serve position (9)" rule can be enforced. Scoring itself reuses the generic
Match / MatchParticipant / MatchSet tables via the ThrowBall sport engine —
this table only tracks lineup state, which has no generic equivalent.
"""
from sqlalchemy import (
    Column, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class ThrowBallLineup(Base):
    __tablename__ = "throw_ball_lineups"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.match_id", ondelete="CASCADE"), nullable=False, index=True)
    team_member_id = Column(Integer, ForeignKey("team_members.tm_id", ondelete="CASCADE"), nullable=False, index=True)

    # Which side this player is on — mirrors MatchParticipant.position (1 or 2).
    position = Column(Integer, nullable=False)

    on_court = Column(Boolean, nullable=False, default=True)
    # Rotation slot 1-9 while on court; null while on the bench.
    # Position 9 is the serve position — a player there cannot be substituted.
    court_position = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("match_id", "team_member_id", name="uq_tb_lineup_member"),
        CheckConstraint("position IN (1, 2)", name="ck_tb_lineup_position"),
    )

    match = relationship("Match")
    team_member = relationship("TeamMember")
