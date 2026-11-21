"""Ramassage automatique des objets sur la case du joueur."""

from __future__ import annotations

from wonderland.engine.entities import ItemKind, Weapon
from wonderland.engine.events import Event, ItemPicked, PlayerHealed, WeaponAcquired
from wonderland.engine.rules import POTION_HEAL
from wonderland.engine.state import GameState


def collect_items(state: GameState, events: list[Event]) -> None:
    player = state.player
    item = state.item_at(*player.position)
    if item is None:
        return

    del state.items[item.id]
    events.append(ItemPicked(item.id, item.kind.name, item.x, item.y))

    if item.kind is ItemKind.HAT:
        player.hats.add(item.id)
    elif item.kind is ItemKind.POTION:
        healed = player.heal(POTION_HEAL)
        events.append(PlayerHealed(healed))
    elif item.kind is ItemKind.LAUNCHER:
        player.weapon = Weapon.SUGAR_LAUNCHER
        events.append(WeaponAcquired(Weapon.SUGAR_LAUNCHER.name))
