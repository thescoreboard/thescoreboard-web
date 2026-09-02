"""
Throw Ball scoring engine.

Rules (as configured by the organizer):
  - 7 players per team on court, up to 5 substitutes on the bench (12 total).
  - Best of 3 or best of 5 sets (match.match_data["format"]).
  - Each set: rally scoring, first team to 15 points wins the set (no win-by-2).
  - Match winner: first team to win 2 sets (best_of_3) or 3 sets (best_of_5).
  - 2 timeouts per team per set, max 5 substitutions per team per set.
  - No substitution while a player is in the serve position.

Data model: this module intentionally does NOT talk to the database. Every
method takes plain dicts shaped like the schemas in the spec (Match.match_data,
Participant rows) and returns updated plain dicts. The calling route is
responsible for loading those dicts from the ORM, invoking the service, and
persisting the returned data back (db.add / db.commit).

Two fields are used here that are not spelled out in the original Participant
example but are required to implement the rules exactly as specified:
  - participant["team"]: "team_a" | "team_b"
  - participant["court_position"]: int, 1-9 — the player's current rotation
    slot on court. Position 9 is the serve position; a player standing there
    cannot be substituted out. Routes must populate/maintain this field
    alongside "position_on_court" as players rotate.

Each set entry in match_data["sets"] also carries a "substitutions_used"
counter (mirroring "timeouts_used") so record limits can be enforced. This
key is not present in the spec's example payload but is created here on
first use.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------

class ThrowBallError(Exception):
    """Base exception for all Throw Ball rule violations."""


class InvalidScoreError(ThrowBallError):
    """Raised when a set score is out of range or otherwise not a legal result."""


class TimeoutError(ThrowBallError):
    """Raised on illegal timeout calls (e.g. no timeouts left in the set).

    NOTE: this intentionally shadows the builtin `TimeoutError` within this
    module's namespace, per the spec's requested exception name. It has
    nothing to do with I/O timeouts — only `except ThrowBallError` /
    `except app.services.sports.throw_ball.TimeoutError` should be used to
    catch it.
    """


class SubstitutionError(ThrowBallError):
    """Raised on illegal substitutions (serve position, limit exceeded, bad state)."""


class TeamNotReadyError(ThrowBallError):
    """Raised when a team does not have 7 players on court (walkover conditions)."""


class AuthorizationError(ThrowBallError):
    """Raised when the requesting organizer does not own/control this match."""


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

VALID_FORMATS = {"best_of_3": 2, "best_of_5": 3}  # format -> sets needed to win
VALID_GENDER_FORMATS = {"women_only", "mixed", "open"}
POINTS_TO_WIN_SET = 15
PLAYERS_ON_COURT = 7
MAX_TIMEOUTS_PER_TEAM_PER_SET = 2
MAX_SUBS_PER_TEAM_PER_SET = 5
SERVE_POSITION = 9
TEAMS = ("team_a", "team_b")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _other_team(team: str) -> str:
    return "team_b" if team == "team_a" else "team_a"


class ThrowBallSport:
    """Pure rules/validation engine for Throw Ball matches. No DB access."""

    # ----------------------------------------------------------------
    # Match lifecycle
    # ----------------------------------------------------------------

    def initialize_match(
        self,
        tournament_id: str,
        group_id: Optional[str],
        team_a_id: str,
        team_b_id: str,
        format: str = "best_of_3",
        gender_format: str = "open",
    ) -> Dict[str, Any]:
        """
        Build a brand-new Match dict for Throw Ball, ready to be persisted.

        Raises:
            ThrowBallError: if `format` or `gender_format` is not recognized.
        """
        if format not in VALID_FORMATS:
            raise ThrowBallError(
                f"Invalid format '{format}'. Must be one of {sorted(VALID_FORMATS)}."
            )
        if gender_format not in VALID_GENDER_FORMATS:
            raise ThrowBallError(
                f"Invalid gender_format '{gender_format}'. "
                f"Must be one of {sorted(VALID_GENDER_FORMATS)}."
            )

        return {
            "tournament_id": tournament_id,
            "group_id": group_id,
            "team_a_id": team_a_id,
            "team_b_id": team_b_id,
            "sport_type": "throw_ball",
            "match_data": {
                "sport_type": "throw_ball",
                "format": format,
                "gender_format": gender_format,
                "sets": [],
                "match_winner": None,
                "sets_won": {"team_a": 0, "team_b": 0},
                "match_status": "scheduled",
            },
        }

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _verify_organizer(match: Dict[str, Any], organizer_id: Any) -> None:
        """
        Verify the requesting user is allowed to mutate this match.

        `match["organizer_id"]` is expected to be populated by the route
        (e.g. from the owning Tournament/Event) before calling into this
        service. If it is absent, authorization cannot be checked here and
        the caller must have already enforced it at the route/dependency
        layer.
        """
        owner = match.get("organizer_id")
        if owner is not None and owner != organizer_id:
            raise AuthorizationError(
                "You are not authorized to modify this match."
            )

    @staticmethod
    def _sets_needed(match_data: Dict[str, Any]) -> int:
        return VALID_FORMATS[match_data["format"]]

    @staticmethod
    def _max_sets(match_data: Dict[str, Any]) -> int:
        return 3 if match_data["format"] == "best_of_3" else 5

    @staticmethod
    def _find_set(match_data: Dict[str, Any], set_num: int) -> Optional[Dict[str, Any]]:
        for s in match_data["sets"]:
            if s["set_num"] == set_num:
                return s
        return None

    @staticmethod
    def _blank_set(set_num: int) -> Dict[str, Any]:
        return {
            "set_num": set_num,
            "team_a_score": 0,
            "team_b_score": 0,
            "winner": None,
            "timeouts_used": {"team_a": 0, "team_b": 0},
            "substitutions_used": {"team_a": 0, "team_b": 0},
            "started_at": _now_iso(),
            "ended_at": None,
        }

    # ----------------------------------------------------------------
    # Scoring
    # ----------------------------------------------------------------

    def record_set_score(
        self,
        match: Dict[str, Any],
        set_num: int,
        team_a_score: int,
        team_b_score: int,
        organizer_id: Any,
    ) -> Dict[str, Any]:
        """
        Record (or correct) the final score of one set and, if the set
        decides the match, close the match out.

        Validation:
          - Match must not already be completed.
          - set_num must be in range for the configured format, and cannot
            skip ahead of the current set.
          - Both scores must be 0-15.
          - Exactly one team must have scored 15; ties at 15 are illegal;
            neither team may already be closed out below 15-15.

        Returns:
            The full updated match dict.
        """
        self._verify_organizer(match, organizer_id)
        data = match["match_data"]

        if data["match_status"] == "completed":
            raise ThrowBallError("Match is already completed; cannot record more sets.")

        max_sets = self._max_sets(data)
        if not (1 <= set_num <= max_sets):
            raise InvalidScoreError(
                f"set_num must be between 1 and {max_sets} for format '{data['format']}'."
            )

        completed_sets = [s for s in data["sets"] if s["winner"]]
        next_set_num = len(completed_sets) + 1
        if set_num > next_set_num:
            raise InvalidScoreError(
                f"Cannot record set {set_num} before set {next_set_num} is completed."
            )

        existing = self._find_set(data, set_num)
        if existing and existing["winner"]:
            raise InvalidScoreError(
                f"Set {set_num} has already been completed and cannot be re-recorded."
            )

        for label, score in (("team_a_score", team_a_score), ("team_b_score", team_b_score)):
            if not isinstance(score, int) or isinstance(score, bool):
                raise InvalidScoreError(f"{label} must be an integer.")
            if score < 0 or score > POINTS_TO_WIN_SET:
                raise InvalidScoreError(
                    f"{label} must be between 0 and {POINTS_TO_WIN_SET} (got {score})."
                )

        if team_a_score == POINTS_TO_WIN_SET and team_b_score == POINTS_TO_WIN_SET:
            raise InvalidScoreError(
                "Both teams cannot score 15 in the same set — a tie is impossible."
            )
        if team_a_score < POINTS_TO_WIN_SET and team_b_score < POINTS_TO_WIN_SET:
            raise InvalidScoreError(
                "One team must reach 15 points for the set to be complete."
            )

        winner = "team_a" if team_a_score == POINTS_TO_WIN_SET else "team_b"

        set_record = existing or self._blank_set(set_num)
        set_record["team_a_score"] = team_a_score
        set_record["team_b_score"] = team_b_score
        set_record["winner"] = winner
        set_record["ended_at"] = _now_iso()

        if existing:
            idx = data["sets"].index(existing)
            data["sets"][idx] = set_record
        else:
            data["sets"].append(set_record)
            data["sets"].sort(key=lambda s: s["set_num"])

        sets_won = {"team_a": 0, "team_b": 0}
        for s in data["sets"]:
            if s["winner"]:
                sets_won[s["winner"]] += 1
        data["sets_won"] = sets_won

        needed = self._sets_needed(data)
        if sets_won["team_a"] >= needed:
            data["match_winner"] = "team_a"
            data["match_status"] = "completed"
        elif sets_won["team_b"] >= needed:
            data["match_winner"] = "team_b"
            data["match_status"] = "completed"
        else:
            data["match_status"] = "in_progress"

        match["match_data"] = data
        return match

    # ----------------------------------------------------------------
    # Timeouts
    # ----------------------------------------------------------------

    def record_timeout(
        self,
        match: Dict[str, Any],
        set_num: int,
        team: str,
        organizer_id: Any,
    ) -> Dict[str, Any]:
        """
        Record a 30-second timeout for `team` in set `set_num`.

        Validation:
          - team must be "team_a" or "team_b".
          - The set must not already be complete.
          - Team must have fewer than 2 timeouts used in this set.

        Returns:
            The full updated match dict.
        """
        self._verify_organizer(match, organizer_id)
        data = match["match_data"]

        if data["match_status"] == "completed":
            raise TimeoutError("Match is already completed; cannot call a timeout.")
        if team not in TEAMS:
            raise ThrowBallError(f"team must be one of {TEAMS} (got '{team}').")

        max_sets = self._max_sets(data)
        if not (1 <= set_num <= max_sets):
            raise ThrowBallError(
                f"set_num must be between 1 and {max_sets} for format '{data['format']}'."
            )

        set_record = self._find_set(data, set_num)
        if set_record is None:
            set_record = self._blank_set(set_num)
            data["sets"].append(set_record)
            data["sets"].sort(key=lambda s: s["set_num"])

        if set_record["winner"]:
            raise TimeoutError(f"Set {set_num} is already complete; cannot call a timeout.")

        set_record.setdefault("timeouts_used", {"team_a": 0, "team_b": 0})
        used = set_record["timeouts_used"].get(team, 0)
        if used >= MAX_TIMEOUTS_PER_TEAM_PER_SET:
            raise TimeoutError(f"Team {team} has no timeouts left in set {set_num}.")

        set_record["timeouts_used"][team] = used + 1
        match["match_data"] = data
        return match

    # ----------------------------------------------------------------
    # Substitutions
    # ----------------------------------------------------------------

    def substitute_player(
        self,
        match: Dict[str, Any],
        participants: List[Dict[str, Any]],
        on_court_participant_id: Any,
        bench_participant_id: Any,
        organizer_id: Any,
    ) -> Dict[str, Any]:
        """
        Swap a bench player onto the court in place of an on-court player.

        Validation:
          - Both participants must exist and belong to the same team.
          - on_court participant must currently be "on_court".
          - bench participant must currently be "bench".
          - The on-court player being replaced must not be in the serve
            position (court_position == 9).
          - The team must not have already used 5 substitutions in the
            current set.

        Returns:
            {"match": <updated match dict>, "participants": <updated list>}
        """
        self._verify_organizer(match, organizer_id)
        data = match["match_data"]

        if data["match_status"] == "completed":
            raise SubstitutionError("Match is already completed; cannot substitute.")

        on_court = next(
            (p for p in participants if p["id"] == on_court_participant_id), None
        )
        bench = next(
            (p for p in participants if p["id"] == bench_participant_id), None
        )
        if on_court is None:
            raise SubstitutionError(f"Participant {on_court_participant_id} not found.")
        if bench is None:
            raise SubstitutionError(f"Participant {bench_participant_id} not found.")

        if on_court["position_on_court"] != "on_court":
            raise SubstitutionError(
                f"Participant {on_court_participant_id} is not currently on court."
            )
        if bench["position_on_court"] != "bench":
            raise SubstitutionError(
                f"Participant {bench_participant_id} is not currently on the bench."
            )
        if on_court["team"] != bench["team"]:
            raise SubstitutionError("Cannot substitute between two different teams.")

        if on_court.get("court_position") == SERVE_POSITION:
            raise SubstitutionError("Cannot substitute in serve position.")

        team = on_court["team"]
        completed_sets = [s for s in data["sets"] if s["winner"]]
        current_set_num = len(completed_sets) + 1
        set_record = self._find_set(data, current_set_num)
        if set_record is None:
            set_record = self._blank_set(current_set_num)
            data["sets"].append(set_record)
            data["sets"].sort(key=lambda s: s["set_num"])

        set_record.setdefault("substitutions_used", {"team_a": 0, "team_b": 0})
        used = set_record["substitutions_used"].get(team, 0)
        if used >= MAX_SUBS_PER_TEAM_PER_SET:
            raise SubstitutionError(
                f"Max substitutions exceeded for {team} in set {current_set_num} "
                f"(limit {MAX_SUBS_PER_TEAM_PER_SET})."
            )
        set_record["substitutions_used"][team] = used + 1

        # Bench player inherits the outgoing player's court slot; outgoing
        # player goes to the bench with no slot.
        on_court_slot = on_court.get("court_position")
        on_court["position_on_court"], bench["position_on_court"] = "bench", "on_court"
        on_court["court_position"] = None
        bench["court_position"] = on_court_slot

        match["match_data"] = data
        return {"match": match, "participants": participants}

    # ----------------------------------------------------------------
    # Read-only / validation
    # ----------------------------------------------------------------

    def get_live_match_state(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Build the spectator/TV-display summary for the current match state."""
        data = match["match_data"]
        completed_sets = [s for s in data["sets"] if s["winner"]]
        current_set_num = min(len(completed_sets) + 1, self._max_sets(data))
        current_set = self._find_set(data, current_set_num) or self._blank_set(current_set_num)

        timeouts_used = current_set.get("timeouts_used", {"team_a": 0, "team_b": 0})
        timeouts_remaining = {
            team: MAX_TIMEOUTS_PER_TEAM_PER_SET - timeouts_used.get(team, 0)
            for team in TEAMS
        }

        return {
            "match_status": data["match_status"],
            "match_winner": data["match_winner"],
            "format": data["format"],
            "gender_format": data["gender_format"],
            "current_set_num": current_set_num,
            "current_set_score": {
                "team_a": current_set["team_a_score"],
                "team_b": current_set["team_b_score"],
            },
            "sets_won": data["sets_won"],
            "timeouts_remaining": timeouts_remaining,
            "sets": data["sets"],
        }

    def validate_team_ready(
        self,
        match: Dict[str, Any],
        participants: List[Dict[str, Any]],
        team: str,
    ) -> List[str]:
        """
        Check whether `team` has a legal lineup to start/continue the match.

        Returns a list of human-readable error strings (empty list = ready).
        A non-empty list on match start implies a walkover for the opposing
        team, per the spec's "Error Handling" section.
        """
        if team not in TEAMS:
            raise ThrowBallError(f"team must be one of {TEAMS} (got '{team}').")

        errors: List[str] = []
        team_players = [p for p in participants if p["team"] == team]
        on_court = [p for p in team_players if p["position_on_court"] == "on_court"]

        if len(on_court) != PLAYERS_ON_COURT:
            errors.append(
                f"{team} has {len(on_court)} players on court; "
                f"{PLAYERS_ON_COURT} are required (walkover if unresolved)."
            )

        gender_format = match["match_data"].get("gender_format")
        if gender_format == "women_only":
            bad = [p for p in team_players if p.get("gender") != "female"]
            if bad:
                errors.append(
                    f"{team} has {len(bad)} non-female player(s) registered "
                    f"in a women-only event."
                )

        return errors
