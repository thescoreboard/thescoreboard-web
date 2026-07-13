"""
Role computation — extracted from auth.py so it can be imported by any
router (dashboard, auth, etc.) without creating circular dependencies.
"""
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import OrgMember
from app.models.tournament_member import TournamentMember


def compute_roles(user: User, db: Session) -> list[str]:
    """
    Derive the user's role list from DB state.
    Every authenticated user is a 'player'.
    'organiser' is added when they belong to at least one org, OR when they
    were invited to help manage at least one tournament (staff-only users
    need the organiser mode switch too).
    'superadmin' is added when the DB flag is set.
    """
    roles: list[str] = ["player"]
    has_org = db.query(OrgMember).filter(OrgMember.user_id == user.user_id).first()
    has_tournament = None
    if not has_org:
        has_tournament = db.query(TournamentMember).filter(
            TournamentMember.user_id == user.user_id).first()
    if has_org or has_tournament:
        roles.append("organiser")
    if user.is_superadmin:
        roles.append("superadmin")
    return roles
