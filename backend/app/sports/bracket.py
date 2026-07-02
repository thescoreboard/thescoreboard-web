"""
Sport-agnostic single-elimination bracket engine.

This module is intentionally sport-independent — it handles only bracket
topology (who plays whom, in which round, with what stage label).  All
sport-specific scoring rules live in the individual sport engines.

Stage names produced
────────────────────
  preliminary | round_of_32 | round_of_16 | quarter | semi | final | third_place

Core guarantee
──────────────
Every participant receives AT MOST ONE bye across the entire tournament.
Byes are placed exclusively in round 1 (the "preliminary" round when present).
From round 2 onward the bracket is always a perfect power of 2 — no further
byes are ever needed.

Algorithm
─────────
Given n players:
  1.  Compute next power-of-2 bracket size B = 2^⌈log₂(n)⌉.
  2.  half_bracket = B / 2  — players entering round 2.
  3.  preliminary_matches = n − half_bracket.
  4.  bye_count            = half_bracket − preliminary_matches.
  5.  Round 1: preliminary_matches real matches played.
      Remaining bye_count players skip directly to round 2.
  6.  Rounds 2+: always half_bracket players, always clean power of 2.

Examples
────────
  n=2  → 1 final
  n=3  → 1 preliminary  + 1 final            (1 bye)
  n=4  → 2 semi         + 1 final            (no byes)
  n=5  → 1 preliminary  + 2 semi  + 1 final  (3 byes)
  n=8  → 4 quarter      + 2 semi  + 1 final  (no byes)
  n=12 → 4 preliminary  + 4 quarter + 2 semi + 1 final  (4 byes)
  n=16 → 8 round_of_16  + 4 quarter + 2 semi + 1 final  (no byes)
"""
import math
import random
from typing import Dict, List, Optional


# ── Stage naming ──────────────────────────────────────────────

def stage_for_size(n: int) -> str:
    """Map player count entering a round to its stage name."""
    if n <= 2:  return "final"
    if n <= 4:  return "semi"
    if n <= 8:  return "quarter"
    if n <= 16: return "round_of_16"
    if n <= 32: return "round_of_32"
    return "preliminary"


# ── Seeded slot ordering ──────────────────────────────────────

