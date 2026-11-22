"""Données d'une partie (run) côté serveur : mode, statut, résultats par niveau, latences."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RunMode(Enum):
    PRACTICE = "practice"  # un seul niveau, déjà débloqué, rejouable
    CAMPAIGN = "campaign"  # niveaux 1 → 5 enchaînés ; une mort termine la campagne


class RunStatus(Enum):
    RUNNING = "RUNNING"
    WON = "WON"  # tous les niveaux du run terminés
    DEAD = "DEAD"
    TIMEOUT = "TIMEOUT"  # temps limite d'un niveau dépassé
    DISCONNECTED = "DISCONNECTED"  # le bot s'est déconnecté
    REPLACED = "REPLACED"  # l'équipe a relancé une partie du même mode
    STOPPED = "STOPPED"  # arrêtée par un admin


@dataclass
class LevelResult:
    level: int
    status: str
    ticks: int
    hp: int
    hats: int


@dataclass
class LatencyStats:
    """Temps de réponse du bot : sert à repérer un humain qui jouerait « à la main »."""

    samples: int = 0
    total: float = 0.0
    max: float = 0.0
    timeouts: int = 0

    def record(self, seconds: float) -> None:
        self.samples += 1
        self.total += seconds
        self.max = max(self.max, seconds)

    @property
    def average(self) -> float:
        return self.total / self.samples if self.samples else 0.0


@dataclass
class RunInfo:
    id: str
    team_id: str
    mode: RunMode
    levels: list[int]
    seed: int
    status: RunStatus = RunStatus.RUNNING
    current_level: int | None = None
    current_tick: int = 0
    total_ticks: int = 0
    results: list[LevelResult] = field(default_factory=list)
    latency: LatencyStats = field(default_factory=LatencyStats)
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    kills: int = 0
    score: int = 0
    achievements_unlocked: list[str] = field(default_factory=list)

    @property
    def levels_completed(self) -> list[int]:
        return [r.level for r in self.results if r.status == "WON"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "team_id": self.team_id,
            "mode": self.mode.value,
            "levels": self.levels,
            "status": self.status.value,
            "current_level": self.current_level,
            "current_tick": self.current_tick,
            "total_ticks": self.total_ticks,
            "levels_completed": self.levels_completed,
            "results": [r.__dict__ for r in self.results],
            "latency": {
                "average_ms": round(self.latency.average * 1000, 1),
                "max_ms": round(self.latency.max * 1000, 1),
                "timeouts": self.latency.timeouts,
            },
            "kills": self.kills,
            "score": self.score,
            "achievements_unlocked": self.achievements_unlocked,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }
