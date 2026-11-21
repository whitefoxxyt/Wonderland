"""Pièges : révélation des pièges cachés et dégâts sur les pièges actifs."""

from __future__ import annotations

from wonderland.engine.entities import Entity, Mob
from wonderland.engine.events import Event, TrapRevealed, TrapTriggered
from wonderland.engine.rules import BOSS_TRAP_MULTIPLIER, TRAP_REVEAL_RADIUS
from wonderland.engine.state import GameState
from wonderland.engine.systems.combat import apply_damage


def reveal_near_player(state: GameState, events: list[Event]) -> None:
    """Révèle les pièges cachés à distance <= TRAP_REVEAL_RADIUS du joueur."""
    px, py = state.player.position
    for pos in sorted(state.traps):
        trap = state.traps[pos]
        if trap.visible:
            continue
        if abs(trap.x - px) + abs(trap.y - py) <= TRAP_REVEAL_RADIUS:
            trap.revealed = True
            events.append(TrapRevealed(trap.id, trap.x, trap.y))


def update_traps(state: GameState, events: list[Event]) -> None:
    """Chaque piège actif ce tick blesse l'entité qui se tient dessus (joueur ET mobs)."""
    for pos in sorted(state.traps):
        trap = state.traps[pos]
        if not trap.is_active(state.tick):
            continue

        victims: list[Entity] = []
        if state.player.position == pos:
            victims.append(state.player)
        mob = state.mob_at(*pos)
        if mob is not None:
            victims.append(mob)

        for victim in victims:
            if not trap.visible:
                trap.revealed = True
                events.append(TrapRevealed(trap.id, trap.x, trap.y))
            events.append(TrapTriggered(trap.id, victim.id, trap.x, trap.y))
            damage = trap.damage
            if isinstance(victim, Mob) and victim.is_boss:
                damage *= BOSS_TRAP_MULTIPLIER
            apply_damage(state, victim, damage, source_id=None, cause="trap", events=events)
            if not state.running:
                return
