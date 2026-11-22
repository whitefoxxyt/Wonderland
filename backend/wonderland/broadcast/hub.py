"""Diffusion en direct des parties vers les spectateurs (écran public, mosaïque, suivi d'une partie).

Canaux :
    "featured"   : la partie vedette + les moments forts de toutes les parties + le classement
    "all"        : toutes les parties (mode mosaïque)
    "run:<id>"   : une seule partie

Messages envoyés :
    snapshot   à la connexion : état courant du canal
    frame      image d'une partie (au plus `live_fps` par seconde et par partie)
    featured   la partie vedette a changé
    highlight  moment fort (niveau gagné, mort, phase du boss, succès débloqué)
    run_end    fin d'une partie (résumé, score)
    leaderboard classement mis à jour (après chaque partie)

Chaque spectateur a sa propre file bornée : un spectateur lent perd les images
les plus anciennes au lieu de ralentir les parties.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from wonderland.broadcast.featured import FeaturedSelector, Score
from wonderland.broadcast.frames import distance_to_exit, level_progress, state_frame
from wonderland.config import Settings
from wonderland.engine.events import BossPhaseChanged, Event, LevelCompleted, PlayerDied
from wonderland.engine.state import GameState
from wonderland.runs.listeners import RunListener
from wonderland.runs.models import RunInfo, RunMode

FEATURED = "featured"
ALL = "all"

Message = dict[str, Any]


def run_channel(run_id: str) -> str:
    return f"run:{run_id}"


class BroadcastHub(RunListener):
    def __init__(
        self,
        settings: Settings,
        team_name: Callable[[str], str] = lambda team_id: team_id,
        leaderboard: Callable[[], list[dict[str, Any]]] | None = None,
        clock: Callable[[], float] = time.monotonic,
        queue_size: int = 200,
    ) -> None:
        self.min_interval = 1 / settings.live_fps if settings.live_fps > 0 else 0.0
        self.team_name = team_name
        self.leaderboard = leaderboard
        self.clock = clock
        self.queue_size = queue_size
        self.selector = FeaturedSelector()
        self._subscribers: dict[str, set[asyncio.Queue[Message]]] = {}
        self._frames: dict[str, Message] = {}
        self._scores: dict[str, Score] = {}
        self._campaign: dict[str, bool] = {}
        self._start_distance: dict[str, int | None] = {}
        self._last_sent: dict[str, float] = {}

    # ---------- abonnements ----------

    def subscribe(self, channel: str) -> asyncio.Queue[Message]:
        queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=self.queue_size)
        self._subscribers.setdefault(channel, set()).add(queue)
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue[Message]) -> None:
        self._subscribers.get(channel, set()).discard(queue)

    def snapshot(self, channel: str) -> Message:
        featured = self.selector.current
        if channel == ALL:
            runs = list(self._frames.values())
        elif channel == FEATURED:
            runs = [self._frames[featured]] if featured in self._frames else []
        else:
            run_id = channel.removeprefix("run:")
            runs = [self._frames[run_id]] if run_id in self._frames else []
        return {"type": "snapshot", "featured": featured, "runs": runs}

    @property
    def featured(self) -> str | None:
        return self.selector.current

    # ---------- crochets de partie ----------

    def on_level_start(self, run: RunInfo, state: GameState) -> None:
        self._campaign[run.id] = run.mode is RunMode.CAMPAIGN
        self._start_distance[run.id] = distance_to_exit(state)
        self._update(run, state, [], force=True)

    def on_tick(self, run: RunInfo, state: GameState, events: list[Event]) -> None:
        highlight = self._highlight_text(run, state, events)
        if highlight:
            self.selector.highlight(run.id, self.clock())
            self._highlight(run, "event", highlight)
        self._update(run, state, events, force=bool(highlight))

    def on_level_end(self, run: RunInfo, state: GameState) -> None:
        self._update(run, state, [], force=True)

    def on_run_end(self, run: RunInfo) -> None:
        message = {"type": "run_end", "run": run.to_dict(), "team": self.team_name(run.team_id)}
        for channel in (ALL, FEATURED, run_channel(run.id)):
            self._publish(channel, message)
        for store in (self._frames, self._scores, self._campaign, self._start_distance, self._last_sent):
            store.pop(run.id, None)
        if self.leaderboard is not None:
            rows = self.leaderboard()
            for channel in (ALL, FEATURED):
                self._publish(channel, {"type": "leaderboard", "rows": rows})
        self._refresh_featured()

    def on_achievement(self, team_id: str, achievement: Any, run: RunInfo) -> None:
        """À brancher sur AchievementService.on_unlock."""
        self.selector.highlight(run.id, self.clock())
        self._highlight(run, "achievement", f"{self.team_name(team_id)} débloque « {achievement.name} »")
        self._refresh_featured()

    # ---------- interne ----------

    def _update(self, run: RunInfo, state: GameState, events: list[Event], *, force: bool) -> None:
        progress = level_progress(state, self._start_distance.get(run.id))
        frame = {
            "type": "frame",
            "run_id": run.id,
            "team_id": run.team_id,
            "team": self.team_name(run.team_id),
            "mode": run.mode.value,
            "levels_completed": run.levels_completed,
            "total_ticks": run.total_ticks + (state.tick if state.running else 0),
            "progress": round(progress, 3),
            **state_frame(state, events),
        }
        self._frames[run.id] = frame
        self._scores[run.id] = (float(len(run.levels_completed)), progress)

        now = self.clock()
        if not force and now - self._last_sent.get(run.id, -1e9) < self.min_interval:
            return
        self._last_sent[run.id] = now
        self._publish(ALL, frame)
        self._publish(run_channel(run.id), frame)
        self._refresh_featured()
        if run.id == self.selector.current:
            self._publish(FEATURED, frame)

    def _refresh_featured(self) -> None:
        campaign = {rid: s for rid, s in self._scores.items() if self._campaign.get(rid)}
        candidates = campaign or self._scores  # les campagnes d'abord, sinon l'entraînement
        previous = self.selector.current
        current = self.selector.update(candidates, self.clock())
        if current == previous:
            return
        frame = self._frames.get(current) if current else None
        self._publish(
            FEATURED,
            {"type": "featured", "run_id": current, "team": frame["team"] if frame else None},
        )
        if frame is not None:
            self._publish(FEATURED, frame)

    def _highlight(self, run: RunInfo, kind: str, text: str) -> None:
        message = {"type": "highlight", "run_id": run.id, "kind": kind, "text": text}
        for channel in (ALL, FEATURED, run_channel(run.id)):
            self._publish(channel, message)

    def _highlight_text(self, run: RunInfo, state: GameState, events: list[Event]) -> str | None:
        team = self.team_name(run.team_id)
        level = state.config.level_id
        for event in events:
            if isinstance(event, LevelCompleted):
                return f"{team} termine le niveau {level} !"
            if isinstance(event, PlayerDied):
                return f"{team} tombe au niveau {level}…"
            if isinstance(event, BossPhaseChanged):
                return f"La Reine passe en phase {event.phase} face à {team} !"
        return None

    def _publish(self, channel: str, message: Message) -> None:
        for queue in self._subscribers.get(channel, ()):
            if queue.full():
                try:
                    queue.get_nowait()  # on sacrifie le plus ancien message
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(message)
