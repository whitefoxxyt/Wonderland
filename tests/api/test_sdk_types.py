"""Le SDK TypeScript doit décrire exactement l'observation envoyée par le serveur."""

from __future__ import annotations

import re

from conftest import ROOT
from wonderland.engine import Direction, observe
from wonderland.engine.systems.projectiles import spawn_projectile
from wonderland.levels import load_level

TYPES = (ROOT / "sdk" / "typescript" / "src" / "types.ts").read_text(encoding="utf-8")


def interface_fields(name: str) -> set[str]:
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", TYPES, re.DOTALL)
    assert match, f"interface {name} absente de types.ts"
    return set(re.findall(r"^\s+(\w+)\??:", match.group(1), re.MULTILINE))


def test_typescript_types_match_observation():
    state = load_level(4, seed=1)  # niveau avec mobs, pièges et objets
    state.config.vision_radius = None
    archer = next(m for m in state.mobs.values() if m.kind == "card_archer")
    spawn_projectile(state, archer, Direction.LEFT, from_player=False, damage=1, speed=2,
                     max_range=5, kind="arrow", events=[])
    obs = observe(state)
    assert interface_fields("Observation") == set(obs)
    assert interface_fields("LevelInfo") == set(obs["level"])
    assert interface_fields("You") == set(obs["you"])
    assert interface_fields("Mob") == set(obs["mobs"][0])
    assert interface_fields("Item") == set(obs["items"][0])
    assert interface_fields("Trap") == set(obs["traps"][0])
    assert interface_fields("Projectile") == set(obs["projectiles"][0])
