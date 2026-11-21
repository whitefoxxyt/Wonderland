"""Ligne de vue et brouillard de guerre."""

from __future__ import annotations

from collections.abc import Iterator

from wonderland.engine.grid import Grid
from wonderland.engine.state import GameState

Position = tuple[int, int]


def line_cells(a: Position, b: Position) -> Iterator[Position]:
    """Cases traversées par le segment a → b (algorithme de Bresenham), extrémités incluses."""
    x0, y0 = a
    x1, y1 = b
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        yield x0, y0
        if (x0, y0) == (x1, y1):
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def line_of_sight(grid: Grid, a: Position, b: Position) -> bool:
    """Vrai si aucune case ENTRE a et b ne bloque la vue (murs, brume).

    Les extrémités ne comptent pas : on voit le mur qu'on regarde,
    et on voit la première case de brume (mais pas au-delà).
    """
    cells = list(line_cells(a, b))
    return not any(grid.blocks_vision(x, y) for x, y in cells[1:-1])


def visible_cells(state: GameState) -> set[Position] | None:
    """Cases visibles par le joueur, ou None si le niveau est en vision totale."""
    radius = state.config.vision_radius
    if radius is None:
        return None
    px, py = state.player.position
    visible: set[Position] = set()
    for y in range(py - radius, py + radius + 1):
        for x in range(px - radius, px + radius + 1):
            if not state.grid.in_bounds(x, y):
                continue
            if (x - px) ** 2 + (y - py) ** 2 > radius * radius + radius:
                continue
            if line_of_sight(state.grid, (px, py), (x, y)):
                visible.add((x, y))
    return visible


def update_discovered(state: GameState) -> None:
    """Mémorise le terrain déjà vu (le bot garde la carte des zones explorées)."""
    visible = visible_cells(state)
    if visible is not None:
        state.discovered |= visible
