"""Bot de référence : prouve que chaque niveau est faisable.

Il n'utilise QUE l'observation JSON, exactement comme le bot d'une équipe.
Stratégie, par priorité :
    1. défense : parer un coup armé, un projectile ou une charge qui arrive
    2. corps-à-corps sur un mob adjacent (se tourner puis frapper)
    3. tirer si un mob est aligné devant soi
    4. aller vers un objectif : objets → Reine (niveau boss) → sortie → exploration
       (plus court chemin, en évitant les pièges et en attendant qu'ils se désactivent)

⚠️ Ne pas distribuer aux équipes : c'est la solution !
"""

from __future__ import annotations

import heapq
from typing import Any

DIRS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
TRAP_COST = 8
MOB_COST = 15

_memory: dict[str, Any] = {"level": None, "items": {}}


def decide(obs: dict[str, Any]) -> str:
    me = obs["you"]
    pos = (me["x"], me["y"])
    _remember(obs)

    action = _defend(obs, pos) or _melee(obs, pos, me) or _shoot(obs, pos, me)
    if action:
        return action
    return _navigate(obs, pos, me)


# ---------- mémoire ----------


def _remember(obs: dict[str, Any]) -> None:
    if obs["tick"] == 0 or _memory["level"] != obs["level"]["id"]:
        _memory["level"] = obs["level"]["id"]
        _memory["items"] = {}
    for item in obs["items"]:
        _memory["items"][item["id"]] = item
    for event in obs["events"]:
        if event["type"] == "ItemPicked":
            _memory["items"].pop(event["item_id"], None)


# ---------- 1. défense ----------


def _defend(obs: dict[str, Any], pos: tuple[int, int]) -> str | None:
    incoming = 0
    for mob in obs["mobs"]:
        dx, dy = DIRS[mob["facing"]]
        if mob["state"] == "WINDUP" and (mob["x"] + dx, mob["y"] + dy) == pos:
            incoming += 2 if mob["boss"] else 1
    if incoming:
        # Encerclé : si on peut encaisser, on profite d'un mob étourdi pour frapper.
        stunned_adjacent = any(
            m["state"] == "STUNNED" and abs(m["x"] - pos[0]) + abs(m["y"] - pos[1]) == 1
            for m in obs["mobs"]
        )
        if not (stunned_adjacent and obs["you"]["hp"] > incoming + 1):
            return "PARRY"
    for mob in obs["mobs"]:
        if mob["state"] == "CHARGING":
            distance = _heading_distance(obs, (mob["x"], mob["y"]), mob["facing"], pos)
            if distance is not None:
                if distance <= 2:
                    return "PARRY"
                return _sidestep(obs, pos, mob["facing"]) or "PARRY"
    for projectile in obs["projectiles"]:
        if not projectile["hostile"]:
            continue
        start = (projectile["x"], projectile["y"])
        distance = _heading_distance(obs, start, projectile["direction"], pos)
        if distance is not None and distance <= projectile["speed"]:
            return "PARRY"
    return None


def _heading_distance(
    obs: dict[str, Any], start: tuple[int, int], facing: str, target: tuple[int, int]
) -> int | None:
    """Distance si `target` est droit devant `start` sans mur entre les deux."""
    dx, dy = DIRS[facing]
    x, y = start
    for distance in range(1, 20):
        x, y = x + dx, y + dy
        if not _in_grid(obs, x, y) or obs["grid"][y][x] == "#":
            return None
        if (x, y) == target:
            return distance
    return None


def _sidestep(obs: dict[str, Any], pos: tuple[int, int], facing: str) -> str | None:
    perpendicular = ("LEFT", "RIGHT") if facing in ("UP", "DOWN") else ("UP", "DOWN")
    for name in perpendicular:
        dx, dy = DIRS[name]
        if _walkable(obs, pos[0] + dx, pos[1] + dy) and not _trap_active(obs, pos[0] + dx, pos[1] + dy):
            return f"MOVE_{name}"
    return None


# ---------- 2. corps-à-corps ----------


def _melee(obs: dict[str, Any], pos: tuple[int, int], me: dict[str, Any]) -> str | None:
    adjacent = [m for m in obs["mobs"] if abs(m["x"] - pos[0]) + abs(m["y"] - pos[1]) == 1]
    if not adjacent:
        return None
    fx, fy = DIRS[me["facing"]]
    if any((m["x"], m["y"]) == (pos[0] + fx, pos[1] + fy) for m in adjacent):
        return "ATTACK"  # déjà tourné vers un mob : ne pas perdre un tick à pivoter
    adjacent.sort(key=lambda m: (m["state"] != "STUNNED", m["hp"], m["id"]))
    target = adjacent[0]
    direction = _direction_to(pos, (target["x"], target["y"]))
    if me["facing"] == direction:
        return "ATTACK"
    return f"MOVE_{direction}"  # case occupée → le joueur se tourne sans bouger


# ---------- 3. tir ----------


