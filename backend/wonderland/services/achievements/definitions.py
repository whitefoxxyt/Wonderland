"""Les 16 succès du jeu. Pour en ajouter un : une classe ici + l'ajouter à ALL_ACHIEVEMENTS."""

from __future__ import annotations

from functools import cache

from wonderland.engine.events import (
    DamageDealt,
    Event,
    InvalidAction,
    ItemPicked,
    MobKilled,
    ParrySucceeded,
    PlayerDied,
    PlayerMoved,
    PlayerWaited,
    TimedOut,
    TrapTriggered,
)
from wonderland.engine.state import GameState, Status
from wonderland.levels import available_levels, level_summary
from wonderland.runs.models import RunMode, RunStatus
from wonderland.services.achievements.base import Achievement, AchievementContext

BOSS_LEVEL = 5
TIME_LIMIT_TICKS = 900  # « 15 minutes » : 1 tick = 1 seconde de jeu
TEA_CHAIR = (2, (11, 9))  # (niveau, case) : la chaise vide de la table du thé
CHESHIRE_SPOT = (3, (10, 2))  # (niveau, case) : au cœur de la brume


@cache
def _hats() -> set[str]:
    return {f"{n}:{x}:{y}" for n in available_levels() for x, y in level_summary(n)["hats"]}


@cache
def _levels_with_mobs() -> set[int]:
    return {n for n in available_levels() if level_summary(n)["mobs"] > 0}


def _won(state: GameState, level: int | None = None) -> bool:
    return state.status is Status.WON and (level is None or state.config.level_id == level)


# ---------- visibles dès le départ ----------


class DownTheRabbitHole(Achievement):
    id = "down_the_rabbit_hole"
    name = "Dans le terrier"
    description = "Terminer le niveau 1."
    hint = "Suivez le Lapin Blanc."
    points = 10
    hidden = False

    def on_level_end(self, ctx: AchievementContext, state: GameState) -> bool:
        return _won(state, 1)


class FirstToCourt(Achievement):
    id = "first_to_court"
    name = "Premier à la cour"
    description = "Être la première équipe à vaincre la Reine de Cœur."
    hint = "Il n'y aura qu'un seul élu."
    points = 200
    hidden = False

    def on_level_end(self, ctx: AchievementContext, state: GameState) -> bool:
        return _won(state, BOSS_LEVEL) and not ctx.holders()


# ---------- cachés ----------


class LateRabbit(Achievement):
    id = "late_rabbit"
    name = "Je suis en retard !"
    description = f"Terminer la campagne en moins de {TIME_LIMIT_TICKS} ticks (15 minutes de jeu)."
    hint = "Le Lapin n'a jamais le temps…"
    points = 150

    def on_run_end(self, ctx: AchievementContext) -> bool:
        run = ctx.run
        return (
            run.mode is RunMode.CAMPAIGN
            and run.status is RunStatus.WON
            and run.total_ticks < TIME_LIMIT_TICKS
        )


class OffWithTheirHeads(Achievement):
    id = "off_with_their_heads"
    name = "Qu'on leur coupe la tête !"
    description = "Gagner chaque niveau peuplé sans laisser un seul ennemi debout."
    hint = "Ne laissez personne derrière vous."
    points = 100

    def on_level_end(self, ctx: AchievementContext, state: GameState) -> bool:
        level = state.config.level_id
        if _won(state) and not state.mobs and level in _levels_with_mobs():
            cleared = set(ctx.progress.get("levels", [])) | {level}
            ctx.progress["levels"] = sorted(cleared)
        return set(ctx.progress.get("levels", [])) >= _levels_with_mobs()


class HatCollector(Achievement):
    id = "hat_collector"
    name = "Collectionneur de chapeaux"
    description = "Ramasser tous les chapeaux du Chapelier fou."
    hint = "Le Chapelier a perdu quelque chose à chaque étape."
    points = 100

    def on_tick(self, ctx: AchievementContext, state: GameState, events: list[Event]) -> bool:
        picked = {
            f"{state.config.level_id}:{e.x}:{e.y}"
            for e in events
            if isinstance(e, ItemPicked) and e.kind == "HAT"
        }
        if not picked:
            return False
        ctx.progress["hats"] = sorted(set(ctx.progress.get("hats", [])) | picked)
        return set(ctx.progress["hats"]) >= _hats()


