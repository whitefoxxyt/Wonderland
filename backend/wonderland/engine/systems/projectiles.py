"""Projectiles : création, déplacement, collisions.

Les projectiles du joueur touchent les mobs ; ceux des mobs ne touchent que le joueur
(ils traversent les autres mobs). Un joueur qui pare détruit le projectile.
"""

from __future__ import annotations

from wonderland.engine.actions import Direction
from wonderland.engine.entities import Entity, Projectile
from wonderland.engine.events import Event, ParrySucceeded, ProjectileEnded, ShotFired
from wonderland.engine.grid import Tile
from wonderland.engine.state import GameState
from wonderland.engine.systems.combat import apply_damage


def spawn_projectile(
    state: GameState,
    owner: Entity,
    direction: Direction,
    *,
    from_player: bool,
    damage: int,
    speed: int,
    max_range: int,
    kind: str,
    events: list[Event],
) -> Projectile:
    projectile = Projectile(
        id=state.new_id(),
        x=owner.x,
        y=owner.y,
        direction=direction,
        owner_id=owner.id,
        from_player=from_player,
        damage=damage,
        speed=speed,
        range_left=max_range,
        kind=kind,
    )
    state.projectiles[projectile.id] = projectile
    events.append(ShotFired(owner.id, projectile.id, owner.x, owner.y, direction.name))
    return projectile


def advance_projectiles(state: GameState, events: list[Event]) -> None:
    for projectile_id in sorted(state.projectiles):
        projectile = state.projectiles.get(projectile_id)
        if projectile is None:
            continue
        # Le joueur a pu marcher sur le projectile pendant son action (croisement).
        if _resolve_hit(state, projectile, events):
            continue
        for _ in range(projectile.speed):
            nx = projectile.x + projectile.direction.dx
            ny = projectile.y + projectile.direction.dy
            if not state.grid.in_bounds(nx, ny) or state.grid.get(nx, ny) is Tile.WALL:
                _end(state, projectile, "wall", events)
                break
            projectile.x, projectile.y = nx, ny
            projectile.range_left -= 1
            if _resolve_hit(state, projectile, events):
                break
            if projectile.range_left <= 0:
                _end(state, projectile, "range", events)
                break
        if not state.running:
            return


def _resolve_hit(state: GameState, projectile: Projectile, events: list[Event]) -> bool:
    x, y = projectile.position
    if projectile.from_player:
        target = state.mob_at(x, y)
        if target is None:
            return False
        _end(state, projectile, "hit", events)
        apply_damage(
            state,
            target,
            projectile.damage,
            source_id=projectile.owner_id,
            cause="projectile",
            events=events,
        )
        return True

    player = state.player
    if player.position != (x, y) or projectile.owner_id == player.id:
        return False
    if player.parrying:
        events.append(ParrySucceeded(projectile.owner_id, "projectile"))
        _end(state, projectile, "parried", events)
        return True
    _end(state, projectile, "hit", events)
    apply_damage(
        state,
        player,
        projectile.damage,
        source_id=projectile.owner_id,
        cause="projectile",
        events=events,
    )
    return True


def _end(state: GameState, projectile: Projectile, reason: str, events: list[Event]) -> None:
    state.projectiles.pop(projectile.id, None)
    events.append(ProjectileEnded(projectile.id, projectile.x, projectile.y, reason))
