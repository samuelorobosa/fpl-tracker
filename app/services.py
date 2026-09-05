"""Business logic that sits between the FPL client and the API routes."""
from __future__ import annotations

from .alternatives import flagged_player_ids, group_by_position, suggest_alternatives
from .diff_engine import diff_players
from .fixture_difficulty import DEFAULT_HORIZON, build_team_outlook, format_run
from .fpl_client import FPLClient, current_event_id
from .schemas import SquadAlert
from .storage import (
    load_previous_player_snapshot,
    save_player_snapshot,
    save_team_snapshot,
)

POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def _slim_players(bootstrap: dict) -> list[dict]:
    """Project the full bootstrap-static player list down to tracked fields."""
    teams_by_id = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    slim = []
    for p in bootstrap["elements"]:
        slim.append(
            {
                "id": p["id"],
                "web_name": p["web_name"],
                "team_id": p["team"],
                "team_short": teams_by_id.get(p["team"], "UNK"),
                "position": POSITION_MAP.get(p["element_type"], "UNK"),
                "now_cost": p["now_cost"] / 10,
                "status": p["status"],
                "news": p["news"],
                "chance_of_playing_next_round": p.get("chance_of_playing_next_round"),
                "form": p["form"],
                "total_points": p["total_points"],
                # Present in bootstrap-static; used to break ties when ranking
                # replacement candidates.
                "expected_goal_involvements": p.get("expected_goal_involvements"),
            }
        )
    return slim


async def fetch_and_snapshot_current_week() -> tuple[int, list[dict]]:
    """Pull live data, save it as this week's snapshot, return (gameweek, players)."""
    async with FPLClient() as client:
        bootstrap = await client.get_bootstrap_static()
    gameweek = current_event_id(bootstrap)
    players = _slim_players(bootstrap)
    save_player_snapshot(gameweek, players)
    return gameweek, players


async def get_squad_player_ids(team_id: int) -> tuple[int, set[int]]:
    """Get (gameweek, player ids) for a manager's most recent submitted squad.

    Uses the manager's own current_event rather than the global gameweek,
    since a team created mid-season has no picks for earlier gameweeks.
    """
    async with FPLClient() as client:
        gameweek = await client.get_entry_current_event(team_id)
        picks = await client.get_entry_picks(team_id, gameweek)
    return gameweek, {p["element"] for p in picks["picks"]}


async def build_squad_alerts(team_id: int) -> tuple[int, list[SquadAlert]]:
    """The main workflow: snapshot this week, diff against last week,
    and filter changes down to just the players in this manager's squad.
    """
    squad_gameweek, squad_ids = await get_squad_player_ids(team_id)
    global_gameweek, current_players = await fetch_and_snapshot_current_week()
    previous = load_previous_player_snapshot(before=global_gameweek)

    if previous is None:
        # First run — nothing to diff against yet. Not an error, just no history.
        return squad_gameweek, []

    _, previous_players = previous
    return squad_gameweek, alerts_for_squad(previous_players, current_players, squad_ids)


def alerts_for_squad(
    previous_players: list[dict],
    current_players: list[dict],
    squad_ids: set[int],
) -> list[SquadAlert]:
    """Diff two snapshots and keep only the changes affecting this squad."""
    alerts: list[SquadAlert] = []
    for change in diff_players(previous_players, current_players):
        if change.player_id not in squad_ids:
            continue
        alerts.append(
            SquadAlert(
                player_id=change.player_id,
                web_name=change.web_name,
                message=_format_message(change),
                severity=change.severity,
            )
        )
    return alerts


async def build_readable_squad(team_id: int) -> dict:
    """Join a manager's raw picks (player ids only) against player data,
    so the response has names/teams/positions instead of bare ids.
    """
    async with FPLClient() as client:
        bootstrap = await client.get_bootstrap_static()
        gameweek = await client.get_entry_current_event(team_id)
        picks_data = await client.get_entry_picks(team_id, gameweek)

    players_by_id = {p["id"]: p for p in _slim_players(bootstrap)}

    squad = []
    for pick in picks_data["picks"]:
        player = players_by_id.get(pick["element"], {})
        squad.append(
            {
                "web_name": player.get("web_name", "Unknown"),
                "team_short": player.get("team_short", "UNK"),
                "position": player.get("position", "UNK"),
                "now_cost": player.get("now_cost"),
                "status": player.get("status"),
                "news": player.get("news"),
                "squad_position": pick["position"],  # 1-11 XI, 12-15 bench
                "is_starting": pick["position"] <= 11,
                "is_captain": pick["is_captain"],
                "is_vice_captain": pick["is_vice_captain"],
                "multiplier": pick["multiplier"],
            }
        )

    return {
        "team_id": team_id,
        "gameweek": gameweek,
        "entry_history": picks_data["entry_history"],
        "active_chip": picks_data["active_chip"],
        "squad": squad,
    }