class MoreDeadThanAlive(Achievement):
    id = "more_dead_than_alive"
    name = "Plus mort que vif"
    description = "Mourir au moins une fois dans chaque niveau."
    hint = "L'échec est aussi un chemin."
    points = 50

    def on_tick(self, ctx: AchievementContext, state: GameState, events: list[Event]) -> bool:
        if not any(isinstance(e, PlayerDied) for e in events):
            return False
        ctx.progress["levels"] = sorted(set(ctx.progress.get("levels", [])) | {state.config.level_id})
        return set(ctx.progress["levels"]) >= set(available_levels())


class _BossDamageTracker(Achievement):
    """Mémorise les causes des dégâts reçus par la Reine pendant le niveau boss."""

    def on_level_start(self, ctx: AchievementContext, state: GameState) -> bool:
        boss = state.boss()
        ctx.scratch["boss_id"] = boss.id if boss else None
        ctx.scratch["causes"] = []
        return False

    def on_tick(self, ctx: AchievementContext, state: GameState, events: list[Event]) -> bool:
        boss_id = ctx.scratch.get("boss_id")
        for e in events:
            if isinstance(e, DamageDealt) and e.target_id == boss_id:
                ctx.scratch["causes"].append(e.cause)
        return False


class RiggedCroquet(_BossDamageTracker):
    id = "rigged_croquet"
    name = "Partie de croquet truquée"
    description = "Vaincre la Reine de Cœur sans jamais la frapper ni lui tirer dessus."
    hint = "La Reine ne regarde jamais où elle met les pieds."
    points = 200

    def on_level_end(self, ctx: AchievementContext, state: GameState) -> bool:
        causes = set(ctx.scratch.get("causes", []))
        return _won(state, BOSS_LEVEL) and not causes & {"melee", "projectile"}


class KnifeIsEnough(_BossDamageTracker):
    id = "knife_is_enough"
    name = "Le couteau suffit"
    description = "Vaincre la Reine de Cœur uniquement au couteau."
    hint = "Un vrai duel ne se fait pas de loin."
    points = 150

    def on_level_end(self, ctx: AchievementContext, state: GameState) -> bool:
        causes = set(ctx.scratch.get("causes", []))
        return _won(state, BOSS_LEVEL) and causes == {"melee"}


class _StayStill(Achievement):
    """Rester N ticks d'affilée sur une case précise d'un niveau."""

    spot: tuple[int, tuple[int, int]] = (0, (0, 0))
    ticks_needed = 1
    waits_only = False

    def on_tick(self, ctx: AchievementContext, state: GameState, events: list[Event]) -> bool:
        level, position = self.spot
        here = state.config.level_id == level and state.player.position == position
        moved = any(isinstance(e, PlayerMoved) for e in events)
        waited = any(isinstance(e, PlayerWaited) for e in events)
        if here and not moved and (waited or not self.waits_only):
            ctx.scratch["count"] = ctx.scratch.get("count", 0) + 1
        else:
            ctx.scratch["count"] = 0
        return ctx.scratch["count"] >= self.ticks_needed


class TeaTime(_StayStill):
    id = "tea_time"
    name = "Il est toujours six heures"
    description = "Rester assis 6 ticks sur la chaise vide de la table du thé (niveau 2)."
    hint = "Au thé, il faut savoir s'asseoir."
    points = 50
    spot = TEA_CHAIR
    ticks_needed = 6


class CheshireSmile(_StayStill):
    id = "cheshire_smile"
    name = "Le sourire sans le chat"
    description = "Attendre 3 ticks au cœur de la brume de la forêt (niveau 3)."
    hint = "Certains n'apparaissent qu'à ceux qui attendent dans la brume."
    points = 75
    spot = CHESHIRE_SPOT
    ticks_needed = 3
    waits_only = True


class RoyalGuard(Achievement):
    id = "royal_guard"
    name = "Garde royale"
    description = "Réussir 10 parades dans une même partie."
    hint = "La meilleure attaque…"
    points = 75

    def on_tick(self, ctx: AchievementContext, state: GameState, events: list[Event]) -> bool:
        ctx.scratch["parries"] = ctx.scratch.get("parries", 0) + sum(
            1 for e in events if isinstance(e, ParrySucceeded)
        )
        return ctx.scratch["parries"] >= 10


