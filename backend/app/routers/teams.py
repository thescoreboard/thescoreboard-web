"""
Team routes — create/manage teams and their rosters.
Used by both organisers (admin panel) and public team registration.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.player import Team, TeamMember
from app.models.group import EventParticipant
from app.models.organization import Organization, OrgMember
from app.models.event import Event
from app.models.tournament import Tournament
from app.utils.auth import get_current_user
from app.utils.ratelimit import public_registration_limiter

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────

class TeamMemberIn(BaseModel):
    name:          str
    role:          Optional[str] = "player"
    jersey_number: Optional[int] = None
    age:           Optional[int] = None


SEED_SCORES = {"beginner": 2, "intermediate": 5, "advanced": 8, "pro": 10}


class TeamCreate(BaseModel):
    name:          str
    sport_key:     Optional[str] = None
    contact_name:  Optional[str] = None
    contact_phone: Optional[str] = None
    seed_level:    Optional[str] = None  # beginner / intermediate / advanced / pro
    members:       List[TeamMemberIn] = []


class TeamOut(BaseModel):
    team_id:       int
    name:          str
    sport_key:     Optional[str]
    contact_name:  Optional[str]
    contact_phone: Optional[str]
    member_count:  int
    members:       List[dict]

    class Config:
        from_attributes = True


def _serialize_team(team: Team) -> dict:
    return {
        "team_id":       team.team_id,
        "name":          team.name,
        "sport_key":     team.sport_key,
        "contact_name":  team.contact_name,
        "contact_phone": team.contact_phone,
        "seed_level":    team.seed_level,
        "member_count":  len(team.members),
        "members": [
            {
                "tm_id":         m.tm_id,
                "name":          m.name,
                "role":          m.role,
                "jersey_number": m.jersey_number,
                "age":           m.age,
            }
            for m in sorted(team.members, key=lambda x: (x.role != "captain", x.role != "vice_captain", x.tm_id))
        ],
    }


# ── Organiser: create team manually ──────────────────────────

@router.post("/orgs/{org_id}/teams")
def create_team(
    org_id: int,
    data: TeamCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Organiser creates a team and adds it to their org."""
    org = db.query(Organization).filter(Organization.org_id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not getattr(user, "is_superadmin", False):
        member = db.query(OrgMember).filter(
            OrgMember.org_id == org_id,
            OrgMember.user_id == user.user_id
        ).first()
        if not member:
            raise HTTPException(status_code=403, detail="Not authorized for this organization")

    team = Team(
        org_id=org_id,
        name=data.name.strip(),
        sport_key=data.sport_key,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        seed_level=data.seed_level,
    )
    db.add(team)
    db.flush()

    for m in data.members:
        db.add(TeamMember(
            team_id=team.team_id,
            name=m.name.strip(),
            role=m.role or "player",
            jersey_number=m.jersey_number,
            age=m.age,
        ))

    db.commit()
    db.refresh(team)
    return _serialize_team(team)


@router.get("/orgs/{org_id}/teams")
def list_org_teams(
    org_id: int,
    sport_key: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Team).filter(Team.org_id == org_id).options(joinedload(Team.members))
    if sport_key:
        query = query.filter(Team.sport_key == sport_key)
    teams = query.order_by(Team.name).all()
    return [_serialize_team(t) for t in teams]


@router.delete("/teams/{team_id}")
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    team = db.query(Team).filter(Team.team_id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    # SEC-4: verify the caller owns the org this team belongs to
    if team.org_id and not user.is_superadmin:
        member = db.query(OrgMember).filter(
            OrgMember.org_id == team.org_id,
            OrgMember.user_id == user.user_id,
        ).first()
        if not member:
            raise HTTPException(status_code=403, detail="Not authorized to delete this team")
    db.delete(team)
    db.commit()
    return {"ok": True}


# ── Enroll team in event ──────────────────────────────────────

@router.post("/events/{event_id}/teams")
def add_team_to_event(
    event_id: int,
    team_id: int,
    group_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Enroll an existing team in an event."""
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Accept both "team" and "doubles_pair" — doubles_pair is stored as "team"
    # but old events created before the fix may still have "doubles_pair" in the DB
    if event.participant_type not in ("team", "doubles_pair"):
        raise HTTPException(
            status_code=400,
            detail=f"This event is for individual players, not teams. "
                   f"Event participant_type is '{event.participant_type}'."
        )

    existing = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.team_id == team_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Team already enrolled in this event")

    # Auto-compute seed score from team's seed_level
    team = db.query(Team).filter(Team.team_id == team_id).first()
    seed = None
    if team and team.seed_level:
        seed = SEED_SCORES.get(team.seed_level.lower())

    ep = EventParticipant(event_id=event_id, team_id=team_id, group_id=group_id, seed=seed)
    db.add(ep)
    db.commit()
    return {"ok": True, "ep_id": ep.ep_id}


@router.delete("/events/{event_id}/teams/{team_id}")
def remove_team_from_event(
    event_id: int,
    team_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ep = db.query(EventParticipant).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.team_id == team_id,
    ).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Team not in this event")
    db.delete(ep)
    db.commit()
    return {"ok": True}


@router.get("/events/{event_id}/teams")
def get_event_teams(event_id: int, db: Session = Depends(get_db)):
    """Public — list all teams enrolled in an event."""
    eps = (
        db.query(EventParticipant)
        .filter(EventParticipant.event_id == event_id, EventParticipant.team_id.isnot(None))
        .options(joinedload(EventParticipant.team).joinedload(Team.members))
        .all()
    )
    return [
        {
            "ep_id":    ep.ep_id,
            "group_id": ep.group_id,
            "team":     _serialize_team(ep.team) if ep.team else None,
        }
        for ep in eps
    ]


# ── Public team / doubles-pair registration ───────────────────

class PublicTeamRegistration(BaseModel):
    # Doubles form sends: name, event_id (singular), contact_phone, members
    # Team form sends:    team_name, event_ids (list), contact_name, contact_phone, members
    # Both are accepted — fields normalised in the handler below.
    name:          Optional[str] = None   # doubles pair name
    team_name:     Optional[str] = None   # full-team name (legacy)
    contact_name:  Optional[str] = ""
    contact_phone: Optional[str] = ""
    sport_key:     Optional[str] = None
    event_id:      Optional[int] = None   # singular — doubles form
    event_ids:     List[int]     = []     # plural   — team form
    members:       List[TeamMemberIn]


@router.post("/public/tournaments/{tournament_id}/register-team",
             dependencies=[Depends(public_registration_limiter)])
def public_register_team(
    tournament_id: int,
    data: PublicTeamRegistration,
    db: Session = Depends(get_db),
):
    """
    Public registration for teams (cricket/football) and doubles pairs (TT/badminton).
    No auth required. Tournament must currently have registration open.
    """
    tournament = db.query(Tournament).filter(
        Tournament.tournament_id == tournament_id,
        Tournament.is_active == True,
    ).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if not tournament.registration_open:
        raise HTTPException(status_code=400, detail="Tournament is not accepting registrations")

    # ── Normalise name (doubles sends "name", teams send "team_name")
    team_display_name = (data.name or data.team_name or "").strip()
    if not team_display_name:
        raise HTTPException(status_code=422, detail="Pair or team name is required")

    # ── Normalise event IDs (doubles sends event_id int, teams send event_ids list)
    all_event_ids: List[int] = list(data.event_ids)
    if data.event_id and data.event_id not in all_event_ids:
        all_event_ids.append(data.event_id)

    if len(data.members) < 1:
        raise HTTPException(status_code=400, detail="At least one member is required")

    # ── Resolve target events
    if all_event_ids:
        target_events = db.query(Event).filter(
            Event.tournament_id == tournament_id,
            Event.event_id.in_(all_event_ids),
            Event.is_active == True,
            Event.participant_type.in_(["team", "doubles_pair"]),
        ).all()
    else:
        target_events = db.query(Event).filter(
            Event.tournament_id == tournament_id,
            Event.is_active == True,
            Event.participant_type.in_(["team", "doubles_pair"]),
        ).all()

    if not target_events:
        raise HTTPException(status_code=400, detail="No matching events found in this tournament")

    # ── Doubles-specific validation: exactly 2 members per pair
    doubles_events = [e for e in target_events if e.participant_type == "doubles_pair"]
    if doubles_events and len(data.members) != 2:
        raise HTTPException(
            status_code=422,
            detail=f"Doubles pair registration requires exactly 2 players (got {len(data.members)})"
        )

    # ── Deduplicate: reuse existing team/pair with same name + phone
    contact_phone = (data.contact_phone or "").strip()
    existing = db.query(Team).filter(
        Team.org_id == tournament.org_id,
        Team.name == team_display_name,
        Team.contact_phone == contact_phone,
    ).first()

    if existing:
        team = existing
    else:
        team = Team(
            org_id=tournament.org_id,
            name=team_display_name,
            contact_name=(data.contact_name or "").strip(),
            contact_phone=contact_phone,
        )
        db.add(team)
        db.flush()

        for i, m in enumerate(data.members):
            db.add(TeamMember(
                team_id=team.team_id,
                name=m.name.strip(),
                role=m.role if m.role else ("player1" if i == 0 else "player2"),
                jersey_number=m.jersey_number,
                age=m.age,
            ))

    # ── Enrol in target events
    enrolled = []
    for event in target_events:
        already = db.query(EventParticipant).filter(
            EventParticipant.event_id == event.event_id,
            EventParticipant.team_id == team.team_id,
        ).first()
        if already:
            continue
        db.add(EventParticipant(event_id=event.event_id, team_id=team.team_id))
        enrolled.append(event.event_id)

    db.commit()

    is_doubles = bool(doubles_events)
    return {
        "ok":              True,
        "team_id":         team.team_id,
        "team_name":       team.name,
        "member_count":    len(data.members),
        "enrolled_events": enrolled,
        "message": (
            f"Pair '{team.name}' registered for {tournament.name}"
            if is_doubles else
            f"Team '{team.name}' registered for {tournament.name}"
        ),
    }