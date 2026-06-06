# ABOUTME: Integration tests — CREATURE_MOVED / CREATURE_PLACED events drive entity.grid_x/y (#647).
# ABOUTME: Verifies EntityManager subscription, tween enqueue, and idempotent re-subscribe.

from __future__ import annotations

from dataclasses import dataclass

from client_2d.animation import MovementTweenQueue
from client_2d.entities import (
    Entity,
    EntityManager,
    EntityType,
)


@dataclass
class _Pos:
    x: int
    y: int


class _StubEvent:
    def __init__(self, data: dict):
        self.data = data


class _StubBus:
    """Minimal pub/sub stub matching dnd_engine.utils.events.EventBus surface."""

    def __init__(self):
        self._subs: dict = {}

    def subscribe(self, event_type, handler):
        self._subs.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type, handler):
        if event_type in self._subs:
            self._subs[event_type].remove(handler)

    def publish(self, event_type, event):
        for handler in self._subs.get(event_type, []):
            handler(event)


def _make_entity(eid: str, x: int, y: int) -> Entity:
    return Entity(
        entity_id=eid,
        grid_x=x,
        grid_y=y,
        entity_type=EntityType.MONSTER,
    )


class TestEntityManagerEventSync:
    def test_creature_moved_updates_grid_position(self):
        from dnd_engine.utils.events import EventType

        em = EntityManager()
        bus = _StubBus()
        em.subscribe_to_engine_events(bus)
        ent = _make_entity("goblin_1", 5, 5)
        em._add_entity(ent)

        event = _StubEvent({
            "entity_id": "goblin_1",
            "origin": _Pos(5, 5),
            "to": _Pos(6, 5),
        })
        bus.publish(EventType.CREATURE_MOVED, event)

        assert ent.grid_x == 6
        assert ent.grid_y == 5

    def test_creature_placed_snaps_grid_position(self):
        from dnd_engine.utils.events import EventType

        em = EntityManager()
        bus = _StubBus()
        em.subscribe_to_engine_events(bus)
        ent = _make_entity("pc_brick", 0, 0)
        em._add_entity(ent)

        event = _StubEvent({"entity_id": "pc_brick", "position": _Pos(7, 3)})
        bus.publish(EventType.CREATURE_PLACED, event)

        assert ent.grid_x == 7
        assert ent.grid_y == 3

    def test_unknown_entity_id_is_ignored(self):
        from dnd_engine.utils.events import EventType

        em = EntityManager()
        bus = _StubBus()
        em.subscribe_to_engine_events(bus)

        event = _StubEvent({
            "entity_id": "no_such_entity",
            "origin": _Pos(0, 0),
            "to": _Pos(1, 0),
        })
        # Should not raise.
        bus.publish(EventType.CREATURE_MOVED, event)

    def test_tween_queue_receives_enqueue_per_step(self):
        from dnd_engine.utils.events import EventType

        em = EntityManager()
        bus = _StubBus()
        tweens = MovementTweenQueue()
        em.subscribe_to_engine_events(bus, tween_queue=tweens)
        ent = _make_entity("goblin_1", 5, 5)
        em._add_entity(ent)

        event = _StubEvent({
            "entity_id": "goblin_1",
            "origin": _Pos(5, 5),
            "to": _Pos(6, 5),
        })
        bus.publish(EventType.CREATURE_MOVED, event)

        assert tweens.depth("goblin_1") == 1

    def test_resubscribe_swaps_buses_cleanly(self):
        from dnd_engine.utils.events import EventType

        em = EntityManager()
        bus_a = _StubBus()
        bus_b = _StubBus()
        em.subscribe_to_engine_events(bus_a)
        em.subscribe_to_engine_events(bus_b)
        ent = _make_entity("goblin_1", 0, 0)
        em._add_entity(ent)

        # Old bus is no longer wired.
        bus_a.publish(EventType.CREATURE_MOVED, _StubEvent({
            "entity_id": "goblin_1",
            "origin": _Pos(0, 0),
            "to": _Pos(9, 9),
        }))
        assert ent.grid_x == 0  # unchanged

        # New bus is.
        bus_b.publish(EventType.CREATURE_MOVED, _StubEvent({
            "entity_id": "goblin_1",
            "origin": _Pos(0, 0),
            "to": _Pos(1, 0),
        }))
        assert ent.grid_x == 1

    def test_malformed_event_data_is_tolerated(self):
        from dnd_engine.utils.events import EventType

        em = EntityManager()
        bus = _StubBus()
        em.subscribe_to_engine_events(bus)

        # Missing required keys — handler should not raise.
        bus.publish(EventType.CREATURE_MOVED, _StubEvent({}))
        bus.publish(EventType.CREATURE_PLACED, _StubEvent({"entity_id": "g"}))
