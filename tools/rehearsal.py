"""Répétition générale : simule l'événement contre un serveur qui tourne.

Pour chaque équipe du fichier teams.json : une campagne (bot de référence) ET une partie
d'entraînement au comportement « difficile » (lent, actions invalides, déconnexion…),
soit 10 parties simultanées pour 5 équipes, plus quelques écrans spectateurs.

    python tools/rehearsal.py --url ws://localhost:8000 --teams teams.json

⚠️ Les parties sont enregistrées dans la base du serveur : remettez-la à zéro après
(POST /api/admin/reset avec {"confirm": "RESET"}).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import random
import time
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlencode

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

REFERENCE_BOT = Path(__file__).parent / "bots" / "reference_bot.py"
MOVES = ["MOVE_UP", "MOVE_DOWN", "MOVE_LEFT", "MOVE_RIGHT"]
PRACTICE_BEHAVIOURS = ["random", "slow", "invalid", "disconnect", "reference"]


def fresh_reference_bot() -> ModuleType:
    """Une instance par bot : le bot de référence garde une mémoire au niveau du module."""
    spec = importlib.util.spec_from_file_location(f"ref_{random.random()}", REFERENCE_BOT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def bot(url: str, token: str, mode: str, behaviour: str) -> dict[str, Any]:
    params = {"token": token, "mode": mode}
    if mode == "practice":
        params["level"] = 1
    reference = fresh_reference_bot()
    started = time.monotonic()
    result: dict[str, Any] = {"mode": mode, "behaviour": behaviour, "status": "?"}
    timeout = 0.3
    try:
        async with connect(f"{url}/ws/bot?{urlencode(params)}", max_size=2**22) as ws:
            async for raw in ws:
                message = json.loads(raw)
                kind = message["type"]
                if kind == "hello":
                    timeout = message["tick_timeout"]
                    result["run_id"] = message["run_id"]
                elif kind == "observation":
                    tick = message["tick"]
                    if behaviour == "disconnect" and tick >= 30:
                        result["status"] = "client parti (voulu)"
                        break
                    if behaviour == "slow" and tick % 5 == 4:
                        await asyncio.sleep(timeout * 1.5)  # dépasse le délai une fois sur 5
                    if behaviour == "reference":
                        action = reference.decide(message["data"])
                    elif behaviour == "invalid" and tick % 3 == 0:
                        action = "SAUTER"
                    else:
                        action = random.choice(MOVES)
                    try:
                        await ws.send(json.dumps({"type": "action", "tick": tick, "action": action}))
                    except ConnectionClosed:
                        pass  # trop tard : la partie est finie, on lit encore le message de fin
                elif kind == "run_end":
                    result.update(
                        status=message["status"],
                        score=message["score"],
                        ticks=message["total_ticks"],
                        achievements=len(message["achievements"]),
                    )
                    break
                elif kind == "error":
                    result["status"] = f"refusé : {message['message']}"
                    break
    except (ConnectionClosed, OSError) as exc:
        result["status"] = f"erreur : {exc}"
    result["seconds"] = round(time.monotonic() - started, 1)
    return result


async def spectator(url: str, path: str, stop: asyncio.Event) -> dict[str, int]:
    counts: dict[str, int] = {}
    async with connect(f"{url}{path}", max_size=2**22) as ws:
        while not stop.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
            except TimeoutError:
                continue
            kind = json.loads(raw)["type"]
            counts[kind] = counts.get(kind, 0) + 1
    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="ws://localhost:8000")
    parser.add_argument("--teams", default="teams.json")
    args = parser.parse_args()
    teams = json.loads(Path(args.teams).read_text(encoding="utf-8"))

    stop = asyncio.Event()
    screens = [
        asyncio.create_task(spectator(args.url, path, stop))
        for path in ("/ws/live", "/ws/live/all", "/ws/live/all")
    ]
    await asyncio.sleep(0.5)

    jobs = []
    for index, team in enumerate(teams):
        practice = PRACTICE_BEHAVIOURS[index % len(PRACTICE_BEHAVIOURS)]
        jobs.append((team["name"], bot(args.url, team["token"], "campaign", "reference")))
        jobs.append((team["name"], bot(args.url, team["token"], "practice", practice)))
    print(f"{len(jobs)} parties simultanées, {len(screens)} écrans spectateurs…")
    results = await asyncio.gather(*(job for _, job in jobs))

    await asyncio.sleep(1)
    stop.set()
    spectators = await asyncio.gather(*screens)

    print(f"\n{'équipe':<12}{'mode':<10}{'comportement':<13}{'statut':<24}{'ticks':>7}{'score':>8}{'s':>7}")
    for (name, _), r in zip(jobs, results, strict=True):
        print(
            f"{name:<12}{r['mode']:<10}{r['behaviour']:<13}{r['status']:<24}"
            f"{r.get('ticks', '-'):>7}{r.get('score', '-'):>8}{r['seconds']:>7}"
        )
    for path, counts in zip(("/ws/live", "/ws/live/all", "/ws/live/all"), spectators, strict=True):
        print(f"spectateur {path:<14} {counts}")


if __name__ == "__main__":
    asyncio.run(main())