class NotAScratch(Achievement):
    id = "not_a_scratch"
    name = "Sans une égratignure"
    description = "Terminer le niveau 2 sans perdre un seul PV."
    hint = "Un thé, pas une bagarre."
    points = 75

    def on_level_start(self, ctx: AchievementContext, state: GameState) -> bool:
        ctx.scratch["hurt"] = False
        return False

    def on_tick(self, ctx: AchievementContext, state: GameState, events: list[Event]) -> bool:
        if any(isinstance(e, DamageDealt) and e.target_id == state.player.id for e in events):
            ctx.scratch["hurt"] = True
        return False

    def on_level_end(self, ctx: AchievementContext, state: GameState) -> bool:
        return _won(state, 2) and not ctx.scratch.get("hurt", True)


class ShortestPath(Achievement):
    id = "shortest_path"
    name = "Tout droit, sans hésiter"
    description = "Terminer le labyrinthe (niveau 4) sans jamais repasser par la même case."
    hint = "Tout droit, sans hésiter."
    points = 100

    def on_level_start(self, ctx: AchievementContext, state: GameState) -> bool:
        ctx.scratch["visited"] = {state.player.position}
        ctx.scratch["clean"] = True
        return False

    def on_tick(self, ctx: AchievementContext, state: GameState, events: list[Event]) -> bool:
        for e in events:
            if isinstance(e, PlayerMoved):
                if (e.x, e.y) in ctx.scratch["visited"]:
                    ctx.scratch["clean"] = False
                ctx.scratch["visited"].add((e.x, e.y))
        return False

    def on_level_end(self, ctx: AchievementContext, state: GameState) -> bool:
        return _won(state, 4) and ctx.scratch.get("clean", False)


class CleanCode(Achievement):
    id = "clean_code"
    name = "Code propre"
    description = "Gagner une campagne sans aucune action invalide ni dépassement de temps."
    hint = "Le Lapin déteste attendre une réponse."
    points = 100

    def on_tick(self, ctx: AchievementContext, state: GameState, events: list[Event]) -> bool:
        if any(isinstance(e, (InvalidAction, TimedOut)) for e in events):
            ctx.scratch["dirty"] = True
        return False

    def on_run_end(self, ctx: AchievementContext) -> bool:
        run = ctx.run
        return (
            run.mode is RunMode.CAMPAIGN
            and run.status is RunStatus.WON
            and not ctx.scratch.get("dirty", False)
        )


class SugarRain(Achievement):
    id = "sugar_rain"
    name = "Pluie de sucre"
    description = "Abattre 5 ennemis au lance-sucres dans une même partie."
    hint = "Le Chapelier a plus d'un tour dans son sac."
    points = 75

    def on_tick(self, ctx: AchievementContext, state: GameState, events: list[Event]) -> bool:
        ctx.scratch["kills"] = ctx.scratch.get("kills", 0) + sum(
            1 for e in events if isinstance(e, MobKilled) and e.cause == "projectile"
        )
        return ctx.scratch["kills"] >= 5


class Tightrope(Achievement):
    id = "tightrope"
    name = "Pas de deux"
    description = "Dans le labyrinthe, marcher 5 fois sur un piège pile quand il est éteint."
    hint = "Les pièges de la Reine respirent. Apprenez leur rythme."
    points = 75

    def on_tick(self, ctx: AchievementContext, state: GameState, events: list[Event]) -> bool:
        if state.config.level_id != 4:
            return False
        hurt = any(isinstance(e, TrapTriggered) and e.entity_id == state.player.id for e in events)
        for e in events:
            trap = state.traps.get((e.x, e.y)) if isinstance(e, PlayerMoved) else None
            if trap is not None and trap.period > trap.active_for and not hurt:
                ctx.scratch["dances"] = ctx.scratch.get("dances", 0) + 1
        return ctx.scratch.get("dances", 0) >= 5


ALL_ACHIEVEMENTS: list[Achievement] = [
    DownTheRabbitHole(),
    LateRabbit(),
    OffWithTheirHeads(),
    HatCollector(),
    MoreDeadThanAlive(),
    RiggedCroquet(),
    TeaTime(),
    CheshireSmile(),
    RoyalGuard(),
    NotAScratch(),
    ShortestPath(),
    KnifeIsEnough(),
    CleanCode(),
    SugarRain(),
    Tightrope(),
    FirstToCourt(),
]
