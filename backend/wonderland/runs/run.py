"""Boucle d'une partie : envoie une observation, attend l'action du bot (avec délai), joue le tick.

La boucle ne connaît pas les WebSockets : elle parle à un BotConnection.
→ testable avec une fausse connexion, et réutilisable pour un autre transport.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from typing import Any, Protocol

from wonderland.config import Settings
from wonderland.engine import Engine, GameState, Status, observe
from wonderland.engine.events import Event
from wonderland.levels import load_level
from wonderland.runs.models import LevelResult, RunInfo, RunMode, RunStatus
from wonderland.runs.protocol import (
    Hello,
    LevelEnd,
    LevelStart,
    ObservationMessage,
    RunEnd,
    parse_action,
)

# Appelé après chaque tick : (run, état, événements). Servira aux succès, au score, au direct.
TickListener = Callable[[RunInfo, GameState, list[Event]], None]


class BotDisconnected(Exception):
    """Le bot a fermé la connexion."""


class BotConnection(Protocol):
    async def send(self, message: dict[str, Any]) -> None: ...

    async def receive(self) -> Any:
        """Renvoie le prochain message JSON décodé (None si illisible) ou lève BotDisconnected."""
        ...


_STATUS_BY_LEVEL_END = {Status.DEAD: RunStatus.DEAD, Status.TIMEOUT: RunStatus.TIMEOUT}


class Run:
    def __init__(
        self,
        info: RunInfo,
        connection: BotConnection,
        settings: Settings,
        listeners: list[TickListener] | None = None,
    ) -> None:
        self.info = info
        self.connection = connection
        self.settings = settings
        self.listeners = listeners or []
        self.engine = Engine()

    async def play(self) -> RunInfo:
        info = self.info
        connected = True
        try:
            await self._send(
                Hello(
                    run_id=info.id,
                    team=info.team_id,
                    mode=info.mode.value,
                    levels=info.levels,
                    tick_timeout=self.settings.tick_timeout,
                )
            )
            rng = random.Random(info.seed)
            for level in info.levels:
                level_seed = rng.randrange(2**31)
                if not await self._play_level(level, level_seed):
                    break
            else:
                info.status = RunStatus.WON
        except BotDisconnected:
            connected = False
            info.status = RunStatus.DISCONNECTED
        except asyncio.CancelledError:
            # Remplacée ou arrêtée par le RunManager (qui a déjà fixé le statut).
            await self._finish(connected)
            raise
        await self._finish(connected)
        return info

    async def _play_level(self, level: int, seed: int) -> bool:
        """Joue un niveau ; renvoie True s'il est gagné."""
        info = self.info
        state = load_level(level, seed=seed)
        info.current_level = level
        info.current_tick = 0
        practice_seed = seed if info.mode is RunMode.PRACTICE else None
        await self._send(LevelStart(level=level, name=state.config.name, seed=practice_seed))

        while state.running:
            await self._send(
                ObservationMessage(run_id=info.id, level=level, tick=state.tick, data=observe(state))
            )
            action, timed_out = await self._await_action(state.tick)
            events = self.engine.step(state, action, timed_out=timed_out)
            info.current_tick = state.tick
            for listener in self.listeners:
                listener(info, state, events)
            await asyncio.sleep(0)  # laisse tourner les autres parties

        info.total_ticks += state.tick
        info.results.append(
            LevelResult(level, state.status.name, state.tick, state.player.hp, len(state.player.hats))
        )
        await self._send(
            LevelEnd(level=level, status=state.status.name, ticks=state.tick, hp=state.player.hp)
        )
        if state.status is Status.WON:
            return True
        info.status = _STATUS_BY_LEVEL_END.get(state.status, RunStatus.DEAD)
        return False

    async def _await_action(self, tick: int) -> tuple[str | None, bool]:
        """Attend l'action du tick `tick`. Renvoie (action, timed_out)."""
        loop = asyncio.get_running_loop()
        start = loop.time()
        deadline = start + self.settings.tick_timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(self.connection.receive(), remaining)
            except TimeoutError:
                break
            message = parse_action(raw)
            if message is not None and message.tick < tick:
                continue  # réponse en retard à une observation précédente : ignorée
            self.info.latency.record(loop.time() - start)
            if message is None or message.tick != tick:
                return None, False  # message invalide → InvalidAction (compte comme WAIT)
            return message.action, False
        self.info.latency.timeouts += 1
        return None, True

    async def _send(self, message: Any) -> None:
        await self.connection.send(message.model_dump())

    async def _finish(self, connected: bool) -> None:
        self.info.ended_at = time.time()
        if not connected:
            return
        try:
            await self._send(
                RunEnd(
                    status=self.info.status.value,
                    levels_completed=self.info.levels_completed,
                    total_ticks=self.info.total_ticks,
                )
            )
        except (BotDisconnected, RuntimeError):
            pass
