"""Persistence for weekly snapshots.

Two kinds of snapshot live here, and the split matters:

* **Player snapshots** are the whole league — all ~650 players — and are
  identical no matter which manager's digest triggered the save. They are keyed
  by the *global* gameweek, so two managers sitting on different current events
  can't write the same day's data under two different labels (which produced an
  empty, silently useless diff).
* **Team snapshots** are one manager's 15 picks, and are genuinely per-team, so
  they get a folder each.

Flat JSON files, so the whole thing runs with zero infrastructure. The
interface is small enough to swap in SQLite/Postgres later without touching the
diff engine or the API layer.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Overridable so a deployment can point at a mounted volume. Snapshots MUST
# land on persistent storage: on an ephemeral filesystem every restart wipes
# the baseline, and alerts silently return nothing forever.
DATA_DIR = Path(
    os.environ.get("FPL_DATA_DIR")
    or Path(__file__).resolve().parent.parent / "data"
)
PLAYERS_DIR = DATA_DIR / "players"
TEAMS_DIR = DATA_DIR / "teams"


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _read(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _gameweeks_in(directory: Path) -> list[int]:
    """Gameweek numbers with a stored file, ascending."""
    weeks = []
    for f in directory.glob("gw*.json"):
        try:
            weeks.append(int(f.stem[2:]))
        except ValueError:
            continue
    return sorted(weeks)


# --- League-wide player pool ------------------------------------------------

def save_player_snapshot(gameweek: int, players: list[dict]) -> None:
    """Persist the full player pool for a global gameweek."""
    _write(PLAYERS_DIR / f"gw{gameweek}.json", players)


def load_player_snapshot(gameweek: int) -> list[dict] | None:
    return _read(PLAYERS_DIR / f"gw{gameweek}.json")


def load_previous_player_snapshot(before: int) -> tuple[int, list[dict]] | None:
    """The most recent snapshot taken *earlier* than `before`.

    Deliberately not `before - 1`: snapshots are only written when someone runs
    a digest, so gaps are normal — skipping a week shouldn't silently disable
    alerts. Returns (gameweek, players) so callers can report what was compared.
    """
    earlier = [gw for gw in _gameweeks_in(PLAYERS_DIR) if gw < before]
    if not earlier:
        return None
    gameweek = earlier[-1]
    players = load_player_snapshot(gameweek)
    return None if players is None else (gameweek, players)


def player_gameweeks() -> list[int]:
    """Every gameweek with a stored player pool, ascending."""
    return _gameweeks_in(PLAYERS_DIR) if PLAYERS_DIR.exists() else []


def latest_player_gameweek() -> int | None:
    weeks = player_gameweeks()
    return weeks[-1] if weeks else None


# --- Per-team picks ---------------------------------------------------------

def _team_dir(team_id: int) -> Path:
    return TEAMS_DIR / str(team_id)


def save_team_snapshot(team_id: int, gameweek: int, snapshot: dict) -> None:
    """Persist one manager's squad for a gameweek, building their own history."""
    _write(_team_dir(team_id) / f"gw{gameweek}.json", snapshot)


def load_team_snapshot(team_id: int, gameweek: int) -> dict | None:
    return _read(_team_dir(team_id) / f"gw{gameweek}.json")


def team_gameweeks(team_id: int) -> list[int]:
    """Every gameweek stored for a team, ascending. Empty if never loaded."""
    directory = _team_dir(team_id)
    return _gameweeks_in(directory) if directory.exists() else []


def stored_teams() -> dict[str, list[int]]:
    """Every team with stored history, mapped to its gameweeks."""
    if not TEAMS_DIR.exists():
        return {}
    return {
        d.name: _gameweeks_in(d)
        for d in sorted(TEAMS_DIR.iterdir())
        if d.is_dir()
    }
