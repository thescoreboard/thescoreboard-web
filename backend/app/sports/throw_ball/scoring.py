"""
Throw Ball scoring engine.

Rules:
  - Rally scoring, first team to 15 points wins the set (no deuce, no cap —
    hitting 15 always wins immediately, unlike TT/Badminton).
  - Match winner: first team to win 2 sets (best_of_3) or 3 sets (best_of_5).

This plugs into the SAME generic set-based scoring path in
app/routers/matches.py used by table_tennis and badminton (score_p1/score_p2
per set via MatchSet, sets_won tallied onto MatchParticipant.score) — only
the config differs. Timeouts, substitutions, and the 7-on-court lineup are
NOT representable in that generic path and are handled by
app/routers/throw_ball.py + app/models/throw_ball.ThrowBallLineup instead.
"""
from typing import Optional
from app.sports.base import BaseSport


DEFAULT_CONFIG = {
    "sets_to_win":              2,      # best_of_3 → need 2 sets. best_of_5 → 3.
    "points_per_set":           15,     # first to 15 wins the set
    "win_margin":                1,     # no deuce — win by 1 is enough at 15
    "max_points":                15,
    "gender_format":       "open",      # "women_only" | "mixed" | "open"
    "max_timeouts_per_set":       2,
    "max_substitutions_per_set":  5,
    "players_on_court":           7,
}

VALID_SETS_TO_WIN = [2, 3]           # best_of_3 → 2, best_of_5 → 3
VALID_GENDER_FORMATS = ["women_only", "mixed", "open"]


class ThrowBall(BaseSport):

    def get_default_config(self) -> dict:
        return DEFAULT_CONFIG.copy()

    def validate_config(self, config: dict) -> dict:
        clean = DEFAULT_CONFIG.copy()

        if "sets_to_win" in config:
            stw = int(config["sets_to_win"])
            if stw not in VALID_SETS_TO_WIN:
                raise ValueError(f"sets_to_win must be one of {VALID_SETS_TO_WIN} (2 = best of 3, 3 = best of 5)")
            clean["sets_to_win"] = stw

        if "gender_format" in config:
            gf = config["gender_format"]
            if gf not in VALID_GENDER_FORMATS:
                raise ValueError(f"gender_format must be one of {VALID_GENDER_FORMATS}")
            clean["gender_format"] = gf

        return clean

    def check_set_winner(self, score_p1: int, score_p2: int, config: dict) -> Optional[int]:
        pts = config.get("points_per_set", 15)
        for pos, mine, theirs in [(1, score_p1, score_p2), (2, score_p2, score_p1)]:
            if mine >= pts and mine > theirs:
                return pos
        return None

    def check_match_winner(self, sets_won_p1: int, sets_won_p2: int, config: dict) -> Optional[int]:
        needed = config.get("sets_to_win", 2)
        if sets_won_p1 >= needed:
            return 1
        if sets_won_p2 >= needed:
            return 2
        return None

    def check_instant_win(self, score_p1: int, score_p2: int, config: dict) -> Optional[int]:
        return None  # Throw Ball has no instant-win rule

    def get_server(self, score_p1: int, score_p2: int, first_server: int, config: dict) -> Optional[int]:
        # Only the serving team can score (rally scoring); server is tracked
        # externally via match.current_server, same as badminton.
        return None

    def get_match_summary(self, match) -> dict:
        parts = sorted(match.participants, key=lambda p: p.position)
        sets  = sorted(match.sets, key=lambda s: s.set_number) if match.sets else []

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
            "match_id":       match.match_id,
            "status":         match.status,
            "stage":          match.stage,
            "round":          match.round,
            "current_server": match.current_server,
            "player_1": {
                "name":      _name(p1),
                "score":     p1.score     if p1 else 0,
                "is_winner": p1.is_winner if p1 else False,
            },
            "player_2": {
                "name":      _name(p2),
                "score":     p2.score     if p2 else 0,
                "is_winner": p2.is_winner if p2 else False,
            },
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

    @property
    def has_sets(self) -> bool:
        return True
