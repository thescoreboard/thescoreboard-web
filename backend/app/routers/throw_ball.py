"""
Throw Ball routes — lineup, timeouts, substitutions, and the spectator/live
view. Set/match scoring itself goes through the generic PATCH
/matches/{id}/score endpoint in matches.py (sport="throw_ball" is handled by
the same set-based branch used for table_tennis/badminton).

Timeout and substitution counters are per-set and have no generic column to
live in, so they're tracked in Match.live_state["throw_ball"], keyed by the
current set number — mirroring how cricket/football already stash
sport-specific counters in live_state.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified
from typing import List, Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.match import Match, MatchParticipant
from app.models.player import TeamMember
from app.models.throw_ball import ThrowBallLineup
from app.utils.auth import get_current_user
from app.routers.matches import _load_match, _check_event_access, _push_ws_update

router = APIRouter()

PLAYERS_ON_COURT = 7
MAX_TIMEOUTS_PER_SET = 2
MAX_SUBSTITUTIONS_PER_SET = 5
SERVE_POSITION = 9


# ── Schemas ───────────────────────────────────────────────────

class LineupEntry(BaseModel):
    team_member_id: int
    on_court: bool = True
    court_position: Optional[int] = Field(None, ge=1, le=9)


class LineupSubmit(BaseModel):
    position: int = Field(..., ge=1, le=2)
    lineup: List[LineupEntry]


class TimeoutRequest(BaseModel):
    position: int = Field(..., ge=1, le=2)


class SubstituteRequest(BaseModel):
    position: int = Field(..., ge=1, le=2)
    out_team_member_id: int
    in_team_member_id: int


# ── Helpers ───────────────────────────────────────────────────

def _require_throw_ball(match: Match) -> None:
    if match.event.sport_key != "throw_ball":
        raise HTTPException(status_code=400, detail="This match is not a Throw Ball match")


def _current_set(match: Match):
    sets = sorted(match.sets, key=lambda s: s.set_number)
    current = next((s for s in sets if not s.is_complete), None)
    return current or (sets[-1] if sets else None)


def _serialize_lineup(rows: List[ThrowBallLineup]) -> List[dict]:
    return [
        {
            "id": r.id,
            "team_member_id": r.team_member_id,
            "name": r.team_member.name if r.team_member else None,
            "jersey_number": r.team_member.jersey_number if r.team_member else None,
            "gender": r.team_member.gender if r.team_member else None,
            "position": r.position,
            "on_court": r.on_court,
            "court_position": r.court_position,
        }
        for r in sorted(rows, key=lambda r: (r.position, r.court_position or 99))
    ]


# ── Routes ────────────────────────────────────────────────────

@router.post("/matches/{match_id}/throw-ball/lineup")
def submit_lineup(
    match_id: int,
    data: LineupSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Set (or replace) one team's court lineup: up to 12 players, exactly 7
    marked on_court with a unique court_position (1-9) each. Required before
    the match can be scored/go live.
    """
    match = _load_match(match_id, db)
    _check_event_access(match.event, user, db)
    _require_throw_ball(match)

    mp = next((p for p in match.participants if p.position == data.position), None)
    if not mp or not mp.team_id:
        raise HTTPException(status_code=400, detail=f"No team assigned to position {data.position}")

    member_ids = [e.team_member_id for e in data.lineup]
    if len(set(member_ids)) != len(member_ids):
        raise HTTPException(status_code=400, detail="Duplicate team_member_id in lineup")

    members = db.query(TeamMember).filter(TeamMember.tm_id.in_(member_ids)).all()
    members_by_id = {m.tm_id: m for m in members}
    for mid in member_ids:
        member = members_by_id.get(mid)
        if not member or member.team_id != mp.team_id:
            raise HTTPException(status_code=400, detail=f"team_member {mid} is not on this team's roster")

    on_court_entries = [e for e in data.lineup if e.on_court]
    if len(on_court_entries) != PLAYERS_ON_COURT:
        raise HTTPException(
            status_code=400,
            detail=f"Exactly {PLAYERS_ON_COURT} players must be on court (got {len(on_court_entries)})",
        )
    court_positions = [e.court_position for e in on_court_entries]
    if any(cp is None for cp in court_positions) or len(set(court_positions)) != len(court_positions):
        raise HTTPException(status_code=400, detail="Each on-court player needs a unique court_position (1-9)")

    event = match.event
    gender_format = (event.sport_config or {}).get("gender_format", "open")
    if gender_format == "women_only":
        non_female = [mid for mid in member_ids if (members_by_id[mid].gender or "").lower() != "female"]
        if non_female:
            raise HTTPException(
                status_code=400,
                detail=f"team_member(s) {non_female} are not registered as female in a women-only event",
            )

    # Replace this team's lineup wholesale — simplest to reason about and
    # matches how organisers actually use it (re-submit the full 12).
    db.query(ThrowBallLineup).filter(
        ThrowBallLineup.match_id == match_id,
        ThrowBallLineup.position == data.position,
    ).delete()
    db.flush()

    rows = []
    for e in data.lineup:
        row = ThrowBallLineup(
            match_id=match_id,
            team_member_id=e.team_member_id,
            position=data.position,
            on_court=e.on_court,
            court_position=e.court_position if e.on_court else None,
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for r in rows:
        db.refresh(r)
    return {"match_id": match_id, "position": data.position, "lineup": _serialize_lineup(rows)}


@router.get("/matches/{match_id}/throw-ball/lineup")
def get_lineup(
    match_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    match = _load_match(match_id, db)
    _require_throw_ball(match)
    rows = (
        db.query(ThrowBallLineup)
        .filter(ThrowBallLineup.match_id == match_id)
        .options(joinedload(ThrowBallLineup.team_member))
        .all()
    )
    return {"match_id": match_id, "lineup": _serialize_lineup(rows)}


@router.post("/matches/{match_id}/throw-ball/timeout")
def record_timeout(
    match_id: int,
    data: TimeoutRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    match = _load_match(match_id, db)
    _check_event_access(match.event, user, db)
    _require_throw_ball(match)

    current_set = _current_set(match)
    if not current_set:
        raise HTTPException(status_code=400, detail="No active set to call a timeout in")
    if current_set.is_complete:
        raise HTTPException(status_code=400, detail=f"Set {current_set.set_number} is already complete; cannot call a timeout")

    ls = dict(match.live_state or {})
    tb = dict(ls.get("throw_ball") or {})
    timeouts = dict(tb.get("timeouts") or {})
    set_key = str(current_set.set_number)
    set_timeouts = dict(timeouts.get(set_key) or {"1": 0, "2": 0})

    used = set_timeouts.get(str(data.position), 0)
    if used >= MAX_TIMEOUTS_PER_SET:
        raise HTTPException(
            status_code=400,
            detail=f"Team {data.position} has no timeouts left in set {current_set.set_number}",
        )
    set_timeouts[str(data.position)] = used + 1
    timeouts[set_key] = set_timeouts
    tb["timeouts"] = timeouts
    ls["throw_ball"] = tb
    match.live_state = ls
    flag_modified(match, "live_state")

    db.commit()
    background_tasks.add_task(_push_ws_update, match.event_id)
    return {
        "set_number": current_set.set_number,
        "timeouts_used": set_timeouts,
        "timeouts_remaining": {
            "1": MAX_TIMEOUTS_PER_SET - set_timeouts.get("1", 0),
            "2": MAX_TIMEOUTS_PER_SET - set_timeouts.get("2", 0),
        },
    }


@router.post("/matches/{match_id}/throw-ball/substitute")
def substitute_player(
    match_id: int,
    data: SubstituteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    match = _load_match(match_id, db)
    _check_event_access(match.event, user, db)
    _require_throw_ball(match)

    current_set = _current_set(match)
    if not current_set:
        raise HTTPException(status_code=400, detail="No active set to substitute in")
    if current_set.is_complete:
        raise HTTPException(status_code=400, detail=f"Set {current_set.set_number} is already complete; cannot substitute")

    rows = db.query(ThrowBallLineup).filter(
        ThrowBallLineup.match_id == match_id,
        ThrowBallLineup.position == data.position,
    ).all()
    out_row = next((r for r in rows if r.team_member_id == data.out_team_member_id), None)
    in_row = next((r for r in rows if r.team_member_id == data.in_team_member_id), None)
    if not out_row:
        raise HTTPException(status_code=400, detail=f"team_member {data.out_team_member_id} is not in this match's lineup")
    if not in_row:
        raise HTTPException(status_code=400, detail=f"team_member {data.in_team_member_id} is not in this match's lineup")
    if not out_row.on_court:
        raise HTTPException(status_code=400, detail=f"team_member {data.out_team_member_id} is not currently on court")
    if in_row.on_court:
        raise HTTPException(status_code=400, detail=f"team_member {data.in_team_member_id} is not currently on the bench")
    if out_row.court_position == SERVE_POSITION:
        raise HTTPException(status_code=400, detail="Cannot substitute in serve position")

    ls = dict(match.live_state or {})
    tb = dict(ls.get("throw_ball") or {})
    subs = dict(tb.get("substitutions") or {})
    set_key = str(current_set.set_number)
    set_subs = dict(subs.get(set_key) or {"1": 0, "2": 0})

    used = set_subs.get(str(data.position), 0)
    if used >= MAX_SUBSTITUTIONS_PER_SET:
        raise HTTPException(
            status_code=400,
            detail=f"Max substitutions exceeded for team {data.position} in set {current_set.set_number} "
                   f"(limit {MAX_SUBSTITUTIONS_PER_SET})",
        )
    set_subs[str(data.position)] = used + 1
    subs[set_key] = set_subs
    tb["substitutions"] = subs
    ls["throw_ball"] = tb
    match.live_state = ls
    flag_modified(match, "live_state")

    slot = out_row.court_position
    out_row.on_court, in_row.on_court = False, True
    out_row.court_position, in_row.court_position = None, slot

    db.commit()
    background_tasks.add_task(_push_ws_update, match.event_id)
    rows = db.query(ThrowBallLineup).filter(
        ThrowBallLineup.match_id == match_id,
        ThrowBallLineup.position == data.position,
    ).options(joinedload(ThrowBallLineup.team_member)).all()
    return {
        "set_number": current_set.set_number,
        "substitutions_used": set_subs,
        "lineup": _serialize_lineup(rows),
    }


@router.get("/matches/{match_id}/throw-ball/live")
def get_live_state(
    match_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Spectator/TV-display summary: current set, scores, timeouts remaining, status."""
    match = _load_match(match_id, db)
    _require_throw_ball(match)

    sets = sorted(match.sets, key=lambda s: s.set_number)
    current_set = _current_set(match)
    parts = sorted(match.participants, key=lambda p: p.position)

    ls = match.live_state or {}
    tb = ls.get("throw_ball") or {}
    set_key = str(current_set.set_number) if current_set else None
    timeouts_used = (tb.get("timeouts") or {}).get(set_key, {"1": 0, "2": 0}) if set_key else {"1": 0, "2": 0}

    return {
        "match_id": match.match_id,
        "status": match.status,
        "current_set_number": current_set.set_number if current_set else None,
        "current_set_score": {
            "team_1": current_set.score_p1 if current_set else 0,
            "team_2": current_set.score_p2 if current_set else 0,
        },
        "sets_won": {
            "team_1": parts[0].score if len(parts) > 0 else 0,
            "team_2": parts[1].score if len(parts) > 1 else 0,
        },
        "timeouts_remaining": {
            "team_1": MAX_TIMEOUTS_PER_SET - timeouts_used.get("1", 0),
            "team_2": MAX_TIMEOUTS_PER_SET - timeouts_used.get("2", 0),
        },
        "sets": [
            {
                "set_number": s.set_number,
                "score_p1": s.score_p1,
                "score_p2": s.score_p2,
                "winner": s.winner_position,
                "is_complete": s.is_complete,
            }
            for s in sets
        ],
    }