def _format_message(change) -> str:
    if change.field == "positional_role":
        return f"{change.web_name}: possible positional switch — {change.new_value}"
    if change.field == "status":
        return f"{change.web_name}: availability status changed from '{change.old_value}' to '{change.new_value}'"
    if change.field == "chance_of_playing_next_round":
        return f"{change.web_name}: chance of playing next round changed to {change.new_value}%"
    if change.field == "now_cost":
        return f"{change.web_name}: price changed from £{change.old_value}m to £{change.new_value}m"
    if change.field == "news":
        return f"{change.web_name}: news updated — \"{change.new_value}\""
    return f"{change.web_name}: {change.field} changed to {change.new_value}"


async def build_weekly_digest(team_id: int, horizon: int = DEFAULT_HORIZON) -> dict:
    """The one-call weekly briefing: squad + alerts + fixture difficulty.

    Deliberately does all its network I/O in a single client session rather
    than composing build_readable_squad()/build_squad_alerts(), which would
    each re-download the ~1.7MB bootstrap payload independently.
    """
    async with FPLClient() as client:
        bootstrap = await client.get_bootstrap_static()
        gameweek = await client.get_entry_current_event(team_id)
        picks_data = await client.get_entry_picks(team_id, gameweek)
        fixtures = await client.get_fixtures()

    current_players = _slim_players(bootstrap)
    # The pool is league-wide, so it is filed under the GLOBAL gameweek. Filing
    # it under this manager's current event would let two managers on different
    # events write the same day's data under two labels, and diff to nothing.
    global_gameweek = current_event_id(bootstrap)
    save_player_snapshot(global_gameweek, current_players)

    players_by_id = {p["id"]: p for p in current_players}
    outlook = build_team_outlook(bootstrap, fixtures, horizon=horizon)

    squad = []
    for pick in picks_data["picks"]:
        player = players_by_id.get(pick["element"], {})
        team_outlook = outlook.get(player.get("team_id"), {})
        squad.append(
            {
                "player_id": pick["element"],
                "web_name": player.get("web_name", "Unknown"),
                "team_short": player.get("team_short", "UNK"),
                "position": player.get("position", "UNK"),
                "now_cost": player.get("now_cost"),
                "status": player.get("status"),
                "news": player.get("news"),
                "form": player.get("form"),
                "squad_position": pick["position"],
                "is_starting": pick["position"] <= 11,
                "is_captain": pick["is_captain"],
                "is_vice_captain": pick["is_vice_captain"],
                "multiplier": pick["multiplier"],
                "avg_difficulty": team_outlook.get("avg_difficulty"),
                "fixture_run": format_run(team_outlook) if team_outlook else "unknown",
                "fixtures": team_outlook.get("fixtures", []),
            }
        )

    previous = load_previous_player_snapshot(before=global_gameweek)
    squad_ids = {p["element"] for p in picks_data["picks"]}
    alerts = (
        alerts_for_squad(previous[1], current_players, squad_ids)
        if previous is not None
        else []
    )

    _attach_alternatives(squad, current_players, outlook, squad_ids, alerts)

    save_team_snapshot(
        team_id,
        gameweek,
        {
            "team_id": team_id,
            "gameweek": gameweek,
            "entry_history": picks_data["entry_history"],
            "active_chip": picks_data["active_chip"],
            "squad": squad,
        },
    )

    return {
        "team_id": team_id,
        "gameweek": gameweek,
        "horizon": horizon,
        "has_previous_snapshot": previous is not None,
        "compared_against_gameweek": previous[0] if previous else None,
        "entry_history": picks_data["entry_history"],
        "active_chip": picks_data["active_chip"],
        "alerts": alerts,
        "squad": squad,
        "easiest_runs": _rank_runs(outlook, reverse=False)[:5],
        "hardest_runs": _rank_runs(outlook, reverse=True)[:5],
    }


def _rank_runs(outlook: dict[int, dict], reverse: bool) -> list[dict]:
    """League-wide fixture runs sorted by average difficulty, for transfer ideas."""
    ranked = sorted(
        (e for e in outlook.values() if e["avg_difficulty"] is not None),
        key=lambda e: e["avg_difficulty"],
        reverse=reverse,
    )
    return [
        {
            "team_short": e["team_short"],
            "avg_difficulty": e["avg_difficulty"],
            "count": e["count"],
            "run": format_run(e),
        }
        for e in ranked
    ]


def _attach_alternatives(
    squad: list[dict],
    pool: list[dict],
    outlook: dict[int, dict],
    owned_ids: set[int],
    alerts: list[SquadAlert],
) -> None:
    """Add `suggested_alternatives` in place, but only for players worth
    reconsidering — an unchanged, in-form player doesn't need a shortlist,
    and filling one in for all 15 would bury the ones that matter.

    The pool is grouped once and shared across the whole squad; nothing here
    touches the network.
    """
    flagged = flagged_player_ids(squad, {a.player_id for a in alerts})
    pool_by_position = group_by_position(pool)

    for player in squad:
        player["suggested_alternatives"] = (
            suggest_alternatives(player, pool_by_position, outlook, owned_ids)
            if player["player_id"] in flagged
            else None
        )
