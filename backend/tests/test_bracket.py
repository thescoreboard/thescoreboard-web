"""
Pure-logic tests: bracket topology, qualifier ordering, badminton scoring.
"""
import pytest

from app.sports.bracket import (
    build_bracket,
    expected_match_count,
    order_group_qualifiers,
)
from app.sports.badminton.scoring import Badminton


# ── build_bracket topology ────────────────────────────────────

@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 8, 12, 16])
def test_total_match_count_is_n_minus_1(n):
    specs = build_bracket(list(range(1, n + 1)), shuffle=False)
    assert len(specs) == n - 1 == expected_match_count(n)


def test_shapes_for_key_sizes():
    def stages(n):
        return [s["stage"] for s in build_bracket(list(range(1, n + 1)), shuffle=False)]

    assert stages(2) == ["final"]
    assert stages(3) == ["preliminary", "final"]
    assert stages(4) == ["semi", "semi", "final"]
    assert stages(5) == ["preliminary", "semi", "semi", "final"]
    assert stages(8) == ["quarter"] * 4 + ["semi"] * 2 + ["final"]


def test_third_place_added_for_4_plus():
    specs = build_bracket([1, 2, 3, 4], shuffle=False, third_place=True)
    assert specs[-1]["stage"] == "third_place"
    specs = build_bracket([1, 2, 3], shuffle=False, third_place=True)
    assert all(s["stage"] != "third_place" for s in specs)


def test_byes_only_in_round_1():
    # n=5 → 3 byes; rounds 2+ must be a clean power of two (all slots known or TBD)
    specs = build_bracket([1, 2, 3, 4, 5], shuffle=False)
    r1 = [s for s in specs if s["round"] == 1]
    assert len(r1) == 1  # single preliminary
    # bye players (1,2,3) appear directly in round 2
    r2_pids = [pid for s in specs if s["round"] == 2 for pid in (s["pid1"], s["pid2"])]
    assert {1, 2, 3} <= set(p for p in r2_pids if p is not None)


# ── order_group_qualifiers ────────────────────────────────────

def test_two_groups_cross_pairing():
    # A1 must NOT meet B1 (other champion) or A2 (group-mate) in round 1
    ordered = order_group_qualifiers(["A1", "B1"], ["A2", "B2"])
    assert ordered == ["A1", "B2", "B1", "A2"]


def test_four_groups_no_champion_vs_champion_and_no_group_rematch():
    winners = ["A1", "B1", "C1", "D1"]
    runners = ["A2", "B2", "C2", "D2"]
    ordered = order_group_qualifiers(winners, runners)
    assert len(ordered) == 8
    pairs = [(ordered[i], ordered[i + 1]) for i in range(0, 8, 2)]
    for a, b in pairs:
        assert a[0] != b[0], f"group-mates rematch in round 1: {a} vs {b}"
        assert not (a.endswith("1") and b.endswith("1")), f"champions meet in round 1: {a} vs {b}"


def test_uneven_qualifiers_champions_get_byes():
    # 3 groups → 6 qualifiers (not a power of two): champions listed first
    # so build_bracket hands its byes to them.
    ordered = order_group_qualifiers(["A1", "B1", "C1"], ["A2", "B2", "C2"])
    assert ordered[:3] == ["A1", "B1", "C1"]


def test_winners_only():
    assert order_group_qualifiers(["A1", "B1"], []) == ["A1", "B1"]


# ── Badminton scoring rules (BWF) ─────────────────────────────

def test_badminton_set_rules():
    b = Badminton()
    cfg = b.get_default_config()
    assert b.check_set_winner(21, 19, cfg) == 1     # normal win
    assert b.check_set_winner(21, 20, cfg) is None  # must win by 2
    assert b.check_set_winner(22, 20, cfg) == 2 or b.check_set_winner(20, 22, cfg) == 2
    assert b.check_set_winner(29, 29, cfg) is None  # not decided yet
    assert b.check_set_winner(30, 29, cfg) == 1     # golden point cap
    assert b.check_set_winner(19, 21, cfg) == 2


def test_badminton_match_rules():
    b = Badminton()
    cfg = b.get_default_config()          # best of 3
    assert b.check_match_winner(1, 1, cfg) is None
    assert b.check_match_winner(2, 0, cfg) == 1
    assert b.check_match_winner(1, 2, cfg) == 2