def _seeded_slots(n: int) -> List[int]:
    """
    Slot ordering for a power-of-2 bracket of size n so that:
      - Seed 1 and Seed 2 are in opposite halves.
      - Seeds 3 and 4 are each in a different quarter from seeds 1 and 2.
      - And so on recursively.

    Example: n=4 → [0, 3, 1, 2]
             n=8 → [0, 7, 3, 4, 1, 6, 2, 5]
    """
    if n == 2:
        return [0, 1]
    half = _seeded_slots(n // 2)
    result = []
    for r in half:
        result.append(r)
        result.append(n - 1 - r)
    return result


# ── Bracket builder ───────────────────────────────────────────

def build_bracket(
    player_ids: List,
    *,
    shuffle: bool = True,
    third_place: bool = False,
    seed_scores: Optional[Dict] = None,
) -> List[dict]:
    """
    Return an ordered list of match-specs for a single-elimination tournament.

    Each spec:
        pid1   : player/team ID  or  None (TBD — filled by winner propagation)
        pid2   : player/team ID  or  None
        stage  : stage name string
        round  : 1-based integer

    The caller is responsible for persisting these specs as Match rows.
    """
    ids = list(player_ids)
    n   = len(ids)
    if n < 2:
        return []

    if seed_scores:
        ids.sort(key=lambda pid: seed_scores.get(pid, 0), reverse=True)
    elif shuffle:
        random.shuffle(ids)

    # ── Bracket sizing ────────────────────────────────────────
    bracket_size = 2 ** math.ceil(math.log2(n)) if n > 1 else 2
    half_bracket = bracket_size // 2

    prelim_count = n - half_bracket
    bye_count    = half_bracket - prelim_count

    # Seeded slot ordering for perfect power-of-2 brackets
    if seed_scores and bye_count == 0:
        slots  = _seeded_slots(n)
        seeded = [None] * n
        for rank, slot in enumerate(slots):
            if rank < len(ids):
                seeded[slot] = ids[rank]
        ids = [pid for pid in seeded if pid is not None]

    bye_players = ids[:bye_count]
    r1_players  = ids[bye_count:]

    # Round 1 stage label
    r1_stage = "preliminary" if bye_count > 0 else stage_for_size(n)

    specs: List[dict] = []
    round_num = 1

    # ── Round 1 ───────────────────────────────────────────────
    r1_winners: List[Optional] = []
    for i in range(0, len(r1_players), 2):
        a = r1_players[i]
        b = r1_players[i + 1] if i + 1 < len(r1_players) else None
        if b is not None:
            specs.append({"pid1": a, "pid2": b, "stage": r1_stage, "round": round_num})
            r1_winners.append(None)
        else:
            r1_winners.append(a)

    # ── Rounds 2+ (clean power-of-2) ─────────────────────────
    current: List[Optional] = list(bye_players) + r1_winners
    round_num = 2

    while len(current) > 1:
        stage    = stage_for_size(len(current))
        next_rnd: List[Optional] = []
        for i in range(0, len(current), 2):
            if i + 1 >= len(current):
                next_rnd.append(current[i])
                continue
            a = current[i]
            b = current[i + 1]
            specs.append({"pid1": a, "pid2": b, "stage": stage, "round": round_num})
            next_rnd.append(None)
        current   = next_rnd
        round_num += 1

    # ── Optional 3rd-place match ──────────────────────────────
    if third_place and n >= 4:
        specs.append({"pid1": None, "pid2": None, "stage": "third_place", "round": round_num})

    return specs


# ── Group assignment ──────────────────────────────────────────

def assign_players_to_groups(
    player_ids: List,
    num_groups: int,
    *,
    shuffle: bool = True,
    seed_scores: Optional[Dict] = None,
) -> List[List]:
    """
    Distribute player_ids as evenly as possible across num_groups using a
    snake/serpentine draft so no group receives all the top seeds.

    With seed_scores: sort DESC then snake-draft across groups:
        Round 1 (forward):  group 0, 1, ..., n-1
        Round 2 (backward): group n-1, ..., 1, 0
    Without seed_scores: random shuffle + same snake pattern.
    """
    ids = list(player_ids)

    if seed_scores:
        ids.sort(key=lambda pid: seed_scores.get(pid, 0), reverse=True)
    elif shuffle:
        random.shuffle(ids)

    groups: List[List] = [[] for _ in range(num_groups)]
    for i, pid in enumerate(ids):
        pass_index  = i // num_groups
        pos_in_pass = i % num_groups
        group_idx   = (num_groups - 1 - pos_in_pass) if pass_index % 2 == 1 else pos_in_pass
        groups[group_idx].append(pid)

    return groups


# ── Group-qualifier ordering ──────────────────────────────────

def order_group_qualifiers(winners: List, runners: List) -> List:
    """
    Order group-stage qualifiers for build_bracket, which pairs ADJACENT slots.

    When every group contributed both a champion and a runner-up and the total
    is a power of two, champions are cross-paired with a DIFFERENT group's
    runner-up (A1 vs B2, B1 vs C2, …): group-mates cannot rematch in round 1
    and no champion faces another champion immediately.

    Otherwise champions are listed first, so any byes go to them
    (build_bracket assigns byes from the front of the list).
    """
    total = len(winners) + len(runners)
    is_pow2 = total >= 2 and (total & (total - 1)) == 0
    if runners and len(runners) == len(winners) and is_pow2:
        ordered: List = []
        for i, w in enumerate(winners):
            ordered.append(w)
            ordered.append(runners[(i + 1) % len(runners)])
        return ordered
    return list(winners) + list(runners)


# ── Convenience ───────────────────────────────────────────────

def expected_match_count(n: int, third_place: bool = False) -> int:
    """Total matches build_bracket will produce (always n-1, plus 1 for third_place)."""
    if n < 2:
        return 0
    count = n - 1
    if third_place and n >= 4:
        count += 1
    return count
