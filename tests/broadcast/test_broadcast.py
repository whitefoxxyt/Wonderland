"""Diffusion en direct (partie vedette, hub) et replays."""

from __future__ import annotations

import asyncio

from conftest import FakeBot, fast_settings, load_reference_bot
from wonderland.broadcast import ALL, FEATURED, BroadcastHub, FeaturedSelector, run_channel
from wonderland.persistence import Database
from wonderland.replays import ReplayRecorder, replay_frames
from wonderland.runs import RunManager, RunMode
from wonderland.teams import Team

TEAM = Team("t1", "Equipe 1", "tok1")
OTHER = Team("t2", "Equipe 2", "tok2")


def drain(queue: asyncio.Queue) -> list[dict]:
    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


# ---------- partie vedette ----------


def test_selector_picks_most_advanced():
    selector = FeaturedSelector()
    assert selector.update({"a": (1, 0.5), "b": (2, 0.1)}, now=0) == "b"


def test_selector_hysteresis():
    selector = FeaturedSelector(hold=5)
    selector.update({"a": (1, 0.5)}, now=0)
    assert selector.update({"a": (1, 0.5), "b": (1, 0.9)}, now=1) == "a"  # b vient de passer devant
    assert selector.update({"a": (1, 0.5), "b": (1, 0.9)}, now=4) == "a"
    assert selector.update({"a": (1, 0.5), "b": (1, 0.9)}, now=6.5) == "b"  # devant depuis 5 s


def test_selector_highlight_wins_temporarily():
    selector = FeaturedSelector(highlight=5)
    scores = {"a": (3, 0.0), "b": (1, 0.0)}
    selector.update(scores, now=0)
    selector.highlight("b", now=1)
    assert selector.update(scores, now=2) == "b"
    assert selector.update(scores, now=7) == "a"


def test_selector_follows_finished_run():
    selector = FeaturedSelector()
    selector.update({"a": (1, 0.0), "b": (0, 0.0)}, now=0)
    assert selector.update({"b": (0, 0.0)}, now=1) == "b"
    assert selector.update({}, now=2) is None


# ---------- hub ----------


def make_manager(hub: BroadcastHub, db: Database | None = None) -> RunManager:
    manager = RunManager(fast_settings())
    if db is not None:
        manager.subscribe(ReplayRecorder(db))
    manager.subscribe(hub)
    return manager


def play(manager: RunManager, team: Team, mode: RunMode, level: int | None = 1):
    info = manager.prepare(team, mode, level, seed=3)
    return manager.execute(info, FakeBot(load_reference_bot().decide))


def test_hub_streams_frames_and_end():
    hub = BroadcastHub(fast_settings(live_fps=0), team_name=str.upper)

    async def scenario():
        queue = hub.subscribe(ALL)
        info = await play(make_manager(hub), TEAM, RunMode.PRACTICE)
        return info, drain(queue)

    info, messages = asyncio.run(scenario())
    frames = [m for m in messages if m["type"] == "frame"]
    assert len(frames) == info.total_ticks + 2  # état initial + chaque tick + fin de niveau
    assert frames[0]["team"] == "T1"
    assert frames[0]["grid"][0].startswith("####")
    assert any(m["type"] == "highlight" for m in messages)
    assert messages[-1]["type"] == "run_end"
    assert hub.snapshot(ALL)["runs"] == []  # partie terminée : plus affichée


def test_hub_throttles_frames():
    hub = BroadcastHub(fast_settings(live_fps=1))

    async def scenario():
        queue = hub.subscribe(run_channel("dummy"))
        all_queue = hub.subscribe(ALL)
        await play(make_manager(hub), TEAM, RunMode.PRACTICE)
        return drain(queue), drain(all_queue)

    other, messages = asyncio.run(scenario())
    assert other == []  # canal d'une autre partie : rien
    assert len([m for m in messages if m["type"] == "frame"]) < 10


def test_campaign_is_featured_over_practice():
    hub = BroadcastHub(fast_settings(live_fps=0))
    seen: set[str] = set()

    async def scenario():
        queue = hub.subscribe(FEATURED)
        manager = make_manager(hub)
        practice = asyncio.create_task(play(manager, OTHER, RunMode.PRACTICE))
        campaign = asyncio.create_task(play(manager, TEAM, RunMode.CAMPAIGN, None))
        await asyncio.sleep(0.05)
        seen.add(hub.featured)
        await asyncio.gather(practice, campaign)
        return drain(queue)

    messages = asyncio.run(scenario())
    frames = [m for m in messages if m["type"] == "frame"]
    assert {f["mode"] for f in frames[5:50]} == {"campaign"}
    assert any(m["type"] == "featured" for m in messages)


def test_slow_spectator_drops_old_messages():
    hub = BroadcastHub(fast_settings(live_fps=0), queue_size=5)

    async def scenario():
        queue = hub.subscribe(ALL)
        await play(make_manager(hub), TEAM, RunMode.PRACTICE)
        return drain(queue)

    messages = asyncio.run(scenario())
    assert len(messages) == 5
    assert messages[-1]["type"] == "run_end"


# ---------- replays ----------


def test_replay_reproduces_the_game():
    db = Database(":memory:")
    hub = BroadcastHub(fast_settings())
    info = asyncio.run(play(make_manager(hub, db), TEAM, RunMode.CAMPAIGN, None))
    replay = db.load_replay(info.id)
    assert [entry["level"] for entry in replay["levels"]] == [1, 2, 3, 4, 5]
    for index, result in enumerate(info.results):
        frames = replay_frames(replay, index)
        assert frames[-1]["tick"] == result.ticks
        assert frames[-1]["status"] == result.status
        assert frames[-1]["player"]["hp"] == result.hp
