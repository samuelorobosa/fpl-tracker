"""
Thin async client around the public, unauthenticated Fantasy Premier League API.

No API key is required. These endpoints are the same ones the official
FPL website and app use under the hood.

Docs (unofficial, community-maintained):
https://github.com/vaastav/Fantasy-Premier-League/wiki/Data
"""
from __future__ import annotations

import httpx

BASE_URL = "https://fantasy.premierleague.com/api"


def current_event_id(bootstrap: dict) -> int:
    """The global current/next gameweek, read from an already-fetched payload.

    Split out from the client method so callers holding a bootstrap response
    don't have to download it a second time just to learn the gameweek.
    """
    for event in bootstrap["events"]:
        if event["is_current"] or event["is_next"]:
            return event["id"]
    return bootstrap["events"][-1]["id"]


class FPLClient:
    """Async wrapper for the FPL public API.

    Usage:
        async with FPLClient() as client:
            data = await client.get_bootstrap_static()
    """

    def __init__(self, timeout: float = 15.0) -> None:
        self._client = httpx.AsyncClient(base_url=BASE_URL, timeout=timeout)

    async def __aenter__(self) -> "FPLClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def get_bootstrap_static(self) -> dict:
        """The single most useful endpoint: all players, teams, positions,
        gameweeks, and each player's current status/news/price in one call.
        """
        resp = await self._client.get("/bootstrap-static/")
        resp.raise_for_status()
        return resp.json()

    async def get_fixtures(self, event: int | None = None) -> list[dict]:
        """All fixtures, optionally filtered to a single gameweek."""
        params = {"event": event} if event is not None else None
        resp = await self._client.get("/fixtures/", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_entry(self, team_id: int) -> dict:
        """Public summary info for a single manager's team (your squad)."""
        resp = await self._client.get(f"/entry/{team_id}/")
        resp.raise_for_status()
        return resp.json()

    async def get_entry_picks(self, team_id: int, event: int) -> dict:
        """The 15 players a manager picked for a specific gameweek."""
        resp = await self._client.get(f"/entry/{team_id}/event/{event}/picks/")
        resp.raise_for_status()
        return resp.json()

    async def get_entry_history(self, team_id: int) -> dict:
        """A manager's season history, including the chips they have played."""
        resp = await self._client.get(f"/entry/{team_id}/history/")
        resp.raise_for_status()
        return resp.json()

    async def get_current_event(self) -> int:
        """Convenience helper: figure out the global current/next gameweek id.

        Note: this is the *league-wide* gameweek, not necessarily a gameweek
        a given manager has picks for. A manager who joined mid-season won't
        have picks for gameweeks before they created a team — use
        get_entry_current_event() for a manager-specific lookup instead.
        """
        return current_event_id(await self.get_bootstrap_static())

    async def get_entry_current_event(self, team_id: int) -> int:
        """The most recent gameweek this specific manager actually has
        picks for. Falls back to the global current event if the entry
        payload doesn't expose it (shouldn't normally happen).
        """
        entry = await self.get_entry(team_id)
        current_event = entry.get("current_event")
        if current_event:
            return current_event
        return await self.get_current_event()
