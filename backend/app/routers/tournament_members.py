"""
Tournament members & invite links — per-tournament multi-user access.

Org members of the owning org are implicit permanent admins ("owners"):
they appear in the member list with source="org" and cannot be removed,
demoted, or promoted here (manage that via the organization instead).
Everything in this router is admin-only except accepting an invite and
leaving a tournament.
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.organization import OrgMember
from app.models.tournament import Tournament
from app.models.tournament_member import TournamentMember, TournamentInvite
from app.schemas.member import (
    InviteCreate, InviteOut, MemberOut, MembersResponse, MemberRoleUpdate,
)
from app.utils.auth import get_current_user
from app.utils.tournament_access import require_tournament_access, ROLE_ADMIN

router = APIRouter()


def _is_org_member(t: Tournament, user_id: int, db: Session) -> bool:
    return db.query(OrgMember).filter(
        OrgMember.org_id == t.org_id, OrgMember.user_id == user_id).first() is not None


def _invite_state(inv: TournamentInvite) -> str | None:
    """None if the invite is usable, else why not."""
    if inv.revoked_at is not None:
        return "revoked"
    if inv.expires_at is not None:
        expires = inv.expires_at
        if expires.tzinfo is None:  # SQLite returns naive datetimes
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            return "expired"
    if inv.max_uses is not None and inv.use_count >= inv.max_uses:
        return "expired"
    return None


# ── Members list ──────────────────────────────────────────────

@router.get("/tournaments/{tournament_id}/members", response_model=MembersResponse)
def list_members(
    tournament_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t, _ = require_tournament_access(tournament_id, user, db, min_role=ROLE_ADMIN)

    members: list[MemberOut] = []

    org_rows = (
        db.query(OrgMember, User)
        .join(User, User.user_id == OrgMember.user_id)
        .filter(OrgMember.org_id == t.org_id)
        .all()
    )
    for _om, u in org_rows:
        members.append(MemberOut(
            user_id=u.user_id, name=u.name, email=u.email,
            role="admin", source="org",
        ))

    member_rows = (
        db.query(TournamentMember, User)
        .join(User, User.user_id == TournamentMember.user_id)
        .filter(TournamentMember.tournament_id == tournament_id)
        .order_by(TournamentMember.created_at)
        .all()
    )
    org_user_ids = {u.user_id for _om, u in org_rows}
    for tm, u in member_rows:
        if u.user_id in org_user_ids:
            continue  # owners take precedence
        members.append(MemberOut(
            user_id=u.user_id, name=u.name, email=u.email,
            role=tm.role, source="invite", created_at=tm.created_at,
        ))

    invites = [
        InviteOut(
            invite_id=i.invite_id, token=i.token, role=i.role,
            created_at=i.created_at, expires_at=i.expires_at, use_count=i.use_count,
        )
        for i in db.query(TournamentInvite)
        .filter(TournamentInvite.tournament_id == tournament_id)
        .order_by(TournamentInvite.created_at.desc())
        .all()
        if _invite_state(i) is None
    ]

    return MembersResponse(members=members, invites=invites)


# ── Invites ───────────────────────────────────────────────────

@router.post("/tournaments/{tournament_id}/invites", response_model=InviteOut)
def create_invite(
    tournament_id: int,
    data: InviteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_tournament_access(tournament_id, user, db, min_role=ROLE_ADMIN)

    invite = TournamentInvite(
        token=secrets.token_urlsafe(24),
        tournament_id=tournament_id,
        role=data.role,
        created_by=user.user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=data.expires_in_days),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return InviteOut(
        invite_id=invite.invite_id, token=invite.token, role=invite.role,
        created_at=invite.created_at, expires_at=invite.expires_at, use_count=invite.use_count,
    )


@router.delete("/tournaments/{tournament_id}/invites/{invite_id}")
def revoke_invite(
    tournament_id: int,
    invite_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_tournament_access(tournament_id, user, db, min_role=ROLE_ADMIN)
    invite = db.query(TournamentInvite).filter(
        TournamentInvite.invite_id == invite_id,
        TournamentInvite.tournament_id == tournament_id,
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.post("/tournaments/invites/{token}/accept")
def accept_invite(
    token: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invite = db.query(TournamentInvite).filter(TournamentInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    state = _invite_state(invite)
    if state:
        raise HTTPException(status_code=410, detail=f"invite_{state}")

    t = db.query(Tournament).filter(
        Tournament.tournament_id == invite.tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")

    result = {
        "ok": True,
        "tournament_id": t.tournament_id,
        "tournament_name": t.name,
        "role": invite.role,
        "already_member": False,
    }

    # Org members are already owners — nothing to add.
    if _is_org_member(t, user.user_id, db):
        result["already_member"] = True
        result["role"] = "admin"
        return result

    existing = db.query(TournamentMember).filter(
        TournamentMember.tournament_id == t.tournament_id,
        TournamentMember.user_id == user.user_id,
    ).first()
    if existing:
        result["already_member"] = True
        # Upgrade staff → admin if the invite grants admin; never downgrade.
        if invite.role == "admin" and existing.role != "admin":
            existing.role = "admin"
            invite.use_count += 1
            db.commit()
            result["already_member"] = False  # role changed — treat as a fresh grant
        result["role"] = existing.role
        return result

    db.add(TournamentMember(
        tournament_id=t.tournament_id,
        user_id=user.user_id,
        role=invite.role,
        invited_by=invite.created_by,
    ))
    invite.use_count += 1
    db.commit()
    return result


# ── Member role management ────────────────────────────────────

@router.patch("/tournaments/{tournament_id}/members/{member_user_id}")
def update_member_role(
    tournament_id: int,
    member_user_id: int,
    data: MemberRoleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t, _ = require_tournament_access(tournament_id, user, db, min_role=ROLE_ADMIN)

    if _is_org_member(t, member_user_id, db):
        raise HTTPException(status_code=400, detail="Organization owners always have admin access")

    member = db.query(TournamentMember).filter(
        TournamentMember.tournament_id == tournament_id,
        TournamentMember.user_id == member_user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    member.role = data.role
    db.commit()
    return {"ok": True, "role": member.role}


@router.delete("/tournaments/{tournament_id}/members/{member_user_id}")
def remove_member(
    tournament_id: int,
    member_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Admins can remove anyone (except owners); any member can remove themself (leave).
    if member_user_id == user.user_id:
        t, _ = require_tournament_access(tournament_id, user, db)
    else:
        t, _ = require_tournament_access(tournament_id, user, db, min_role=ROLE_ADMIN)

    if _is_org_member(t, member_user_id, db):
        raise HTTPException(status_code=400, detail="Organization owners cannot be removed here")

    member = db.query(TournamentMember).filter(
        TournamentMember.tournament_id == tournament_id,
        TournamentMember.user_id == member_user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    db.delete(member)
    db.commit()
    return {"ok": True}
