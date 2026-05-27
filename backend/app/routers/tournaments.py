"""
Tournament routes — create wizard, workspace data, lifecycle management.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization, OrgMember
from app.models.tournament import Tournament, Sponsor, TOURNAMENT_STATUSES
from typing import List
from app.models.event import Event
from app.models.match import Match, MatchParticipant, MatchSet
from app.models.group import Group, EventParticipant
from app.schemas.tournament import TournamentCreate, TournamentUpdate, TournamentOut, SponsorCreate, SponsorUpdate, SponsorOut
from app.utils.auth import get_current_user, require_pro
from app.utils.slug import generate_unique_slug
from app.sports.registry import get_sport_engine
from app.sports.bracket import build_bracket, assign_players_to_groups

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────

def _check_org_access(org_id: int, user: User, db: Session):
    if not user.is_superadmin:
        member = db.query(OrgMember).filter(
            OrgMember.org_id == org_id, OrgMember.user_id == user.user_id).first()
        if not member:
            raise HTTPException(status_code=403, detail="Not authorized for this organization")


def _check_tournament_access(tournament_id: int, user: User, db: Session) -> Tournament:
    t = db.query(Tournament).filter(Tournament.tournament_id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    _check_org_access(t.org_id, user, db)
    return t



def _serialize_match(m: Match) -> dict:
    parts = sorted(m.participants, key=lambda p: p.position)
    p1 = parts[0] if len(parts) > 0 else None
    p2 = parts[1] if len(parts) > 1 else None
    sets = sorted(m.sets, key=lambda s: s.set_number) if m.sets else []

    def _participant_data(p, label):
        if not p:
            return {"player_id": None, "team_id": None, "name": "TBD", "score": 0, "is_winner": False}
        name = "TBD"
        if p.player:
            name = p.player.name
        elif p.team:
            name = p.team.name
        return {
            "player_id": p.player_id,
            "team_id":   p.team_id,
            "name":      name,
            "score":     p.score,
            "is_winner": p.is_winner,
        }

    return {
        "match_id":       m.match_id,
        "event_id":       m.event_id,
        "group_id":       m.group_id,
        "stage":          m.stage,
        "round":          m.round,
        "status":         m.status,
        "table_number":   m.table_number,
        "current_server": m.current_server,
        "live_state":     m.live_state,
        "started_at":     str(m.started_at)  if m.started_at  else None,
        "finished_at":    str(m.finished_at) if m.finished_at else None,
        "player_1":       _participant_data(p1, "player_1"),
        "player_2":       _participant_data(p2, "player_2"),
        "sets": [
            {
                "set_number":  s.set_number,
                "score_p1":    s.score_p1,
                "score_p2":    s.score_p2,
                "winner":      s.winner_position,
                "is_complete": s.is_complete,
            }
            for s in sets
        ],
    }


# ── Create tournament (wizard) ────────────────────────────────

@router.post("/{org_id}/tournaments", response_model=TournamentOut)
def create_tournament(
    org_id: int,
    data: TournamentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_org_access(org_id, user, db)
    org = db.query(Organization).filter(Organization.org_id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    slug = generate_unique_slug(
        data.name,
        lambda s: db.query(Tournament).filter(Tournament.slug == s).first() is not None,
    )

    tournament = Tournament(
        org_id=org_id,
        name=data.name,
        slug=slug,
        venue=data.venue,
        city=data.city,
        state=data.state,
        venue_lat=data.venue_lat,
        venue_lng=data.venue_lng,
        start_date=data.start_date,
        end_date=data.end_date,
        is_multi_sport=data.is_multi_sport,
        is_published=data.is_published,
        primary_color=data.primary_color,
        status="draft",
    )
    db.add(tournament)
    db.flush()

    for ev_input in data.events:
        try:
            engine = get_sport_engine(ev_input.sport_key)
        except KeyError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if data.is_multi_sport:
            # Multi-sport: store a clean shell — no defaults injected.
            # The organiser completes per-sport setup from the dashboard.
            config        = None
            is_configured = False
            event_format  = None          # set during setup wizard
        else:
            # Single-sport: apply engine defaults + any provided overrides now.
            config = engine.get_default_config()
            if ev_input.sport_config:
                try:
                    config = engine.validate_config({**config, **ev_input.sport_config})
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e))
            is_configured = True
            event_format  = ev_input.format  # validated non-null by creation wizard

        participant_type = ev_input.participant_type or "individual"

        event = Event(
            tournament_id=tournament.tournament_id,
            name=ev_input.name,
            sport_key=ev_input.sport_key,
            format=event_format,
            participant_type=participant_type,
            sport_config=config,
            squad_size=ev_input.squad_size,
            team_size=ev_input.team_size,
            substitutes=ev_input.substitutes,
            is_configured=is_configured,
        )
        db.add(event)

    db.commit()
    db.refresh(tournament)
    return tournament


# ── List tournaments ──────────────────────────────────────────

@router.get("/{org_id}/tournaments", response_model=List[TournamentOut])
def list_tournaments(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_org_access(org_id, user, db)
    return (
        db.query(Tournament)
        .filter(Tournament.org_id == org_id)
        .options(joinedload(Tournament.sponsors))
        .order_by(Tournament.created_at.desc())
        .all()
    )


# ── Get single tournament ────────────────────────────────────

@router.get("/tournaments/{tournament_id}", response_model=TournamentOut)
def get_tournament(
    tournament_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _check_tournament_access(tournament_id, user, db)


# ── Tournament workspace data ─────────────────────────────────

@router.get("/tournaments/{tournament_id}/workspace")
def get_workspace(
    tournament_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Returns ALL data needed to render the tournament workspace."""
    t = _check_tournament_access(tournament_id, user, db)

    events_data = []
    total_players = 0
    total_matches = 0
    total_live = 0
    total_done = 0

    events = db.query(Event).filter(
        Event.tournament_id == tournament_id, Event.is_active == True
    ).all()

    for event in events:
        is_team_event = event.participant_type in ("team", "doubles_pair")

        # Groups
        groups = db.query(Group).filter(Group.event_id == event.event_id).order_by(Group.name).all()

        # Single bulk query for ALL participants in this event — avoids N queries for N groups.
        all_eps = (
            db.query(EventParticipant)
            .filter(EventParticipant.event_id == event.event_id)
            .options(
                joinedload(EventParticipant.player),
                joinedload(EventParticipant.team),
            )
            .all()
        )
        eps_by_group: dict = {}
        for ep in all_eps:
            eps_by_group.setdefault(ep.group_id, []).append(ep)

        groups_data = []
        for g in groups:
            participants = eps_by_group.get(g.group_id, [])
            groups_data.append({
                "group_id": g.group_id,
                "name":     g.name,
                "participants": [
                    _serialize_participant(ep, is_team_event)
                    for ep in participants
                ],
                # keep backward compat key
                "players": [
                    _serialize_participant(ep, is_team_event)
                    for ep in participants
                ],
            })

        # Ungrouped participants — already loaded above, just filter by group_id=None
        ungrouped = eps_by_group.get(None, [])

        # Matches
        matches = (
            db.query(Match).filter(Match.event_id == event.event_id)
            .options(
                joinedload(Match.participants).joinedload(MatchParticipant.player),
                joinedload(Match.participants).joinedload(MatchParticipant.team),
                joinedload(Match.sets),
            )
            .order_by(Match.stage, Match.round, Match.match_id)
            .all()
        )

        # Derive count from already-loaded data — avoids an extra COUNT(*) query per event
        grouped_count = sum(len(g["participants"]) for g in groups_data)
        participant_count = grouped_count + len(ungrouped)
        match_count  = len(matches)
        live_count   = sum(1 for m in matches if m.status == "live")
        done_count   = sum(1 for m in matches if m.status == "done")

        total_players += participant_count
        total_matches += match_count
        total_live    += live_count
        total_done    += done_count

        events_data.append({
            "event_id":        event.event_id,
            "name":            event.name,
            "sport_key":       event.sport_key,
            "format":          event.format,
            "participant_type": event.participant_type,
            "sport_config":    event.sport_config,
            "status":          event.status,
            "is_configured":   event.is_configured,
            "squad_size":      event.squad_size,
            "team_size":       event.team_size,
            "substitutes":     event.substitutes,
            "player_count":    participant_count,
            "match_count":     match_count,
            "live_count":      live_count,
            "done_count":      done_count,
            "groups":          groups_data,
            "ungrouped_players": [
                _serialize_participant(ep, is_team_event)
                for ep in ungrouped
            ],
            "matches": [_serialize_match(m) for m in matches],
        })

    sponsors = db.query(Sponsor).filter(Sponsor.tournament_id == t.tournament_id).all()

    return {
        "tournament": {
            "tournament_id":  t.tournament_id,
            "org_id":         t.org_id,
            "name":           t.name,
            "slug":           t.slug,
            "description":    t.description,
            "is_multi_sport": t.is_multi_sport,
            "venue":          t.venue,
            "city":           t.city,
            "state":          t.state,
            "venue_lat":      t.venue_lat,
            "venue_lng":      t.venue_lng,
            "start_date":     str(t.start_date) if t.start_date else None,
            "end_date":       str(t.end_date)   if t.end_date   else None,
            "status":         t.status,
            "primary_color":  t.primary_color,
            "is_published":     t.is_published,
            "tournament_info":  t.tournament_info,
            "poster_url":       t.poster_url or getattr(t, "banner_url", None),
            "logo_url":       t.logo_url,
            "sponsors": [
                {
                    "sponsor_id":    s.sponsor_id,
                    "name":          s.name,
                    "tier":          s.tier,
                    "logo_url":      s.logo_url,
                    "website":       s.website,
                    "contact_phone": s.contact_phone,
                    "description":   s.description,
                }
                for s in sponsors
            ],
        },
        "events": events_data,
        "stats": {
            "total_events":   len(events_data),
            "total_players":  total_players,
            "total_matches":  total_matches,
            "live_matches":   total_live,
            "done_matches":   total_done,
        },
    }


