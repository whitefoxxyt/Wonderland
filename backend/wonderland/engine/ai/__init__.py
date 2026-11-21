"""IA des mobs. Le champ `Mob.brain` (texte) est résolu ici en objet Brain."""

from wonderland.engine.ai.base import Brain
from wonderland.engine.ai.brains import (
    ArcherBrain,
    ChaserBrain,
    ErraticBrain,
    IdleBrain,
    PatrolBrain,
)
from wonderland.engine.ai.queen import QueenBrain

BRAINS: dict[str, Brain] = {
    "idle": IdleBrain(),
    "chaser": ChaserBrain(),
    "patrol": PatrolBrain(),
    "erratic": ErraticBrain(),
    "archer": ArcherBrain(),
    "queen": QueenBrain(),
}


def get_brain(name: str) -> Brain:
    try:
        return BRAINS[name]
    except KeyError:
        raise ValueError(f"IA inconnue : {name!r}") from None
