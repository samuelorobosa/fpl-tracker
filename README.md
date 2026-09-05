# FPL Weekly Tracker

A FastAPI backend and single-page dashboard over the public, unauthenticated
[Fantasy Premier League API](https://fantasy.premierleague.com/api/). It tracks a squad
week to week and flags the things that are easy to miss manually: injury news, price
changes, and positional role changes (a midfielder suddenly listed at right-back).

Read-only by design — it surfaces information and suggestions, but never makes transfers
or uses chips. All actual changes stay manual in the official FPL app.

## Endpoints

| Endpoint | What it does |
|---|---|
| `GET /players` | Slimmed player list (`?full=true` for the raw bootstrap payload) |
| `GET /fixtures` | All fixtures, optionally `?event=` for one gameweek |
| `GET /fixtures/difficulty` | Every team's next N fixtures with FPL's 1-5 difficulty rating |
| `GET /squad/{team_id}` | Raw picks (player ids only) |
| `GET /squad/{team_id}/readable` | Picks joined against player data |
| `GET /squad/{team_id}/alerts` | This week's changes affecting your squad |
| `GET /squad/{team_id}/digest` | Squad + alerts + fixture difficulty in one call |

Dashboard at `/ui/`, interactive API docs at `/docs`.

## Running

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python -m uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/ui/ and enter an FPL team id.

## Gotchas

- `/entry/{id}/event/{event}/picks/` only returns data **after that gameweek's deadline
  has passed** — including for your own team. Future gameweeks 404. This is a platform
  limitation, not a bug.
- Alerts work by diffing this week's snapshot against last week's, so the first run for a
  given gameweek only saves a baseline and reports nothing.
- Snapshots are flat JSON in `data/`, one file per gameweek, and are gitignored.

## Tests

```bash
venv/bin/python -m pytest
```
