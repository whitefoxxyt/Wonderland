import pytest
from wonderland.engine.grid import Grid, Tile


@pytest.fixture
def grid() -> Grid:
    return Grid.from_lines([
        "#######",
        "#.^~.E#",
        "#######",
    ])


def test_dimensions(grid):
    assert (grid.width, grid.height) == (7, 3)


def test_get_uses_x_then_y(grid):
    assert grid.get(5, 1) is Tile.EXIT
    assert grid.get(2, 1) is Tile.TRAP
    assert grid.get(3, 1) is Tile.MIST


@pytest.mark.parametrize("tile, walkable, blocks_vision, dangerous", [
    (Tile.WALL,  False, True,  False),
    (Tile.FLOOR, True,  False, False),
    (Tile.TRAP,  True,  False, True),
    (Tile.MIST,  True,  True,  False),
    (Tile.EXIT,  True,  False, False),
])
def test_tile_properties(tile, walkable, blocks_vision, dangerous):
    assert tile.walkable is walkable
    assert tile.blocks_vision is blocks_vision
    assert tile.dangerous is dangerous


@pytest.mark.parametrize("x, y", [(-1, 1), (7, 1), (1, -1), (1, 3)])
def test_out_of_bounds(grid, x, y):
    assert not grid.is_walkable(x, y)
    assert grid.blocks_vision(x, y)
    with pytest.raises(IndexError):
        grid.get(x, y)


def test_neighbors(grid):
    assert set(grid.neighbors(1, 1)) == {(2, 1)}           # entouré de murs sauf à droite
    assert set(grid.neighbors(3, 1)) == {(2, 1), (4, 1)}


def test_find(grid):
    assert grid.find(Tile.EXIT) == [(5, 1)]
    assert grid.find(Tile.TRAP) == [(2, 1)]


def test_set_and_copy_are_independent(grid):
    clone = grid.copy()
    clone.set(1, 1, Tile.WALL)
    assert clone.get(1, 1) is Tile.WALL
    assert grid.get(1, 1) is Tile.FLOOR


def test_round_trip(grid):
    assert grid.to_lines() == ["#######", "#.^~.E#", "#######"]


def test_iter_covers_all_cells(grid):
    assert len(list(grid)) == 7 * 3


def test_rejects_ragged_lines():
    with pytest.raises(ValueError, match="Ligne 1"):
        Grid.from_lines(["###", "##"])


def test_rejects_unknown_char():
    with pytest.raises(ValueError, match=r"\(1, 0\)"):
        Grid.from_lines(["#Z#"])