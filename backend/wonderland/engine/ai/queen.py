"""La Reine de Cœur : boss en 3 phases, lisible via son état dans l'observation.

Phase 1 (> 60 % PV) : avance lentement, invoque des gardes-cartes, charge parfois.
Phase 2 (> 25 % PV) : quand le joueur est aligné, charge (1 fois sur 2) ou lance un hérisson.
Phase 3            : charge dès que le joueur est aligné.

En marchant elle contourne les pièges, mais quand elle CHARGE elle ne regarde plus
où elle met les pieds : une charge qui finit sur un piège actif l'étourdit dessus,
et les pièges lui infligent double dégâts. Une charge contre un mur l'étourdit aussi.
→ Il est possible de la vaincre sans la toucher (succès « Partie de croquet truquée »).
"""

from __future__ import annotations

from wonderland.engine.ai.base import (
    DIRECTIONS,
    Brain,
    Charge,
    Intent,
    Move,
    Shoot,
    Wait,
    aligned_direction,
    is_free_for_mob,
    step_towards,
)
from wonderland.engine.ai.brains import melee_or_none
from wonderland.engine.entities import Mob
from wonderland.engine.events import BossPhaseChanged, Event, MobSpawned
from wonderland.engine.state import GameState

FIRST_SUMMON_TICK = 10
SUMMON_EVERY = {1: 15, 2: 20}
SUMMON_COUNT = 2
MAX_MINIONS = 3
CHARGE_RANGE = 12
CHARGE_CHANCE = {1: 0.3, 2: 0.5, 3: 1.0}  # probabilité de charger quand le joueur est aligné
HEDGEHOG_SPEED = 1
HEDGEHOG_RANGE = 10
HEDGEHOG_COOLDOWN = 4


def queen_phase(mob: Mob) -> int:
    ratio = mob.hp / mob.max_hp
    if ratio > 0.6:
        return 1
    if ratio > 0.25:
        return 2
    return 3


class QueenBrain(Brain):
    def decide(self, state: GameState, mob: Mob, events: list[Event]) -> Intent:
        phase = queen_phase(mob)
        if phase != mob.memory.get("phase", 1):
            mob.memory["phase"] = phase
            events.append(BossPhaseChanged(mob.id, phase))

        if phase in SUMMON_EVERY:
            self._maybe_summon(state, mob, phase, events)

        intent = melee_or_none(state, mob)
        if intent is not None:
            return intent

        if mob.attack_cooldown == 0:
            direction = aligned_direction(state, mob, CHARGE_RANGE)
            if direction is not None:
                if state.rng.random() < CHARGE_CHANCE[phase]:
                    return Charge(direction)
                if phase >= 2 and mob.distance_to(state.player) <= HEDGEHOG_RANGE:
                    return Shoot(
                        direction, HEDGEHOG_SPEED, HEDGEHOG_RANGE, HEDGEHOG_COOLDOWN, "hedgehog"
                    )

        # En marchant elle contourne les pièges ; c'est en CHARGEANT qu'elle ne regarde plus.
        step = step_towards(state, mob, state.player.position, avoid_traps=True)
        return Move(step) if step is not None else Wait()

    def _maybe_summon(self, state: GameState, mob: Mob, phase: int, events: list[Event]) -> None:
        if state.tick < mob.memory.get("next_summon", FIRST_SUMMON_TICK):
            return
        mob.memory["next_summon"] = state.tick + SUMMON_EVERY[phase]

        minions = [mid for mid in mob.memory.get("minions", []) if mid in state.mobs]
        summoned = 0
        for direction in DIRECTIONS:
            if summoned >= SUMMON_COUNT or len(minions) >= MAX_MINIONS:
                break
            x, y = mob.x + direction.dx, mob.y + direction.dy
            if not is_free_for_mob(state, x, y, avoid_traps=True):
                continue
            guard = state.add_mob("card_guard", x, y, brain="chaser", sight=40)
            minions.append(guard.id)
            summoned += 1
            events.append(MobSpawned(guard.id, guard.kind, x, y))
        mob.memory["minions"] = minions
