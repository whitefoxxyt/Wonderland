"""Évalue les succès pendant les parties et les enregistre en base."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from wonderland.engine.events import Event
from wonderland.engine.state import GameState
from wonderland.persistence import Database
from wonderland.runs.listeners import RunListener
from wonderland.runs.models import RunInfo
from wonderland.services.achievements.base import Achievement, AchievementContext
from wonderland.services.achievements.definitions import ALL_ACHIEVEMENTS

# Appelé à chaque déblocage : (équipe, succès, partie). Servira au direct (phase 7).
UnlockCallback = Callable[[str, Achievement, RunInfo], None]


class AchievementService(RunListener):
    def __init__(self, db: Database, achievements: list[Achievement] | None = None) -> None:
        self.db = db
        self.achievements = achievements if achievements is not None else ALL_ACHIEVEMENTS
        self._by_id = {a.id: a for a in self.achievements}
        self._unlocked: dict[str, set[str]] = {}
        self._progress: dict[tuple[str, str], dict[str, Any]] = {}
        self._scratch: dict[tuple[str, str], dict[str, Any]] = {}
        self._callbacks: list[UnlockCallback] = []
        self.hint_level: int = db.get_admin("hint_level", 1)

    def on_unlock(self, callback: UnlockCallback) -> None:
        self._callbacks.append(callback)

    def set_hint_level(self, level: int) -> None:
        self.hint_level = level
        self.db.set_admin("hint_level", level)

    def reset_cache(self) -> None:
        """À appeler après une remise à zéro de la base."""
        self._unlocked.clear()
        self._progress.clear()
        self._scratch.clear()

    # ---------- crochets de partie ----------

    def on_level_start(self, run: RunInfo, state: GameState) -> None:
        self._dispatch(run, lambda a, ctx: a.on_level_start(ctx, state))

    def on_tick(self, run: RunInfo, state: GameState, events: list[Event]) -> None:
        self._dispatch(run, lambda a, ctx: a.on_tick(ctx, state, events))

    def on_level_end(self, run: RunInfo, state: GameState) -> None:
        self._dispatch(run, lambda a, ctx: a.on_level_end(ctx, state))
        self._save_progress(run.team_id)

    def on_run_end(self, run: RunInfo) -> None:
        self._dispatch(run, lambda a, ctx: a.on_run_end(ctx))
        self._save_progress(run.team_id)
        for key in [k for k in self._scratch if k[0] == run.id]:
            del self._scratch[key]

    # ---------- consultation ----------

    def unlocked(self, team_id: str) -> set[str]:
        if team_id not in self._unlocked:
            self._unlocked[team_id] = set(self.db.unlocked_achievements(team_id))
        return self._unlocked[team_id]

    def points(self, team_id: str) -> int:
        return sum(self._by_id[a].points for a in self.unlocked(team_id) if a in self._by_id)

    def for_team(self, team_id: str) -> list[dict[str, Any]]:
        unlocked = self.unlocked(team_id)
        return [a.public(a.id in unlocked, self.hint_level) for a in self.achievements]

    def catalog(self) -> list[dict[str, Any]]:
        """Vue publique : succès cachés masqués + nombre d'équipes qui les ont."""
        result = []
        for achievement in self.achievements:
            entry = achievement.public(unlocked=False, hint_level=self.hint_level)
            entry["teams"] = len(self.db.achievement_holders(achievement.id))
            result.append(entry)
        return result

    # ---------- interne ----------

    def _dispatch(self, run: RunInfo, call: Callable[[Achievement, AchievementContext], bool]) -> None:
        team = run.team_id
        for achievement in self.achievements:
            if achievement.id in self.unlocked(team):
                continue
            ctx = self._context(run, achievement)
            if call(achievement, ctx):
                self._unlock(run, achievement)

    def _context(self, run: RunInfo, achievement: Achievement) -> AchievementContext:
        progress_key = (run.team_id, achievement.id)
        if progress_key not in self._progress:
            self._progress[progress_key] = self.db.load_progress(*progress_key)
        scratch = self._scratch.setdefault((run.id, achievement.id), {})
        return AchievementContext(
            team_id=run.team_id,
            run=run,
            progress=self._progress[progress_key],
            scratch=scratch,
            holders=lambda: [
                t for t in self.db.achievement_holders(achievement.id) if t != run.team_id
            ],
        )

    def _unlock(self, run: RunInfo, achievement: Achievement) -> None:
        if not self.db.unlock_achievement(run.team_id, achievement.id, run.id):
            return
        self.unlocked(run.team_id).add(achievement.id)
        run.achievements_unlocked.append(achievement.name)
        for callback in self._callbacks:
            callback(run.team_id, achievement, run)

    def _save_progress(self, team_id: str) -> None:
        for (team, achievement_id), data in self._progress.items():
            if team == team_id and data:
                self.db.save_progress(team, achievement_id, data)
