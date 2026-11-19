from enum import Enum

import pytest
from backend.wonderland.engine.actions import Action, Direction

# --- TEST DIRECTION ---
@pytest.mark.parametrize(
    ("direction", "expected_dx", "expected_dy"),
    [
        (Direction.UP, 0, -1),
        (Direction.DOWN, 0, 1),
        (Direction.LEFT, -1, 0),
        (Direction.RIGHT, 1, 0),
    ]
)
def test_direction(direction: Direction, expected_dx: int, expected_dy: int):
    assert direction.dx == expected_dx
    assert direction.dy == expected_dy

# --- TEST ACTION ---
def test_action_correspondance_noms() -> None:
    expected_actions = {
        "MOVE_UP",
        "MOVE_DOWN",
        "MOVE_LEFT",
        "MOVE_RIGHT",
        "ATTACK",
        "PARRY",
        "SHOOT",
        "WAIT",
    }
    assert {action.name for action in Action} == expected_actions
    for action in Action:
        assert action.value == action.name
        assert isinstance(action.value, str)

@pytest.mark.parametrize(
    ("action", "expected_direction"),
    [
        (Action.MOVE_UP, Direction.UP),
        (Action.MOVE_DOWN, Direction.DOWN),
        (Action.MOVE_LEFT, Direction.LEFT),
        (Action.MOVE_RIGHT, Direction.RIGHT),
        (Action.ATTACK, None),
        (Action.PARRY, None),
        (Action.SHOOT, None),
        (Action.WAIT, None),
    ],
)
def test_action_direction(action: Action, expected_direction: Direction | None):
    assert action.direction == expected_direction

@pytest.mark.parametrize(
    ("invalid_input"),
    [
        "MOVE_UPP",
        "",
        " ",
        "JUMP",
        None,
        123,
        ["MOVE_UP"],
    ],
)
def test_action_parse_invalid(invalid_input: object):
    assert Action.parse(invalid_input) is None