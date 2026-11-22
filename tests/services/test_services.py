"""Score, succès, persistance et classement."""

from __future__ import annotations

import asyncio

import pytest
from conftest import FakeBot, fast_settings, load_reference_bot
from wonderland.engine.events import (
    DamageDealt,
    LevelCompleted,
    PlayerDied,
    PlayerWaited,
)
from wonderland.engine.state import Status
from wonderland.levels import load_level
from wonderland.persistence import Database
from wonderland.runs import RunManager, RunMode, RunStatus
from wonderland.runs.models import LevelResult, RunInfo
from wonderland.services.achievements import AchievementService
from wonderland.services.leaderboard import RunRecorder, leaderboard
from wonderland.services.scoring import ScoringService, compute_score
from wonderland.teams import Team, TeamRegistry

TEAM = Team("t1", "Equipe 1", "tok1")
OTHER = Team("t2", "Equipe 2", "tok2")


@pytest.fixture
def db() -> Database:
    return Database(":memory:")


def make_manager(db: Database) -> tuple[RunManager, AchievementService]:
    manager = RunManager(fast_settings())
    achievements = AchievementService(db)
    manager.subscribe(ScoringService())
    manager.subscribe(achievements)
    manager.subscribe(RunRecorder(db))
    return manager, achievements


def play(manager: RunManager, team: Team, mode: RunMode, level: int | None = None) -> RunInfo:
    info = manager.prepare(team, mode, level, seed=1)
    return asyncio.run(manager.execute(info, FakeBot(load_reference_bot().decide)))


def fake_run(team: Team = TEAM, mode: RunMode = RunMode.PRACTICE) -> RunInfo:
    return RunInfo(id="r1", team_id=team.id, mode=mode, levels=[1], seed=0)


# ---------- score ----------


def test_compute_score():
    run = fake_run()
    run.results = [LevelResult(1, "WON", 70, 5, 1), LevelResult(2, "DEAD", 50, 0, 0)]
    run.kills = 2
    run.status = RunStatus.DEAD
    # 1000 + 2×(80−70) + 50 (chapeau) + 2×20 (kills) − 100 (mort)
    assert compute_score(run, {1: 80, 2: 100}) == 1000 + 20 + 50 + 40 - 100


# ---------- campagne complète : score, succès, base ----------


def test_campaign_unlocks_expected_achievements(db):
    manager, achievements = make_manager(db)
    info = play(manager, TEAM, RunMode.CAMPAIGN)

    assert info.status is RunStatus.WON
    assert info.score > 5000
    unlocked = achievements.unlocked(TEAM.id)
    for expected in ("down_the_rabbit_hole", "late_rabbit", "clean_code", "first_to_court"):
        assert expected in unlocked
    assert "Premier à la cour" in info.achievements_unlocked

    saved = db.runs_for_team(TEAM.id)
    assert saved[0]["score"] == info.score
    assert saved[0]["levels_completed"] == [1, 2, 3, 4, 5]


def test_first_to_court_is_unique(db):
    manager, achievements = make_manager(db)
    play(manager, TEAM, RunMode.CAMPAIGN)
    play(manager, OTHER, RunMode.CAMPAIGN)
    assert "first_to_court" in achievements.unlocked(TEAM.id)
    assert "first_to_court" not in achievements.unlocked(OTHER.id)


def test_unlocks_survive_a_restart(db):
    manager, _ = make_manager(db)
    play(manager, TEAM, RunMode.PRACTICE, level=1)
    fresh = AchievementService(db)  # simule un redémarrage du serveur
    assert "down_the_rabbit_hole" in fresh.unlocked(TEAM.id)
    assert db.unlocked_levels() == {TEAM.id: 2}
    assert RunManager(fast_settings(), unlocked=db.unlocked_levels()).unlocked_level(TEAM.id) == 2


# ---------- succès isolés (états construits à la main) ----------


def test_more_dead_than_alive_accumulates_across_runs(db):
    service = AchievementService(db)
    for level in [1, 2, 3, 4]:
        service.on_tick(fake_run(), load_level(level, seed=0), [PlayerDied("trap", None)])
    assert "more_dead_than_alive" not in service.unlocked(TEAM.id)
    service.on_level_end(fake_run(), load_level(4, seed=0))  # sauvegarde la progression
    restarted = AchievementService(db)
    restarted.on_tick(fake_run(), load_level(5, seed=0), [PlayerDied("melee", 3)])
    assert "more_dead_than_alive" in restarted.unlocked(TEAM.id)


def test_tea_time(db):
    service = AchievementService(db)
    state = load_level(2, seed=0)
    state.player.move_to(11, 9)
    run = fake_run()
    for _ in range(5):
        service.on_tick(run, state, [PlayerWaited()])
    assert "tea_time" not in service.unlocked(TEAM.id)
    service.on_tick(run, state, [PlayerWaited()])
    assert "tea_time" in service.unlocked(TEAM.id)


def _boss_fight(db: Database, causes: list[str]) -> set[str]:
    service = AchievementService(db)
    run = fake_run()
    state = load_level(5, seed=0)
    queen = state.boss()
    service.on_level_start(run, state)
    service.on_tick(run, state, [DamageDealt(1, queen.id, 2, c, 10) for c in causes])
    state.status = Status.WON
    service.on_tick(run, state, [LevelCompleted(5, 100)])
    service.on_level_end(run, state)
    return service.unlocked(TEAM.id)


def test_rigged_croquet_only_with_traps(db):
    unlocked = _boss_fight(db, ["trap", "trap"])
    assert "rigged_croquet" in unlocked
    assert "knife_is_enough" not in unlocked


def test_knife_is_enough(db):
    unlocked = _boss_fight(db, ["melee", "melee"])
    assert "knife_is_enough" in unlocked
    assert "rigged_croquet" not in unlocked


def test_hidden_achievements_are_masked(db):
    service = AchievementService(db)
    view = {a["hint"]: a for a in service.for_team(TEAM.id)}
    hidden = view["Le Lapin n'a jamais le temps…"]
    assert hidden["name"] == "???"
    assert hidden["description"] is None
    assert view["Suivez le Lapin Blanc."]["name"] == "Dans le terrier"


# ---------- classement ----------


def test_leaderboard_order(db):
    manager, achievements = make_manager(db)
    play(manager, OTHER, RunMode.PRACTICE, level=1)
    play(manager, TEAM, RunMode.CAMPAIGN)
    board = leaderboard(db, TeamRegistry([TEAM, OTHER]), achievements)
    assert [row["team_id"] for row in board] == [TEAM.id, OTHER.id]
    assert board[0]["max_level"] == 5
    assert board[1]["max_level"] == 1
    assert board[0]["rank"] == 1


def test_hat_collector_needs_every_hat(db):
    from wonderland.engine.events import ItemPicked
    from wonderland.levels import level_summary

    service = AchievementService(db)
    for level in range(1, 6):
        x, y = level_summary(level)["hats"][0]
        assert "hat_collector" not in service.unlocked(TEAM.id)
        service.on_tick(fake_run(), load_level(level, seed=0), [ItemPicked(99, "HAT", x, y)])
    assert "hat_collector" in service.unlocked(TEAM.id)
