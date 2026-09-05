"""Pydantic models for request/response shapes used by the API layer.

These are intentionally slimmed-down projections of the much larger FPL
payloads — we only keep the fields the tracker actually needs.
"""
from __future__ import annotations

from pydantic import BaseModel


class PlayerSnapshot(BaseModel):
    """A single player's tracked state at a point in time."""

    id: int
    web_name: str
    team_id: int
    team_short: str
    position: str  # GKP / DEF / MID / FWD
    now_cost: float  # in millions, e.g. 15.5
    status: str  # 'a' available, 'i' injured, 'd' doubtful, 's' suspended, 'u' unavailable
    news: str
    chance_of_playing_next_round: int | None = None
    form: str
    total_points: int


class PlayerChange(BaseModel):
    """A detected difference between two snapshots of the same player."""

    player_id: int
    web_name: str
    field: str
    old_value: str | None
    new_value: str | None
    severity: str  # 'info' | 'warning' | 'critical'


class SquadAlert(BaseModel):
    """A single actionable alert surfaced for a manager's squad."""

    player_id: int
    web_name: str
    message: str
    severity: str


class SquadAlertsResponse(BaseModel):
    team_id: int
    gameweek: int
    alerts: list[SquadAlert]
