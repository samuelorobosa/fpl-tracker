"""Fixture difficulty ratings (FDR) derived from the public fixtures endpoint.

FPL already ships a 1-5 difficulty rating on every fixture — `team_h_difficulty`
for the home side and `team_a_difficulty` for the away side — but it's buried in
the fixtures payload keyed by team id, which is useless on its own. This module
turns it into a per-team outlook: the next N unplayed fixtures for every team,
plus an average difficulty so runs can be compared at a glance.

1 = easiest, 5 = hardest.
"""
from __future__ import annotations

DEFAULT_HORIZON = 5


def _upcoming(fixtures: list[dict]) -> list[dict]:
    """Unplayed fixtures that have actually been assigned a gameweek.

    Postponed fixtures sit in the payload with `event: null` until they're
    rescheduled — they have no place in a forward-looking run, so drop them.
    """
    return sorted(
        (f for f in fixtures if not f.get("finished") and f.get("event") is not None),
        key=lambda f: (f["event"], f.get("kickoff_time") or ""),
    )


def build_team_outlook(
    bootstrap: dict,
    fixtures: list[dict],
    horizon: int = DEFAULT_HORIZON,
) -> dict[int, dict]:
    """Map every team id to its next `horizon` fixtures with difficulty.

    Returns {team_id: {"team_short", "fixtures": [...], "avg_difficulty"}}.
    A team with a blank gameweek simply gets fewer fixtures than the horizon,
    which is itself signal — that's why `count` is included in the response.
    """
    short_by_id = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    outlook: dict[int, dict] = {
        team_id: {"team_id": team_id, "team_short": short, "fixtures": []}
        for team_id, short in short_by_id.items()
    }

    for fixture in _upcoming(fixtures):
        for team_id, opponent_id, is_home, difficulty in (
            (fixture["team_h"], fixture["team_a"], True, fixture["team_h_difficulty"]),
            (fixture["team_a"], fixture["team_h"], False, fixture["team_a_difficulty"]),
        ):
            entry = outlook.get(team_id)
            if entry is None or len(entry["fixtures"]) >= horizon:
                continue
            entry["fixtures"].append(
                {
                    "event": fixture["event"],
                    "opponent_short": short_by_id.get(opponent_id, "UNK"),
                    "is_home": is_home,
                    "difficulty": difficulty,
                    "kickoff_time": fixture.get("kickoff_time"),
                }
            )

    for entry in outlook.values():
        difficulties = [f["difficulty"] for f in entry["fixtures"]]
        entry["count"] = len(difficulties)
        entry["avg_difficulty"] = (
            round(sum(difficulties) / len(difficulties), 2) if difficulties else None
        )

    return outlook


def format_run(entry: dict) -> str:
    """One-line human summary of a run, e.g. "BOU (H) 2, ARS (A) 5"."""
    return ", ".join(
        f"{f['opponent_short']} ({'H' if f['is_home'] else 'A'}) {f['difficulty']}"
        for f in entry["fixtures"]
    ) or "no scheduled fixtures"
