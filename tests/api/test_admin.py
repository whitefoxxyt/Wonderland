"""Routes admin."""

from __future__ import annotations

import pytest
from conftest import fast_settings, load_reference_bot
from fastapi.testclient import TestClient
from wonderland.api.app import create_app
from wonderland.persistence import Database
from wonderland.teams import Team, TeamRegistry

TOKEN = "team-token"
ADMIN = {"X-Admin-Token": "admin-secret"}


def build(admin_token: str = "admin-secret") -> TestClient:
    settings = fast_settings(admin_token=admin_token, tick_timeout=1.0)
    app = create_app(settings, TeamRegistry([Team("t1", "Equipe", TOKEN)]), Database(":memory:"))
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    return build()


def play_level_1(client: TestClient) -> dict:
    decide = load_reference_bot().decide
    with client.websocket_connect(f"/ws/bot?token={TOKEN}&mode=practice&level=1") as ws:
        while (message := ws.receive_json())["type"] not in ("run_end", "error"):
            if message["type"] == "observation":
                action = decide(message["data"])
                ws.send_json({"type": "action", "tick": message["tick"], "action": action})
    return message


def test_admin_disabled_without_token():
    assert build(admin_token="").get("/api/admin/status").status_code == 403


def test_admin_requires_the_right_token(client):
    assert client.get("/api/admin/status").status_code == 401
    assert client.get("/api/admin/status", headers={"X-Admin-Token": "nope"}).status_code == 401
    status = client.get("/api/admin/status", headers=ADMIN).json()
    assert status["accept_runs"] is True
    assert status["active_runs"] == []


def test_freezing_the_game_refuses_new_runs(client):
    client.post("/api/admin/accept-runs", json={"value": False}, headers=ADMIN)
    assert play_level_1(client)["type"] == "error"
    client.post("/api/admin/accept-runs", json={"value": True}, headers=ADMIN)
    assert play_level_1(client)["status"] == "WON"


def test_frozen_leaderboard_hides_new_results(client):
    client.post("/api/admin/leaderboard/freeze", json={"value": True}, headers=ADMIN)
    play_level_1(client)
    assert client.get("/api/leaderboard").json()[0]["max_level"] == 0  # public : figé
    assert client.get("/api/admin/leaderboard", headers=ADMIN).json()[0]["max_level"] == 1
    client.post("/api/admin/leaderboard/freeze", json={"value": False}, headers=ADMIN)
    assert client.get("/api/leaderboard").json()[0]["max_level"] == 1


def test_second_hints(client):
    hidden = [a for a in client.get("/api/achievements").json() if a["name"] == "???"]
    assert all(a["extra_hint"] is None for a in hidden)
    client.post("/api/admin/hints", json={"level": 2}, headers=ADMIN)
    hidden = [a for a in client.get("/api/achievements").json() if a["name"] == "???"]
    assert all(a["extra_hint"] for a in hidden)
    assert client.post("/api/admin/hints", json={"level": 3}, headers=ADMIN).status_code == 400


def test_stop_unknown_run(client):
    assert client.post("/api/admin/runs/nope/stop", headers=ADMIN).status_code == 404
    assert client.post("/api/admin/runs/stop-all", headers=ADMIN).json() == {"stopped": 0}


def test_reset_needs_confirmation_and_clears_everything(client):
    play_level_1(client)
    assert client.post("/api/admin/reset", json={"confirm": "oui"}, headers=ADMIN).status_code == 400
    assert client.post("/api/admin/reset", json={"confirm": "RESET"}, headers=ADMIN).json()["reset"]
    me = client.get(f"/api/teams/me?token={TOKEN}").json()
    assert me["unlocked_level"] == 1
    assert me["runs"] == []
    assert not any(a["unlocked"] for a in me["achievements"])
    assert client.get("/api/leaderboard").json()[0]["max_level"] == 0
