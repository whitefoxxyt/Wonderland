"""Serveur FastAPI : WebSocket des bots + API REST de consultation.

Lancer le serveur (depuis la racine du projet, venv activé) :
    uvicorn wonderland.api.app:create_app --factory --host 0.0.0.0 --port 8000

Un bot se connecte sur :
    ws://<hôte>:8000/ws/bot?token=<token>&mode=practice&level=1
    ws://<hôte>:8000/ws/bot?token=<token>&mode=campaign
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from wonderland.config import Settings
from wonderland.levels import available_levels
from wonderland.levels.loader import level_path
from wonderland.runs import BotDisconnected, RunManager, RunMode, RunRejected
from wonderland.runs.protocol import ErrorMessage, json_schemas
from wonderland.teams import TeamRegistry

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


def create_app(settings: Settings | None = None, teams: TeamRegistry | None = None) -> FastAPI:
    settings = settings or Settings()
    teams = teams or TeamRegistry.from_file(settings.teams_file)
    manager = RunManager(settings)

    app = FastAPI(title="Wonderland", version="0.1.0")
    app.state.settings = settings
    app.state.teams = teams
    app.state.manager = manager

    # ---------- REST ----------

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "active_runs": len(manager.active_runs())}

    @app.get("/api/levels")
    def levels() -> list[dict[str, Any]]:
        result = []
        for number in available_levels():
            data = json.loads(level_path(number).read_text(encoding="utf-8"))
            result.append(
                {
                    "id": number,
                    "name": data["name"],
                    "max_ticks": data["max_ticks"],
                    "vision_radius": data.get("vision_radius"),
                    "win": data.get("win", "exit"),
                }
            )
        return result

    @app.get("/api/runs/active")
    def active_runs() -> list[dict[str, Any]]:
        return [info.to_dict() for info in manager.active_runs()]

    @app.get("/api/runs/{run_id}")
    def run_details(run_id: str) -> dict[str, Any]:
        info = manager.get(run_id)
        if info is None:
            raise HTTPException(status_code=404, detail="Partie inconnue")
        return info.to_dict()

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

    return app


async def _refuse(websocket: WebSocket, message: str, code: int) -> None:
    await websocket.send_json(ErrorMessage(message=message).model_dump())
    await websocket.close(code=code)
