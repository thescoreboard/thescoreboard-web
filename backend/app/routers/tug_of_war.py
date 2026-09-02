"""
Tug of War routes — weigh-in, pull results, cautions, injury substitution,
and the spectator/live view.

Each pull is recorded as a MatchSet row (see app/sports/tug_of_war/scoring.py
for why), created/advanced the same way table_tennis/badminton advance sets
in matches.py. Weigh-in rosters, cautions, and disqualification live in
TugOfWarWeighIn/TugOfWarPuller since they have no generic equivalent.
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified
from typing import List, Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.event import Event
from app.models.match import Match, MatchParticipant, MatchSet
from app.models.player import TeamMember
from app.models.tug_of_war import TugOfWarWeighIn, TugOfWarPuller
from app.utils.auth import get_current_user
from app.routers.matches import _load_match, _check_event_access, _push_ws_update, _finish_match

router = APIRouter()

WEIGHT_LIMITS_KG = {
    "featherweight": 500.0,
    "lightweight": 560.0,
    "middleweight": 600.0,
    "heavyweight": 700.0,
    "superheavyweight": 800.0,
}
PULLERS_PER_TEAM = 8
VALID_POSITIONS = {"anchor"} | {f"puller_{i}" for i in range(1, 8)}
POSITION_ORDER = {f"puller_{i}": i for i in range(1, 8)}
POSITION_ORDER["anchor"] = 8
MAX_CAUTIONS_BEFORE_DQ = 2
MAX_INJURY_SUBS = 1
SETS_TO_WIN = 2  # best of 3 pulls


# ── Schemas ───────────────────────────────────────────────────

class PullerIn(BaseModel):
    team_member_id: int
    weight_kg: float = Field(..., gt=0)
    position: str


class WeighInSubmit(BaseModel):
    position: int = Field(..., ge=1, le=2)
    pullers: List[PullerIn]


class PullResult(BaseModel):
    winning_position: int = Field(..., ge=1, le=2)
    duration_seconds: int = Field(..., ge=0)


class CautionRequest(BaseModel):
    position: int = Field(..., ge=1, le=2)
    reason: Optional[str] = None


class InjurySubRequest(BaseModel):
    position: int = Field(..., ge=1, le=2)
    injured_team_member_id: int
    replacement_team_member_id: int
    replacement_weight_kg: float = Field(..., gt=0)


# ── Helpers ───────────────────────────────────────────────────

def _require_tug_of_war(match: Match) -> None:
    if match.event.sport_key != "tug_of_war":
        raise HTTPException(status_code=400, detail="This match is not a Tug of War match")


def _weight_limit(match: Match) -> float:
    if not match.weight_category or match.weight_category not in WEIGHT_LIMITS_KG:
        raise HTTPException(status_code=400, detail="This match has no valid weight_category set")
    return WEIGHT_LIMITS_KG[match.weight_category]


def _weighins(match_id: int, db: Session) -> dict:
    rows = db.query(TugOfWarWeighIn).filter(TugOfWarWeighIn.match_id == match_id).all()
    return {w.position: w for w in rows}


def _serialize_puller(p: TugOfWarPuller) -> dict:
    return {
        "id": p.id,
        "team_member_id": p.team_member_id,
        "name": p.team_member.name if p.team_member else None,
        "weight_kg": p.weight_kg,
        "position": p.position,
        "position_order": p.position_order,
        "substituted_for_team_member_id": p.substituted_for_team_member_id,
    }


def _serialize_weighin(w: TugOfWarWeighIn) -> dict:
    return {
        "position": w.position,
        "total_weight_kg": w.total_weight_kg,
        "verified_at": str(w.verified_at) if w.verified_at else None,
        "caution_count": w.caution_count,
        "substitution_count": w.substitution_count,
        "is_disqualified": w.is_disqualified,
        "disqualified_reason": w.disqualified_reason,
        "pullers": [_serialize_puller(p) for p in sorted(w.pullers, key=lambda p: p.position_order)],
    }


# ── Routes ────────────────────────────────────────────────────

@router.post("/matches/{match_id}/tug-of-war/weigh-in")
def record_weigh_in(
    match_id: int,
    data: WeighInSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    match = _load_match(match_id, db)
    _check_event_access(match.event, user, db)
    _require_tug_of_war(match)

    if match.status in ("live", "done"):
        raise HTTPException(status_code=400, detail="Cannot weigh in after the match has started")

    mp = next((p for p in match.participants if p.position == data.position), None)
    if not mp or not mp.team_id:
        raise HTTPException(status_code=400, detail=f"No team assigned to position {data.position}")

    existing = db.query(TugOfWarWeighIn).filter(
        TugOfWarWeighIn.match_id == match_id,
        TugOfWarWeighIn.position == data.position,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Team {data.position} has already been weighed in")

    if len(data.pullers) != PULLERS_PER_TEAM:
        raise HTTPException(status_code=400, detail=f"Exactly {PULLERS_PER_TEAM} pullers are required")

    positions = [p.position for p in data.pullers]
    if len(set(positions)) != len(positions) or set(positions) != VALID_POSITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Positions must be exactly {sorted(VALID_POSITIONS)}",
        )

    member_ids = [p.team_member_id for p in data.pullers]
    members = {m.tm_id: m for m in db.query(TeamMember).filter(TeamMember.tm_id.in_(member_ids)).all()}
    for mid in member_ids:
        member = members.get(mid)
        if not member or member.team_id != mp.team_id:
            raise HTTPException(status_code=400, detail=f"team_member {mid} is not on this team's roster")

    total_weight = sum(p.weight_kg for p in data.pullers)
    limit = _weight_limit(match)
    if total_weight > limit:
        raise HTTPException(
            status_code=400,
            detail=f"Team exceeds weight limit for {match.weight_category} "
                   f"({limit:g}kg max, you have {total_weight:g}kg)",
        )

    weighin = TugOfWarWeighIn(
        match_id=match_id,
        position=data.position,
        total_weight_kg=total_weight,
    )
    db.add(weighin)
    db.flush()

    for p in data.pullers:
        db.add(TugOfWarPuller(
            weighin_id=weighin.id,
            team_member_id=p.team_member_id,
            weight_kg=p.weight_kg,
            position=p.position,
            position_order=POSITION_ORDER[p.position],
        ))

    db.commit()
    weighin = db.query(TugOfWarWeighIn).options(
        joinedload(TugOfWarWeighIn.pullers).joinedload(TugOfWarPuller.team_member)
    ).filter(TugOfWarWeighIn.id == weighin.id).first()
    return _serialize_weighin(weighin)


@router.get("/matches/{match_id}/tug-of-war/weigh-in")
def get_weigh_ins(
    match_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    match = _load_match(match_id, db)
    _require_tug_of_war(match)
    rows = db.query(TugOfWarWeighIn).options(
        joinedload(TugOfWarWeighIn.pullers).joinedload(TugOfWarPuller.team_member)
    ).filter(TugOfWarWeighIn.match_id == match_id).all()
    return {"match_id": match_id, "weigh_ins": [_serialize_weighin(w) for w in rows]}


@router.post("/matches/{match_id}/tug-of-war/pull")
def record_pull_result(
    match_id: int,
    data: PullResult,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    match = _load_match(match_id, db)
    _check_event_access(match.event, user, db)
    _require_tug_of_war(match)

    if match.status == "done":
        raise HTTPException(status_code=400, detail="Match is already completed; cannot record more pulls")

    weighins = _weighins(match_id, db)
    for pos in (1, 2):
        w = weighins.get(pos)
        if not w:
            raise HTTPException(status_code=400, detail=f"Cannot start match: team_{pos} not weighed in yet")
        if w.is_disqualified:
            raise HTTPException(status_code=400, detail=f"Team {pos} is disqualified; no further pulls can be recorded")

    completed = sorted([s for s in match.sets if s.is_complete], key=lambda s: s.set_number)
    pulls_won = {1: 0, 2: 0}
    for s in completed:
        if s.winner_position:
            pulls_won[s.winner_position] += 1

    if pulls_won[1] >= SETS_TO_WIN or pulls_won[2] >= SETS_TO_WIN:
        raise HTTPException(status_code=400, detail="Match is already completed; cannot record more pulls")

    next_pull_num = len(completed) + 1
    if next_pull_num > 3:
        raise HTTPException(status_code=400, detail="A tug of war match cannot go beyond 3 pulls")
    if next_pull_num == 3 and not (pulls_won[1] == 1 and pulls_won[2] == 1):
        raise HTTPException(
            status_code=400,
            detail="Cannot record pull 3 until pull 1 & pull 2 are both recorded and split 1-1",
        )

    current_set = next((s for s in match.sets if not s.is_complete), None)
    if not current_set:
        current_set = MatchSet(match_id=match.match_id, set_number=next_pull_num)
        db.add(current_set)
        db.flush()
        match.sets.append(current_set)

    current_set.score_p1 = 1 if data.winning_position == 1 else 0
    current_set.score_p2 = 1 if data.winning_position == 2 else 0
    current_set.winner_position = data.winning_position
    current_set.is_complete = True

    pulls_won[data.winning_position] += 1

    now = datetime.now(timezone.utc)
    started_at = now - timedelta(seconds=data.duration_seconds)
    ls = dict(match.live_state or {})
    pulls_log = list(ls.get("pulls") or [])
    pulls_log.append({
        "pull_num": next_pull_num,
        "winning_position": data.winning_position,
        "duration_seconds": data.duration_seconds,
        "started_at": started_at.isoformat(),
        "ended_at": now.isoformat(),
    })
    ls["pulls"] = pulls_log

    parts = sorted(match.participants, key=lambda p: p.position)
    if len(parts) == 2:
        parts[0].score = pulls_won[1]
        parts[1].score = pulls_won[2]

    match_winner = 1 if pulls_won[1] >= SETS_TO_WIN else (2 if pulls_won[2] >= SETS_TO_WIN else None)
    if match_winner:
        loser = 3 - match_winner
        ls["match_points"] = {
            str(match_winner): 3 if pulls_won[loser] == 0 else 2,
            str(loser): 0 if pulls_won[loser] == 0 else 1,
        }
        match.live_state = ls
        flag_modified(match, "live_state")
        _finish_match(match, match_winner, db)
    else:
        next_set = MatchSet(match_id=match.match_id, set_number=next_pull_num + 1)
        db.add(next_set)
        db.flush()
        match.sets.append(next_set)
        match.live_state = ls
        flag_modified(match, "live_state")

    db.flush()
    result = {
        "match_id": match.match_id,
        "status": match.status,
        "pulls_won": pulls_won,
        "match_winner": match_winner,
        "pulls": pulls_log,
    }
    db.commit()
    background_tasks.add_task(_push_ws_update, match.event_id)
    return result


@router.post("/matches/{match_id}/tug-of-war/caution")
def record_caution(
    match_id: int,
    data: CautionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    match = _load_match(match_id, db)
    _check_event_access(match.event, user, db)
    _require_tug_of_war(match)

    weighin = db.query(TugOfWarWeighIn).filter(
        TugOfWarWeighIn.match_id == match_id,
        TugOfWarWeighIn.position == data.position,
    ).first()
    if not weighin:
        raise HTTPException(status_code=400, detail=f"Team {data.position} has not been weighed in yet")
    if weighin.is_disqualified:
        raise HTTPException(status_code=400, detail=f"Team {data.position} is already disqualified")

    weighin.caution_count += 1
    disqualified = weighin.caution_count > MAX_CAUTIONS_BEFORE_DQ

    if disqualified:
        weighin.is_disqualified = True
        weighin.disqualified_reason = "cautions_exceeded"
        winner = 3 - data.position
        ls = dict(match.live_state or {})
        ls["match_points"] = {str(winner): 3, str(data.position): 0}
        ls["disqualified"] = {"position": data.position, "reason": "cautions_exceeded"}
        match.live_state = ls
        flag_modified(match, "live_state")
        _finish_match(match, winner, db)

    db.flush()
    result = {
        "position": data.position,
        "caution_count": weighin.caution_count,
        "max": MAX_CAUTIONS_BEFORE_DQ,
        "disqualified": disqualified,
        "match_status": match.status,
    }
    db.commit()
    background_tasks.add_task(_push_ws_update, match.event_id)
    return result


@router.post("/matches/{match_id}/tug-of-war/injury-substitute")
def injury_substitute(
    match_id: int,
    data: InjurySubRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    match = _load_match(match_id, db)
    _check_event_access(match.event, user, db)
    _require_tug_of_war(match)

    if match.status in ("live", "done") or any(s.is_complete for s in match.sets):
        raise HTTPException(status_code=400, detail="Cannot substitute after the match has started")

    weighin = db.query(TugOfWarWeighIn).options(
        joinedload(TugOfWarWeighIn.pullers)
    ).filter(
        TugOfWarWeighIn.match_id == match_id,
        TugOfWarWeighIn.position == data.position,
    ).first()
    if not weighin:
        raise HTTPException(status_code=400, detail=f"Team {data.position} has not been weighed in yet")
    if weighin.substitution_count >= MAX_INJURY_SUBS:
        raise HTTPException(
            status_code=400,
            detail=f"Team already has {MAX_INJURY_SUBS} substitution. No more allowed.",
        )

    puller = next((p for p in weighin.pullers if p.team_member_id == data.injured_team_member_id), None)
    if not puller:
        raise HTTPException(status_code=400, detail=f"team_member {data.injured_team_member_id} is not on this team's roster")

    new_total = weighin.total_weight_kg - puller.weight_kg + data.replacement_weight_kg
    limit = _weight_limit(match)
    if new_total > limit:
        raise HTTPException(
            status_code=400,
            detail=f"Replacement pushes team over the weight limit for {match.weight_category} "
                   f"({limit:g}kg max, would have {new_total:g}kg)",
        )

    puller.substituted_for_team_member_id = puller.team_member_id
    puller.team_member_id = data.replacement_team_member_id
    puller.weight_kg = data.replacement_weight_kg

    weighin.total_weight_kg = new_total
    weighin.substitution_count += 1

    db.commit()
    weighin = db.query(TugOfWarWeighIn).options(
        joinedload(TugOfWarWeighIn.pullers).joinedload(TugOfWarPuller.team_member)
    ).filter(TugOfWarWeighIn.id == weighin.id).first()
    return _serialize_weighin(weighin)


@router.get("/matches/{match_id}/tug-of-war/live")
def get_live_state(
    match_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    match = _load_match(match_id, db)
    _require_tug_of_war(match)

    weighins = _weighins(match_id, db)
    completed = sorted([s for s in match.sets if s.is_complete], key=lambda s: s.set_number)
    pulls_won = {1: 0, 2: 0}
    for s in completed:
        if s.winner_position:
            pulls_won[s.winner_position] += 1

    return {
        "match_id": match.match_id,
        "status": match.status,
        "weight_category": match.weight_category,
        "current_pull_num": min(len(completed) + 1, 3),
        "pulls_won": pulls_won,
        "team_1_verified": 1 in weighins,
        "team_2_verified": 2 in weighins,
        "cautions": {
            "1": weighins[1].caution_count if 1 in weighins else 0,
            "2": weighins[2].caution_count if 2 in weighins else 0,
        },
        "disqualified": {
            "1": weighins[1].is_disqualified if 1 in weighins else False,
            "2": weighins[2].is_disqualified if 2 in weighins else False,
        },
        "pulls": (match.live_state or {}).get("pulls", []),
    }


@router.get("/events/{event_id}/tug-of-war/weight-categories")
def get_enabled_categories(
    event_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    enabled = (event.sport_config or {}).get("enabled_weight_categories")
    return {"event_id": event_id, "weight_categories": enabled or list(WEIGHT_LIMITS_KG.keys())}