def _shoot(obs: dict[str, Any], pos: tuple[int, int], me: dict[str, Any]) -> str | None:
    if me["weapon"] != "SUGAR_LAUNCHER" or me["shoot_cooldown"] > 0:
        return None
    for mob in obs["mobs"]:
        distance = _heading_distance(obs, pos, me["facing"], (mob["x"], mob["y"]))
        if distance is not None and distance <= 6:
            return "SHOOT"
    return None


# ---------- 4. navigation ----------


def _navigate(obs: dict[str, Any], pos: tuple[int, int], me: dict[str, Any]) -> str:
    goals = _goals(obs, me)
    for goal_set in goals:
        found = _first_step(obs, pos, goal_set)
        if found is None:
            continue
        step, reached = found
        if obs["grid"][reached[1]][reached[0]] == "?":
            _memory["explore_target"] = reached
        nx, ny = pos[0] + DIRS[step][0], pos[1] + DIRS[step][1]
        trap = next((t for t in obs["traps"] if (t["x"], t["y"]) == (nx, ny)), None)
        if trap and trap["active_this_turn"]:
            always_on = trap["period"] == trap["active_for"]
            if not always_on or me["hp"] <= trap["damage"]:
                return "WAIT"  # on attend que le piège se désactive (ou on reste prudent)
        return f"MOVE_{step}"
    return "WAIT"


def _goals(obs: dict[str, Any], me: dict[str, Any]) -> list[set[tuple[int, int]]]:
    goals: list[set[tuple[int, int]]] = []
    wanted = {"HAT", "LAUNCHER"} | ({"POTION"} if me["hp"] < me["max_hp"] else set())
    items = {(i["x"], i["y"]) for i in _memory["items"].values() if i["kind"] in wanted}
    if items:
        goals.append(items)
    if obs["level"]["win_condition"] == "boss":
        boss = [m for m in obs["mobs"] if m["boss"]]
        if boss:
            bx, by = boss[0]["x"], boss[0]["y"]
            goals.append({(bx + dx, by + dy) for dx, dy in DIRS.values()})
    exits = {(x, y) for y, row in enumerate(obs["grid"]) for x, c in enumerate(row) if c == "E"}
    if exits:
        goals.append(exits)
    unknown = {(x, y) for y, row in enumerate(obs["grid"]) for x, c in enumerate(row) if c == "?"}
    if unknown:
        # On garde la même cible d'exploration tant qu'elle reste inconnue (évite les allers-retours).
        target = _memory.get("explore_target")
        if target in unknown:
            goals.append({target})
        goals.append(unknown)
    return goals


def _first_step(
    obs: dict[str, Any], start: tuple[int, int], goals: set[tuple[int, int]]
) -> tuple[str, tuple[int, int]] | None:
    """Dijkstra : renvoie (premier pas, objectif atteint). Pièges et mobs coûteux."""
    blocked = {(m["x"], m["y"]) for m in obs["mobs"]}
    traps = {(t["x"], t["y"]) for t in obs["traps"]}
    queue: list[tuple[int, int, tuple[int, int], str | None]] = [(0, 0, start, None)]
    best: dict[tuple[int, int], int] = {start: 0}
    counter = 0
    while queue:
        cost, _, current, first = heapq.heappop(queue)
        if current in goals and current != start and first is not None:
            return first, current
        if cost > best.get(current, 10**9):
            continue
        if current != start and obs["grid"][current[1]][current[0]] == "?":
            continue  # on n'étend pas le chemin à travers l'inconnu
        for name, (dx, dy) in DIRS.items():
            nxt = (current[0] + dx, current[1] + dy)
            if not _in_grid(obs, *nxt) or obs["grid"][nxt[1]][nxt[0]] == "#":
                continue
            step_cost = cost + 1
            if nxt in traps:
                step_cost += TRAP_COST
            if nxt in blocked:
                step_cost += MOB_COST  # on passera « à travers » en combattant
            if step_cost < best.get(nxt, 10**9):
                best[nxt] = step_cost
                counter += 1
                heapq.heappush(queue, (step_cost, counter, nxt, first or name))
    return None


# ---------- utilitaires ----------


def _in_grid(obs: dict[str, Any], x: int, y: int) -> bool:
    return 0 <= x < obs["width"] and 0 <= y < obs["height"]


def _walkable(obs: dict[str, Any], x: int, y: int) -> bool:
    if not _in_grid(obs, x, y) or obs["grid"][y][x] in "#?":
        return False
    return all((m["x"], m["y"]) != (x, y) for m in obs["mobs"])


def _trap_active(obs: dict[str, Any], x: int, y: int) -> bool:
    return any((t["x"], t["y"]) == (x, y) and t["active_this_turn"] for t in obs["traps"])


def _direction_to(a: tuple[int, int], b: tuple[int, int]) -> str:
    delta = (b[0] - a[0], b[1] - a[1])
    return next(name for name, d in DIRS.items() if d == delta)
