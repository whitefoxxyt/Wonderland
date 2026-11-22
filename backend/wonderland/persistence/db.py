"""Persistance SQLite (module standard sqlite3, aucune dépendance).

Quatre tables :
    runs                  une ligne par partie terminée
    achievements          succès débloqués (une ligne par équipe et par succès)
    achievement_progress  progression des succès « cumulatifs » (JSON libre)
    replays               graine + actions de chaque partie (suffit à la rejouer)

Le serveur tourne dans un seul thread asyncio et les requêtes sont minuscules :
pas besoin d'ORM ni de pool de connexions.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from wonderland.runs.models import RunInfo

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id               TEXT PRIMARY KEY,
    team_id          TEXT NOT NULL,
    mode             TEXT NOT NULL,
    status           TEXT NOT NULL,
    seed             INTEGER NOT NULL,
    levels           TEXT NOT NULL,
    levels_completed TEXT NOT NULL,
    results          TEXT NOT NULL,
    total_ticks      INTEGER NOT NULL,
    kills            INTEGER NOT NULL,
    score            INTEGER NOT NULL,
    latency          TEXT NOT NULL,
    started_at       REAL NOT NULL,
    ended_at         REAL
);
CREATE INDEX IF NOT EXISTS runs_team ON runs (team_id);

CREATE TABLE IF NOT EXISTS achievements (
    team_id        TEXT NOT NULL,
    achievement_id TEXT NOT NULL,
    run_id         TEXT,
    unlocked_at    REAL NOT NULL,
    PRIMARY KEY (team_id, achievement_id)
);

CREATE TABLE IF NOT EXISTS replays (
    run_id TEXT PRIMARY KEY,
    data   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS achievement_progress (
    team_id        TEXT NOT NULL,
    achievement_id TEXT NOT NULL,
    data           TEXT NOT NULL,
    PRIMARY KEY (team_id, achievement_id)
);
"""


class Database:
    def __init__(self, path: str | Path) -> None:
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---------- parties ----------

    def save_run(self, info: RunInfo) -> None:
        data = info.to_dict()
        self.conn.execute(
            """INSERT OR REPLACE INTO runs VALUES
               (:id, :team_id, :mode, :status, :seed, :levels, :levels_completed, :results,
                :total_ticks, :kills, :score, :latency, :started_at, :ended_at)""",
            {
                **data,
                "seed": info.seed,
                "levels": json.dumps(data["levels"]),
                "levels_completed": json.dumps(data["levels_completed"]),
                "results": json.dumps(data["results"]),
                "latency": json.dumps(data["latency"]),
            },
        )
        self.conn.commit()

    def runs_for_team(self, team_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM runs WHERE team_id = ? ORDER BY started_at", (team_id,)
        ).fetchall()
        return [_decode_run(row) for row in rows]

    def unlocked_levels(self) -> dict[str, int]:
        """Niveau max débloqué par équipe = (plus haut niveau gagné) + 1."""
        best: dict[str, int] = {}
        for row in self.conn.execute("SELECT team_id, levels_completed FROM runs"):
            for level in json.loads(row["levels_completed"]):
                best[row["team_id"]] = max(best.get(row["team_id"], 1), level + 1)
        return best

    # ---------- succès ----------

    def unlock_achievement(self, team_id: str, achievement_id: str, run_id: str | None) -> bool:
        """Renvoie True si le succès vient d'être débloqué (False s'il l'était déjà)."""
        cursor = self.conn.execute(
            "INSERT OR IGNORE INTO achievements VALUES (?, ?, ?, ?)",
            (team_id, achievement_id, run_id, time.time()),
        )
        self.conn.commit()
        return cursor.rowcount == 1

    def unlocked_achievements(self, team_id: str) -> dict[str, float]:
        rows = self.conn.execute(
            "SELECT achievement_id, unlocked_at FROM achievements WHERE team_id = ?", (team_id,)
        )
        return {row["achievement_id"]: row["unlocked_at"] for row in rows}

    def achievement_holders(self, achievement_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT team_id FROM achievements WHERE achievement_id = ? ORDER BY unlocked_at",
            (achievement_id,),
        )
        return [row["team_id"] for row in rows]

    def load_progress(self, team_id: str, achievement_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT data FROM achievement_progress WHERE team_id = ? AND achievement_id = ?",
            (team_id, achievement_id),
        ).fetchone()
        return json.loads(row["data"]) if row else {}

    def save_progress(self, team_id: str, achievement_id: str, data: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO achievement_progress VALUES (?, ?, ?)",
            (team_id, achievement_id, json.dumps(data)),
        )
        self.conn.commit()

    # ---------- replays ----------

    def save_replay(self, run_id: str, data: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO replays VALUES (?, ?)", (run_id, json.dumps(data, separators=(",", ":")))
        )
        self.conn.commit()

    def load_replay(self, run_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT data FROM replays WHERE run_id = ?", (run_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    # ---------- admin ----------

    def reset(self) -> None:
        """Vide toutes les tables (avant l'événement, après la répétition générale)."""
        self.conn.executescript("DELETE FROM runs; DELETE FROM achievements; DELETE FROM achievement_progress;"
            " DELETE FROM replays;")
        self.conn.commit()


def _decode_run(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for key in ("levels", "levels_completed", "results", "latency"):
        data[key] = json.loads(data[key])
    return data
