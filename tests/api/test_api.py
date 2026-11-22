"""API FastAPI : routes REST et WebSocket des bots (client de test, sans vrai réseau)."""

from __future__ import annotations

import pytest
from conftest import load_reference_bot
from fastapi.testclient import TestClient
from wonderland.api.app import create_app
from wonderland.config import Settings
from wonderland.persistence import Database
from wonderland.teams import Team, TeamRegistry

TOKEN = "secret-token"


@pytest.fixture
def client() -> TestClient:
    settings = Settings()
    settings.tick_timeout = 1.0
    settings.run_cooldown = 0
    settings.campaign_tick_delay = 0
    app = create_app(settings, TeamRegistry([Team("t1", "Equipe test", TOKEN)]), Database(":memory:"))
    return TestClient(app)


def test_health_and_levels(client):
    assert client.get("/api/health").json()["status"] == "ok"
    levels = client.get("/api/levels").json()
    assert [lvl["id"] for lvl in levels] == [1, 2, 3, 4, 5]
    assert levels[4]["win"] == "boss"


def test_protocol_schema(client):
    schema = client.get("/api/protocol/schema").json()
    assert "ActionMessage" in schema


def test_unknown_run_is_404(client):
    assert client.get("/api/runs/nope").status_code == 404


def test_bad_token_is_refused(client):
    with client.websocket_connect("/ws/bot?token=wrong&mode=practice&level=1") as ws:
        message = ws.receive_json()
    assert message == {"type": "error", "message": "Token invalide"}


def test_locked_level_is_refused(client):
    with client.websocket_connect(f"/ws/bot?token={TOKEN}&mode=practice&level=4") as ws:
        message = ws.receive_json()
    assert message["type"] == "error"


def test_full_practice_game_over_websocket(client):
    decide = load_reference_bot().decide
    with client.websocket_connect(f"/ws/bot?token={TOKEN}&mode=practice&level=1&seed=3") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        while True:
            message = ws.receive_json()
            if message["type"] == "observation":
                action = decide(message["data"])
                ws.send_json({"type": "action", "tick": message["tick"], "action": action})
            elif message["type"] == "run_end":
                break
    assert message["status"] == "WON"
    run = client.get(f"/api/runs/{hello['run_id']}").json()
    assert run["levels_completed"] == [1]
    assert run["latency"]["timeouts"] == 0


def test_team_dashboard_requires_token(client):
    assert client.get("/api/teams/me").status_code == 401
    me = client.get("/api/teams/me", headers={"X-Team-Token": TOKEN}).json()
    assert me["unlocked_level"] == 1
    assert len(me["achievements"]) == 16


def test_leaderboard_and_achievements_after_a_game(client):
    decide = load_reference_bot().decide
    with client.websocket_connect(f"/ws/bot?token={TOKEN}&mode=practice&level=1") as ws:
        while (message := ws.receive_json())["type"] != "run_end":
            if message["type"] == "observation":
                action = decide(message["data"])
                ws.send_json({"type": "action", "tick": message["tick"], "action": action})
    assert message["score"] > 1000
    assert "Dans le terrier" in message["achievements"]

    board = client.get("/api/leaderboard").json()
    assert board[0]["max_level"] == 1
    catalog = client.get("/api/achievements").json()
    assert next(a for a in catalog if a["name"] == "Dans le terrier")["teams"] == 1
    assert client.get(f"/api/teams/me?token={TOKEN}").json()["unlocked_level"] == 2


def test_live_page_and_snapshot(client):
    page = client.get("/live")
    assert page.status_code == 200
    assert "/ws/live" in page.text
    with client.websocket_connect("/ws/live") as ws:
        assert ws.receive_json() == {"type": "snapshot", "featured": None, "runs": []}
    assert client.get("/api/live").json()["runs"] == []


def test_replay_routes(client):
    decide = load_reference_bot().decide
    with client.websocket_connect(f"/ws/bot?token={TOKEN}&mode=practice&level=1") as ws:
        run_id = ws.receive_json()["run_id"]
        while (message := ws.receive_json())["type"] != "run_end":
            if message["type"] == "observation":
                action = decide(message["data"])
                ws.send_json({"type": "action", "tick": message["tick"], "action": action})
    replay = client.get(f"/api/runs/{run_id}/replay").json()
    assert replay["levels"][0]["level"] == 1
    frames = client.get(f"/api/runs/{run_id}/replay/0").json()
    assert frames[-1]["status"] == "WON"
    assert client.get(f"/api/runs/{run_id}/replay/5").status_code == 404
