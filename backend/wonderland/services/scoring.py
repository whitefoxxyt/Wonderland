"""Score d'une partie.

    + 1000 par niveau gagné
    + 2 × (par_ticks − ticks utilisés) par niveau gagné, si on bat le temps de référence
    +   50 par chapeau ramassé (niveaux gagnés uniquement)
    +   20 par mob tué
    −  100 si la partie se termine par une mort

Tous les réglages sont dans les constantes ci-dessous (à ajuster après playtest).
"""

from __future__ import annotations

from wonderland.engine.events import Event, MobKilled
from wonderland.engine.state import GameState
from wonderland.levels import available_levels, level_summary
from wonderland.runs.listeners import RunListener
from wonderland.runs.models import RunInfo, RunStatus

LEVEL_POINTS = 1000
TIME_BONUS_PER_TICK = 2
HAT_POINTS = 50
KILL_POINTS = 20
DEATH_PENALTY = 100


def compute_score(run: RunInfo, par_ticks: dict[int, int]) -> int:
    score = 0
    for result in run.results:
        if result.status != "WON":
            continue
        score += LEVEL_POINTS
        score += TIME_BONUS_PER_TICK * max(0, par_ticks.get(result.level, 0) - result.ticks)
        score += HAT_POINTS * result.hats
    score += KILL_POINTS * run.kills
    if run.status is RunStatus.DEAD:
        score -= DEATH_PENALTY
    return max(0, score)


class ScoringService(RunListener):
    def __init__(self) -> None:
        self.par_ticks = {n: level_summary(n)["par_ticks"] for n in available_levels()}

    def on_tick(self, run: RunInfo, state: GameState, events: list[Event]) -> None:
        run.kills += sum(1 for e in events if isinstance(e, MobKilled))

    def on_run_end(self, run: RunInfo) -> None:
        run.score = compute_score(run, self.par_ticks)
