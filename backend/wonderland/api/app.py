"""Serveur FastAPI : WebSocket des bots + API REST de consultation.

Lancer le serveur (depuis la racine du projet, venv activé) :
    uvicorn wonderland.api.app:create_app --factory --host 0.0.0.0 --port 8000

Un bot se connecte sur :
    ws://<hôte>:8000/ws/bot?token=<token>&mode=practice&level=1
    ws://<hôte>:8000/ws/bot?token=<token>&mode=campaign

Spectateurs :
    ws://<hôte>:8000/ws/live              partie vedette + moments forts + classement
    ws://<hôte>:8000/ws/live/all          toutes les parties (mosaïque)
    ws://<hôte>:8000/ws/live/run/<run_id> une partie précise
    http://<hôte>:8000/live               page de test minimale (en attendant le front Angular)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from wonderland.broadcast import ALL, FEATURED, BroadcastHub, run_channel
from wonderland.config import Settings
from wonderland.levels import available_levels, level_summary
from wonderland.persistence import Database
from wonderland.replays import ReplayRecorder, replay_frames
from wonderland.runs import BotDisconnected, RunManager, RunMode, RunRejected
from wonderland.runs.protocol import ErrorMessage, json_schemas
from wonderland.services.achievements import AchievementService
from wonderland.services.leaderboard import RunRecorder, leaderboard
from wonderland.services.scoring import ScoringService
from wonderland.teams import Team, TeamRegistry

LIVE_PAGE = Path(__file__).parent / "static" / "live.html"

# Codes de fermeture WebSocket applicatifs (plage 4000-4999).
CLOSE_UNAUTHORIZED = 4401
CLOSE_BAD_REQUEST = 4400
CLOSE_REJECTED = 4409


class WebSocketConnection:
    """Adapte un WebSocket Starlette à l'interface BotConnection de la boucle de jeu."""

    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket

    async def send(self, message: dict[str, Any]) -> None:
        try:
            await self.websocket.send_json(message)
        except (WebSocketDisconnect, RuntimeError) as exc:
            raise BotDisconnected from exc

    async def receive(self) -> Any:
        try:
            text = await self.websocket.receive_text()
        except (WebSocketDisconnect, RuntimeError) as exc:
            raise BotDisconnected from exc
        try:
            return json.loads(text)
        except ValueError:
            return None


