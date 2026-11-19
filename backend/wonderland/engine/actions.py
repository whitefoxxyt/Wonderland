from __future__ import annotations

from enum import Enum


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    # Mouvements horizontaux
    @property
    def dx(self) -> int:
        return self.value[0]

    # Mouvements verticaux
    @property
    def dy(self) -> int:
        return self.value[1]

class Action(Enum):
    MOVE_UP = "MOVE_UP"
    MOVE_DOWN = "MOVE_DOWN"
    MOVE_LEFT = "MOVE_LEFT"
    MOVE_RIGHT = "MOVE_RIGHT"
    ATTACK = "ATTACK"
    PARRY = "PARRY"
    SHOOT = "SHOOT"
    WAIT = "WAIT"

    @property
    def direction(self) -> Direction | None:
        return {
            Action.MOVE_UP: Direction.UP,
            Action.MOVE_DOWN: Direction.DOWN,
            Action.MOVE_LEFT: Direction.LEFT,
            Action.MOVE_RIGHT: Direction.RIGHT,
        }.get(self)

    @classmethod
    def parse(cls, text: str) -> Action | None:
        if not isinstance(text, str):
            return None
        try:
            return cls(text.strip().upper())
        except ValueError:
            return None


