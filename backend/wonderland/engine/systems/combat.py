"""Application des dégâts et conséquences (mort, victoire contre le boss)."""

from __future__ import annotations

from wonderland.engine.entities import Entity, Mob, MobState
from wonderland.engine.events import (
    DamageDealt,
    Event,
    LevelCompleted,
    MobKilled,
    MobStunned,
    PlayerDied,
)
from wonderland.engine.state import GameState, Status


def apply_damage(
    state: GameState,
    target: Entity,
    amount: int,
    *,
    source_id: int | None,
    cause: str,
    events: list[Event],
) -> int:
    """Inflige des dégâts à `target` et gère sa mort. Renvoie les dégâts réellement infligés.

    C'est le SEUL endroit où une entité perd des PV : toutes les sources
    (couteau, projectile, piège, charge) passent par ici.
    """
    if amount <= 0 or not target.alive:
        return 0

    dealt = target.take_damage(amount)
    events.append(DamageDealt(source_id, target.id, dealt, cause, target.hp))
    if target.alive:
        return dealt

    if target is state.player:
        events.append(PlayerDied(cause, source_id))
        state.status = Status.DEAD
        return dealt

    assert isinstance(target, Mob)
    state.mobs.pop(target.id, None)
    events.append(MobKilled(target.id, target.kind, source_id, cause))
    if target.is_boss and state.config.win_condition == "boss" and state.running:
        state.status = Status.WON
        events.append(LevelCompleted(state.config.level_id, state.tick))
    return dealt


def stun(mob: Mob, ticks: int, events: list[Event]) -> None:
    mob.state = MobState.STUNNED
    mob.state_ticks = ticks
    events.append(MobStunned(mob.id, ticks))
