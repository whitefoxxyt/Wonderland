"""Image (frame) d'une partie pour les spectateurs.

Contrairement à l'observation du bot, le spectateur voit TOUT : pièges cachés,
mobs dans la brume… Le rayon de vision du joueur est fourni pour dessiner le brouillard.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from wonderland.engine.events import Event
from wonderland.engine.grid import Tile
from wonderland.engine.state import GameState

Position = tuple[int, int]


def state_frame(state: GameState, events: list[Event] | None = None) -> dict[str, Any]:
    player = state.player
    return {
        "level": state.config.level_id,
        "level_name": state.config.name,
        "tick": state.tick,
        "max_ticks": state.config.max_ticks,
        "status": state.status.name,
        "vision_radius": state.config.vision_radius,
        "grid": state.grid.to_lines(),
        "player": {
            "x": player.x,
            "y": player.y,
            "hp": player.hp,
            "max_hp": player.max_hp,
            "facing": player.facing.name,
            "weapon": player.weapon.name,
            "parrying": player.parrying,
            "hats": len(player.hats),
        },
        "mobs": [
            {
                "id": m.id,
                "kind": m.kind,
                "x": m.x,
                "y": m.y,
                "hp": m.hp,
                "max_hp": m.max_hp,
                "facing": m.facing.name,
                "state": m.state.name,
                "boss": m.is_boss,
            }
            for m in state.sorted_mobs()
        ],
        "items": [
            {"id": i.id, "kind": i.kind.name, "x": i.x, "y": i.y}
            for i in sorted(state.items.values(), key=lambda i: i.id)
        ],
        "traps": [
            {"x": t.x, "y": t.y, "hidden": not t.visible, "active": t.is_active(state.tick)}
            for _, t in sorted(state.traps.items())
        ],
        "projectiles": [
            {"id": p.id, "x": p.x, "y": p.y, "direction": p.direction.name, "kind": p.kind}
            for p in sorted(state.projectiles.values(), key=lambda p: p.id)
        ],
        "events": [e.to_dict() for e in (events if events is not None else state.last_events)],
    }


def distance_to_exit(state: GameState) -> int | None:
    """Plus court chemin (BFS, murs seulement) du joueur vers la sortie la plus proche."""
    exits = set(state.grid.find(Tile.EXIT))
    if not exits:
        return None
    start = state.player.position
    seen = {start}
    queue: deque[tuple[Position, int]] = deque([(start, 0)])
    while queue:
        (x, y), dist = queue.popleft()
        if (x, y) in exits:
            return dist
        for nxt in state.grid.neighbors(x, y):
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, dist + 1))
    return None


def level_progress(state: GameState, start_distance: int | None) -> float:
    """Avancement dans le niveau, entre 0 et 1 (sert à choisir la partie mise en avant)."""
    if state.config.win_condition == "boss":
        boss = state.boss()
        return 1.0 if boss is None else 1 - boss.hp / boss.max_hp
    distance = distance_to_exit(state)
    if distance is None or not start_distance:
        return 0.0
    return max(0.0, min(1.0, 1 - distance / start_distance))
