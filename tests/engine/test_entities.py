import pytest
from wonderland.engine.actions import Direction
from wonderland.engine.entities import Entity, Mob, MobState, Player, Trap


def make_entity(**kwargs) -> Entity:
    return Entity(**{"id": 1, "x": 2, "y": 2, "hp": 3, "max_hp": 3, **kwargs})


def test_partial_damage():
    entity = make_entity()
    assert entity.take_damage(2) == 2
    assert entity.hp == 1
    assert entity.alive


def test_lethal_damage_returns_real_damage():
    entity = make_entity()
    assert entity.take_damage(10) == 3
    assert entity.hp == 0
    assert not entity.alive


def test_heal_is_capped():
    entity = make_entity(hp=1)
    assert entity.heal(5) == 2
    assert entity.hp == 3


@pytest.mark.parametrize("method", ["take_damage", "heal"])
def test_negative_amount_raises(method):
    with pytest.raises(ValueError):
        getattr(make_entity(), method)(-1)


def test_front_and_distance():
    entity = make_entity(facing=Direction.LEFT)
    assert entity.front() == (1, 2)
    assert make_entity(x=0, y=0).distance_to(make_entity(x=3, y=4)) == 7


def test_players_do_not_share_hats():
    a = Player(id=1, x=0, y=0, hp=5, max_hp=5)
    b = Player(id=2, x=0, y=0, hp=5, max_hp=5)
    a.hats.add(42)
    assert b.hats == set()


def test_mob_defaults_to_idle():
    assert Mob(id=1, x=0, y=0, hp=1, max_hp=1).state is MobState.IDLE


def test_periodic_trap():
    trap = Trap(id=1, x=0, y=0, period=4, active_for=2, offset=2)
    assert [trap.is_active(t) for t in range(4)] == [False, False, True, True]
    assert trap.ticks_until_active(0) == 2
    assert trap.ticks_until_active(2) == 0