def create_app(
    settings: Settings | None = None,
    teams: TeamRegistry | None = None,
    db: Database | None = None,
) -> FastAPI:
    settings = settings or Settings()
    teams = teams or TeamRegistry.from_file(settings.teams_file)
    db = db or Database(settings.db_path)
    manager = RunManager(settings, unlocked=db.unlocked_levels())

    # Ordre important : le score et les succès remplissent la partie AVANT son enregistrement,
    # et la diffusion passe en dernier pour annoncer un classement à jour.
    achievements = AchievementService(db)
    hub = BroadcastHub(
        settings,
        team_name=lambda team_id: team.name if (team := teams.get(team_id)) else team_id,
        leaderboard=lambda: leaderboard(db, teams, achievements),
    )
    achievements.on_unlock(hub.on_achievement)
    manager.subscribe(ScoringService())
    manager.subscribe(achievements)
    manager.subscribe(ReplayRecorder(db))
    manager.subscribe(RunRecorder(db))
    manager.subscribe(hub)

    app = FastAPI(title="Wonderland", version="0.1.0")
    app.state.settings = settings
    app.state.teams = teams
    app.state.manager = manager
    app.state.db = db
    app.state.achievements = achievements
    app.state.hub = hub

    def current_team(token: str | None, header_token: str | None) -> Team:
        team = teams.authenticate(header_token or token)
        if team is None:
            raise HTTPException(status_code=401, detail="Token invalide")
        return team

    # ---------- REST ----------

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "active_runs": len(manager.active_runs())}

    @app.get("/api/levels")
    def levels() -> list[dict[str, Any]]:
        fields = ("id", "name", "max_ticks", "par_ticks", "vision_radius", "win")
        return [{k: level_summary(n)[k] for k in fields} for n in available_levels()]

    @app.get("/api/leaderboard")
    def get_leaderboard() -> list[dict[str, Any]]:
        return leaderboard(db, teams, achievements)

    @app.get("/api/achievements")
    def achievement_catalog() -> list[dict[str, Any]]:
        return achievements.catalog()

    @app.get("/api/teams/me")
    def my_team(
        token: str | None = None, x_team_token: str | None = Header(default=None)
    ) -> dict[str, Any]:
        """Tableau de bord d'une équipe (token en ?token= ou en-tête X-Team-Token)."""
        team = current_team(token, x_team_token)
        return {
            "id": team.id,
            "name": team.name,
            "unlocked_level": manager.unlocked_level(team.id),
            "achievement_points": achievements.points(team.id),
            "achievements": achievements.for_team(team.id),
            "runs": db.runs_for_team(team.id),
        }

    @app.get("/api/runs/active")
    def active_runs() -> list[dict[str, Any]]:
        return [info.to_dict() for info in manager.active_runs()]

    @app.get("/api/runs/{run_id}")
    def run_details(run_id: str) -> dict[str, Any]:
        info = manager.get(run_id)
        if info is None:
            raise HTTPException(status_code=404, detail="Partie inconnue")
        return info.to_dict()

    @app.get("/api/runs/{run_id}/replay")
    def run_replay(run_id: str) -> dict[str, Any]:
        """Graine + actions de chaque niveau (léger)."""
        replay = db.load_replay(run_id)
        if replay is None:
            raise HTTPException(status_code=404, detail="Replay inconnu")
        return replay

    @app.get("/api/runs/{run_id}/replay/{level_index}")
    def run_replay_frames(run_id: str, level_index: int) -> list[dict[str, Any]]:
        """Toutes les images d'un niveau du replay (level_index = 0 pour le premier niveau joué)."""
        replay = db.load_replay(run_id)
        if replay is None or not 0 <= level_index < len(replay["levels"]):
            raise HTTPException(status_code=404, detail="Replay inconnu")
        return replay_frames(replay, level_index)

    @app.get("/api/live")
    def live_state() -> dict[str, Any]:
        """État du direct en HTTP (secours si le WebSocket est bloqué)."""
        return hub.snapshot(ALL)

    @app.get("/live", response_class=HTMLResponse)
    def live_page() -> str:
        return LIVE_PAGE.read_text(encoding="utf-8")

    @app.get("/api/protocol/schema")
    def protocol_schema() -> dict[str, Any]:
        return json_schemas()

    # ---------- WebSocket des bots ----------

    @app.websocket("/ws/bot")
    async def bot_socket(
        websocket: WebSocket,
        token: str | None = None,
        mode: str = "practice",
        level: int | None = None,
        seed: int | None = None,
    ) -> None:
        await websocket.accept()

        team = teams.authenticate(token)
        if team is None:
            await _refuse(websocket, "Token invalide", CLOSE_UNAUTHORIZED)
            return
        try:
            run_mode = RunMode(mode)
        except ValueError:
            await _refuse(websocket, "mode doit valoir 'practice' ou 'campaign'", CLOSE_BAD_REQUEST)
            return
        try:
            info = manager.prepare(team, run_mode, level, seed)
        except RunRejected as exc:
            await _refuse(websocket, str(exc), CLOSE_REJECTED)
            return

        await manager.execute(info, WebSocketConnection(websocket))
        try:
            await websocket.close()
        except RuntimeError:
            pass  # déjà fermé par le bot

    # ---------- WebSockets des spectateurs ----------

    async def spectate(websocket: WebSocket, channel: str) -> None:
        await websocket.accept()
        queue = hub.subscribe(channel)
        try:
            await websocket.send_json(hub.snapshot(channel))
            while True:
                await websocket.send_json(await queue.get())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            hub.unsubscribe(channel, queue)

    @app.websocket("/ws/live")
    async def live_featured(websocket: WebSocket) -> None:
        await spectate(websocket, FEATURED)

    @app.websocket("/ws/live/all")
    async def live_all(websocket: WebSocket) -> None:
        await spectate(websocket, ALL)

    @app.websocket("/ws/live/run/{run_id}")
    async def live_run(websocket: WebSocket, run_id: str) -> None:
        await spectate(websocket, run_channel(run_id))

    return app


async def _refuse(websocket: WebSocket, message: str, code: int) -> None:
    await websocket.send_json(ErrorMessage(message=message).model_dump())
    await websocket.close(code=code)
