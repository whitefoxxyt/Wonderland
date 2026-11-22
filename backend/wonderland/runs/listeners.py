"""Écouteurs de parties : le point de branchement des services (score, succès, base, direct).

Un service hérite de RunListener et surcharge seulement ce qui l'intéresse.
La boucle de jeu les appelle dans l'ordre d'abonnement ; une exception dans un
écouteur est journalisée mais n'interrompt JAMAIS la partie.
"""

from __future__ import annotations

from wonderland.engine.events import Event
from wonderland.engine.state import GameState
from wonderland.runs.models import RunInfo


class RunListener:
    def on_level_start(self, run: RunInfo, state: GameState) -> None:
        """Niveau chargé, avant le premier tick."""

    def on_tick(self, run: RunInfo, state: GameState, events: list[Event]) -> None:
        """Après chaque tick (state.tick a déjà été incrémenté)."""

    def on_level_end(self, run: RunInfo, state: GameState) -> None:
        """Niveau terminé (gagné, mort ou temps écoulé). run.results contient déjà ce niveau."""

    def on_run_end(self, run: RunInfo) -> None:
        """Partie terminée, quelle qu'en soit la raison (aussi remplacée / déconnectée)."""