def _serialize_participant(ep: EventParticipant, is_team: bool) -> dict:
    if is_team and ep.team:
        return {
            "ep_id":    ep.ep_id,
            "team_id":  ep.team.team_id,
            "name":     ep.team.name,
            "seed":     ep.seed,
            "group_id": ep.group_id,
        }
    elif ep.player:
        return {
            "ep_id":      ep.ep_id,
            "player_id":  ep.player.player_id,
            "name":       ep.player.name,
            "age":        ep.player.age,
            "gender":     ep.player.gender,
            "seed":       ep.seed,
            "seed_level": ep.player.seed_level,
            "group_id":   ep.group_id,
        }
    return {"ep_id": ep.ep_id, "name": "Unknown", "seed": ep.seed, "seed_level": None, "group_id": ep.group_id}


# ── Update tournament ─────────────────────────────────────────

@router.patch("/{org_id}/tournaments/{tournament_id}", response_model=TournamentOut)
def update_tournament(
    org_id: int,
    tournament_id: int,
    data: TournamentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_org_access(org_id, user, db)
    t = db.query(Tournament).filter(
        Tournament.tournament_id == tournament_id, Tournament.org_id == org_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")

    # ERR-3: status transitions must go through the dedicated /transition endpoint
    # which enforces lifecycle ordering. Accepting status via PATCH would let
    # organisers jump from draft→completed or go backward.
    _PATCH_BLOCKED = {"status", "is_active"}
    for field, val in data.model_dump(exclude_unset=True).items():
        if field in _PATCH_BLOCKED:
            continue
        setattr(t, field, val)

    db.commit()
    db.refresh(t)
    return t


# ── Delete tournament ─────────────────────────────────────────

@router.delete("/{org_id}/tournaments/{tournament_id}")
def delete_tournament(
    org_id: int,
    tournament_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_org_access(org_id, user, db)
    t = db.query(Tournament).filter(
        Tournament.tournament_id == tournament_id,
        Tournament.org_id == org_id,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    db.delete(t)
    db.commit()
    return {"ok": True}


# ── Sponsor CRUD ─────────────────────────────────────────────

@router.post("/tournaments/{tournament_id}/sponsors", response_model=SponsorOut)
def create_sponsor(
    tournament_id: int,
    data: SponsorCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_pro),   # Pro plan required
):
    t = _check_tournament_access(tournament_id, user, db)
    sponsor = Sponsor(
        tournament_id = t.tournament_id,
        name          = data.name,
        tier          = data.tier,
        logo_url      = data.logo_url,
        website       = data.website,
        contact_phone = data.contact_phone,
        description   = data.description,
    )
    db.add(sponsor)
    db.commit()
    db.refresh(sponsor)
    return sponsor


@router.patch("/tournaments/{tournament_id}/sponsors/{sponsor_id}", response_model=SponsorOut)
def update_sponsor(
    tournament_id: int,
    sponsor_id: int,
    data: SponsorUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_pro),   # Pro plan required
):
    _check_tournament_access(tournament_id, user, db)
    s = db.query(Sponsor).filter(
        Sponsor.sponsor_id == sponsor_id,
        Sponsor.tournament_id == tournament_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sponsor not found")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(s, field, val)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/tournaments/{tournament_id}/sponsors/{sponsor_id}")
def delete_sponsor(
    tournament_id: int,
    sponsor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_pro),   # Pro plan required
):
    _check_tournament_access(tournament_id, user, db)
    s = db.query(Sponsor).filter(
        Sponsor.sponsor_id == sponsor_id,
        Sponsor.tournament_id == tournament_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sponsor not found")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ── Lifecycle transitions ─────────────────────────────────────

@router.post("/tournaments/{tournament_id}/transition")
def transition_status(
    tournament_id: int,
    target_status: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Move tournament to the next lifecycle phase."""
    t = _check_tournament_access(tournament_id, user, db)

    if target_status not in TOURNAMENT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {target_status}")

    t.status = target_status

    # Auto-publish when going live
    if target_status == "live":
        t.is_published = True

    db.commit()
    return {"ok": True, "status": t.status}


# ── Generate fixtures ─────────────────────────────────────────

@router.post("/events/{event_id}/generate-fixtures")
def generate_fixtures(
    event_id: int,
    third_place: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Auto-generate fixtures for an event.

    Behaviour by format:
      group_knockout  — round-robin within each group (groups must exist and be populated)
      round_robin     — everyone plays everyone (no groups needed)
      direct_knockout — single-elimination bracket (no groups needed, participants shuffled randomly)

    third_place=true adds a 3rd-place match for direct_knockout events (4+ participants).
    Works for both individual (player_id) and team (team_id) events.
    """
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not event.is_configured:
        raise HTTPException(
            status_code=400,
            detail=(
                "Sport configuration is incomplete. "
                "Open this sport from the tournament dashboard and complete setup first."
            ),
        )
    if not event.format:
        raise HTTPException(
            status_code=400,
            detail="Event format is not set. Please complete sport setup first.",
        )

    t = db.query(Tournament).filter(Tournament.tournament_id == event.tournament_id).first()
    _check_org_access(t.org_id, user, db)

    engine = get_sport_engine(event.sport_key)
    is_team_event = event.participant_type in ("team", "doubles_pair")

    # Default sets_to_win comes from event config; organiser can override per match.
    # We honour the configured value for ALL stages so that sport-specific defaults
    # (e.g. badminton always BO3) are respected and not silently overridden.
    default_sets_to_win = (event.sport_config or engine.get_default_config()).get("sets_to_win", 2)

    # ── Helper: sets_to_win for a given match stage ───────────
    def _sets_for_stage(stage: str, is_group: bool = False) -> int:  # noqa: ARG001
        return default_sets_to_win

    # ── Helper: create one match between two participants ─────
    def _create_match(pid1, pid2, group_id, stage, round_num, table_num):
        match = Match(
            event_id=event_id,
            group_id=group_id,
            round=round_num,
            stage=stage,
            status="scheduled",
            table_number=table_num,
            live_state={"sets_to_win": _sets_for_stage(stage, is_group=group_id is not None)},
        )
        db.add(match)
        db.flush()

        # Create a participant record for each known position.
        # Rolling-knockout brackets may have one known player (a bye who cascaded
        # forward) and one TBD slot in the same match — handle both independently.
        to_add = []
        for pos, pid in ((1, pid1), (2, pid2)):
            if pid is None:
                continue
            if is_team_event:
                to_add.append(MatchParticipant(match_id=match.match_id, team_id=pid, position=pos))
            else:
                to_add.append(MatchParticipant(match_id=match.match_id, player_id=pid, position=pos))
        if to_add:
            db.add_all(to_add)

        if hasattr(engine, "check_set_winner"):
            db.add(MatchSet(match_id=match.match_id, set_number=1))

        return match

    # ── Helper: get all participant IDs for this event ────────
    def _get_all_ids():
        eps = db.query(EventParticipant).filter(
            EventParticipant.event_id == event_id
        ).all()
        if is_team_event:
            return [ep.team_id for ep in eps if ep.team_id]
        return [ep.player_id for ep in eps if ep.player_id]

    # ── Helper: build {participant_id: seed_score} dict ───────
    def _get_seed_scores():
        eps = db.query(EventParticipant).filter(
            EventParticipant.event_id == event_id,
            EventParticipant.seed.isnot(None),
        ).all()
        if not eps:
            return None  # no seeds set — fall back to shuffle
        scores = {}
        for ep in eps:
            pid = ep.team_id if is_team_event else ep.player_id
            if pid and ep.seed is not None:
                scores[pid] = ep.seed
        return scores if scores else None

    # ── Helper: already-existing pair set ─────────────────────
    def _existing_pairs(group_id=None):
        q = db.query(Match).filter(Match.event_id == event_id)
        if group_id is not None:
            q = q.filter(Match.group_id == group_id)
        existing = q.options(joinedload(Match.participants)).all()
        pairs = set()
        for m in existing:
            if is_team_event:
                ids = tuple(sorted(p.team_id for p in m.participants if p.team_id))
            else:
                ids = tuple(sorted(p.player_id for p in m.participants if p.player_id))
            if len(ids) == 2:
                pairs.add(ids)
        return pairs

    matches_created = 0
    table_counter = 0

    # ════════════════════════════════════════════════════════════
    # FORMAT: group_knockout — round-robin within each group
    # ════════════════════════════════════════════════════════════
    if event.format == "group_knockout":
        groups = db.query(Group).filter(Group.event_id == event_id).all()
        if not groups:
            raise HTTPException(
                status_code=400,
                detail="No groups found. Create groups and assign participants first."
            )

        for group in groups:
            eps = db.query(EventParticipant).filter(
                EventParticipant.event_id == event_id,
                EventParticipant.group_id == group.group_id,
            ).all()

            if len(eps) < 2:
                continue

            ids = [ep.team_id if is_team_event else ep.player_id for ep in eps]
            existing = _existing_pairs(group.group_id)

            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    pair = tuple(sorted([ids[i], ids[j]]))
                    if pair in existing:
                        continue
                    table_counter += 1
                    _create_match(ids[i], ids[j], group.group_id, "group", 1, ((table_counter - 1) % 2) + 1)
                    matches_created += 1

    # ════════════════════════════════════════════════════════════
    # FORMAT: round_robin — everyone plays everyone, no groups
    # ════════════════════════════════════════════════════════════
    elif event.format == "round_robin":
        ids = _get_all_ids()
        if len(ids) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 participants to generate fixtures.")

        existing = _existing_pairs()

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                pair = tuple(sorted([ids[i], ids[j]]))
                if pair in existing:
                    continue
                table_counter += 1
                _create_match(ids[i], ids[j], None, "round_robin", 1, ((table_counter - 1) % 2) + 1)
                matches_created += 1

    # ════════════════════════════════════════════════════════════
    # FORMAT: direct_knockout — single elimination bracket
    # ════════════════════════════════════════════════════════════
    elif event.format == "direct_knockout":
        ids = _get_all_ids()
        if len(ids) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 participants to generate fixtures.")

        # Delete any existing knockout matches before regenerating
        existing_matches = db.query(Match).filter(Match.event_id == event_id).all()
        for m in existing_matches:
            db.delete(m)
        db.flush()

        # Delegate bracket layout to the dedicated knockout module.
        # build_bracket returns an ordered list of match specs with correct
        # stage labels and round numbers for any player count.
        seed_scores = _get_seed_scores()
        specs = build_bracket(ids, shuffle=not seed_scores, third_place=third_place, seed_scores=seed_scores)

        for spec in specs:
            table_counter += 1
            _create_match(
                spec["pid1"], spec["pid2"],
                None,
                spec["stage"],
                spec["round"],
                ((table_counter - 1) % 2) + 1,
            )
            matches_created += 1

    else:
        raise HTTPException(status_code=400, detail=f"Unknown format: {event.format}")

    db.commit()
    return {
        "ok": True,
        "format": event.format,
        "matches_created": matches_created,
    }


# ── Standings (round-robin / group-stage points table) ────────

@router.get("/events/{event_id}/standings")
def get_standings(
    event_id: int,
    db: Session = Depends(get_db),
):
    """
    Compute live standings for round_robin or group_knockout events.
    Calculated on-the-fly from completed matches — no stale cache issues.
    Returns a list of groups (or a single 'all' group for round_robin).
    """
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    is_team = event.participant_type in ("team", "doubles_pair")

    # Load all done matches with participants and sets
    matches = (
        db.query(Match)
        .filter(Match.event_id == event_id, Match.status == "done")
        .options(
            joinedload(Match.participants).joinedload(MatchParticipant.player),
            joinedload(Match.participants).joinedload(MatchParticipant.team),
            joinedload(Match.sets),
        )
        .all()
    )

    def _pid(mp):
        return mp.team_id if is_team else mp.player_id

    def _name(mp):
        if is_team and mp.team:
            return mp.team.name
        if mp.player:
            return mp.player.name
        return "Unknown"

    # Build standings dict: {group_id: {participant_id: row}}
    standings: dict = {}

    def _ensure(group_id, pid, name):
        if group_id not in standings:
            standings[group_id] = {}
        if pid not in standings[group_id]:
            standings[group_id][pid] = {
                "participant_id": pid,
                "name":           name,
                "matches_played": 0,
                "wins":           0,
                "losses":         0,
                "sets_won":       0,
                "sets_lost":      0,
                "points_for":     0,
                "points_against": 0,
                "ranking_points": 0,
            }

    for m in matches:
        parts = sorted(m.participants, key=lambda p: p.position)
        if len(parts) < 2:
            continue

        mp1, mp2 = parts[0], parts[1]
        p1_id = _pid(mp1)
        p2_id = _pid(mp2)
        if not p1_id or not p2_id:
            continue

        gid = m.group_id  # None for round_robin

        _ensure(gid, p1_id, _name(mp1))
        _ensure(gid, p2_id, _name(mp2))

        row1 = standings[gid][p1_id]
        row2 = standings[gid][p2_id]

        # Sets and points from MatchSet records
        p1_sets = p2_sets = 0
        p1_pts  = p2_pts  = 0
        for s in m.sets:
            if s.is_complete:
                if s.winner_position == 1:
                    p1_sets += 1
                elif s.winner_position == 2:
                    p2_sets += 1
            p1_pts += s.score_p1
            p2_pts += s.score_p2

        # Aggregate scores from MatchParticipant for aggregate-scored sports
        # (use sets won as sets for TT/badminton, or mp.score for others)
        if not m.sets:
            p1_sets = mp1.score
            p2_sets = mp2.score

        winner_pos = mp1.position if mp1.is_winner else (mp2.position if mp2.is_winner else None)

        row1["matches_played"] += 1
        row2["matches_played"] += 1
        row1["sets_won"]  += p1_sets
        row1["sets_lost"] += p2_sets
        row2["sets_won"]  += p2_sets
        row2["sets_lost"] += p1_sets
        row1["points_for"]     += p1_pts
        row1["points_against"] += p2_pts
        row2["points_for"]     += p2_pts
        row2["points_against"] += p1_pts

        if winner_pos == 1:
            row1["wins"]           += 1
            row1["ranking_points"] += 2
            row2["losses"]         += 1
        elif winner_pos == 2:
            row2["wins"]           += 1
            row2["ranking_points"] += 2
            row1["losses"]         += 1

    # Ensure ALL enrolled participants appear even with 0 played
    eps = (
        db.query(EventParticipant)
        .filter(EventParticipant.event_id == event_id)
        .options(
            joinedload(EventParticipant.player),
            joinedload(EventParticipant.team),
        )
        .all()
    )
    for ep in eps:
        pid  = ep.team_id if is_team else ep.player_id
        name = ep.team.name if (is_team and ep.team) else (ep.player.name if ep.player else "Unknown")
        _ensure(ep.group_id, pid, name)

    # Sort each group by: ranking_points desc, set_ratio desc, points_ratio desc
    def _sort_key(row):
        sr = row["sets_won"] / max(row["sets_lost"], 1)
        pr = row["points_for"] / max(row["points_against"], 1)
        return (-row["ranking_points"], -sr, -pr)

    groups_out = []
    if event.format == "group_knockout":
        groups = db.query(Group).filter(Group.event_id == event_id).order_by(Group.name).all()
        for g in groups:
            rows = sorted(standings.get(g.group_id, {}).values(), key=_sort_key)
            groups_out.append({"group_id": g.group_id, "name": g.name, "rows": rows})
    else:
        rows = sorted(standings.get(None, {}).values(), key=_sort_key)
        groups_out.append({"group_id": None, "name": "Standings", "rows": rows})

    return {"event_id": event_id, "format": event.format, "groups": groups_out}


# ── Phase 1: create groups + round-robin fixtures ─────────────

@router.post("/events/{event_id}/generate-groups")
def generate_groups(
    event_id: int,
    num_groups: int = 4,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Phase 1 of group_knockout setup.

    1. Splits all registered participants into num_groups balanced groups.
    2. Generates round-robin fixtures within each group.

    Safe to call again if NO group matches have been played yet — it will
    wipe existing groups and regenerate from scratch.  Refuses if any group
    match is already live or done (to prevent data loss).
    """
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.format != "group_knockout":
        raise HTTPException(status_code=400, detail="Event format must be group_knockout")
    if num_groups < 2:
        raise HTTPException(status_code=400, detail="num_groups must be at least 2")

    t = db.query(Tournament).filter(Tournament.tournament_id == event.tournament_id).first()
    _check_org_access(t.org_id, user, db)

    is_team_event = event.participant_type in ("team", "doubles_pair")
    engine = get_sport_engine(event.sport_key)
    default_sets_to_win = (event.sport_config or engine.get_default_config()).get("sets_to_win", 2)

    # Refuse regeneration if any group match has been started
    started = (
        db.query(Match)
        .filter(Match.event_id == event_id, Match.group_id != None, Match.status != "scheduled")
        .count()
    )
    if started:
        raise HTTPException(
            status_code=409,
            detail="Cannot regenerate groups — group matches are already in progress or done.",
        )

    # Also refuse if a knockout bracket already exists
    knockout_exists = (
        db.query(Match)
        .filter(Match.event_id == event_id, Match.group_id == None)
        .count()
    )
    if knockout_exists:
        raise HTTPException(
            status_code=409,
            detail="Cannot regenerate groups — knockout bracket already generated.",
        )

    # Collect all enrolled participants
    eps = db.query(EventParticipant).filter(EventParticipant.event_id == event_id).all()
    if len(eps) < num_groups * 2:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {num_groups * 2} participants for {num_groups} groups.",
        )

    all_ids = [ep.team_id if is_team_event else ep.player_id for ep in eps]
    ep_by_pid = {}
    seed_map = {}
    for ep in eps:
        pid = ep.team_id if is_team_event else ep.player_id
        ep_by_pid[pid] = ep
        if pid and ep.seed is not None:
            seed_map[pid] = ep.seed
    seed_scores_for_groups = seed_map if seed_map else None

    # Delete old groups and their scheduled matches
    old_groups = db.query(Group).filter(Group.event_id == event_id).all()
    for g in old_groups:
        # Unassign participants first
        db.query(EventParticipant).filter(
            EventParticipant.event_id == event_id,
            EventParticipant.group_id == g.group_id,
        ).update({"group_id": None})
        # Delete scheduled matches in this group
        for m in db.query(Match).filter(Match.group_id == g.group_id).all():
            db.delete(m)
        db.delete(g)
    db.flush()

    # Create new groups and assign participants
    group_labels = [chr(ord("A") + i) for i in range(num_groups)]
    assigned_groups = assign_players_to_groups(
        all_ids, num_groups,
        shuffle=not seed_scores_for_groups,
        seed_scores=seed_scores_for_groups,
    )

    matches_created = 0
    table_counter = 0

    for idx, pid_list in enumerate(assigned_groups):
        label = group_labels[idx] if idx < len(group_labels) else f"Group {idx + 1}"
        group = Group(event_id=event_id, name=f"Group {label}")
        db.add(group)
        db.flush()

        # Assign participants to this group
        for pid in pid_list:
            ep = ep_by_pid.get(pid)
            if ep:
                ep.group_id = group.group_id

        # Single-elimination bracket within this group.
        # build_bracket gives byes as early as possible (round 1 only),
        # guaranteeing at most one bye per player.
        specs = build_bracket(pid_list, shuffle=True, third_place=False)
        for spec in specs:
            table_counter += 1
            match = Match(
                event_id=event_id,
                group_id=group.group_id,
                round=spec["round"],
                stage=spec["stage"],
                status="scheduled",
                table_number=((table_counter - 1) % 2) + 1,
                live_state={"sets_to_win": default_sets_to_win},
            )
            db.add(match)
            db.flush()

            to_add = []
            for pos, pid in ((1, spec["pid1"]), (2, spec["pid2"])):
                if pid is None:
                    continue
                if is_team_event:
                    to_add.append(MatchParticipant(match_id=match.match_id, team_id=pid, position=pos))
                else:
                    to_add.append(MatchParticipant(match_id=match.match_id, player_id=pid, position=pos))
            if to_add:
                db.add_all(to_add)

            if hasattr(engine, "check_set_winner"):
                db.add(MatchSet(match_id=match.match_id, set_number=1))

            matches_created += 1

    db.commit()
    return {
        "ok": True,
        "groups_created": num_groups,
        "matches_created": matches_created,
        "participants_per_group": [len(g) for g in assigned_groups],
    }


# ── Phase 1b: generate bracket matches for manually-assigned groups ──

@router.post("/events/{event_id}/generate-group-matches")
def generate_group_matches(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Generate single-elimination bracket matches for groups that were assigned
    manually (instead of going through generate-groups which randomises everything).

    Requires:
     - Groups already exist for the event
     - Each group has ≥ 2 participants assigned
     - No group matches exist yet (safe guard against accidental duplication)
    """
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    t = db.query(Tournament).filter(Tournament.tournament_id == event.tournament_id).first()
    _check_org_access(t.org_id, user, db)

    is_team_event = event.participant_type in ("team", "doubles_pair")
    engine        = get_sport_engine(event.sport_key)
    default_stw   = (event.sport_config or engine.get_default_config()).get("sets_to_win", 2)

    groups = db.query(Group).filter(Group.event_id == event_id).all()
    if not groups:
        raise HTTPException(
            status_code=400,
            detail="No groups found. Create groups and assign participants first.",
        )

    # Refuse if group matches already exist
    existing = (
        db.query(Match)
        .filter(Match.event_id == event_id, Match.group_id != None)
        .count()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Group matches already exist. Reset groups first.",
        )

    matches_created = 0
    table_counter   = 0

    for group in groups:
        eps = db.query(EventParticipant).filter(
            EventParticipant.event_id == event_id,
            EventParticipant.group_id == group.group_id,
        ).all()
        if len(eps) < 2:
            continue

        ids   = [ep.team_id if is_team_event else ep.player_id for ep in eps]
        specs = build_bracket(ids, shuffle=False, third_place=False)

        for spec in specs:
            table_counter += 1
            match = Match(
                event_id=event_id,
                group_id=group.group_id,
                round=spec["round"],
                stage=spec["stage"],
                status="scheduled",
                table_number=((table_counter - 1) % 2) + 1,
                live_state={"sets_to_win": default_stw},
            )
            db.add(match)
            db.flush()

            to_add = []
            for pos, pid in ((1, spec["pid1"]), (2, spec["pid2"])):
                if pid is None:
                    continue
                if is_team_event:
                    to_add.append(MatchParticipant(match_id=match.match_id, team_id=pid, position=pos))
                else:
                    to_add.append(MatchParticipant(match_id=match.match_id, player_id=pid, position=pos))
            if to_add:
                db.add_all(to_add)

            if hasattr(engine, "check_set_winner"):
                db.add(MatchSet(match_id=match.match_id, set_number=1))

            matches_created += 1

    db.commit()
    return {"ok": True, "matches_created": matches_created}


# ── Phase 2: generate knockout bracket from group standings ───

@router.post("/events/{event_id}/generate-knockout-from-groups")
def generate_knockout_from_groups(
    event_id: int,
    qualifiers_per_group: int = 2,
    third_place: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Phase 2 of group_knockout setup.

    Reads current group standings, picks the top `qualifiers_per_group`
    players from each group, seeds them with interleaved ordering
    (A1, B1, C1, A2, B2, …), then builds a single-elimination bracket.

    Safe to call again — replaces any existing knockout matches as long as
    none of them have been started.
    """
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.format != "group_knockout":
        raise HTTPException(status_code=400, detail="Event format must be group_knockout")
    if qualifiers_per_group < 1:
        raise HTTPException(status_code=400, detail="qualifiers_per_group must be at least 1")

    t = db.query(Tournament).filter(Tournament.tournament_id == event.tournament_id).first()
    _check_org_access(t.org_id, user, db)

    is_team_event = event.participant_type in ("team", "doubles_pair")
    engine = get_sport_engine(event.sport_key)
    default_sets_to_win = (event.sport_config or engine.get_default_config()).get("sets_to_win", 2)

    # Must have groups
    groups = db.query(Group).filter(Group.event_id == event_id).all()
    if not groups:
        raise HTTPException(status_code=400, detail="No groups found. Run generate-groups first.")

    # Refuse regeneration if knockout matches are in progress
    started_knockout = (
        db.query(Match)
        .filter(Match.event_id == event_id, Match.group_id == None, Match.status != "scheduled")
        .count()
    )
    if started_knockout:
        raise HTTPException(
            status_code=409,
            detail="Cannot regenerate knockout — knockout matches already in progress or done.",
        )

    # Qualify from each group's completed knockout final.
    # Slot 0 = group champion  (final winner)
    # Slot 1 = group runner-up (final loser) — only if qualifiers_per_group >= 2
    # Seeding interleave: A1,B1,C1,D1,A2,B2,C2,D2 so champions are on opposite halves.
    buckets: list = [[] for _ in range(qualifiers_per_group)]
    groups_not_ready = 0

    for group in groups:
        group_final = (
            db.query(Match)
            .filter(
                Match.event_id == event_id,
                Match.group_id == group.group_id,
                Match.stage == "final",
                Match.status == "done",
            )
            .options(joinedload(Match.participants))
            .first()
        )
        if not group_final:
            groups_not_ready += 1
            continue

        winner_mp = next((p for p in group_final.participants if p.is_winner), None)
        loser_mp  = next((p for p in group_final.participants if not p.is_winner), None)

        if winner_mp:
            pid = winner_mp.team_id or winner_mp.player_id
            if pid:
                buckets[0].append(pid)

        if qualifiers_per_group >= 2 and loser_mp:
            pid = loser_mp.team_id or loser_mp.player_id
            if pid:
                buckets[1].append(pid)

    qualified_ids: list = []
    for bucket in buckets:
        qualified_ids.extend(bucket)

    if len(qualified_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{groups_not_ready} group(s) have no completed final yet. "
                "Finish each group's knockout bracket before generating the championship bracket."
            ),
        )

    # Delete any existing knockout matches (scheduled only — started ones were blocked above)
    existing_knockout = db.query(Match).filter(Match.event_id == event_id, Match.group_id == None).all()
    for m in existing_knockout:
        db.delete(m)
    db.flush()

    # Build bracket — shuffle=False because seeding order is already meaningful
    specs = build_bracket(qualified_ids, shuffle=False, third_place=third_place)

    matches_created = 0
    table_counter = 0

    for spec in specs:
        table_counter += 1
        match = Match(
            event_id=event_id,
            group_id=None,
            round=spec["round"],
            stage=spec["stage"],
            status="scheduled",
            table_number=((table_counter - 1) % 2) + 1,
            live_state={"sets_to_win": default_sets_to_win},
        )
        db.add(match)
        db.flush()

        to_add = []
        for pos, pid in ((1, spec["pid1"]), (2, spec["pid2"])):
            if pid is None:
                continue
            if is_team_event:
                to_add.append(MatchParticipant(match_id=match.match_id, team_id=pid, position=pos))
            else:
                to_add.append(MatchParticipant(match_id=match.match_id, player_id=pid, position=pos))
        if to_add:
            db.add_all(to_add)

        if hasattr(engine, "check_set_winner"):
            db.add(MatchSet(match_id=match.match_id, set_number=1))

        matches_created += 1

    db.commit()
    return {
        "ok": True,
        "qualifiers": len(qualified_ids),
        "matches_created": matches_created,
        "groups_not_ready": groups_not_ready,
    }