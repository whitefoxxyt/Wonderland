"""Application de l'action du joueur.

Règle importante : un déplacement bloqué (mur, mob) TOURNE quand même le joueur.
C'est la seule façon de viser un mob adjacent avant ATTACK ou SHOOT.
"""

from __future__ import annotations

from wonderland.engine.actions import Action, Direction
from wonderland.engine.entities import Weapon
from wonderland.engine.events import (
    AttackMissed,
    Event,
    InvalidAction,
    PlayerBumped,
    PlayerMoved,
    PlayerParrying,
    PlayerWaited,
)
from wonderland.engine.rules import (
    KNIFE_DAMAGE,
    LAUNCHER_COOLDOWN,
    LAUNCHER_DAMAGE,
    LAUNCHER_RANGE,
    LAUNCHER_SPEED,
)
from wonderland.engine.state import GameState
from wonderland.engine.systems.combat import apply_damage
from wonderland.engine.systems.projectiles import spawn_projectile
from wonderland.engine.systems.traps import reveal_near_player


def apply_player_action(state: GameState, action: Action, events: list[Event]) -> None:
    if action.direction is not None:
        _move(state, action.direction, events)
    elif action is Action.ATTACK:
        _attack(state, events)
    elif action is Action.SHOOT:
        _shoot(state, events)
    elif action is Action.PARRY:
        state.player.parrying = True
        events.append(PlayerParrying())
    else:
        events.append(PlayerWaited())


def _move(state: GameState, direction: Direction, events: list[Event]) -> None:
    player = state.player
    player.facing = direction
    nx, ny = player.x + direction.dx, player.y + direction.dy
    if not state.is_free(nx, ny):
        events.append(PlayerBumped(nx, ny))
        return
    from_x, from_y = player.position
    player.move_to(nx, ny)
    events.append(PlayerMoved(from_x, from_y, nx, ny))
    reveal_near_player(state, events)


def _attack(state: GameState, events: list[Event]) -> None:
    player = state.player
    tx, ty = player.front()
    target = state.mob_at(tx, ty)
    if target is None:
        events.append(AttackMissed(player.id, tx, ty))
        return
    apply_damage(state, target, KNIFE_DAMAGE, source_id=player.id, cause="melee", events=events)


def _shoot(state: GameState, events: list[Event]) -> None:
    player = state.player
    if player.weapon is not Weapon.SUGAR_LAUNCHER:
        events.append(InvalidAction("no_ranged_weapon"))
        return
    if player.shoot_cooldown > 0:
        events.append(InvalidAction("cooldown"))
        return
    player.shoot_cooldown = LAUNCHER_COOLDOWN
    spawn_projectile(
        state,
        player,
        player.facing,
        from_player=True,
        damage=LAUNCHER_DAMAGE,
        speed=LAUNCHER_SPEED,
        max_range=LAUNCHER_RANGE,
        kind="sugar",
        events=events,
    )
