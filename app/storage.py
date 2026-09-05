"""Persistence for weekly snapshots.

Starts as flat JSON files on disk so the whole thing runs with zero
infrastructure. The interface is small enough to swap in Postgres/SQLite/
Redis later without touching the diff engine or API layer.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def _snapshot_path(gameweek: int) -> Path:
    return DATA_DIR / f"snapshot_gw{gameweek}.json"


def save_snapshot(gameweek: int, players: list[dict]) -> None:
    """Persist a list of PlayerSnapshot-shaped dicts for a given gameweek."""
    path = _snapshot_path(gameweek)
    path.write_text(json.dumps(players, indent=2))


def load_snapshot(gameweek: int) -> list[dict] | None:
    """Return the stored snapshot for a gameweek, or None if never saved."""
    path = _snapshot_path(gameweek)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def latest_saved_gameweek() -> int | None:
    """Find the highest gameweek number we already have a snapshot for."""
    weeks = []
    for f in DATA_DIR.glob("snapshot_gw*.json"):
        try:
            weeks.append(int(f.stem.replace("snapshot_gw", "")))
        except ValueError:
            continue
    return max(weeks) if weeks else None
