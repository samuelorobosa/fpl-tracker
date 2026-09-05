import pytest

from app import storage


@pytest.fixture(autouse=True)
def temp_data_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PLAYERS_DIR", tmp_path / "players")
    monkeypatch.setattr(storage, "TEAMS_DIR", tmp_path / "teams")


def test_player_snapshot_round_trip():
    storage.save_player_snapshot(3, [{"id": 1}])
    assert storage.load_player_snapshot(3) == [{"id": 1}]
    assert storage.load_player_snapshot(4) is None


def test_previous_snapshot_skips_gaps():
    """Snapshots are only written when a digest runs, so a missed week must
    not silently disable alerts."""
    storage.save_player_snapshot(2, [{"id": "gw2"}])
    storage.save_player_snapshot(5, [{"id": "gw5"}])
    assert storage.load_previous_player_snapshot(before=8) == (5, [{"id": "gw5"}])
    assert storage.load_previous_player_snapshot(before=5) == (2, [{"id": "gw2"}])
    assert storage.load_previous_player_snapshot(before=2) is None


def test_teams_are_kept_apart():
    storage.save_team_snapshot(111, 3, {"squad": ["a"]})
    storage.save_team_snapshot(222, 3, {"squad": ["b"]})
    assert storage.load_team_snapshot(111, 3) == {"squad": ["a"]}
    assert storage.load_team_snapshot(222, 3) == {"squad": ["b"]}


def test_team_gameweeks_lists_history():
    assert storage.team_gameweeks(111) == []
    storage.save_team_snapshot(111, 4, {})
    storage.save_team_snapshot(111, 3, {})
    assert storage.team_gameweeks(111) == [3, 4]


def test_status_helpers_report_what_is_stored():
    assert storage.player_gameweeks() == []
    assert storage.stored_teams() == {}

    storage.save_player_snapshot(3, [{"id": 1}])
    storage.save_player_snapshot(4, [{"id": 1}])
    storage.save_team_snapshot(3732633, 3, {})

    assert storage.player_gameweeks() == [3, 4]
    assert storage.stored_teams() == {"3732633": [3]}
