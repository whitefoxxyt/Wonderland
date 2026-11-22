"""Socle des succès.

Un succès est une petite classe qui réagit aux crochets de partie et renvoie True
au moment où il est débloqué. Deux mémoires sont à sa disposition :
    ctx.progress : persistante, par équipe (ex. « niveaux où l'équipe est morte »)
    ctx.scratch  : temporaire, propre à la partie en cours (ex. « dégâts reçus ce niveau »)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from wonderland.engine.events import Event
from wonderland.engine.state import GameState
from wonderland.runs.models import RunInfo


@dataclass
class AchievementContext:
    team_id: str
    run: RunInfo
    progress: dict[str, Any]
    scratch: dict[str, Any] = field(default_factory=dict)
    # Nombre d'AUTRES équipes ayant déjà ce succès (pour les succès « premier arrivé »).
    holders: Callable[[], list[str]] = list


class Achievement:
    id: str = ""
    name: str = ""
    description: str = ""  # révélée une fois débloqué
    hint: str = ""  # affiché tant que le succès est verrouillé
    extra_hint: str = ""  # second indice, plus explicite, révélé par l'organisateur
    points: int = 50
    hidden: bool = True  # caché = nom affiché « ??? » tant qu'il n'est pas débloqué

    def on_level_start(self, ctx: AchievementContext, state: GameState) -> bool:
        return False

    def on_tick(self, ctx: AchievementContext, state: GameState, events: list[Event]) -> bool:
        return False

    def on_level_end(self, ctx: AchievementContext, state: GameState) -> bool:
        return False

    def on_run_end(self, ctx: AchievementContext) -> bool:
        return False

    def public(self, unlocked: bool, hint_level: int = 1) -> dict[str, Any]:
        """Vue envoyée aux équipes. hint_level >= 2 : le second indice est révélé."""
        visible = unlocked or not self.hidden
        return {
            "id": self.id if visible else None,
            "name": self.name if visible else "???",
            "description": self.description if visible else None,
            "hint": self.hint,
            "extra_hint": self.extra_hint if (visible or hint_level >= 2) and self.extra_hint else None,
            "points": self.points,
            "unlocked": unlocked,
        }
