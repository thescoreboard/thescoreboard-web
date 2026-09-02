"""
Tug of War scoring engine.

A "pull" is modeled as a set: each MatchSet row is one pull (set_number =
pull_num), score_p1/score_p2 are 1/0 flags for who won it, winner_position
is the winning side, is_complete is always True once recorded (a pull has
no partial state). This lets pulls reuse the same Standing/points machinery
every other sport's sets use. Match winner: first team to win 2 pulls
(best of 3).

Weigh-in, cautions, disqualification, and injury substitution have no
generic equivalent and are handled by app/routers/tug_of_war.py +
app/models/tug_of_war.py instead — this engine only covers pull scoring.
"""
from typing import Optional
from app.sports.base import BaseSport


WEIGHT_CATEGORIES = [
    "featherweight", "lightweight", "middleweight", "heavyweight", "superheavyweight",
]

DEFAULT_CONFIG = {
    "sets_to_win": 2,      # best of 3 pulls — first to 2 wins the match
    "points_per_set": 1,   # a pull is a 1/0 win flag, not a point total —
                            # used by the generic walkover endpoint in
                            # matches.py, which scores walkover sets as
                            # points_per_set-0.
    "enabled_weight_categories": WEIGHT_CATEGORIES.copy(),
}


class TugOfWar(BaseSport):

    def get_default_config(self) -> dict:
        return {**DEFAULT_CONFIG, "enabled_weight_categories": WEIGHT_CATEGORIES.copy()}

    def validate_config(self, config: dict) -> dict:
        # Best of 3 pulls is fixed by the rules — sets_to_win/points_per_set
        # are not organiser-configurable. enabled_weight_categories is.
        clean = {**DEFAULT_CONFIG, "enabled_weight_categories": WEIGHT_CATEGORIES.copy()}

        if "enabled_weight_categories" in config:
            cats = config["enabled_weight_categories"]
            if not cats or not isinstance(cats, list):
                raise ValueError("enabled_weight_categories must be a non-empty list")
            unknown = set(cats) - set(WEIGHT_CATEGORIES)
            if unknown:
                raise ValueError(f"Unknown weight categories: {sorted(unknown)}")
            clean["enabled_weight_categories"] = cats

        return clean

    def check_set_winner(self, score_p1: int, score_p2: int, config: dict) -> Optional[int]:
        # Pulls are decided explicitly (POST .../pull), not by point thresholds.
        return None

    def check_match_winner(self, sets_won_p1: int, sets_won_p2: int, config: dict) -> Optional[int]:
        needed = config.get("sets_to_win", 2)
        if sets_won_p1 >= needed:
            return 1
        if sets_won_p2 >= needed:
            return 2
        return None

    def check_instant_win(self, score_p1: int, score_p2: int, config: dict) -> Optional[int]:
        return None

    def get_server(self, score_p1: int, score_p2: int, first_server: int, config: dict) -> Optional[int]:
        return None  # no serving concept in tug of war

    def get_match_summary(self, match) -> dict:
        parts = sorted(match.participants, key=lambda p: p.position)
        pulls = sorted(match.sets, key=lambda s: s.set_number) if match.sets else []

        p1 = parts[0] if len(parts) > 0 else None
        p2 = parts[1] if len(parts) > 1 else None

        def _name(p):
            if not p:
                return "TBD"
            if p.team:
                return p.team.name
            if p.player:
                return p.player.name
            return "TBD"

        return {
            "match_id":        match.match_id,
            "status":          match.status,
            "stage":           match.stage,
            "round":           match.round,
            "weight_category": match.weight_category,
            "team_1": {
                "name":      _name(p1),
                "pulls_won": p1.score     if p1 else 0,
                "is_winner": p1.is_winner if p1 else False,
            },
            "team_2": {
                "name":      _name(p2),
                "pulls_won": p2.score     if p2 else 0,
                "is_winner": p2.is_winner if p2 else False,
            },
            "pulls": [
                {
                    "pull_num":   s.set_number,
                    "winner":     s.winner_position,
                    "is_complete": s.is_complete,
                }
                for s in pulls
            ],
        }

    @property
    def has_sets(self) -> bool:
        return True
