"""Socle des IA de mobs : intentions et fonctions utilitaires.

Une IA (Brain) ne modifie pas le monde directement : elle renvoie une INTENTION
(bouger, armer une attaque, tirer, charger, attendre) que systems/mobs.py applique.
Seule exception : la Reine invoque des gardes elle-même.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from wonderland.engine.actions import Direction
from wonderland.engine.entities import Mob
from wonderland.engine.events import Event
from wonderland.engine.state import GameState
from wonderland.engine.vision import line_of_sight

Position = tuple[int, int]

# Ordre fixe des directions : garantit qu'une IA décide toujours pareil à état égal.
DIRECTIONS: tuple[Direction, ...] = (Direction.UP, Direction.RIGHT, Direction.DOWN, Direction.LEFT)
OPPOSITE: dict[Direction, Direction] = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}


# ---------- intentions ----------


@dataclass(frozen=True)
class Wait:
    pass


@dataclass(frozen=True)
class Move:
    direction: Direction


@dataclass(frozen=True)
class Windup:
    """Arme une attaque au corps-à-corps : elle frappera au prochain tick."""

    direction: Direction


@dataclass(frozen=True)
class Shoot:
    direction: Direction
    speed: int
    max_range: int
    cooldown: int
    kind: str
    damage: int = 1


@dataclass(frozen=True)
class Charge:
    direction: Direction


Intent = Wait | Move | Windup | Shoot | Charge


class Brain:
    """IA par défaut : ne fait rien."""

    def decide(self, state: GameState, mob: Mob, events: list[Event]) -> Intent:
        return Wait()


# ---------- utilitaires ----------


def direction_between(a: Position, b: Position) -> Direction | None:
    """Direction pour aller de a à b si elles sont adjacentes, sinon None."""
    delta = (b[0] - a[0], b[1] - a[1])
    for direction in DIRECTIONS:
        if (direction.dx, direction.dy) == delta:
            return direction
    return None


def player_adjacent_direction(state: GameState, mob: Mob) -> Direction | None:
    return direction_between(mob.position, state.player.position)


def can_see_player(state: GameState, mob: Mob) -> bool:
    if mob.distance_to(state.player) > mob.sight:
        return False
    return line_of_sight(state.grid, mob.position, state.player.position)


def is_free_for_mob(state: GameState, x: int, y: int, *, avoid_traps: bool) -> bool:
    if not state.is_free(x, y):
        return False
    return not (avoid_traps and (x, y) in state.traps)


def free_directions(state: GameState, mob: Mob, *, avoid_traps: bool = True) -> list[Direction]:
    return [
        d
        for d in DIRECTIONS
        if is_free_for_mob(state, mob.x + d.dx, mob.y + d.dy, avoid_traps=avoid_traps)
    ]


def aligned_direction(state: GameState, mob: Mob, max_range: int) -> Direction | None:
    """Direction du joueur s'il est sur la même ligne/colonne, à portée, sans mur entre les deux."""
    px, py = state.player.position
    if mob.x != px and mob.y != py:
        return None
    distance = abs(mob.x - px) + abs(mob.y - py)
    if distance == 0 or distance > max_range:
        return None
    dx = (px > mob.x) - (px < mob.x)
    dy = (py > mob.y) - (py < mob.y)
    for step in range(1, distance):
        if not state.grid.is_walkable(mob.x + dx * step, mob.y + dy * step):
            return None
    return direction_between((0, 0), (dx, dy))


def step_towards(
    state: GameState, mob: Mob, goal: Position, *, avoid_traps: bool = True
) -> Direction | None:
    """Premier pas du plus court chemin (BFS) vers `goal`, ou None si inaccessible."""
    start = mob.position
    if start == goal:
        return None
    first_step: dict[Position, Direction | None] = {start: None}
    queue: deque[Position] = deque([start])
    while queue:
        current = queue.popleft()
        for direction in DIRECTIONS:
            nxt = (current[0] + direction.dx, current[1] + direction.dy)
            if nxt in first_step:
                continue
            if nxt == goal:
                if not state.grid.is_walkable(*nxt):
                    continue
            elif not is_free_for_mob(state, *nxt, avoid_traps=avoid_traps):
                continue
            first_step[nxt] = direction if current == start else first_step[current]
            if nxt == goal:
                return first_step[nxt]
            queue.append(nxt)
    return None
