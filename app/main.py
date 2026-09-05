"""FastAPI app: weekly FPL squad tracker.

Run locally with:
    uvicorn app.main:app --reload

Then visit http://127.0.0.1:8000/docs for interactive Swagger docs.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .fpl_client import FPLClient
from .schemas import SquadAlertsResponse
from .fixture_difficulty import DEFAULT_HORIZON, build_team_outlook
from .services import (
    _slim_players,
    build_readable_squad,
    build_squad_alerts,
    build_weekly_digest,
)

app = FastAPI(
    title="FPL Weekly Tracker",
    description="Pulls live data from the public FPL API and flags squad-relevant changes week to week.",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/players")
async def list_players(full: bool = False) -> dict | list[dict]:
    """Player data. By default returns a slimmed-down list (name, team,
    position, price, status) — the full bootstrap-static payload is several
    MB and will hang a browser tab trying to render it. Pass ?full=true
    only if you specifically need the raw payload (all teams/gameweek
    metadata included) and are consuming it programmatically, not viewing
    it in Swagger.
    """
    async with FPLClient() as client:
        bootstrap = await client.get_bootstrap_static()
    if full:
        return bootstrap
    return _slim_players(bootstrap)


@app.get("/fixtures")
async def list_fixtures(event: int | None = None) -> list[dict]:
    """All fixtures, optionally filtered to a single gameweek."""
    async with FPLClient() as client:
        return await client.get_fixtures(event=event)


@app.get("/fixtures/difficulty")
async def fixture_difficulty(horizon: int = DEFAULT_HORIZON) -> list[dict]:
    """Every team's next `horizon` unplayed fixtures with FPL's own 1-5
    difficulty rating, sorted easiest run first. Blank gameweeks show up
    as a `count` below the horizon.
    """
    if not 1 <= horizon <= 10:
        raise HTTPException(status_code=422, detail="horizon must be between 1 and 10")
    async with FPLClient() as client:
        bootstrap = await client.get_bootstrap_static()
        fixtures = await client.get_fixtures()
    outlook = build_team_outlook(bootstrap, fixtures, horizon=horizon)
    return sorted(
        outlook.values(),
        key=lambda e: (e["avg_difficulty"] is None, e["avg_difficulty"]),
    )


@app.get("/squad/{team_id}")
async def get_squad(team_id: int) -> dict:
    """This manager's most recent gameweek picks (their own current_event,
    not the global gameweek — matters for teams created mid-season).
    """
    async with FPLClient() as client:
        try:
            gameweek = await client.get_entry_current_event(team_id)
            return await client.get_entry_picks(team_id, gameweek)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller
            raise HTTPException(status_code=404, detail=f"Could not fetch squad for team_id={team_id}: {exc}")


@app.get("/squad/{team_id}/readable")
async def get_readable_squad(team_id: int) -> dict:
    """Squad picks joined with player names/teams/positions/prices —
    the human-readable version of /squad/{team_id}, which only returns
    raw player ids.
    """
    try:
        return await build_readable_squad(team_id)
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller
        raise HTTPException(status_code=404, detail=f"Could not fetch squad for team_id={team_id}: {exc}")


@app.get("/squad/{team_id}/alerts", response_model=SquadAlertsResponse)
async def get_squad_alerts(team_id: int) -> SquadAlertsResponse:
    """The main endpoint: run this once a week (e.g. via cron) to get
    a list of anything that changed for players in your squad since
    the last time this was run — injuries, price changes, positional
    switches flagged in team news, etc.
    """
    gameweek, alerts = await build_squad_alerts(team_id)
    return SquadAlertsResponse(team_id=team_id, gameweek=gameweek, alerts=alerts)


@app.get("/squad/{team_id}/digest")
async def get_weekly_digest(team_id: int, horizon: int = DEFAULT_HORIZON) -> dict:
    """The weekly briefing in one call: readable squad, this week's alerts,
    and each player's upcoming fixture difficulty, plus the easiest and
    hardest runs in the league for transfer ideas.
    """
    if not 1 <= horizon <= 10:
        raise HTTPException(status_code=422, detail="horizon must be between 1 and 10")
    try:
        return await build_weekly_digest(team_id, horizon=horizon)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller
        raise HTTPException(status_code=404, detail=f"Could not build digest for team_id={team_id}: {exc}")


# Mounted last so it never shadows the API routes above — this serves the
# single-page dashboard at http://127.0.0.1:8000/ui/
app.mount("/ui", StaticFiles(directory="app/static", html=True), name="ui")
