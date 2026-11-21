"""Ce que le bot voit : un dict 100 % JSON envoyé à chaque tick.

La grille contient la vérité ; l'observation, elle, peut « mentir » :
    - "?"  : case jamais vue (brouillard du niveau 3)
    - un piège caché non révélé est montré comme du sol "."
    - un mob dans la brume n'est visible qu'au contact
"""

from __future__ import annotations

from typing import Any

from wonderland.engine.events import (
    Event,
    MobCharging,
    MobMoved,
    MobSpawned,
    MobStunned,
    MobWindup,
)
from wonderland.engine.grid import Tile
from wonderland.engine.state import GameState
from wonderland.engine.vision import visible_cells

Position = tuple[int, int]

# Événements de mobs masqués quand le mob n'est pas visible (sinon fuite d'info dans le brouillard).
_MOB_EVENTS = (MobMoved, MobWindup, MobCharging, MobSpawned, MobStunned)


def observe(state: GameState) -> dict[str, Any]:
    visible = visible_cells(state)
    player = state.player

    def seen(pos: Position) -> bool:
        return visible is None or pos in visible

    def known(pos: Position) -> bool:
        return seen(pos) or pos in state.discovered

    def entity_visible(pos: Position) -> bool:
        if not seen(pos):
            return False
        in_mist = state.grid.get(*pos) is Tile.MIST
        distance = abs(pos[0] - player.x) + abs(pos[1] - player.y)
        return not in_mist or distance <= 1

    rows: list[str] = []
    for y in range(state.grid.height):
        row = []
        for x in range(state.grid.width):
            if not known((x, y)):
                row.append("?")
                continue
            tile = state.grid.get(x, y)
            trap = state.traps.get((x, y))
            if tile is Tile.TRAP and trap is not None and not trap.visible:
                tile = Tile.FLOOR
            row.append(tile.symbol)
        rows.append("".join(row))

    mobs = [
        {
            "id": mob.id,
            "kind": mob.kind,
            "x": mob.x,
            "y": mob.y,
            "hp": mob.hp,
            "max_hp": mob.max_hp,
            "facing": mob.facing.name,
            "state": mob.state.name,
            "state_ticks": mob.state_ticks,
            "boss": mob.is_boss,
        }
        for mob in state.sorted_mobs()
        if entity_visible(mob.position)
    ]
    visible_mob_ids = {m["id"] for m in mobs}

    items = [
        {"id": item.id, "kind": item.kind.name, "x": item.x, "y": item.y}
        for item in sorted(state.items.values(), key=lambda i: i.id)
        if entity_visible(item.position)
    ]

    traps = [
        {
            "x": trap.x,
            "y": trap.y,
            "active_this_turn": trap.is_active(state.tick),
            "next_active_in": trap.ticks_until_active(state.tick),
            "period": trap.period,
            "active_for": trap.active_for,
            "damage": trap.damage,
        }
        for pos, trap in sorted(state.traps.items())
        if trap.visible and known(pos)
    ]

    projectiles = [
        {
            "id": p.id,
            "x": p.x,
            "y": p.y,
            "direction": p.direction.name,
            "speed": p.speed,
            "hostile": not p.from_player,
            "kind": p.kind,
        }
        for p in sorted(state.projectiles.values(), key=lambda p: p.id)
        if entity_visible(p.position)
    ]

    return {
        "tick": state.tick,
        "status": state.status.name,
        "level": {
            "id": state.config.level_id,
            "name": state.config.name,
            "max_ticks": state.config.max_ticks,
            "ticks_left": state.config.max_ticks - state.tick,
            "vision_radius": state.config.vision_radius,
            "win_condition": state.config.win_condition,
        },
        "you": {
            "id": player.id,
            "x": player.x,
            "y": player.y,
            "hp": player.hp,
            "max_hp": player.max_hp,
            "facing": player.facing.name,
            "weapon": player.weapon.name,
            "shoot_cooldown": player.shoot_cooldown,
            "hats": len(player.hats),
        },
        "width": state.grid.width,
        "height": state.grid.height,
        "grid": rows,
        "mobs": mobs,
        "items": items,
        "traps": traps,
        "projectiles": projectiles,
        "events": [
            e.to_dict() for e in state.last_events if _event_visible(e, visible, visible_mob_ids)
        ],
    }


def _event_visible(event: Event, visible: set[Position] | None, mob_ids: set[int]) -> bool:
    if visible is None or not isinstance(event, _MOB_EVENTS):
        return True
    return event.mob_id in mob_ids
