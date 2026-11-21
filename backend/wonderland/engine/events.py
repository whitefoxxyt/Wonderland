"""Événements émis par le moteur.

Le moteur ne calcule ni score ni succès : il raconte ce qui s'est passé.
Les services (succès, score, diffusion, replays) écoutent ces événements.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class Event:
    @property
    def type(self) -> str:
        return type(self).__name__

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.type}
        for f in fields(self):
            value = getattr(self, f.name)
            data[f.name] = value.name if isinstance(value, Enum) else value
        return data


# ---------- actions du joueur ----------


@dataclass(frozen=True)
class PlayerMoved(Event):
    from_x: int
    from_y: int
    x: int
    y: int


@dataclass(frozen=True)
class PlayerBumped(Event):
    """Déplacement bloqué (mur, mob…). Le joueur s'est quand même tourné."""

    x: int
    y: int


@dataclass(frozen=True)
class PlayerWaited(Event):
    pass


@dataclass(frozen=True)
class PlayerParrying(Event):
    pass


@dataclass(frozen=True)
class InvalidAction(Event):
    reason: str  # "unknown_action" | "no_ranged_weapon" | "cooldown"


@dataclass(frozen=True)
class TimedOut(Event):
    pass


# ---------- combat ----------


@dataclass(frozen=True)
class AttackMissed(Event):
    attacker_id: int
    x: int
    y: int


@dataclass(frozen=True)
class DamageDealt(Event):
    source_id: int | None  # None = piège
    target_id: int
    amount: int
    cause: str  # "melee" | "projectile" | "trap" | "charge"
    hp_left: int


@dataclass(frozen=True)
class ParrySucceeded(Event):
    attacker_id: int
    kind: str  # "melee" | "projectile" | "charge"


@dataclass(frozen=True)
class ShotFired(Event):
    owner_id: int
    projectile_id: int
    x: int
    y: int
    direction: str


@dataclass(frozen=True)
class ProjectileEnded(Event):
    projectile_id: int
    x: int
    y: int
    reason: str  # "wall" | "range" | "hit" | "parried"


# ---------- mobs ----------


@dataclass(frozen=True)
class MobMoved(Event):
    mob_id: int
    x: int
    y: int


@dataclass(frozen=True)
class MobWindup(Event):
    mob_id: int
    direction: str


@dataclass(frozen=True)
class MobCharging(Event):
    mob_id: int
    direction: str


@dataclass(frozen=True)
class MobStunned(Event):
    mob_id: int
    ticks: int


@dataclass(frozen=True)
class MobSpawned(Event):
    mob_id: int
    kind: str
    x: int
    y: int


@dataclass(frozen=True)
class MobKilled(Event):
    mob_id: int
    kind: str
    killer_id: int | None
    cause: str


@dataclass(frozen=True)
class BossPhaseChanged(Event):
    mob_id: int
    phase: int


# ---------- monde ----------


@dataclass(frozen=True)
class TrapTriggered(Event):
    trap_id: int
    entity_id: int
    x: int
    y: int


@dataclass(frozen=True)
class TrapRevealed(Event):
    trap_id: int
    x: int
    y: int


@dataclass(frozen=True)
class ItemPicked(Event):
    item_id: int
    kind: str
    x: int
    y: int


@dataclass(frozen=True)
class PlayerHealed(Event):
    amount: int


@dataclass(frozen=True)
class WeaponAcquired(Event):
    weapon: str


# ---------- fin de partie ----------


@dataclass(frozen=True)
class PlayerDied(Event):
    cause: str
    killer_id: int | None


@dataclass(frozen=True)
class LevelCompleted(Event):
    level_id: int
    tick: int


@dataclass(frozen=True)
class LevelTimeout(Event):
    level_id: int
    tick: int
