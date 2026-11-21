"""Rendu ASCII d'une partie (debug, runner local, logs). Montre TOUT, brouillard compris."""

from __future__ import annotations

from wonderland.engine.entities import ItemKind
from wonderland.engine.grid import Tile
from wonderland.engine.state import GameState

MOB_SYMBOLS = {
    "dormouse": "d",
    "march_hare": "h",
    "card_guard": "G",
    "card_archer": "A",
    "queen": "Q",
}
ITEM_SYMBOLS = {ItemKind.HAT: "H", ItemKind.POTION: "+", ItemKind.LAUNCHER: "L"}
PLAYER_SYMBOLS = {"UP": "▲", "DOWN": "▼", "LEFT": "◀", "RIGHT": "▶"}


def render(state: GameState) -> str:
    cells = [list(line) for line in state.grid.to_lines()]
    for (x, y), trap in state.traps.items():
        cells[y][x] = Tile.TRAP.symbol if trap.visible else "_"
    for item in state.items.values():
        cells[item.y][item.x] = ITEM_SYMBOLS[item.kind]
    for projectile in state.projectiles.values():
        cells[projectile.y][projectile.x] = "*"
    for mob in state.mobs.values():
        cells[mob.y][mob.x] = MOB_SYMBOLS.get(mob.kind, "m")
    player = state.player
    cells[player.y][player.x] = PLAYER_SYMBOLS[player.facing.name]

    header = (
        f"[{state.config.name}] tick {state.tick}/{state.config.max_ticks}"
        f"  PV {player.hp}/{player.max_hp}  arme {player.weapon.name}"
        f"  chapeaux {len(player.hats)}  {state.status.name}"
    )
    mob_lines = [
        f"  {MOB_SYMBOLS.get(m.kind, 'm')}#{m.id} {m.kind} PV {m.hp}/{m.max_hp} {m.state.name}"
        for m in state.sorted_mobs()
    ]
    return "\n".join([header, *("".join(row) for row in cells), *mob_lines])
