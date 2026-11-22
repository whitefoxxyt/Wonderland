"""Boucle de tick : l'unique point d'entrée pour faire avancer une partie.

Ordre de résolution d'un tick (déterministe) :
    1. action du joueur (déplacement / attaque / tir / parade / attente)
    2. ramassage d'objet, puis test de la sortie
    3. projectiles
    4. mobs (frappes armées, charges, puis décisions des IA)
    5. pièges
    6. brouillard, tick + 1, test du temps limite
"""

from __future__ import annotations

from wonderland.engine.actions import Action
from wonderland.engine.events import Event, InvalidAction, LevelCompleted, LevelTimeout, TimedOut
from wonderland.engine.grid import Tile
from wonderland.engine.state import GameState, Status
from wonderland.engine.systems.mobs import run_mobs
from wonderland.engine.systems.pickups import collect_items
from wonderland.engine.systems.player import apply_player_action
from wonderland.engine.systems.projectiles import advance_projectiles
from wonderland.engine.systems.traps import update_traps
from wonderland.engine.vision import update_discovered


class GameOverError(RuntimeError):
    """On a appelé step() sur une partie terminée."""


class Engine:
    def step(
        self,
        state: GameState,
        action: Action | str | None,
        *,
        timed_out: bool = False,
    ) -> list[Event]:
        """Joue un tick. `action` peut être une Action, un texte ("MOVE_UP") ou None.

        Une action invalide ou un timeout compte comme WAIT (et émet un événement).
        """
        if not state.running:
            raise GameOverError(f"Partie terminée ({state.status.name})")

        events: list[Event] = []
        player = state.player
        player.parrying = False
        if player.shoot_cooldown > 0:
            player.shoot_cooldown -= 1

        if isinstance(action, str):
            action = Action.parse(action)
        state.last_input = (action.name if action is not None else None, timed_out)
        if timed_out:
            events.append(TimedOut())
            action = Action.WAIT
        elif action is None:
            events.append(InvalidAction("unknown_action"))
            action = Action.WAIT

        apply_player_action(state, action, events)
        collect_items(state, events)
        self._check_exit(state, events)

        for phase in (advance_projectiles, run_mobs, update_traps):
            if not state.running:
                break
            phase(state, events)

        update_discovered(state)
        state.tick += 1
        if state.running and state.tick >= state.config.max_ticks:
            state.status = Status.TIMEOUT
            events.append(LevelTimeout(state.config.level_id, state.tick))

        state.last_events = events
        return events

    @staticmethod
    def _check_exit(state: GameState, events: list[Event]) -> None:
        if state.config.win_condition != "exit":
            return
        if state.grid.get(*state.player.position) is Tile.EXIT:
            state.status = Status.WON
            events.append(LevelCompleted(state.config.level_id, state.tick))
