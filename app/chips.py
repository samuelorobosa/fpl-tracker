"""Chip usage and availability.

`/entry/{id}/history/` reports which chips a manager has played and when.
Turning that into "what do I still have" needs the season's chip windows, and
bootstrap-static publishes those itself:

    {"name": "wildcard", "start_event": 2,  "stop_event": 19, ...}
    {"name": "wildcard", "start_event": 20, "stop_event": 38, ...}

Reading the windows from the game rather than hardcoding a GW19 reset means the
half-season split is exact, and stays correct if the rules change again.
"""
from __future__ import annotations

# The API's internal names are terse; these are what the game calls them.
CHIP_LABELS = {
    "wildcard": "Wildcard",
    "freehit": "Free Hit",
    "bboost": "Bench Boost",
    "3xc": "Triple Captain",
}

# Used only if bootstrap-static ever stops publishing chip windows.
FALLBACK_WINDOWS = [
    {"name": name, "start_event": start, "stop_event": stop}
    for name in CHIP_LABELS
    for start, stop in ((1, 19), (20, 38))
]


def _label(name: str) -> str:
    return CHIP_LABELS.get(name, name)


def played_chips(history: dict) -> list[dict]:
    """Chips this manager has actually played, oldest first.

    Some responses carry a `status_for_entry` field and some don't; when it is
    present, anything not "played" (e.g. a pending chip) is excluded.
    """
    chips = []
    for chip in history.get("chips") or []:
        status = chip.get("status_for_entry")
        if status is not None and status != "played":
            continue
        chips.append(
            {"name": chip["name"], "label": _label(chip["name"]), "event": chip.get("event")}
        )
    return sorted(chips, key=lambda c: (c["event"] is None, c["event"]))


def chip_status(bootstrap: dict, history: dict, gameweek: int, active_chip: str | None) -> dict:
    """What has been played, and what is still available *this half-season*.

    Availability is per window: a wildcard played in GW3 uses up the first-half
    wildcard, but the GW20-38 one is untouched and only becomes available once
    that window opens.
    """
    windows = bootstrap.get("chips") or FALLBACK_WINDOWS
    used = played_chips(history)

    current_windows = [
        w for w in windows
        if w.get("start_event") is not None
        and w["start_event"] <= gameweek <= w["stop_event"]
    ]

    available = []
    for window in current_windows:
        spent = any(
            u["name"] == window["name"]
            and u["event"] is not None
            and window["start_event"] <= u["event"] <= window["stop_event"]
            for u in used
        )
        if not spent:
            available.append(
                {
                    "name": window["name"],
                    "label": _label(window["name"]),
                    # Worth surfacing: a chip nobody plays before this gameweek
                    # is simply lost when the window closes.
                    "expires_after_event": window["stop_event"],
                }
            )

    window_bounds = (
        {
            "start_event": min(w["start_event"] for w in current_windows),
            "stop_event": max(w["stop_event"] for w in current_windows),
        }
        if current_windows
        else None
    )

    return {
        "active_chip": active_chip,
        "used": used,
        "available": available,
        "current_window": window_bounds,
    }
