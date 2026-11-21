"""Les vrais niveaux : chargement, déterminisme, et preuve qu'ils sont gagnables."""

import pytest
from conftest import load_reference_bot, make_state
from wonderland.engine import Engine, Status, observe
from wonderland.engine.grid import Tile
from wonderland.levels import LevelError, available_levels, load_level

LEVELS = [1, 2, 3, 4, 5]


def test_all_levels_present():
    assert available_levels() == LEVELS


@pytest.mark.parametrize("level", LEVELS)
def test_level_loads(level):
    state = load_level(level, seed=1)
    assert (state.grid.width, state.grid.height) == (20, 20)
    assert state.player.hp == state.player.max_hp
    if state.config.win_condition == "exit":
        assert state.grid.find(Tile.EXIT)
    else:
        assert state.boss() is not None


def test_random_traps_depend_on_seed():
    a = set(load_level(3, seed=1).traps)
    b = set(load_level(3, seed=2).traps)
    assert a != b


@pytest.mark.parametrize("level", LEVELS)
def test_same_seed_same_game(level):
    """Déterminisme : indispensable pour les replays."""
    def play(seed: int) -> list[str]:
        bot = load_reference_bot()
        state = load_level(level, seed=seed)
        engine = Engine()
        log = []
        while state.running:
            log += [repr(e) for e in engine.step(state, bot.decide(observe(state)))]
        return log

    assert play(7) == play(7)


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("level", LEVELS)
def test_reference_bot_wins(level, seed):
    bot = load_reference_bot()
    state = load_level(level, seed=seed)
    engine = Engine()
    while state.running:
        engine.step(state, bot.decide(observe(state)))
    assert state.status is Status.WON, f"niveau {level} seed {seed} : {state.status.name}"


@pytest.mark.parametrize(
    "lines, options",
    [
        (["#####", "#..E#", "#####"], {}),  # pas de départ
        (["#####", "#SZE#", "#####"], {}),  # caractère inconnu
        (["#####", "#S..#", "#####"], {}),  # pas de sortie
        (["#####", "#S.E#", "#####"], {"win": "boss"}),  # pas de boss
    ],
)
def test_invalid_levels_are_rejected(lines, options):
    with pytest.raises(LevelError):
        make_state(lines, **options)
