"""
Tug of War scoring engine.

Rules:
  - 8 pullers per team, no substitutes except 1 injury replacement.
  - Best of 3 pulls (not sets/points). Match winner: first team to win 2 pulls.
  - Match points for standings: 2-0 win = 3 pts (loser 0); 2-1 win = 2 pts
    (loser 1 pt).
  - Weight categories: featherweight (<=500kg), lightweight (<=560kg),
    middleweight (<=600kg), heavyweight (<=700kg), superheavyweight (<=800kg).
    Sum of all 8 pullers' weights must not exceed the category max.
  - Both teams must complete weigh-in before any pull can be recorded.
  - Each team may accrue at most 2 cautions; a 3rd disqualifies them and
    awards the match to the opponent.
  - Team composition is locked after weigh-in except for one injury sub,
    which is only allowed before the match starts.

Data model: like the Throw Ball service, this module does NOT talk to the
database. Every method takes plain dicts shaped like the schemas in the spec
(Match.match_data, TugOfWarTeam, TugOfWarPuller, Tournament.match_data) and
returns updated plain dicts. Routes load these from the ORM, call the
service, and persist the result.

Two additions beyond the spec's literal example payloads, needed to
implement the rules exactly as specified:
  - The "team roster" dict passed to `injury_substitute` bundles a
    TugOfWarTeam dict (key "team") with its list of TugOfWarPuller dicts
    (key "pullers"), and the team dict carries a "substitution_count" field
    (default 0) to enforce the one-injury-sub-per-team limit — the spec's
    TugOfWarTeam example doesn't include this counter but requires the rule.
  - Each puller dict passed to `record_weigh_in` is expected to carry an
    "organization_id" field so the "all participants belong to same
    organization" check can run; if a puller omits it, that check is
    skipped for that puller (callers relying on the check must supply it).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------

class TugOfWarError(Exception):
    """Base exception for all Tug of War rule violations."""


class WeighInError(TugOfWarError):
    """Raised on invalid or out-of-window weigh-in attempts."""


class InvalidPullError(TugOfWarError):
    """Raised on illegal/duplicate/out-of-sequence pull results."""


class DisqualificationError(TugOfWarError):
    """Raised when an action is blocked because a team is disqualified,
    or to signal a disqualification has just occurred."""


class InjurySubError(TugOfWarError):
    """Raised on illegal injury substitutions."""


class AuthorizationError(TugOfWarError):
    """Raised when the requesting organizer does not own/control this match."""


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

WEIGHT_LIMITS_KG: Dict[str, float] = {
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

MAX_CAUTIONS_BEFORE_DQ = 2  # a 3rd caution (count reaches 3) disqualifies
MAX_INJURY_SUBS_PER_TEAM = 1
TEAMS = ("team_a", "team_b")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _other_team(team: str) -> str:
    return "team_b" if team == "team_a" else "team_a"


class TugOfWarSport:
    """Pure rules/validation engine for Tug of War matches. No DB access."""

    # ----------------------------------------------------------------
    # Match lifecycle
    # ----------------------------------------------------------------

    def initialize_match(
        self,
        tournament_id: str,
        group_id: Optional[str],
        team_a_id: str,
        team_b_id: str,
        weight_category: str,
    ) -> Dict[str, Any]:
        """
        Build a brand-new Match dict for Tug of War, ready to be persisted.

        Raises:
            TugOfWarError: if `weight_category` is not recognized.
        """
        if weight_category not in WEIGHT_LIMITS_KG:
            raise TugOfWarError(
                f"Invalid weight_category '{weight_category}'. "
                f"Must be one of {sorted(WEIGHT_LIMITS_KG)}."
            )

        return {
            "tournament_id": tournament_id,
            "group_id": group_id,
            "team_a_id": team_a_id,
            "team_b_id": team_b_id,
            "sport_type": "tug_of_war",
            "weight_category": weight_category,
            "match_data": {
                "team_a_verified": False,
                "team_b_verified": False,
                "pulls": [],
                "match_winner": None,
                "pulls_won": {"team_a": 0, "team_b": 0},
                "match_points": {"team_a": 0, "team_b": 0},
                "cautions": {"team_a": 0, "team_b": 0},
                "match_status": "weigh_in_pending",
            },
        }

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _verify_organizer(match: Dict[str, Any], organizer_id: Any) -> None:
        """See ThrowBallSport._verify_organizer — same convention here."""
        owner = match.get("organizer_id")
        if owner is not None and owner != organizer_id:
            raise AuthorizationError("You are not authorized to modify this match.")

    @staticmethod
    def _weight_limit(match: Dict[str, Any]) -> float:
        category = match["weight_category"]
        if category not in WEIGHT_LIMITS_KG:
            raise TugOfWarError(f"Match has an invalid weight_category '{category}'.")
        return WEIGHT_LIMITS_KG[category]

    @staticmethod
    def _find_pull(data: Dict[str, Any], pull_num: int) -> Optional[Dict[str, Any]]:
        for p in data["pulls"]:
            if p["pull_num"] == pull_num:
                return p
        return None

    # ----------------------------------------------------------------
    # Weigh-in
    # ----------------------------------------------------------------

    def record_weigh_in(
        self,
        match: Dict[str, Any],
        team: str,
        pullers_data: List[Dict[str, Any]],
        organizer_id: Any,
    ) -> Dict[str, Any]:
        """
        Validate and record a team's weigh-in.

        Validation:
          - team must be "team_a" or "team_b", not already verified.
          - Weigh-in must happen before the match starts.
          - Exactly 8 pullers.
          - Positions are exactly {"anchor", "puller_1".."puller_7"}, no dupes.
          - Sum of weights <= the match's weight_category max.
          - All pullers that supply "organization_id" must match.

        Returns:
            {
              "match": <updated match dict>,
              "team": <new TugOfWarTeam dict>,
              "pullers": <new list of TugOfWarPuller dicts>,
            }
        """
        self._verify_organizer(match, organizer_id)
        if team not in TEAMS:
            raise TugOfWarError(f"team must be one of {TEAMS} (got '{team}').")

        data = match["match_data"]
        if data["match_status"] in ("in_progress", "completed"):
            raise WeighInError("Cannot weigh in after the match has started.")
        if data.get(f"{team}_verified"):
            raise WeighInError(f"{team} has already been weighed in.")

        if len(pullers_data) != PULLERS_PER_TEAM:
            raise WeighInError(
                f"Exactly {PULLERS_PER_TEAM} pullers are required (got {len(pullers_data)})."
            )

        positions = [p["position"] for p in pullers_data]
        if len(set(positions)) != len(positions):
            raise WeighInError("Duplicate positions found in puller lineup.")
        if set(positions) != VALID_POSITIONS:
            raise WeighInError(
                f"Positions must be exactly {sorted(VALID_POSITIONS)} (got {sorted(positions)})."
            )

        org_ids = {p["organization_id"] for p in pullers_data if p.get("organization_id")}
        if len(org_ids) > 1:
            raise WeighInError("All pullers must belong to the same organization.")

        total_weight = sum(float(p["weight_kg"]) for p in pullers_data)
        limit = self._weight_limit(match)
        if total_weight > limit:
            raise WeighInError(
                f"Team exceeds weight limit for {match['weight_category']} "
                f"({limit:g}kg max, you have {total_weight:g}kg)."
            )

        now = _now()
        team_record = {
            "match_id": match.get("id"),
            "team_name": pullers_data[0].get("team_name") if pullers_data else None,
            "organization_id": next(iter(org_ids), None),
            "weight_category": match["weight_category"],
            "total_weight_kg": total_weight,
            "verified_at": _iso(now),
            "caution_count": 0,
            "substitution_count": 0,
            "is_disqualified": False,
            "disqualified_reason": None,
        }

        pullers = [
            {
                "participant_id": p["participant_id"],
                "weight_kg": float(p["weight_kg"]),
                "position": p["position"],
                "position_order": POSITION_ORDER[p["position"]],
                "weighed_at": _iso(now),
                "substituted_for": None,
            }
            for p in pullers_data
        ]
        pullers.sort(key=lambda p: p["position_order"])

        data[f"{team}_verified"] = True
        if data["team_a_verified"] and data["team_b_verified"]:
            data["match_status"] = "scheduled"

        match["match_data"] = data
        return {"match": match, "team": team_record, "pullers": pullers}

    # ----------------------------------------------------------------
    # Pulls
    # ----------------------------------------------------------------

    def record_pull_result(
        self,
        match: Dict[str, Any],
        pull_num: int,
        winning_team: str,
        duration_seconds: int,
        organizer_id: Any,
    ) -> Dict[str, Any]:
        """
        Record the outcome of one pull and, if the match is decided, close
        it out and compute standings points.

        Validation:
          - Both teams must be weighed in.
          - Neither team may already be disqualified (3+ cautions).
          - pull_num must be 1, 2, or 3.
          - Pulls must be recorded in order; a pull cannot be re-recorded.
          - pull_num == 3 is only legal if pulls 1 and 2 are 1-1.
          - pull_num == 2/3 is illegal once the match is already decided.

        Returns:
            The full updated match dict.
        """
        self._verify_organizer(match, organizer_id)
        data = match["match_data"]

        if not (data.get("team_a_verified") and data.get("team_b_verified")):
            missing = "team_a" if not data.get("team_a_verified") else "team_b"
            raise WeighInError(f"Cannot start match: {missing} not weighed in yet.")

        for t in TEAMS:
            if data["cautions"].get(t, 0) >= MAX_CAUTIONS_BEFORE_DQ + 1:
                raise DisqualificationError(f"{t} is disqualified; no further pulls can be recorded.")

        if data["match_status"] == "completed":
            raise InvalidPullError("Match is already completed; cannot record more pulls.")
        if pull_num not in (1, 2, 3):
            raise InvalidPullError("pull_num must be 1, 2, or 3.")
        if winning_team not in TEAMS:
            raise InvalidPullError(f"winning_team must be one of {TEAMS} (got '{winning_team}').")
        if self._find_pull(data, pull_num) is not None:
            raise InvalidPullError(f"Pull {pull_num} has already been recorded.")

        recorded_nums = {p["pull_num"] for p in data["pulls"]}
        if pull_num == 2 and 1 not in recorded_nums:
            raise InvalidPullError("Cannot record pull 2 until pull 1 is recorded.")
        if pull_num == 3:
            if recorded_nums != {1, 2}:
                raise InvalidPullError(
                    "Cannot record pull 3 until pull 1 & pull 2 are both recorded."
                )
            if data["pulls_won"]["team_a"] != 1 or data["pulls_won"]["team_b"] != 1:
                raise InvalidPullError(
                    "Pull 3 is not needed — the match was already decided after pull 2."
                )

        now = _now()
        started_at = now - timedelta(seconds=max(int(duration_seconds), 0))
        data["pulls"].append({
            "pull_num": pull_num,
            "winning_team": winning_team,
            "duration_seconds": duration_seconds,
            "started_at": _iso(started_at),
            "ended_at": _iso(now),
        })

        pulls_won = {"team_a": 0, "team_b": 0}
        for p in data["pulls"]:
            pulls_won[p["winning_team"]] += 1
        data["pulls_won"] = pulls_won

        if pulls_won["team_a"] >= 2 or pulls_won["team_b"] >= 2:
            winner = "team_a" if pulls_won["team_a"] >= 2 else "team_b"
            loser = _other_team(winner)
            data["match_winner"] = winner
            data["match_status"] = "completed"
            if pulls_won[loser] == 0:
                data["match_points"] = {winner: 3, loser: 0}
            else:
                data["match_points"] = {winner: 2, loser: 1}
        else:
            data["match_status"] = "in_progress"

        match["match_data"] = data
        return match

    # ----------------------------------------------------------------
    # Cautions
    # ----------------------------------------------------------------

    def record_caution(
        self,
        match: Dict[str, Any],
        team: str,
        reason: Optional[str],
        organizer_id: Any,
    ) -> Dict[str, Any]:
        """
        Record a caution against `team`. A 3rd caution disqualifies the team
        and immediately awards the match to the opponent.

        Validation:
          - team must be "team_a" or "team_b".
          - Team must not already be disqualified.

        Returns:
            {
              "match": <updated match dict>,
              "caution_count": int,
              "max": 2,
              "disqualified": bool,
            }
        """
        self._verify_organizer(match, organizer_id)
        if team not in TEAMS:
            raise TugOfWarError(f"team must be one of {TEAMS} (got '{team}').")

        data = match["match_data"]
        current = data["cautions"].get(team, 0)
        if current > MAX_CAUTIONS_BEFORE_DQ:
            raise DisqualificationError(f"{team} is already disqualified.")

        current += 1
        data["cautions"][team] = current
        disqualified = current > MAX_CAUTIONS_BEFORE_DQ

        if disqualified:
            winner = _other_team(team)
            data["match_winner"] = winner
            data["match_status"] = "completed"
            data["match_points"] = {winner: 3, team: 0}

        match["match_data"] = data
        return {
            "match": match,
            "caution_count": current,
            "max": MAX_CAUTIONS_BEFORE_DQ,
            "disqualified": disqualified,
        }

    # ----------------------------------------------------------------
    # Injury substitution
    # ----------------------------------------------------------------

    def injury_substitute(
        self,
        match: Dict[str, Any],
        team_roster: Dict[str, Any],
        team: str,
        injured_participant_id: Any,
        replacement_participant_id: Any,
        replacement_weight_kg: float,
        organizer_id: Any,
    ) -> Dict[str, Any]:
        """
        Replace one injured puller with a substitute, before the match starts.

        Args:
            team_roster: {"team": <TugOfWarTeam dict>, "pullers": [<TugOfWarPuller dict>, ...]}
            team: "team_a" | "team_b" — which side this roster belongs to.

        Validation:
          - Only 1 substitution allowed per team per match.
          - Match must not have started (match_status != "in_progress"/"completed").
          - injured_participant_id must be on the roster.
          - New total weight must still be <= the category max.

        Returns:
            The updated team_roster dict: {"team": ..., "pullers": [...]}.
        """
        self._verify_organizer(match, organizer_id)
        if team not in TEAMS:
            raise TugOfWarError(f"team must be one of {TEAMS} (got '{team}').")

        data = match["match_data"]
        if data["match_status"] in ("in_progress", "completed"):
            raise InjurySubError("Cannot substitute after the match has started.")

        team_record = team_roster["team"]
        pullers = team_roster["pullers"]

        sub_count = team_record.get("substitution_count", 0)
        if sub_count >= MAX_INJURY_SUBS_PER_TEAM:
            raise InjurySubError(
                f"Team already has {MAX_INJURY_SUBS_PER_TEAM} substitution. No more allowed."
            )

        injured = next(
            (p for p in pullers if p["participant_id"] == injured_participant_id), None
        )
        if injured is None:
            raise InjurySubError(
                f"Participant {injured_participant_id} is not on this team's roster."
            )

        current_total = team_record.get(
            "total_weight_kg", sum(p["weight_kg"] for p in pullers)
        )
        new_total = current_total - injured["weight_kg"] + float(replacement_weight_kg)
        limit = self._weight_limit(match)
        if new_total > limit:
            raise InjurySubError(
                f"Replacement pushes team over the weight limit for "
                f"{match['weight_category']} ({limit:g}kg max, would have {new_total:g}kg)."
            )

        injured["participant_id"] = replacement_participant_id
        injured["weight_kg"] = float(replacement_weight_kg)
        injured["weighed_at"] = _iso(_now())
        injured["substituted_for"] = injured_participant_id

        team_record["total_weight_kg"] = new_total
        team_record["substitution_count"] = sub_count + 1

        return {"team": team_record, "pullers": pullers}

    # ----------------------------------------------------------------
    # Read-only / validation
    # ----------------------------------------------------------------

    def get_live_match_state(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Build the spectator/TV-display summary for the current match state."""
        data = match["match_data"]
        completed = len(data["pulls"])
        current_pull_num = min(completed + 1, 3)

        return {
            "match_status": data["match_status"],
            "match_winner": data["match_winner"],
            "weight_category": match["weight_category"],
            "current_pull_num": current_pull_num,
            "pulls_won": data["pulls_won"],
            "cautions": data["cautions"],
            "team_a_verified": data.get("team_a_verified", False),
            "team_b_verified": data.get("team_b_verified", False),
            "pulls": data["pulls"],
        }

    def validate_match_ready(self, match: Dict[str, Any]) -> List[str]:
        """
        Check whether both teams are ready for pulls to begin.

        Returns a list of human-readable error strings (empty list = ready).
        """
        data = match["match_data"]
        errors: List[str] = []
        if not data.get("team_a_verified"):
            errors.append("team_a has not completed weigh-in.")
        if not data.get("team_b_verified"):
            errors.append("team_b has not completed weigh-in.")
        return errors

    def get_enabled_categories(self, tournament: Dict[str, Any]) -> List[str]:
        """
        Return the weight categories enabled for this tournament's Tug of
        War event. Falls back to every known category if the tournament has
        not restricted the list.
        """
        match_data = tournament.get("match_data") or {}
        enabled = match_data.get("enabled_weight_categories")
        if not enabled:
            return list(WEIGHT_LIMITS_KG.keys())

        unknown = set(enabled) - set(WEIGHT_LIMITS_KG.keys())
        if unknown:
            raise TugOfWarError(f"Unknown weight categories configured: {sorted(unknown)}.")
        return list(enabled)
