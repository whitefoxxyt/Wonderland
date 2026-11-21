import json

from conftest import make_state
from wonderland.engine import Action, observe


def test_observation_is_json_serializable(engine):
    state = make_state(["#######", "#S.d^E#", "#######"])
    engine.step(state, Action.MOVE_RIGHT)
    obs = observe(state)
    json.dumps(obs)
    assert obs["you"]["x"] == 2
    assert obs["mobs"][0]["kind"] == "dormouse"
    assert obs["events"]


def test_hidden_trap_looks_like_floor():
    obs = observe(make_state(["#######", "#S.._E#", "#######"]))
    assert obs["grid"][1] == "#S...E#".replace("S", ".")
    assert obs["traps"] == []


def test_fog_hides_far_cells_and_entities():
    lines = ["############", "#S........d#", "############", "#.........E#", "############"]
    obs = observe(make_state(lines, vision_radius=3))
    assert obs["grid"][1][10] == "?"
    assert obs["mobs"] == []
    assert obs["grid"][1][2] == "."


def test_mist_blocks_vision():
    lines = ["#########", "#S~....E#", "#########"]
    obs = observe(make_state(lines, vision_radius=5))
    assert obs["grid"][1][2] == "~"  # on voit la brume…
    assert obs["grid"][1][4] == "?"  # …mais pas au-delà


def test_discovered_cells_stay_known(engine):
    lines = ["##########", "#S.......#", "##########", "#.......E#", "##########"]
    state = make_state(lines, vision_radius=2)
    for _ in range(5):
        engine.step(state, Action.MOVE_RIGHT)
    assert observe(state)["grid"][1][1] == "."
