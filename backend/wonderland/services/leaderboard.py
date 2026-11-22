"""Enregistrement des parties et classement des équipes.

Ordre du classement :
    1. niveau le plus haut gagné (n'importe quel mode)
    2. meilleur score de campagne
    3. points de succès
    4. départage : qui a atteint son meilleur niveau en premier
"""

from __future__ import annotations

from typing import Any

from wonderland.persistence import Database
from wonderland.runs.listeners import RunListener
from wonderland.runs.models import RunInfo
from wonderland.services.achievements import AchievementService
from wonderland.teams import TeamRegistry


class RunRecorder(RunListener):
    """Sauvegarde chaque partie terminée. À abonner APRÈS le score et les succès."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def on_run_end(self, run: RunInfo) -> None:
        self.db.save_run(run)


def leaderboard(
    db: Database, teams: TeamRegistry, achievements: AchievementService
) -> list[dict[str, Any]]:
    rows = []
    for team in teams.all():
        runs = db.runs_for_team(team.id)
        max_level = 0
        reached_at = float("inf")
        for run in runs:
            for level in run["levels_completed"]:
                when = run["ended_at"] or run["started_at"]
                if level > max_level or (level == max_level and when < reached_at):
                    max_level, reached_at = level, when
        campaign_scores = [r["score"] for r in runs if r["mode"] == "campaign"]
        rows.append(
            {
                "team_id": team.id,
                "team": team.name,
                "max_level": max_level,
                "best_campaign_score": max(campaign_scores, default=0),
                "achievement_points": achievements.points(team.id),
                "achievements": len(achievements.unlocked(team.id)),
                "runs": len(runs),
                "reached_at": reached_at if max_level else None,
            }
        )
    rows.sort(
        key=lambda r: (
            -r["max_level"],
            -r["best_campaign_score"],
            -r["achievement_points"],
            r["reached_at"] or float("inf"),
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows
