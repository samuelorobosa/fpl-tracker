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
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/ui/ and enter an FPL team id.

## Gotchas

- `/entry/{id}/event/{event}/picks/` only returns data **after that gameweek's deadline
  has passed** — including for your own team. Future gameweeks 404. This is a platform
  limitation, not a bug.
- Alerts work by diffing this week's snapshot against last week's, so the first run for a
  given gameweek only saves a baseline and reports nothing.
- Snapshots are flat JSON under `data/`, gitignored, in two kinds:

  ```
  data/
    players/gw3.json          # the whole league pool (~650 players), shared
    teams/3732633/gw3.json    # one manager's 15 picks
  ```

  The player pool is keyed to the **global** gameweek, not the requesting
  manager's current event — otherwise two managers sitting on different events
  write the same day's data under two labels, and the diff between them is
  empty. Alerts compare against the most recent *earlier* snapshot rather than
  `gameweek - 1`, so skipping a week doesn't silently disable them.

## Deploying (Render)

`render.yaml` is a blueprint: point Render at this repo and it reads the config.

```bash
git push            # Render auto-deploys on commit once connected
```

Two things that are not optional:

- **A persistent disk.** Alerts diff this week's player pool against last
  week's, so the snapshot directory must survive restarts. `render.yaml`
  mounts a 1GB disk at `/var/data`, and `FPL_DATA_DIR` points there. Disks
  require a paid instance — on the free tier the filesystem is wiped on every
  deploy and spin-down, and alerts silently never fire.
- **One worker.** Snapshots are flat files; concurrent workers would race
  writing them.

The container binds `$PORT`, which Render injects. `/health` is the health
check path.

## Tests

```bash
venv/bin/pip install -r requirements-dev.txt
```


```bash
venv/bin/python -m pytest
```
