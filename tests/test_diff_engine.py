from app.diff_engine import diff_players


def make_player(**overrides) -> dict:
    base = {
        "id": 1,
        "web_name": "Szoboszlai",
        "team_short": "LIV",
        "position": "MID",
        "now_cost": 7.0,
        "status": "a",
        "news": "",
        "chance_of_playing_next_round": None,
        "form": "5.0",
        "total_points": 30,
    }
    base.update(overrides)
    return base


def test_no_changes_produces_no_diffs():
    old = [make_player()]
    new = [make_player()]
    assert diff_players(old, new) == []


def test_status_change_flagged_as_critical():
    old = [make_player(status="a")]
    new = [make_player(status="i")]
    changes = diff_players(old, new)
    assert len(changes) == 1
    assert changes[0].field == "status"
    assert changes[0].severity == "critical"


def test_price_change_flagged_as_info():
    old = [make_player(now_cost=7.0)]
    new = [make_player(now_cost=7.1)]
    changes = diff_players(old, new)
    assert any(c.field == "now_cost" and c.severity == "info" for c in changes)


def test_positional_keyword_flagged_for_midfielder_playing_right_back():
    # This is the exact Szoboszlai scenario: a MID with news mentioning
    # a defensive role should trigger a positional_role warning.
    old = [make_player(news="")]
    new = [make_player(news="Expected to deputise at right-back due to injuries.")]
    changes = diff_players(old, new)
    fields = [c.field for c in changes]
    assert "positional_role" in fields
    assert "news" in fields  # the news text itself also changed


def test_new_player_not_in_old_snapshot_is_skipped():
    old = []
    new = [make_player()]
    assert diff_players(old, new) == []


def test_forward_position_has_no_positional_keywords_defined():
    old = [make_player(position="FWD", news="")]
    new = [make_player(position="FWD", news="wide role")]
    changes = diff_players(old, new)
    fields = [c.field for c in changes]
    assert "positional_role" in fields  # 'wide role' IS a FWD keyword
