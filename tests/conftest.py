"""Outils partagés par les tests : construire un petit niveau à la volée."""

from __future__ import annotations

import asyncio
import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from wonderland.config import Settings
from wonderland.engine import Engine
from wonderland.engine.state import GameState
from wonderland.levels import parse_level
from wonderland.runs import BotDisconnected

ROOT = Path(__file__).resolve().parent.parent


def make_state(lines: list[str], seed: int = 0, **options: Any) -> GameState:
    """Crée un état depuis une carte ASCII. options : win, vision_radius, traps, start_weapon…"""
    data: dict[str, Any] = {"id": 0, "name": "test", "max_ticks": 100, "map": lines}
    data.update(options)
    return parse_level(data, seed=seed)


def load_reference_bot() -> ModuleType:
    path = ROOT / "tools" / "bots" / "reference_bot.py"
    spec = importlib.util.spec_from_file_location("reference_bot", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def engine() -> Engine:
    return Engine()


SILENT = object()


class FakeBot:
    """Connexion simulée : répond à chaque observation avec decide(obs)."""

    def __init__(
        self,
        decide: Callable[[dict[str, Any]], Any],
        *,
        disconnect_after: int | None = None,
        stale_first: bool = False,
    ) -> None:
        self.decide = decide
        self.disconnect_after = disconnect_after
        self.stale_first = stale_first
        self.sent: list[dict[str, Any]] = []
        self.inbox: asyncio.Queue[Any] = asyncio.Queue()
        self.observations = 0

    async def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)
        if message["type"] != "observation":
            return
        self.observations += 1
        if self.disconnect_after is not None and self.observations > self.disconnect_after:
            await self.inbox.put(BotDisconnected)
            return
        action = self.decide(message["data"])
        if action is SILENT:
            return
        if self.stale_first and message["tick"] > 0:
            await self.inbox.put({"type": "action", "tick": message["tick"] - 1, "action": "WAIT"})
        await self.inbox.put({"type": "action", "tick": message["tick"], "action": action})

    async def receive(self) -> Any:
        item = await self.inbox.get()
        if item is BotDisconnected:
            raise BotDisconnected
        return item

    def types(self) -> list[str]:
        return [m["type"] for m in self.sent]


def fast_settings(**overrides: Any) -> Settings:
    base = Settings()
    base.tick_timeout = 0.2
    base.run_cooldown = 0
    base.campaign_tick_delay = 0
    for key, value in overrides.items():
        setattr(base, key, value)
    return base
