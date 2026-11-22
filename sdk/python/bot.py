"""Votre bot. Seule la fonction `decide` est à écrire.

Lancer :
    python bot.py --token VOTRE_TOKEN --level 1
    python bot.py --token VOTRE_TOKEN --mode campaign

`obs` contient notamment :
    obs["you"]      position, PV, direction, arme, cooldown de tir
    obs["grid"]     liste de lignes : '#' mur, '.' sol, '^' piège, '~' brume, 'E' sortie, '?' inconnu
    obs["mobs"]     ennemis visibles (position, PV, état : IDLE / WINDUP / CHARGING / STUNNED)
    obs["items"], obs["traps"], obs["projectiles"], obs["events"], obs["level"]
"""

from __future__ import annotations

import argparse
import random

from wonderland_sdk import play

MOVES = ["MOVE_UP", "MOVE_DOWN", "MOVE_LEFT", "MOVE_RIGHT"]


def decide(obs: dict) -> str:
    # Exemple naïf : marche au hasard. À vous de faire mieux !
    return random.choice(MOVES)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://localhost:8000")
    parser.add_argument("--token", required=True)
    parser.add_argument("--mode", default="practice", choices=["practice", "campaign"])
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    play(decide, url=args.url, token=args.token, mode=args.mode, level=args.level, seed=args.seed)
