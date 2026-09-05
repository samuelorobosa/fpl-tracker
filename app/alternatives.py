"""Ranks replacement candidates for squad players worth reconsidering.

Everything here works off data already fetched for the digest — the full
bootstrap-static player pool plus the fixture-difficulty outlook — so adding
suggestions costs no extra network calls. It is deliberately a set of pure
functions over plain dicts, so the ranking can be tested without touching
the FPL API.
"""
from __future__ import annotations

# How much more expensive than the outgoing player a candidate may be. Keeps
# suggestions to realistic transfers rather than aspirational upgrades.
PRICE_BUFFER = 0.5

# Number of starters (by lowest form) treated as underperforming. Restricted to
# the XI on purpose: unused bench players sit at form 0.0 and would otherwise
# take every slot, hiding the starter who is actually costing points.
WORST_FORM_COUNT = 3

MAX_SUGGESTIONS = 3

# Score weights. Form leads, as the brief asks. The fixture term is centred on
# 3 (a neutral run), so an easy run adds and a hard one subtracts. xGI is
# season-cumulative rather than recent, so it carries a deliberately small
# weight — enough to break ties between similar form, not enough to let a
# season-long accumulator outrank someone in better current form.
FORM_WEIGHT = 1.0
FIXTURE_WEIGHT = 0.5
XGI_WEIGHT = 0.25


def _as_float(value) -> float:
    """FPL returns most numeric stats as strings ('4.0'), and occasionally null."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def candidate_score(player: dict, avg_difficulty: float | None) -> float:
    """Blended ranking score. Higher is better."""
    score = FORM_WEIGHT * _as_float(player.get("form"))
    if avg_difficulty is not None:
        score += FIXTURE_WEIGHT * (3 - avg_difficulty)
    # Skip the xGI factor entirely when the field is absent, rather than
    # guessing a value for it.
    if player.get("expected_goal_involvements") is not None:
        score += XGI_WEIGHT * _as_float(player["expected_goal_involvements"])
    return score


def flagged_player_ids(squad: list[dict], alert_player_ids: set[int]) -> set[int]:
    """Which squad players are worth suggesting replacements for.

    Three reasons qualify: unavailable, among the worst form in the squad, or
    already surfaced by this week's diff.
    """
    flagged = {p["player_id"] for p in squad if p.get("status") != "a"}
    flagged |= {p["player_id"] for p in squad if p["player_id"] in alert_player_ids}

    starters = [p for p in squad if p.get("is_starting", True)]
    by_form = sorted(starters, key=lambda p: _as_float(p.get("form")))
    flagged |= {p["player_id"] for p in by_form[:WORST_FORM_COUNT]}
    return flagged


def suggest_alternatives(
    player: dict,
    pool_by_position: dict[str, list[dict]],
    outlook: dict[int, dict],
    owned_ids: set[int],
    limit: int = MAX_SUGGESTIONS,
) -> list[dict]:
    """Top replacements for one squad player: same position, affordable,
    available, and not already owned.
    """
    budget = (player.get("now_cost") or 0) + PRICE_BUFFER
    candidates = []
    for other in pool_by_position.get(player.get("position"), []):
        if other["id"] in owned_ids:
            continue
        if other["status"] != "a":
            continue
        if other["now_cost"] > budget:
            continue
        avg = outlook.get(other["team_id"], {}).get("avg_difficulty")
        candidates.append((candidate_score(other, avg), other, avg))

    # Ties broken by price so the cheaper option wins, then by id for a stable
    # ordering across runs.
    candidates.sort(key=lambda c: (-c[0], c[1]["now_cost"], c[1]["id"]))

    return [
        {
            "web_name": other["web_name"],
            "team_short": other["team_short"],
            "now_cost": other["now_cost"],
            "form": other["form"],
            "avg_difficulty": avg,
        }
        for _, other, avg in candidates[:limit]
    ]


def group_by_position(players: list[dict]) -> dict[str, list[dict]]:
    """Bucket the pool once, so each squad player filters a smaller list."""
    grouped: dict[str, list[dict]] = {}
    for player in players:
        grouped.setdefault(player["position"], []).append(player)
    return grouped
