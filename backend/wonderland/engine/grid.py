"""Grille logique d'un niveau.

La grille ne décrit que le TERRAIN (ce qui ne bouge pas).
Le joueur, les mobs, les objets et l'état dynamique des pièges
(actif / inactif, cooldown) vivent dans GameState, pas ici.
Le visuel (pixel art, variantes de tuiles) est géré par le front.
"""

from collections.abc import Iterator
from enum import Enum

# Les 4 voisins orthogonaux (dx, dy). y augmente vers le bas.
_NEIGHBOR_OFFSETS: tuple[tuple[int, int], ...] = ((0, -1), (0, 1), (-1, 0), (1, 0))


class Tile(Enum):
    """Type de case. La valeur est le caractère utilisé dans les cartes ASCII."""

    WALL = "#"
    FLOOR = "."
    TRAP = "^"
    MIST = "~"
    EXIT = "E"

    @property
    def symbol(self) -> str:
        return self.value

    @property
    def walkable(self) -> bool:
        """Peut-on se tenir sur cette case ?"""
        return self is not Tile.WALL

    @property
    def blocks_vision(self) -> bool:
        """Bloque la ligne de vue (utile pour le brouillard du niveau 3)."""
        return self in (Tile.WALL, Tile.MIST)

    @property
    def dangerous(self) -> bool:
        """Peut infliger des dégâts à l'entité qui s'y trouve."""
        return self is Tile.TRAP


class Grid:
    """Carte rectangulaire de Tile, indexée en (x, y) avec (0, 0) en haut à gauche."""

    def __init__(self, tiles: list[list[Tile]]) -> None:
        if not tiles or not tiles[0]:
            raise ValueError("Grid vide")
        width = len(tiles[0])
        for y, row in enumerate(tiles):
            if len(row) != width:
                raise ValueError(
                    f"Ligne {y} de longueur {len(row)}, attendu {width}"
                )

        self._tiles = tiles
        self.width = width
        self.height = len(tiles)

    # ---------- construction / export ----------

    @classmethod
    def from_lines(cls, lines: list[str]) -> "Grid":
        """Construit une grille depuis des lignes ASCII. Lève ValueError si caractère inconnu."""
        tiles: list[list[Tile]] = []
        for y, line in enumerate(lines):
            row: list[Tile] = []
            for x, char in enumerate(line):
                try:
                    row.append(Tile(char))
                except ValueError:
                    raise ValueError(
                        f"Caractère inconnu {char!r} en ({x}, {y})"
                    ) from None
            tiles.append(row)
        return cls(tiles)

    def to_lines(self) -> list[str]:
        return ["".join(tile.symbol for tile in row) for row in self._tiles]

    def copy(self) -> "Grid":
        """Copie indépendante (pour rejouer un niveau sans modifier l'original)."""
        return Grid([row.copy() for row in self._tiles])

    # ---------- accès ----------

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get(self, x: int, y: int) -> Tile:
        self._check_bounds(x, y)
        return self._tiles[y][x]  # ligne (y) puis colonne (x) : SEUL endroit du projet

    def set(self, x: int, y: int, tile: Tile) -> None:
        self._check_bounds(x, y)
        self._tiles[y][x] = tile

    # ---------- requêtes ----------

    def is_walkable(self, x: int, y: int) -> bool:
        """False hors grille : on ne sort jamais de la carte."""
        return self.in_bounds(x, y) and self.get(x, y).walkable

    def blocks_vision(self, x: int, y: int) -> bool:
        """True hors grille : on ne voit pas au-delà des bords."""
        return not self.in_bounds(x, y) or self.get(x, y).blocks_vision

    def find(self, tile: Tile) -> list[tuple[int, int]]:
        """Toutes les positions d'un type de case, dans l'ordre de lecture."""
        return [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if self._tiles[y][x] is tile
        ]

    def neighbors(self, x: int, y: int) -> Iterator[tuple[int, int]]:
        """Voisins orthogonaux praticables (pour l'IA des mobs et le bot de référence)."""
        for dx, dy in _NEIGHBOR_OFFSETS:
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny):
                yield nx, ny

    def __iter__(self) -> Iterator[tuple[int, int, Tile]]:
        """Parcourt toutes les cases : for x, y, tile in grid: ..."""
        for y, row in enumerate(self._tiles):
            for x, tile in enumerate(row):
                yield x, y, tile

    def __repr__(self) -> str:
        return f"Grid({self.width}x{self.height})"

    # ---------- interne ----------

    def _check_bounds(self, x: int, y: int) -> None:
        if not self.in_bounds(x, y):
            raise IndexError(
                f"({x}, {y}) hors de la grille {self.width}x{self.height}"
            )