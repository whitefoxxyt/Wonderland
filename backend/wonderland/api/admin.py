"""Routes de l'organisateur, protégées par l'en-tête X-Admin-Token.

    GET  /api/admin/status              état du jeu + parties en cours (latences comprises)
    POST /api/admin/runs/{id}/stop      arrête une partie
    POST /api/admin/runs/stop-all       arrête toutes les parties
    POST /api/admin/accept-runs         {"value": false} fige le jeu (plus de nouvelles parties)
    POST /api/admin/leaderboard/freeze  {"value": true} fige le classement public (suspense de fin)
    POST /api/admin/hints               {"level": 2} révèle le second indice des succès
    POST /api/admin/announce            {"text": "..."} message sur tous les écrans
    POST /api/admin/reset               {"confirm": "RESET"} efface parties, succès et progression
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from wonderland.broadcast import BroadcastHub
from wonderland.config import Settings
from wonderland.persistence import Database
from wonderland.runs import RunManager, RunStatus
from wonderland.services.achievements import AchievementService


@dataclass
class AdminContext:
    settings: Settings
    manager: RunManager
    db: Database
    achievements: AchievementService
    hub: BroadcastHub
    live_leaderboard: Callable[[], list[dict[str, Any]]]


class Flag(BaseModel):
    value: bool


class HintLevel(BaseModel):
    level: int


class Announcement(BaseModel):
    text: str


class ResetRequest(BaseModel):
    confirm: str


def admin_router(ctx: AdminContext) -> APIRouter:
    def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
        expected = ctx.settings.admin_token
        if not expected:
            raise HTTPException(403, "Routes admin désactivées (WONDERLAND_ADMIN_TOKEN vide)")
        if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
            raise HTTPException(401, "Token admin invalide")

    router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

    @router.get("/status")
    def status() -> dict[str, Any]:
        return {
            "accept_runs": ctx.manager.accept_runs,
            "leaderboard_frozen": ctx.db.get_admin("frozen_leaderboard") is not None,
            "hint_level": ctx.achievements.hint_level,
            "featured": ctx.hub.featured,
            "active_runs": [info.to_dict() for info in ctx.manager.active_runs()],
        }

    @router.post("/runs/stop-all")
    def stop_all() -> dict[str, Any]:
        return {"stopped": ctx.manager.stop_all()}

    @router.post("/runs/{run_id}/stop")
    def stop_run(run_id: str) -> dict[str, Any]:
        if not ctx.manager.stop(run_id, RunStatus.STOPPED):
            raise HTTPException(404, "Aucune partie active avec cet id")
        return {"stopped": run_id}

    @router.post("/accept-runs")
    def accept_runs(flag: Flag) -> dict[str, Any]:
        ctx.manager.accept_runs = flag.value
        ctx.db.set_admin("accept_runs", flag.value)
        return {"accept_runs": flag.value}

    @router.post("/leaderboard/freeze")
    def freeze_leaderboard(flag: Flag) -> dict[str, Any]:
        # On fige une copie du classement actuel ; le vrai continue d'être calculé en coulisses.
        ctx.db.set_admin("frozen_leaderboard", ctx.live_leaderboard() if flag.value else None)
        ctx.hub.push_leaderboard()
        return {"leaderboard_frozen": flag.value}

    @router.post("/hints")
    def reveal_hints(body: HintLevel) -> dict[str, Any]:
        if body.level not in (1, 2):
            raise HTTPException(400, "level doit valoir 1 ou 2")
        ctx.achievements.set_hint_level(body.level)
        if body.level == 2:
            ctx.hub.announce("Nouveaux indices de succès disponibles !")
        return {"hint_level": body.level}

    @router.post("/announce")
    def announce(body: Announcement) -> dict[str, Any]:
        ctx.hub.announce(body.text)
        return {"announced": body.text}

    @router.get("/leaderboard")
    def real_leaderboard() -> list[dict[str, Any]]:
        """Le vrai classement, même quand le classement public est figé."""
        return ctx.live_leaderboard()

    @router.post("/reset")
    def reset(body: ResetRequest) -> dict[str, Any]:
        if body.confirm != "RESET":
            raise HTTPException(400, 'Envoyer {"confirm": "RESET"} pour confirmer')
        stopped = ctx.manager.stop_all()
        ctx.db.reset()
        ctx.manager.reset_progress()
        ctx.manager.accept_runs = True
        ctx.achievements.reset_cache()
        ctx.achievements.set_hint_level(1)
        ctx.hub.push_leaderboard()
        return {"reset": True, "stopped_runs": stopped}

    return router
