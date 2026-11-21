"""État complet d'une partie sur un niveau.

GameState contient TOUT ce qu'il faut pour reprendre une partie :
deux états identiques + les mêmes actions = la même suite d'événements.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from wonderland.engine.actions import Direction
from wonderland.engine.entities import Item, Mob, Player, Projectile, Trap
from wonderland.engine.events import Event
from wonderland.engine.grid import Grid
from wonderland.engine.rules import MOB_TYPES


class Status(Enum):
    RUNNING = "RUNNING"
    WON = "WON"
    DEAD = "DEAD"
    TIMEOUT = "TIMEOUT"


@dataclass
class LevelConfig:
    level_id: int
    name: str
    max_ticks: int
    vision_radius: int | None = None  # None = vision totale
    win_condition: str = "exit"  # "exit" | "boss"


@dataclass
class GameState:
    config: LevelConfig
    grid: Grid
    player: Player
    seed: int
    rng: random.Random
    mobs: dict[int, Mob] = field(default_factory=dict)
    items: dict[int, Item] = field(default_factory=dict)
    traps: dict[tuple[int, int], Trap] = field(default_factory=dict)
    projectiles: dict[int, Projectile] = field(default_factory=dict)
    tick: int = 0
    status: Status = Status.RUNNING
    discovered: set[tuple[int, int]] = field(default_factory=set)
    last_events: list[Event] = field(default_factory=list)
    _next_id: int = 2  # 1 est réservé au joueur

    # ---------- identifiants ----------

    def new_id(self) -> int:
        value = self._next_id
        self._next_id += 1
        return value

    # ---------- requêtes ----------

    @property
    def running(self) -> bool:
        return self.status is Status.RUNNING

    def sorted_mobs(self) -> list[Mob]:
        """Mobs dans un ordre stable (par id) : indispensable au déterminisme."""
        return [self.mobs[mob_id] for mob_id in sorted(self.mobs)]

    def mob_at(self, x: int, y: int) -> Mob | None:
        for mob in self.mobs.values():
            if mob.x == x and mob.y == y:
                return mob
        return None

    def item_at(self, x: int, y: int) -> Item | None:
        for item in self.items.values():
            if item.x == x and item.y == y:
                return item
        return None

    def is_occupied(self, x: int, y: int) -> bool:
        return self.player.position == (x, y) or self.mob_at(x, y) is not None

    def is_free(self, x: int, y: int) -> bool:
        """Case praticable et inoccupée."""
        return self.grid.is_walkable(x, y) and not self.is_occupied(x, y)

    def boss(self) -> Mob | None:
        for mob in self.sorted_mobs():
            if mob.is_boss:
                return mob
        return None

    # ---------- fabrique ----------

    def add_mob(self, kind: str, x: int, y: int, **overrides: Any) -> Mob:
        if kind not in MOB_TYPES:
            raise ValueError(f"Type de mob inconnu : {kind!r}")
        stats = {**MOB_TYPES[kind], **overrides}
        hp = stats.pop("hp")
        facing = stats.pop("facing", Direction.DOWN)
        mob = Mob(id=self.new_id(), x=x, y=y, hp=hp, max_hp=hp, facing=facing, kind=kind, **stats)
        self.mobs[mob.id] = mob
        return mob
