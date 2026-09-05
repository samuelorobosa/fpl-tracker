"""Detects week-over-week changes in player data that matter for FPL decisions.

This is the piece that would have caught something like Szoboszlai being
used at right-back: FPL doesn't change a player's official `element_type`
when a manager shifts him positionally, but the `news` field almost always
gets updated with team-news commentary ("Expected to deputise at right-back"
etc). So alongside real field diffs, we scan `news` text for positional
keywords that don't match the player's own listed position.
"""
from __future__ import annotations

from .schemas import PlayerChange

# Keywords that suggest a player is being used out of position.
POSITIONAL_KEYWORDS = {
    "GKP": [],
    "DEF": ["midfield", "wing-back", "attacking role"],
    "MID": ["right-back", "left-back", "centre-back", "wing-back", "full-back", "defence"],
    "FWD": ["wide role", "wing", "benched", "rotation"],
}

TRACKED_FIELDS = ["status", "news", "chance_of_playing_next_round", "now_cost"]

SEVERITY_BY_FIELD = {
    "status": "critical",
    "chance_of_playing_next_round": "warning",
    "news": "warning",
    "now_cost": "info",
}


def diff_players(old: list[dict], new: list[dict]) -> list[PlayerChange]:
    """Compare two snapshots (lists of player dicts, same shape) by player id."""
    old_by_id = {p["id"]: p for p in old}
    changes: list[PlayerChange] = []

    for player in new:
        pid = player["id"]
        prev = old_by_id.get(pid)
        if prev is None:
            continue  # new player, e.g. just transferred in to the league

        for field in TRACKED_FIELDS:
            old_val = prev.get(field)
            new_val = player.get(field)
            if old_val != new_val and new_val not in (None, ""):
                changes.append(
                    PlayerChange(
                        player_id=pid,
                        web_name=player["web_name"],
                        field=field,
                        old_value=str(old_val) if old_val is not None else None,
                        new_value=str(new_val),
                        severity=SEVERITY_BY_FIELD.get(field, "info"),
                    )
                )

        # Positional-role scan on the news text, independent of whether
        # `news` itself changed this week — it's cheap to re-check.
        news_text = (player.get("news") or "").lower()
        position = player.get("position")
        for keyword in POSITIONAL_KEYWORDS.get(position, []):
            if keyword in news_text:
                changes.append(
                    PlayerChange(
                        player_id=pid,
                        web_name=player["web_name"],
                        field="positional_role",
                        old_value=position,
                        new_value=f"news mentions '{keyword}'",
                        severity="warning",
                    )
                )
                break

    return changes
