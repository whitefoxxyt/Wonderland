"""Outils partagés par les tests : construire un petit niveau à la volée."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from wonderland.engine import Engine
from wonderland.engine.state import GameState
from wonderland.levels import parse_level

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
