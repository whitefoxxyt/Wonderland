"""Configuration du serveur, lue depuis les variables d'environnement (préfixe WONDERLAND_).

Exemple PowerShell :
    $env:WONDERLAND_TICK_TIMEOUT = "0.5"; uvicorn wonderland.api.app:app
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    return os.environ.get(f"WONDERLAND_{name}", default)


@dataclass
class Settings:
    # Délai max (secondes) pour qu'un bot réponde à une observation ; au-delà → WAIT imposé.
    tick_timeout: float = field(default_factory=lambda: float(_env("TICK_TIMEOUT", "0.3")))
    # Attente minimale entre deux lancements d'une même équipe dans un même mode.
    run_cooldown: float = field(default_factory=lambda: float(_env("RUN_COOLDOWN", "3")))
    # Plafond global (5 équipes × 1 entraînement + 1 campagne).
    max_concurrent_runs: int = field(
        default_factory=lambda: int(_env("MAX_CONCURRENT_RUNS", "10"))
    )
    # Fichier des équipes (non versionné : contient les tokens).
    teams_file: Path = field(
        default_factory=lambda: Path(_env("TEAMS_FILE", str(PROJECT_ROOT / "teams.json")))
    )
    # Base SQLite (parties, succès). ":memory:" pour une base jetable.
    db_path: str = field(
        default_factory=lambda: _env("DB_PATH", str(PROJECT_ROOT / "wonderland.db"))
    )
    # Vrai = tous les niveaux jouables en entraînement sans les avoir débloqués (tests, répétition).
    unlock_all: bool = field(default_factory=lambda: _env("UNLOCK_ALL", "0") == "1")
    # Durée minimale d'un tick en CAMPAGNE (secondes) : rend les parties regardables en direct.
    # L'entraînement reste à pleine vitesse.
    campaign_tick_delay: float = field(
        default_factory=lambda: float(_env("CAMPAIGN_TICK_DELAY", "0.1"))
    )
    # Images par seconde max envoyées aux spectateurs pour une partie.
    live_fps: float = field(default_factory=lambda: float(_env("LIVE_FPS", "10")))
    # Token des routes /api/admin (en-tête X-Admin-Token). Vide = routes admin désactivées.
    admin_token: str = field(default_factory=lambda: _env("ADMIN_TOKEN", ""))
    # Niveaux de la campagne, dans l'ordre.
    campaign_levels: tuple[int, ...] = (1, 2, 3, 4, 5)
