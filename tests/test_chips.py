from app.chips import chip_status, played_chips

# Mirrors the real bootstrap-static shape: one window per chip per half-season.
BOOTSTRAP = {
    "chips": [
        {"name": "wildcard", "start_event": 2, "stop_event": 19},
        {"name": "wildcard", "start_event": 20, "stop_event": 38},
        {"name": "freehit", "start_event": 2, "stop_event": 19},
        {"name": "freehit", "start_event": 20, "stop_event": 38},
        {"name": "bboost", "start_event": 1, "stop_event": 19},
        {"name": "bboost", "start_event": 20, "stop_event": 38},
        {"name": "3xc", "start_event": 1, "stop_event": 19},
        {"name": "3xc", "start_event": 20, "stop_event": 38},
    ]
}


def names(chips):
    return sorted(c["name"] for c in chips)


def test_unused_first_half_offers_everything_in_window():
    status = chip_status(BOOTSTRAP, {"chips": []}, gameweek=3, active_chip=None)
    assert names(status["available"]) == ["3xc", "bboost", "freehit", "wildcard"]
    assert status["used"] == []
    assert status["current_window"] == {"start_event": 1, "stop_event": 19}


def test_played_chip_is_removed_from_availability():
    history = {"chips": [{"name": "wildcard", "event": 2}]}
    status = chip_status(BOOTSTRAP, history, gameweek=3, active_chip=None)
    assert names(status["available"]) == ["3xc", "bboost", "freehit"]
    assert status["used"] == [{"name": "wildcard", "label": "Wildcard", "event": 2}]


def test_second_half_chips_reset_after_the_window_rolls_over():
    """A wildcard spent in GW3 must not block the GW20-38 one."""
    history = {"chips": [{"name": "wildcard", "event": 3}]}
    status = chip_status(BOOTSTRAP, history, gameweek=25, active_chip=None)
    assert names(status["available"]) == ["3xc", "bboost", "freehit", "wildcard"]
    assert status["current_window"] == {"start_event": 20, "stop_event": 38}


def test_chip_outside_its_window_does_not_appear_yet():
    """In GW1 the wildcard window has not opened (start_event 2)."""
    status = chip_status(BOOTSTRAP, {"chips": []}, gameweek=1, active_chip=None)
    assert names(status["available"]) == ["3xc", "bboost"]


def test_expiry_is_reported_so_chip_timing_can_be_reasoned_about():
    status = chip_status(BOOTSTRAP, {"chips": []}, gameweek=3, active_chip=None)
    assert all(c["expires_after_event"] == 19 for c in status["available"])


def test_pending_chips_are_not_counted_as_played():
    history = {"chips": [
        {"name": "wildcard", "event": 2, "status_for_entry": "played"},
        {"name": "freehit", "event": 4, "status_for_entry": "pending"},
    ]}
    assert names(played_chips(history)) == ["wildcard"]


def test_active_chip_is_passed_through():
    status = chip_status(BOOTSTRAP, {"chips": []}, gameweek=3, active_chip="bboost")
    assert status["active_chip"] == "bboost"


def test_falls_back_when_bootstrap_omits_chip_windows():
    status = chip_status({}, {"chips": []}, gameweek=3, active_chip=None)
    assert names(status["available"]) == ["3xc", "bboost", "freehit", "wildcard"]
