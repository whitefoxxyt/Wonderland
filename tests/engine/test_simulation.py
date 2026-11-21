"""Règles du tick : déplacements, combat, parade, projectiles, pièges, objets, fin de partie."""

import pytest
from conftest import make_state
from wonderland.engine import Action, Direction, GameOverError, Status
from wonderland.engine.entities import MobState, Weapon

# ---------- déplacements ----------


def test_move_and_bump(engine):
    state = make_state(["#####", "#S..#", "#####", "#..E#", "#####"])
    engine.step(state, Action.MOVE_RIGHT)
    assert state.player.position == (2, 1)

    events = engine.step(state, Action.MOVE_UP)
    assert state.player.position == (2, 1)
    assert state.player.facing is Direction.UP  # bloqué, mais tourné
    assert events[0].type == "PlayerBumped"


def test_reaching_exit_wins(engine):
    state = make_state(["#####", "#SE.#", "#####"])
    events = engine.step(state, "MOVE_RIGHT")
    assert state.status is Status.WON
    assert "LevelCompleted" in [e.type for e in events]
    with pytest.raises(GameOverError):
        engine.step(state, Action.WAIT)


@pytest.mark.parametrize("action", [None, "JUMP"])
def test_invalid_action_is_a_wait(engine, action):
    state = make_state(["#####", "#S.E#", "#####"])
    events = engine.step(state, action)
    assert events[0].type == "InvalidAction"
    assert state.player.position == (1, 1)
    assert state.tick == 1


def test_timeout_flag(engine):
    state = make_state(["#####", "#S.E#", "#####"])
    events = engine.step(state, Action.MOVE_RIGHT, timed_out=True)
    assert events[0].type == "TimedOut"
    assert state.player.position == (1, 1)


def test_max_ticks(engine):
    state = make_state(["#####", "#S.E#", "#####"], max_ticks=3)
    for _ in range(3):
        engine.step(state, Action.WAIT)
    assert state.status is Status.TIMEOUT


# ---------- combat ----------


def test_cannot_walk_into_mob_and_attack_kills_it(engine):
    state = make_state(["######", "#Sd.E#", "######"])
    engine.step(state, Action.MOVE_RIGHT)  # bloqué par le loir, mais tourné vers lui
    assert state.player.position == (1, 1)
    events = engine.step(state, Action.ATTACK)
    assert not state.mobs
    assert "MobKilled" in [e.type for e in events]


def test_mob_windup_then_strike(engine):
    state = make_state(["######", "#S.G.#", "######", "#...E#", "######"])
    engine.step(state, Action.MOVE_RIGHT)  # adjacent au garde → il arme
    guard = next(iter(state.mobs.values()))
    assert guard.state is MobState.WINDUP
    engine.step(state, Action.WAIT)
    assert state.player.hp == state.player.max_hp - 1
    assert guard.state is MobState.IDLE


def test_parry_blocks_and_stuns(engine):
    state = make_state(["######", "#S.G.#", "######", "#...E#", "######"])
    engine.step(state, Action.MOVE_RIGHT)
    events = engine.step(state, Action.PARRY)
    guard = next(iter(state.mobs.values()))
    assert state.player.hp == state.player.max_hp
    assert guard.state is MobState.STUNNED
    assert "ParrySucceeded" in [e.type for e in events]


def test_shoot_requires_launcher(engine):
    state = make_state(["#####", "#S.E#", "#####"])
    events = engine.step(state, Action.SHOOT)
    assert events[0].reason == "no_ranged_weapon"


def test_projectile_kills_mob_at_range(engine):
    state = make_state(["#########", "#S....d.#", "#########", "#......E#", "#########"],
                       start_weapon="SUGAR_LAUNCHER")
    state.player.facing = Direction.RIGHT
    engine.step(state, Action.SHOOT)
    for _ in range(2):
        engine.step(state, Action.WAIT)
    assert not state.mobs
    assert state.player.shoot_cooldown > 0


def test_hostile_projectile_can_be_parried(engine):
    state = make_state(["#########", "#S.....A#", "#########", "#......E#", "#########"])
    hits = parries = 0
    for _ in range(12):
        incoming = any(abs(p.x - state.player.x) <= p.speed for p in state.projectiles.values())
        events = engine.step(state, Action.PARRY if incoming else Action.WAIT)
        parries += sum(e.type == "ParrySucceeded" for e in events)
        hits += sum(e.type == "DamageDealt" for e in events)
    assert parries >= 1
    assert hits == 0


# ---------- pièges ----------


def test_always_active_trap_hurts(engine):
    state = make_state(["######", "#S^.E#", "######"])
    engine.step(state, Action.MOVE_RIGHT)
    assert state.player.hp == state.player.max_hp - 1


def test_periodic_trap_can_be_timed(engine):
    traps = {"period": 2, "active_for": 1, "offset": 0}
    state = make_state(["######", "#S^.E#", "######"], traps=traps)
    engine.step(state, Action.WAIT)  # tick 0 : actif
    engine.step(state, Action.MOVE_RIGHT)  # tick 1 : inactif → on passe
    engine.step(state, Action.MOVE_RIGHT)  # tick 2 : actif mais on est reparti
    assert state.player.hp == state.player.max_hp


def test_hidden_trap_revealed_when_adjacent(engine):
    state = make_state(["#######", "#S.._E#", "#######"])
    trap = state.traps[(4, 1)]
    assert not trap.visible
    engine.step(state, Action.MOVE_RIGHT)
    assert not trap.visible
    events = engine.step(state, Action.MOVE_RIGHT)
    assert trap.visible
    assert "TrapRevealed" in [e.type for e in events]


def test_traps_hurt_mobs_and_double_for_boss(engine):
    state = make_state(["#######", "#S.^Q.#", "#######"], win="boss")
    queen = state.boss()
    queen.move_to(3, 1)
    queen.state, queen.state_ticks = MobState.STUNNED, 5  # reste sur le piège
    engine.step(state, Action.WAIT)
    assert queen.hp == queen.max_hp - 2


# ---------- objets ----------


def test_pickups(engine):
    state = make_state(["#######", "#SH+LE#", "#######"])
    state.player.hp = 2
    for _ in range(3):
        engine.step(state, Action.MOVE_RIGHT)
    assert len(state.player.hats) == 1
    assert state.player.hp == 4
    assert state.player.weapon is Weapon.SUGAR_LAUNCHER
    assert not state.items


# ---------- boss ----------


def test_killing_boss_wins(engine):
    state = make_state(["#####", "#SQ.#", "#####"], win="boss")
    queen = state.boss()
    queen.hp = 1
    state.player.facing = Direction.RIGHT
    engine.step(state, Action.ATTACK)
    assert state.status is Status.WON


def test_dying_ends_the_level(engine):
    state = make_state(["######", "#S^..#", "######", "#...E#", "######"])
    state.player.hp = 1
    events = engine.step(state, Action.MOVE_RIGHT)
    assert state.status is Status.DEAD
    assert events[-1].type == "PlayerDied"
