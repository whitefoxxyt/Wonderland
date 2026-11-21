"""Entités : tout ce qui occupe une position sur la grille et peut changer pendant une partie.

On ne met ici que des DONNÉES et des petites méthodes sans règle de jeu.
Les règles (parade, pièges, dégâts…) vivent dans engine/systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from wonderland.engine.actions import Direction


class Weapon(Enum):
    KNIFE = "KNIFE"
    SUGAR_LAUNCHER = "SUGAR_LAUNCHER"


class MobState(Enum):
    """État lisible par le bot : c'est ce qui rend le combat « algorithmique »."""

    IDLE = "IDLE"
    WINDUP = "WINDUP"  # frappera au prochain tick → c'est le moment de parer
    CHARGING = "CHARGING"  # (Reine) fonce en ligne droite
    STUNNED = "STUNNED"  # ne fait rien pendant state_ticks ticks


class ItemKind(Enum):
    HAT = "HAT"
    POTION = "POTION"
    LAUNCHER = "LAUNCHER"


@dataclass
class Entity:
    id: int
    x: int
    y: int
    hp: int
    max_hp: int
    facing: Direction = Direction.DOWN

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def position(self) -> tuple[int, int]:
        return self.x, self.y

    def move_to(self, x: int, y: int) -> None:
        self.x, self.y = x, y

    def front(self) -> tuple[int, int]:
        """Case juste devant l'entité."""
        return self.x + self.facing.dx, self.y + self.facing.dy

    def distance_to(self, other: Entity) -> int:
        """Distance de Manhattan (déplacements en 4 directions)."""
        return abs(self.x - other.x) + abs(self.y - other.y)

    def take_damage(self, amount: int) -> int:
        """Applique des dégâts et renvoie les dégâts réellement subis (jamais sous 0 PV)."""
        if amount < 0:
            raise ValueError("amount doit être >= 0")
        dealt = min(amount, self.hp)
        self.hp -= dealt
        return dealt

    def heal(self, amount: int) -> int:
        """Soigne sans dépasser max_hp et renvoie les PV réellement rendus."""
        if amount < 0:
            raise ValueError("amount doit être >= 0")
        healed = min(amount, self.max_hp - self.hp)
        self.hp += healed
        return healed


@dataclass
class Player(Entity):
    weapon: Weapon = Weapon.KNIFE
    shoot_cooldown: int = 0
    parrying: bool = False  # vrai uniquement pendant le tick où PARRY est joué
    hats: set[int] = field(default_factory=set)  # ids des chapeaux ramassés


@dataclass
class Mob(Entity):
    kind: str = "generic"
    brain: str = "idle"
    damage: int = 1
    sight: int = 5
    move_every: int = 1
    is_boss: bool = False
    state: MobState = MobState.IDLE
    state_ticks: int = 0  # ticks restants dans l'état courant (stun, charge)
    attack_cooldown: int = 0
    patrol_dir: Direction | None = None
    memory: dict[str, Any] = field(default_factory=dict)  # mémoire libre pour l'IA


@dataclass
class Item:
    id: int
    x: int
    y: int
    kind: ItemKind

    @property
    def position(self) -> tuple[int, int]:
        return self.x, self.y


@dataclass
class Trap:
    """État dynamique d'une case TRAP de la grille.

    Un piège est actif pendant `active_for` ticks tous les `period` ticks,
    décalé de `offset`. period=1 → toujours actif.
    """

    id: int
    x: int
    y: int
    hidden: bool = False
    revealed: bool = False
    period: int = 1
    active_for: int = 1
    offset: int = 0
    damage: int = 1

    @property
    def position(self) -> tuple[int, int]:
        return self.x, self.y

    @property
    def visible(self) -> bool:
        return not self.hidden or self.revealed

    def is_active(self, tick: int) -> bool:
        return (tick + self.offset) % self.period < self.active_for

    def ticks_until_active(self, tick: int) -> int:
        for delay in range(self.period):
            if self.is_active(tick + delay):
                return delay
        return 0


@dataclass
class Projectile:
    id: int
    x: int
    y: int
    direction: Direction
    owner_id: int
    from_player: bool
    damage: int = 1
    speed: int = 1
    range_left: int = 6
    kind: str = "sugar"

    @property
    def position(self) -> tuple[int, int]:
        return self.x, self.y
