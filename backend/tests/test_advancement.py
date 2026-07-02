"""
Winner-advancement + retraction tests against an in-memory DB.

These cover the launch-blocking bug: manually-created knockout matches all
carry round=1, and the old round-keyed propagation stranded their winners.
Advancement is now keyed off canonical stage order.
"""
import pytest
from fastapi import HTTPException

from app.models.event import Event
from app.models.match import Match, MatchParticipant
from app.models.organization import Organization, OrgMember
from app.models.tournament import Tournament
from app.models.user import User
from app.routers.matches import (
    _check_event_access,
    _finish_match,
    _retract_advancement,
)
from app.sports.bracket import build_bracket


# ── Helpers ───────────────────────────────────────────────────

def make_event(db, fmt="group_knockout"):
    ev = Event(tournament_id=1, name="Badminton Singles", sport_key="badminton", format=fmt)
    db.add(ev)
    db.flush()
    return ev


def make_match(db, ev, stage, round_, p1=None, p2=None, group_id=None, status="scheduled"):
    m = Match(event_id=ev.event_id, group_id=group_id, stage=stage, round=round_, status=status)
    db.add(m)
    db.flush()
    for pos, pid in ((1, p1), (2, p2)):
        if pid is not None:
            db.add(MatchParticipant(match_id=m.match_id, player_id=pid, position=pos))
    db.flush()
    db.refresh(m)
    return m


def slot(m, pos):
    """player_id occupying the given position of a match, or None."""
    mp = next((p for p in m.participants if p.position == pos), None)
    return mp.player_id if mp else None


# ── The reported bug: manual matches (all round=1) must advance ──

def test_manual_semis_advance_into_manual_final(db):
    ev = make_event(db)
    semi1 = make_match(db, ev, "semi", 1, 1, 2)
    semi2 = make_match(db, ev, "semi", 1, 3, 4)
    final = make_match(db, ev, "final", 1)          # TBD vs TBD

    _finish_match(semi1, 1, db)   # player 1 wins
    db.flush(); db.refresh(final)
    assert slot(final, 1) == 1

    _finish_match(semi2, 2, db)   # player 4 wins
    db.flush(); db.refresh(final)
    assert slot(final, 2) == 4


def test_semi_loser_lands_in_third_place(db):
    ev = make_event(db)
    semi1 = make_match(db, ev, "semi", 1, 1, 2)
    semi2 = make_match(db, ev, "semi", 1, 3, 4)
    final = make_match(db, ev, "final", 1)
    third = make_match(db, ev, "third_place", 1)

    _finish_match(semi1, 1, db)
    _finish_match(semi2, 1, db)
    db.flush(); db.refresh(third)
    assert slot(third, 1) == 2    # semi1 loser
    assert slot(third, 2) == 4    # semi2 loser


# ── Byes: winner of the preliminary joins the bye player ─────

def test_group_mini_bracket_with_bye(db):
    ev = make_event(db)
    # 3-player group, generate-groups style: P1 has the bye and is
    # pre-seeded into the final; prelim decides the other slot.
    prelim = make_match(db, ev, "preliminary", 1, 2, 3, group_id=1)
    final  = make_match(db, ev, "final",       2, 1, None, group_id=1)

    _finish_match(prelim, 2, db)  # player 3 wins
    db.flush(); db.refresh(final)
    assert slot(final, 1) == 1
    assert slot(final, 2) == 3


# ── Full auto-generated 8-player bracket end-to-end ──────────

def test_full_8_player_bracket_propagation(db):
    ev = make_event(db, fmt="direct_knockout")
    specs = build_bracket(list(range(1, 9)), shuffle=False)
    matches = [
        make_match(db, ev, s["stage"], s["round"], s["pid1"], s["pid2"])
        for s in specs
    ]
    quarters = [m for m in matches if m.stage == "quarter"]
    semis    = [m for m in matches if m.stage == "semi"]
    final    = next(m for m in matches if m.stage == "final")

    for q in quarters:
        _finish_match(q, 1, db)   # position-1 player always wins
    db.flush()
    for s in semis:
        db.refresh(s)
    # quarters were (1,2)(3,4)(5,6)(7,8) → semis must be (1,3) and (5,7)
    assert (slot(semis[0], 1), slot(semis[0], 2)) == (1, 3)
    assert (slot(semis[1], 1), slot(semis[1], 2)) == (5, 7)

    for s in semis:
        _finish_match(s, 1, db)
    db.flush(); db.refresh(final)
    assert (slot(final, 1), slot(final, 2)) == (1, 5)


# ── Retraction: re-running a match must pull its winner back ──

def test_rematch_retracts_winner_then_new_winner_advances(db):
    ev = make_event(db)
    semi1 = make_match(db, ev, "semi", 1, 1, 2)
    make_match(db, ev, "semi", 1, 3, 4)
    final = make_match(db, ev, "final", 1)

    _finish_match(semi1, 1, db)
    db.flush(); db.refresh(final)
    assert slot(final, 1) == 1

    # organiser re-runs semi1
    _retract_advancement(semi1, db)
    db.flush(); db.refresh(final)
    assert slot(final, 1) is None

    semi1.status = "scheduled"
    for p in semi1.participants:
        p.is_winner = False
    _finish_match(semi1, 2, db)   # player 2 wins this time
    db.flush(); db.refresh(final)
    assert slot(final, 1) == 2


def test_retract_blocked_when_next_match_started(db):
    ev = make_event(db)
    semi1 = make_match(db, ev, "semi", 1, 1, 2)
    make_match(db, ev, "semi", 1, 3, 4)
    final = make_match(db, ev, "final", 1)

    _finish_match(semi1, 1, db)
    db.flush()
    final.status = "live"
    db.flush()

    with pytest.raises(HTTPException) as exc:
        _retract_advancement(semi1, db)
    assert exc.value.status_code == 409


def test_group_final_rerun_blocked_once_championship_exists(db):
    ev = make_event(db)
    gfinal = make_match(db, ev, "final", 2, 1, 2, group_id=1, status="done")
    for p in gfinal.participants:
        p.is_winner = p.position == 1
    make_match(db, ev, "semi", 1, 1, 3)   # championship match (group_id=None)
    db.flush()

    with pytest.raises(HTTPException) as exc:
        _retract_advancement(gfinal, db)
    assert exc.value.status_code == 409


# ── Authorization helper ──────────────────────────────────────

def test_check_event_access(db):
    org = Organization(name="Club", slug="club")
    db.add(org); db.flush()
    t = Tournament(org_id=org.org_id, name="Open", slug="open")
    db.add(t); db.flush()
    ev = Event(tournament_id=t.tournament_id, name="BD", sport_key="badminton",
               format="group_knockout")
    db.add(ev); db.flush()

    member   = User(email="m@x.com", name="Member")
    outsider = User(email="o@x.com", name="Outsider")
    admin    = User(email="a@x.com", name="Admin", is_superadmin=True)
    db.add_all([member, outsider, admin]); db.flush()
    db.add(OrgMember(org_id=org.org_id, user_id=member.user_id, role="admin"))
    db.flush()

    _check_event_access(ev, member, db)   # must not raise
    _check_event_access(ev, admin, db)    # superadmin bypass

    with pytest.raises(HTTPException) as exc:
        _check_event_access(ev, outsider, db)
    assert exc.value.status_code == 403
