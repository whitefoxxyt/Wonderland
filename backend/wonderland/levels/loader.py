"""Chargement d'un niveau depuis un fichier JSON (carte ASCII + paramètres).

Légende de la carte :
    Terrain : #  mur      .  sol     ~  brume    E  sortie
              ^  piège visible       _  piège caché
    Spawns  : S  départ du joueur (exactement un)
              H  chapeau   +  potion   L  lance-sucres
              d  loir      h  lièvre de mars
              G  garde-carte (patrouille horizontale)   V  garde-carte (verticale)
              A  carte-archère        Q  Reine de Cœur

Format JSON :
{
  "id": 1, "name": "...", "max_ticks": 300,
  "vision_radius": null,            # entier = brouillard
  "win": "exit",                    # "exit" ou "boss"
  "start_weapon": "KNIFE",          # ou "SUGAR_LAUNCHER"
  "traps": {"period": 1, "active_for": 1, "damage": 1, "random_offsets": false},
  "random_hidden_traps": 0,         # pièges cachés ajoutés au hasard (selon la graine)
  "map": ["####...", ...]
}
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from wonderland.engine.actions import Direction
from wonderland.engine.entities import Item, ItemKind, Player, Trap, Weapon
from wonderland.engine.grid import Grid, Tile
from wonderland.engine.rules import PLAYER_MAX_HP
from wonderland.engine.state import GameState, LevelConfig
from wonderland.engine.vision import update_discovered

DATA_DIR = Path(__file__).parent / "data"

TERRAIN = {
    "#": Tile.WALL,
    ".": Tile.FLOOR,
    "~": Tile.MIST,
    "E": Tile.EXIT,
    "^": Tile.TRAP,
    "_": Tile.TRAP,
}
ITEMS = {"H": ItemKind.HAT, "+": ItemKind.POTION, "L": ItemKind.LAUNCHER}
MOBS: dict[str, tuple[str, dict[str, Any]]] = {
    "d": ("dormouse", {}),
    "h": ("march_hare", {}),
    "G": ("card_guard", {"patrol_dir": Direction.RIGHT}),
    "V": ("card_guard", {"patrol_dir": Direction.DOWN}),
    "A": ("card_archer", {}),
    "Q": ("queen", {}),
}
MIN_RANDOM_TRAP_DISTANCE = 3


class LevelError(ValueError):
    """Fichier de niveau invalide."""


def level_path(level: int | str | Path) -> Path:
    if isinstance(level, int):
        return DATA_DIR / f"level{level}.json"
    return Path(level)


def available_levels() -> list[int]:
    return sorted(int(p.stem.removeprefix("level")) for p in DATA_DIR.glob("level*.json"))


def level_data(level: int | str | Path) -> dict[str, Any]:
    """Contenu brut du fichier JSON d'un niveau."""
    with level_path(level).open(encoding="utf-8") as f:
        return json.load(f)


def level_summary(level: int) -> dict[str, Any]:
    """Infos fixes d'un niveau, utiles aux services (score, succès) et à l'API."""
    data = level_data(level)
    state = parse_level(data, seed=0)
    return {
        "id": level,
        "name": data["name"],
        "max_ticks": data["max_ticks"],
        "par_ticks": data.get("par_ticks", data["max_ticks"]),
        "vision_radius": data.get("vision_radius"),
        "win": data.get("win", "exit"),
        "hats": [item.position for item in state.items.values() if item.kind is ItemKind.HAT],
        "mobs": len(state.mobs),
    }


def load_level(level: int | str | Path, seed: int | None = None) -> GameState:
    """Charge un niveau par numéro (1..5) ou par chemin de fichier."""
    return parse_level(level_data(level), seed)


def parse_level(data: dict[str, Any], seed: int | None = None) -> GameState:
    if seed is None:
        seed = random.randrange(2**31)
    rng = random.Random(seed)
    lines: list[str] = data["map"]

    # 1. Terrain : chaque marqueur d'entité devient du sol.
    terrain = [[TERRAIN.get(char, Tile.FLOOR) for char in line] for line in lines]
    grid = Grid(terrain)

    starts = [(x, y) for y, line in enumerate(lines) for x, c in enumerate(line) if c == "S"]
    if len(starts) != 1:
        raise LevelError(f"Il faut exactement un 'S', trouvé {len(starts)}")
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char not in TERRAIN and char not in ITEMS and char not in MOBS and char != "S":
                raise LevelError(f"Caractère inconnu {char!r} en ({x}, {y})")

    config = LevelConfig(
        level_id=int(data["id"]),
        name=data["name"],
        max_ticks=int(data["max_ticks"]),
        vision_radius=data.get("vision_radius"),
        win_condition=data.get("win", "exit"),
    )
    sx, sy = starts[0]
    player = Player(
        id=1,
        x=sx,
        y=sy,
        hp=PLAYER_MAX_HP,
        max_hp=PLAYER_MAX_HP,
        weapon=Weapon[data.get("start_weapon", "KNIFE")],
    )
    state = GameState(config=config, grid=grid, player=player, seed=seed, rng=rng)

    # 2. Entités, dans l'ordre de lecture (ids stables).
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char in ITEMS:
                item = Item(state.new_id(), x, y, ITEMS[char])
                state.items[item.id] = item
            elif char in MOBS:
                kind, overrides = MOBS[char]
                state.add_mob(kind, x, y, **overrides)

    # 3. Pièges.
    trap_cfg = data.get("traps", {})
    hidden_chars = {(x, y) for y, line in enumerate(lines) for x, c in enumerate(line) if c == "_"}
    for x, y, tile in grid:
        if tile is Tile.TRAP:
            _add_trap(state, x, y, hidden=(x, y) in hidden_chars, cfg=trap_cfg)
    _add_random_hidden_traps(state, int(data.get("random_hidden_traps", 0)), trap_cfg)

    _validate(state)
    update_discovered(state)
    return state


def _add_trap(state: GameState, x: int, y: int, *, hidden: bool, cfg: dict[str, Any]) -> None:
    period = int(cfg.get("period", 1))
    offset = state.rng.randrange(period) if cfg.get("random_offsets") else int(cfg.get("offset", 0))
    state.traps[(x, y)] = Trap(
        id=state.new_id(),
        x=x,
        y=y,
        hidden=hidden,
        period=period,
        active_for=int(cfg.get("active_for", 1)),
        offset=offset,
        damage=int(cfg.get("damage", 1)),
    )


def _add_random_hidden_traps(state: GameState, count: int, cfg: dict[str, Any]) -> None:
    if count <= 0:
        return
    px, py = state.player.position
    candidates = [
        (x, y)
        for x, y, tile in state.grid
        if tile is Tile.FLOOR
        and abs(x - px) + abs(y - py) >= MIN_RANDOM_TRAP_DISTANCE
        and not state.is_occupied(x, y)
        and state.item_at(x, y) is None
    ]
    for x, y in state.rng.sample(candidates, min(count, len(candidates))):
        state.grid.set(x, y, Tile.TRAP)
        _add_trap(state, x, y, hidden=True, cfg=cfg)


def _validate(state: GameState) -> None:
    if state.config.win_condition == "exit" and not state.grid.find(Tile.EXIT):
        raise LevelError("Niveau 'exit' sans case E")
    if state.config.win_condition == "boss" and state.boss() is None:
        raise LevelError("Niveau 'boss' sans boss (Q)")
    if state.config.win_condition not in ("exit", "boss"):
        raise LevelError(f"Condition de victoire inconnue : {state.config.win_condition!r}")
