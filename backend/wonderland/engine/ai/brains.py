"""IA des mobs ordinaires.

Toutes partagent la même règle de corps-à-corps : si le joueur est adjacent et que
l'attaque est rechargée, le mob ARME son coup (WINDUP) et frappera au tick suivant.
"""

from __future__ import annotations

from wonderland.engine.actions import Direction
from wonderland.engine.ai.base import (
    OPPOSITE,
    Brain,
    Intent,
    Move,
    Shoot,
    Wait,
    Windup,
    aligned_direction,
    can_see_player,
    free_directions,
    is_free_for_mob,
    player_adjacent_direction,
    step_towards,
)
from wonderland.engine.entities import Mob
from wonderland.engine.events import Event
from wonderland.engine.state import GameState


def melee_or_none(state: GameState, mob: Mob) -> Intent | None:
    direction = player_adjacent_direction(state, mob)
    if direction is None:
        return None
    if mob.attack_cooldown == 0:
        return Windup(direction)
    return Wait()


def chase(state: GameState, mob: Mob, *, avoid_traps: bool = True) -> Intent | None:
    if not can_see_player(state, mob):
        return None
    step = step_towards(state, mob, state.player.position, avoid_traps=avoid_traps)
    return Move(step) if step is not None else None


class IdleBrain(Brain):
    """Ne bouge pas, frappe seulement si on vient au contact."""

    def decide(self, state: GameState, mob: Mob, events: list[Event]) -> Intent:
        return melee_or_none(state, mob) or Wait()


class ChaserBrain(Brain):
    """Poursuit le joueur dès qu'il le voit (loirs, gardes invoqués par la Reine)."""

    def decide(self, state: GameState, mob: Mob, events: list[Event]) -> Intent:
        return melee_or_none(state, mob) or chase(state, mob) or Wait()


class PatrolBrain(Brain):
    """Fait des allers-retours sur sa ligne ; poursuit le joueur s'il le voit (gardes-cartes)."""

    def decide(self, state: GameState, mob: Mob, events: list[Event]) -> Intent:
        intent = melee_or_none(state, mob) or chase(state, mob)
        if intent is not None:
            return intent
        direction = mob.patrol_dir or Direction.RIGHT
        for candidate in (direction, OPPOSITE[direction]):
            if is_free_for_mob(state, mob.x + candidate.dx, mob.y + candidate.dy, avoid_traps=True):
                mob.patrol_dir = candidate
                return Move(candidate)
        return Wait()


class ErraticBrain(Brain):
    """Lièvre de mars : imprévisible, se rapproche du joueur une fois sur deux."""

    def decide(self, state: GameState, mob: Mob, events: list[Event]) -> Intent:
        intent = melee_or_none(state, mob)
        if intent is not None:
            return intent
        if state.rng.random() < 0.5:
            intent = chase(state, mob)
            if intent is not None:
                return intent
        options = free_directions(state, mob)
        if not options:
            return Wait()
        return Move(state.rng.choice(options))


class ArcherBrain(Brain):
    """Carte-archère : immobile, tire quand le joueur est aligné et visible."""

    COOLDOWN = 4
    SPEED = 2

    def decide(self, state: GameState, mob: Mob, events: list[Event]) -> Intent:
        intent = melee_or_none(state, mob)
        if intent is not None:
            return intent
        if mob.attack_cooldown > 0 or not can_see_player(state, mob):
            return Wait()
        direction = aligned_direction(state, mob, mob.sight)
        if direction is None:
            return Wait()
        return Shoot(direction, self.SPEED, mob.sight, self.COOLDOWN, "arrow", mob.damage)
