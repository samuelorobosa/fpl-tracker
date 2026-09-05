from app.fixture_difficulty import build_team_outlook, format_run

BOOTSTRAP = {
    "teams": [
        {"id": 1, "short_name": "ARS"},
        {"id": 2, "short_name": "LIV"},
        {"id": 3, "short_name": "BOU"},
    ]
}


def fixture(event, home, away, h_diff, a_diff, finished=False):
    return {
        "event": event,
        "team_h": home,
        "team_a": away,
        "team_h_difficulty": h_diff,
        "team_a_difficulty": a_diff,
        "finished": finished,
        "kickoff_time": f"2025-09-{10 + (event or 0):02d}T14:00:00Z",
    }


def test_outlook_gives_each_side_its_own_difficulty():
    outlook = build_team_outlook(BOOTSTRAP, [fixture(4, 1, 2, 4, 3)])
    assert outlook[1]["fixtures"][0] == {
        "event": 4,
        "opponent_short": "LIV",
        "is_home": True,
        "difficulty": 4,
        "kickoff_time": "2025-09-14T14:00:00Z",
    }
    assert outlook[2]["fixtures"][0]["difficulty"] == 3
    assert outlook[2]["fixtures"][0]["is_home"] is False


def test_finished_and_unscheduled_fixtures_are_excluded():
    fixtures = [
        fixture(3, 1, 2, 5, 5, finished=True),
        fixture(None, 1, 3, 2, 2),
        fixture(4, 1, 3, 2, 2),
    ]
    outlook = build_team_outlook(BOOTSTRAP, fixtures)
    assert [f["event"] for f in outlook[1]["fixtures"]] == [4]


def test_horizon_truncates_and_averages_only_kept_fixtures():
    fixtures = [fixture(e, 1, 2, e, 1) for e in (4, 5, 6)]
    outlook = build_team_outlook(BOOTSTRAP, fixtures, horizon=2)
    assert outlook[1]["count"] == 2
    assert outlook[1]["avg_difficulty"] == 4.5  # (4 + 5) / 2


def test_team_with_no_fixtures_has_no_average():
    outlook = build_team_outlook(BOOTSTRAP, [fixture(4, 1, 2, 3, 3)])
    assert outlook[3]["avg_difficulty"] is None
    assert format_run(outlook[3]) == "no scheduled fixtures"


def test_format_run_is_readable():
    outlook = build_team_outlook(BOOTSTRAP, [fixture(4, 1, 2, 4, 3), fixture(5, 3, 1, 2, 2)])
    assert format_run(outlook[1]) == "LIV (H) 4, BOU (A) 2"
