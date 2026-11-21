"""Fait jouer un bot local contre le moteur, sans réseau.

Exemples :
    python tools/local_runner.py --level 1 --bot tools/bots/reference_bot.py
    python tools/local_runner.py --level 3 --seed 7 --delay 0.1
    python tools/local_runner.py --level 5 --quiet

Un bot est un fichier Python qui définit `decide(obs: dict) -> str`.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType

from wonderland.engine import Engine, observe, render
from wonderland.engine.state import GameState
from wonderland.levels import load_level

DEFAULT_BOT = Path(__file__).parent / "bots" / "reference_bot.py"


def load_bot(path: str | Path) -> ModuleType:
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"bot_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Impossible de charger le bot {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "decide"):
        raise SystemExit(f"{path} doit définir decide(obs)")
    return module


def play(level: int, bot: ModuleType, seed: int, *, delay: float = 0.0, quiet: bool = False) -> GameState:
    state = load_level(level, seed=seed)
    engine = Engine()
    while state.running:
        try:
            action = bot.decide(observe(state))
        except Exception as exc:  # noqa: BLE001 — un bot qui plante ne doit pas planter le moteur
            print(f"[tick {state.tick}] le bot a levé {exc!r}", file=sys.stderr)
            action = None
        events = engine.step(state, action)
        if not quiet:
            print("\033[H\033[J" if delay else "", end="")
            print(render(state))
            print("  " + ", ".join(e.type for e in events))
            if delay:
                time.sleep(delay)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--bot", default=str(DEFAULT_BOT))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--delay", type=float, default=0.0, help="secondes entre deux ticks (animation)")
    parser.add_argument("--quiet", action="store_true", help="n'affiche que le résultat")
    args = parser.parse_args()

    state = play(args.level, load_bot(args.bot), args.seed, delay=args.delay, quiet=args.quiet)
    print(
        f"\nNiveau {args.level} : {state.status.name} en {state.tick} ticks, "
        f"PV {state.player.hp}/{state.player.max_hp}, chapeaux {len(state.player.hats)}, "
        f"mobs restants {len(state.mobs)}"
    )


if __name__ == "__main__":
    main()
