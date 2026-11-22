"""Boucle de partie et RunManager, sans réseau (fausse connexion)."""

from __future__ import annotations

import asyncio

import pytest
from conftest import SILENT, FakeBot, fast_settings, load_reference_bot
from wonderland.runs import (
    RunListener,
    RunManager,
    RunMode,
    RunRejected,
    RunStatus,
)
from wonderland.teams import Team

TEAM = Team("t1", "Equipe test", "secret")
def run(manager: RunManager, bot: FakeBot, mode: RunMode, level: int | None = None, seed: int = 1):
    info = manager.prepare(TEAM, mode, level, seed)
    return asyncio.run(manager.execute(info, bot))


# ---------- boucle de partie ----------


def test_practice_win_unlocks_next_level():
    manager = RunManager(fast_settings())
    info = run(manager, FakeBot(load_reference_bot().decide), RunMode.PRACTICE, level=1)
    assert info.status is RunStatus.WON
    assert info.levels_completed == [1]
    assert manager.unlocked_level(TEAM.id) == 2
    assert manager.active_runs() == []
    assert manager.get(info.id) is info


def test_messages_order():
    bot = FakeBot(load_reference_bot().decide)
    run(RunManager(fast_settings()), bot, RunMode.PRACTICE, level=1)
    types = bot.types()
    assert types[:3] == ["hello", "level_start", "observation"]
    assert types[-2:] == ["level_end", "run_end"]
    assert bot.sent[1]["seed"] is not None  # graine communiquée en entraînement


def test_campaign_plays_all_levels():
    info = run(RunManager(fast_settings()), FakeBot(load_reference_bot().decide), RunMode.CAMPAIGN)
    assert info.status is RunStatus.WON
    assert info.levels_completed == [1, 2, 3, 4, 5]
    assert info.total_ticks == sum(r.ticks for r in info.results)


def test_silent_bot_times_out_every_tick():
    manager = RunManager(fast_settings(tick_timeout=0.001))
    bot = FakeBot(lambda obs: SILENT)
    info = run(manager, bot, RunMode.PRACTICE, level=1)
    assert info.status is RunStatus.TIMEOUT
    assert info.latency.timeouts == info.total_ticks


def test_disconnect_ends_run():
    info = run(RunManager(fast_settings()), FakeBot(lambda obs: "WAIT", disconnect_after=5),
               RunMode.PRACTICE, level=1)
    assert info.status is RunStatus.DISCONNECTED
    assert info.current_tick == 5


def test_stale_answers_are_ignored():
    bot = FakeBot(load_reference_bot().decide, stale_first=True)
    info = run(RunManager(fast_settings()), bot, RunMode.PRACTICE, level=1)
    assert info.status is RunStatus.WON


def test_invalid_action_counts_as_wait():
    bot = FakeBot(lambda obs: "FLY", disconnect_after=1)
    run(RunManager(fast_settings()), bot, RunMode.PRACTICE, level=1)
    second_obs = [m for m in bot.sent if m["type"] == "observation"][1]
    assert second_obs["data"]["events"][0]["type"] == "InvalidAction"


# ---------- règles du RunManager ----------


def test_locked_level_is_rejected():
    with pytest.raises(RunRejected, match="débloqué"):
        RunManager(fast_settings()).prepare(TEAM, RunMode.PRACTICE, 3)


def test_unlock_all_setting():
    info = RunManager(fast_settings(unlock_all=True)).prepare(TEAM, RunMode.PRACTICE, 5)
    assert info.levels == [5]


def test_practice_requires_a_level():
    with pytest.raises(RunRejected):
        RunManager(fast_settings()).prepare(TEAM, RunMode.PRACTICE, None)


def test_cooldown():
    manager = RunManager(fast_settings(run_cooldown=60))
    manager.prepare(TEAM, RunMode.PRACTICE, 1)
    with pytest.raises(RunRejected, match="Patiente"):
        manager.prepare(TEAM, RunMode.PRACTICE, 1)
    manager.prepare(TEAM, RunMode.CAMPAIGN)  # l'autre mode n'est pas concerné


def test_same_mode_replaces_previous_run():
    manager = RunManager(fast_settings())
    first = manager.prepare(TEAM, RunMode.PRACTICE, 1)
    second = manager.prepare(TEAM, RunMode.PRACTICE, 1)
    assert first.status is RunStatus.REPLACED
    assert [r.id for r in manager.active_runs()] == [second.id]


def test_one_practice_and_one_campaign_in_parallel():
    manager = RunManager(fast_settings())
    manager.prepare(TEAM, RunMode.PRACTICE, 1)
    manager.prepare(TEAM, RunMode.CAMPAIGN)
    assert len(manager.active_runs()) == 2


def test_global_cap():
    manager = RunManager(fast_settings(max_concurrent_runs=1))
    manager.prepare(TEAM, RunMode.PRACTICE, 1)
    with pytest.raises(RunRejected, match="plein"):
        manager.prepare(Team("t2", "Autre", "x"), RunMode.PRACTICE, 1)


def test_replacing_a_running_game_cancels_it():
    async def scenario():
        manager = RunManager(fast_settings(tick_timeout=0.05))
        first_bot = FakeBot(lambda obs: SILENT)  # joue lentement (timeouts)
        first = manager.prepare(TEAM, RunMode.PRACTICE, 1)
        task = asyncio.create_task(manager.execute(first, first_bot))
        await asyncio.sleep(0.2)
        manager.prepare(TEAM, RunMode.PRACTICE, 1)
        await task
        return first, first_bot

    first, bot = asyncio.run(scenario())
    assert first.status is RunStatus.REPLACED
    assert bot.sent[-1]["type"] == "run_end"
    assert bot.sent[-1]["status"] == "REPLACED"


class Recorder(RunListener):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def on_level_start(self, run, state):
        self.calls.append("level_start")

    def on_tick(self, run, state, events):
        self.calls.append("tick")

    def on_level_end(self, run, state):
        self.calls.append("level_end")

    def on_run_end(self, run):
        self.calls.append("run_end")


class Broken(RunListener):
    def on_tick(self, run, state, events):
        raise RuntimeError("service en panne")


def test_listeners_receive_every_hook():
    manager = RunManager(fast_settings())
    recorder = Recorder()
    manager.subscribe(Broken())  # une panne d'écouteur ne doit pas casser la partie
    manager.subscribe(recorder)
    info = run(manager, FakeBot(load_reference_bot().decide), RunMode.PRACTICE, level=1)
    assert info.status is RunStatus.WON
    assert recorder.calls[0] == "level_start"
    assert recorder.calls[-2:] == ["level_end", "run_end"]
    assert recorder.calls.count("tick") == info.total_ticks
