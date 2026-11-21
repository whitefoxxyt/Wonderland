"""Tour des mobs : résolution des états (frappe, charge, étourdissement) puis décision de l'IA."""

from __future__ import annotations

from wonderland.engine.ai import get_brain
from wonderland.engine.ai.base import Charge, Intent, Move, Shoot, Wait, Windup
from wonderland.engine.entities import Mob, MobState
from wonderland.engine.events import (
    AttackMissed,
    Event,
    MobCharging,
    MobMoved,
    MobWindup,
    ParrySucceeded,
)
from wonderland.engine.rules import (
    CHARGE_DAMAGE,
    CHARGE_MAX_TURNS,
    CHARGE_SPEED,
    CHARGE_STUN_TICKS,
    MOB_STRIKE_COOLDOWN,
    PARRY_STUN_TICKS,
)
from wonderland.engine.state import GameState
from wonderland.engine.systems.combat import apply_damage, stun
from wonderland.engine.systems.projectiles import spawn_projectile


def run_mobs(state: GameState, events: list[Event]) -> None:
    for mob in state.sorted_mobs():
        if not state.running:
            return
        if mob.id not in state.mobs:  # tué plus tôt dans ce tick
            continue

        if mob.attack_cooldown > 0:
            mob.attack_cooldown -= 1

        # Les états en cours se résolvent à chaque tick, quelle que soit la vitesse du mob.
        if mob.state is MobState.STUNNED:
            mob.state_ticks -= 1
            if mob.state_ticks <= 0:
                mob.state = MobState.IDLE
            continue
        if mob.state is MobState.WINDUP:
            _strike(state, mob, events)
            continue
        if mob.state is MobState.CHARGING:
            _charge(state, mob, events)
            continue

        # Mobs lents : n'agissent qu'un tick sur `move_every`.
        if (state.tick + mob.id) % mob.move_every != 0:
            continue

        intent = get_brain(mob.brain).decide(state, mob, events)
        _apply_intent(state, mob, intent, events)


def _apply_intent(state: GameState, mob: Mob, intent: Intent, events: list[Event]) -> None:
    match intent:
        case Move(direction):
            mob.facing = direction
            nx, ny = mob.x + direction.dx, mob.y + direction.dy
            if state.is_free(nx, ny):
                mob.move_to(nx, ny)
                events.append(MobMoved(mob.id, nx, ny))
        case Windup(direction):
            mob.facing = direction
            mob.state = MobState.WINDUP
            events.append(MobWindup(mob.id, direction.name))
        case Shoot(direction, speed, max_range, cooldown, kind, damage):
            mob.facing = direction
            mob.attack_cooldown = cooldown
            spawn_projectile(
                state,
                mob,
                direction,
                from_player=False,
                damage=damage,
                speed=speed,
                max_range=max_range,
                kind=kind,
                events=events,
            )
        case Charge(direction):
            mob.facing = direction
            mob.state = MobState.CHARGING
            mob.state_ticks = CHARGE_MAX_TURNS
            events.append(MobCharging(mob.id, direction.name))
        case Wait():
            pass


def _strike(state: GameState, mob: Mob, events: list[Event]) -> None:
    """Le coup armé au tick précédent part dans la direction où le mob regarde."""
    mob.state = MobState.IDLE
    mob.attack_cooldown = MOB_STRIKE_COOLDOWN
    tx, ty = mob.front()
    player = state.player
    if player.position != (tx, ty):
        events.append(AttackMissed(mob.id, tx, ty))
        return
    if player.parrying:
        events.append(ParrySucceeded(mob.id, "melee"))
        if not mob.is_boss:  # la Reine encaisse la parade sans être étourdie
            stun(mob, PARRY_STUN_TICKS, events)
        return
    apply_damage(state, player, mob.damage, source_id=mob.id, cause="melee", events=events)


def _charge(state: GameState, mob: Mob, events: list[Event]) -> None:
    """Fonce de CHARGE_SPEED cases ; s'arrête sur le joueur, un obstacle ou un piège actif."""
    for _ in range(CHARGE_SPEED):
        nx, ny = mob.front()
        player = state.player
        if player.position == (nx, ny):
            if player.parrying:
                events.append(ParrySucceeded(mob.id, "charge"))
                stun(mob, CHARGE_STUN_TICKS, events)
            else:
                apply_damage(
                    state, player, CHARGE_DAMAGE, source_id=mob.id, cause="charge", events=events
                )
                mob.state = MobState.IDLE
                mob.attack_cooldown = CHARGE_STUN_TICKS
            return
        if not state.is_free(nx, ny):
            stun(mob, CHARGE_STUN_TICKS, events)  # percute un mur / un pilier / un mob
            return
        mob.move_to(nx, ny)
        events.append(MobMoved(mob.id, nx, ny))
        trap = state.traps.get((nx, ny))
        if trap is not None and trap.is_active(state.tick):
            stun(mob, CHARGE_STUN_TICKS, events)  # le piège fera ses dégâts dans la phase pièges
            return

    mob.state_ticks -= 1
    if mob.state_ticks <= 0:
        mob.state = MobState.IDLE
        mob.attack_cooldown = MOB_STRIKE_COOLDOWN
