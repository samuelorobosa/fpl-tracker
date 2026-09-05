from app.alternatives import (
    candidate_score,
    flagged_player_ids,
    group_by_position,
    suggest_alternatives,
)


def pool_player(pid, **overrides) -> dict:
    base = {
        "id": pid,
        "web_name": f"P{pid}",
        "team_id": 1,
        "team_short": "ARS",
        "position": "MID",
        "now_cost": 5.0,
        "status": "a",
        "form": "5.0",
        "expected_goal_involvements": "1.00",
    }
    base.update(overrides)
    return base


def squad_player(pid, **overrides) -> dict:
    base = {
        "player_id": pid, "position": "MID", "now_cost": 5.0,
        "status": "a", "form": "5.0", "is_starting": True,
    }
    base.update(overrides)
    return base


OUTLOOK = {1: {"avg_difficulty": 3.0}, 2: {"avg_difficulty": 2.0}}


def test_excludes_owned_unavailable_and_unaffordable():
    pool = [
        pool_player(1),                       # fine
        pool_player(2),                       # owned
        pool_player(3, status="i"),           # injured
        pool_player(4, now_cost=5.6),         # over budget (5.0 + 0.5 buffer)
        pool_player(5, position="FWD"),       # wrong position
    ]
    out = suggest_alternatives(
        squad_player(99), group_by_position(pool), OUTLOOK, owned_ids={2}
    )
    assert [c["web_name"] for c in out] == ["P1"]


def test_price_buffer_is_inclusive():
    pool = [pool_player(1, now_cost=5.5)]
    out = suggest_alternatives(squad_player(99), group_by_position(pool), OUTLOOK, set())
    assert len(out) == 1


def test_ranked_by_form_then_fixtures():
    pool = [
        pool_player(1, form="4.0"),
        pool_player(2, form="8.0"),
        pool_player(3, form="6.0"),
    ]
    out = suggest_alternatives(squad_player(99), group_by_position(pool), OUTLOOK, set())
    assert [c["web_name"] for c in out] == ["P2", "P3", "P1"]


def test_easier_fixtures_break_a_form_tie():
    pool = [pool_player(1, team_id=1), pool_player(2, team_id=2, team_short="LIV")]
    out = suggest_alternatives(squad_player(99), group_by_position(pool), OUTLOOK, set())
    assert out[0]["web_name"] == "P2"  # same form, easier run
    assert out[0]["avg_difficulty"] == 2.0


def test_capped_at_three():
    pool = [pool_player(i) for i in range(1, 8)]
    out = suggest_alternatives(squad_player(99), group_by_position(pool), OUTLOOK, set())
    assert len(out) == 3


def test_missing_xgi_is_skipped_not_guessed():
    with_xgi = pool_player(1, expected_goal_involvements="4.00")
    without = pool_player(2, expected_goal_involvements=None)
    assert candidate_score(with_xgi, 3.0) > candidate_score(without, 3.0)
    assert candidate_score(without, 3.0) == 5.0  # form only, no fixture swing at 3


def test_bench_players_do_not_crowd_out_the_worst_starter():
    """Unused bench players sit at form 0.0; the starter costing points must
    still be flagged."""
    squad = [
        squad_player(1, form="0.0", is_starting=False),
        squad_player(2, form="0.0", is_starting=False),
        squad_player(3, form="0.0", is_starting=False),
        squad_player(4, form="0.7"),  # worst starter
        squad_player(5, form="8.0"),
    ]
    assert 4 in flagged_player_ids(squad, set())


def test_flagged_covers_injured_worst_form_and_alerted():
    squad = [
        squad_player(1, status="i", form="9.0"),   # unavailable
        squad_player(2, form="0.1"),               # worst form
        squad_player(3, form="0.2"),               # second worst
        squad_player(4, form="0.3"),               # third worst
        squad_player(5, form="9.0"),               # fine, but alerted
        squad_player(6, form="9.5"),               # untouched
    ]
    assert flagged_player_ids(squad, {5}) == {1, 2, 3, 4, 5}
