"""Moteur de jeu pur : aucune I/O réseau ni base de données ici.

Usage minimal :
    from wonderland.engine import Engine, observe
    from wonderland.levels import load_level

    state = load_level(1, seed=42)
    engine = Engine()
    while state.running:
        action = mon_bot(observe(state))
        engine.step(state, action)
"""

from wonderland.engine.actions import Action, Direction
from wonderland.engine.observation import observe
from wonderland.engine.render import render
from wonderland.engine.simulation import Engine, GameOverError
from wonderland.engine.state import GameState, Status

__all__ = [
    "Action",
    "Direction",
    "Engine",
    "GameOverError",
    "GameState",
    "Status",
    "observe",
    "render",
]
