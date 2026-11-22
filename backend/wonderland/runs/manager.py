"""RunManager : qui a le droit de lancer quoi, et suivi des parties en cours.

Règles (décidées pour l'événement) :
    - par équipe : au plus 1 entraînement + 1 campagne en même temps ;
      relancer dans le même mode REMPLACE la partie précédente ;
    - cooldown entre deux lancements d'une équipe dans un même mode ;
    - plafond global de parties simultanées ;
    - entraînement : seulement sur un niveau déjà débloqué (niveau 1 au départ,
      niveau N+1 débloqué en gagnant le niveau N, en entraînement ou en campagne).
"""

from __future__ import annotations

import asyncio
import secrets
import time
import uuid
from dataclasses import dataclass

from wonderland.config import Settings
from wonderland.levels import available_levels
from wonderland.runs.listeners import RunListener
from wonderland.runs.models import RunInfo, RunMode, RunStatus
from wonderland.runs.run import BotConnection, Run
from wonderland.teams import Team

Slot = tuple[str, RunMode]  # (équipe, mode)


class RunRejected(Exception):
    """Lancement refusé ; le message est renvoyé tel quel au bot."""


@dataclass
class _ActiveRun:
    info: RunInfo
    task: asyncio.Task[RunInfo] | None = None


class RunManager:
    def __init__(self, settings: Settings, unlocked: dict[str, int] | None = None) -> None:
        """`unlocked` : niveau max débloqué par équipe (rechargé depuis la base au démarrage)."""
        self.settings = settings
        self._active: dict[str, _ActiveRun] = {}
        self._slots: dict[Slot, str] = {}
        self._last_start: dict[Slot, float] = {}
        self._history: dict[str, RunInfo] = {}
        self._unlocked: dict[str, int] = dict(unlocked or {})
        self._listeners: list[RunListener] = []
        self.accept_runs = True  # False = jeu figé par l'organisateur (annonce des résultats)

    # ---------- abonnements (succès, score, direct…) ----------

    def subscribe(self, listener: RunListener) -> None:
        self._listeners.append(listener)

    # ---------- lancement ----------

    def prepare(
        self, team: Team, mode: RunMode, level: int | None = None, seed: int | None = None
    ) -> RunInfo:
        """Vérifie les règles et réserve la place. Lève RunRejected si refusé."""
        if not self.accept_runs:
            raise RunRejected("Le jeu est figé par l'organisation, patience !")
        slot = (team.id, mode)
        now = time.monotonic()
        elapsed = now - self._last_start.get(slot, -1e9)
        if elapsed < self.settings.run_cooldown:
            wait = self.settings.run_cooldown - elapsed
            raise RunRejected(f"Patiente encore {wait:.1f} s avant de relancer en {mode.value}")

        levels = self._levels_for(team, mode, level)

        replaced = self._slots.get(slot)
        others = len(self._active) - (1 if replaced else 0)
        if others >= self.settings.max_concurrent_runs:
            raise RunRejected("Serveur plein, réessaie dans quelques secondes")

        if replaced:
            self.stop(replaced, RunStatus.REPLACED)

        if mode is RunMode.CAMPAIGN or seed is None:
            seed = secrets.randbelow(2**31)  # campagne : graine imprévisible (anti hard-code)
        info = RunInfo(id=uuid.uuid4().hex[:8], team_id=team.id, mode=mode, levels=levels, seed=seed)
        self._active[info.id] = _ActiveRun(info)
        self._slots[slot] = info.id
        self._last_start[slot] = now
        return info

    async def execute(self, info: RunInfo, connection: BotConnection) -> RunInfo:
        """Joue la partie jusqu'au bout (ou jusqu'à son remplacement)."""
        active = self._active[info.id]
        run = Run(info, connection, self.settings, self._listeners)
        active.task = asyncio.create_task(run.play(), name=f"run-{info.id}")
        await asyncio.wait({active.task})  # ne lève pas si la tâche est annulée
        self._release(info)
        return info

    def stop(self, run_id: str, status: RunStatus = RunStatus.STOPPED) -> bool:
        active = self._active.get(run_id)
        if active is None:
            return False
        active.info.status = status
        if active.task is not None:
            active.task.cancel()
        else:
            self._release(active.info)
        return True

    def stop_all(self, status: RunStatus = RunStatus.STOPPED) -> int:
        run_ids = list(self._active)
        for run_id in run_ids:
            self.stop(run_id, status)
        return len(run_ids)

    def reset_progress(self) -> None:
        """Oublie les niveaux débloqués et l'historique (remise à zéro de l'événement)."""
        self._unlocked.clear()
        self._history.clear()
        self._last_start.clear()

    # ---------- consultation ----------

    def active_runs(self) -> list[RunInfo]:
        return [a.info for a in self._active.values()]

    def get(self, run_id: str) -> RunInfo | None:
        active = self._active.get(run_id)
        return active.info if active else self._history.get(run_id)

    def unlocked_level(self, team_id: str) -> int:
        last = max(available_levels())
        if self.settings.unlock_all:
            return last
        return min(self._unlocked.get(team_id, 1), last)

    # ---------- interne ----------

    def _levels_for(self, team: Team, mode: RunMode, level: int | None) -> list[int]:
        if mode is RunMode.CAMPAIGN:
            return list(self.settings.campaign_levels)
        if level is None:
            raise RunRejected("Le mode practice demande un paramètre level")
        if level not in available_levels():
            raise RunRejected(f"Niveau {level} inconnu")
        if level > self.unlocked_level(team.id):
            raise RunRejected(f"Niveau {level} pas encore débloqué")
        return [level]

    def _release(self, info: RunInfo) -> None:
        if info.ended_at is None:
            info.ended_at = time.time()
        self._active.pop(info.id, None)
        slot = (info.team_id, info.mode)
        if self._slots.get(slot) == info.id:
            del self._slots[slot]
        self._history[info.id] = info
        for won in info.levels_completed:
            self._unlocked[info.team_id] = max(self.unlocked_level(info.team_id), won + 1)
