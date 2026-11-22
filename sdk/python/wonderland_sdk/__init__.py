"""SDK Wonderland : connecte votre fonction `decide(obs)` au serveur de jeu.

Vous n'avez rien à modifier ici : écrivez votre algorithme dans bot.py.

    from wonderland_sdk import play

    def decide(obs: dict) -> str:
        return "MOVE_RIGHT"

    play(decide, url="ws://localhost:8000", token="...", mode="practice", level=1)
"""

from __future__ import annotations

import json
import traceback
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

ACTIONS = (
    "MOVE_UP",
    "MOVE_DOWN",
    "MOVE_LEFT",
    "MOVE_RIGHT",
    "ATTACK",
    "SHOOT",
    "PARRY",
    "WAIT",
)

Decide = Callable[[dict[str, Any]], str]


class ServerError(RuntimeError):
    """Le serveur a refusé la partie (token, niveau non débloqué, cooldown…)."""


def play(
    decide: Decide,
    *,
    url: str = "ws://localhost:8000",
    token: str,
    mode: str = "practice",
    level: int | None = 1,
    seed: int | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Joue une partie complète et renvoie le message de fin (run_end).

    mode="practice" : un seul niveau (`level`), graine fixable avec `seed` pour débugger.
    mode="campaign" : niveaux 1 à 5 enchaînés, graine aléatoire.
    """
    params: dict[str, Any] = {"token": token, "mode": mode}
    if mode == "practice" and level is not None:
        params["level"] = level
    if seed is not None:
        params["seed"] = seed
    address = f"{url.rstrip('/')}/ws/bot?{urlencode(params)}"

    log = print if verbose else (lambda *args, **kwargs: None)
    with connect(address, max_size=2**22) as ws:
        while True:
            try:
                message = json.loads(ws.recv())
            except ConnectionClosed as exc:
                raise ServerError(f"Connexion fermée par le serveur ({exc})") from exc

            kind = message.get("type")
            if kind == "observation":
                action = _safe_decide(decide, message["data"])
                ws.send(json.dumps({"type": "action", "tick": message["tick"], "action": action}))
            elif kind == "hello":
                log(f"Partie {message['run_id']} ({message['mode']}) niveaux {message['levels']}")
            elif kind == "level_start":
                seed_info = f" (seed {message['seed']})" if message.get("seed") is not None else ""
                log(f"→ Niveau {message['level']} : {message['name']}{seed_info}")
            elif kind == "level_end":
                log(f"  {message['status']} en {message['ticks']} ticks, PV {message['hp']}")
            elif kind == "run_end":
                log(f"Fin de partie : {message['status']}, niveaux réussis {message['levels_completed']}")
                return message
            elif kind == "error":
                raise ServerError(message["message"])


def _safe_decide(decide: Decide, obs: dict[str, Any]) -> str:
    """Un bug dans decide() ne doit pas couper la partie : on joue WAIT et on affiche l'erreur."""
    try:
        action = decide(obs)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return "WAIT"
    return str(action)
