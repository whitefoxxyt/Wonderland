"""Replays : on enregistre seulement la graine et les actions, et on re-simule.

Le moteur étant déterministe, (niveau, graine, liste d'actions) suffit à reproduire
exactement la partie, image par image. Un replay de campagne pèse quelques Ko.
"""

from __future__ import annotations

from typing import Any

from wonderland.broadcast.frames import state_frame
from wonderland.engine import Engine
from wonderland.engine.state import GameState
from wonderland.levels import load_level
from wonderland.persistence import Database
from wonderland.runs.listeners import RunListener
from wonderland.runs.models import RunInfo


class ReplayRecorder(RunListener):
    def __init__(self, db: Database) -> None:
        self.db = db
        self._replays: dict[str, dict[str, Any]] = {}

    def on_level_start(self, run: RunInfo, state: GameState) -> None:
        replay = self._replays.setdefault(
            run.id,
            {"run_id": run.id, "team_id": run.team_id, "mode": run.mode.value, "levels": []},
        )
        replay["levels"].append({"level": state.config.level_id, "seed": state.seed, "inputs": []})

    def on_tick(self, run: RunInfo, state: GameState, events: list) -> None:
        replay = self._replays.get(run.id)
        if replay and state.last_input is not None:
            action, timed_out = state.last_input
            replay["levels"][-1]["inputs"].append([action, timed_out])

    def on_run_end(self, run: RunInfo) -> None:
        replay = self._replays.pop(run.id, None)
        if replay is not None:
            self.db.save_replay(run.id, replay)


def replay_frames(replay: dict[str, Any], level_index: int) -> list[dict[str, Any]]:
    """Re-simule un niveau d'un replay et renvoie toutes ses images (état initial inclus)."""
    entry = replay["levels"][level_index]
    state = load_level(entry["level"], seed=entry["seed"])
    engine = Engine()
    frames = [state_frame(state, [])]
    for action, timed_out in entry["inputs"]:
        if not state.running:
            break
        events = engine.step(state, action, timed_out=timed_out)
        frames.append(state_frame(state, events))
    return frames
