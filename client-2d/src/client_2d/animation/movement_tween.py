# ABOUTME: Per-entity movement-tween queue for smooth per-step sprite animation (#647).
# ABOUTME: Ease-out interpolation between (from, to) grid tiles; degrades to teleport under load.

"""MovementTweenQueue — smooth sprite animation for engine-driven movement.

When the engine publishes CREATURE_MOVED, the EntityManager (the
event consumer) updates the entity's grid_x / grid_y and enqueues a
tween in this queue. The render loop calls `tick(dt_ms)` per frame
to advance active tweens, and reads `visual_offset(entity_id)` to
get the current pixel offset to apply to the sprite at draw time.

Tweens use ease-out for a quick "snap to destination" feel
appropriate for tile-based movement (~120 ms per step). When the
queue depth for an entity exceeds `TELEPORT_THRESHOLD`, the queue
clears and snaps to the final position — a graceful degradation
for fast turn sequences (multiple monsters resolving in one tick)
that prevents the UI thread from being starved.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

DEFAULT_DURATION_MS = 120.0
"""Default per-step tween duration. Calibrated for tile-based movement:
fast enough to feel responsive, slow enough that the eye registers the
step direction."""

TELEPORT_THRESHOLD = 3
"""Per-entity queue depth at which we collapse remaining tweens and
teleport to the final tile. Keeps the visual layer responsive when
the engine emits many CREATURE_MOVED events in one tick."""


@dataclass
class MovementTween:
    """A single from→to tile tween with an ease-out time curve."""

    from_x: int
    from_y: int
    to_x: int
    to_y: int
    duration_ms: float = DEFAULT_DURATION_MS
    elapsed_ms: float = 0.0

    @property
    def progress(self) -> float:
        """Linear time progress in [0, 1]."""
        if self.duration_ms <= 0:
            return 1.0
        return max(0.0, min(1.0, self.elapsed_ms / self.duration_ms))

    @property
    def eased_progress(self) -> float:
        """Ease-out cubic — quick start, gentle stop."""
        t = self.progress
        return 1.0 - (1.0 - t) ** 3

    @property
    def is_complete(self) -> bool:
        return self.elapsed_ms >= self.duration_ms

    def current_offset(self) -> tuple[float, float]:
        """Return the (dx, dy) tile-space offset to add to `from_x/y`.

        Returns an interpolated offset where the visible position is
        `(from_x + dx, from_y + dy)` in tile units. At t=0 the offset
        is (0,0); at t=1 it's `(to-from)`.
        """
        e = self.eased_progress
        return ((self.to_x - self.from_x) * e, (self.to_y - self.from_y) * e)


class MovementTweenQueue:
    """Per-entity tween queue.

    All operations are O(1) per entity. The render loop does one
    `tick(dt_ms)` per frame and one `visual_offset(entity_id)` per
    sprite per frame.
    """

    def __init__(self, *, teleport_threshold: int = TELEPORT_THRESHOLD) -> None:
        self._queues: dict[str, deque[MovementTween]] = {}
        self._teleport_threshold = teleport_threshold

    def enqueue(
        self,
        entity_id: str,
        from_tile: tuple[int, int],
        to_tile: tuple[int, int],
        *,
        duration_ms: float = DEFAULT_DURATION_MS,
    ) -> None:
        """Add a from→to tween to the entity's queue.

        If the queue depth would exceed the teleport threshold,
        clear the queue and silently snap to the destination — the
        visual layer cannot keep up with the engine, so a clean
        teleport is preferable to a stuttering chain.
        """
        queue = self._queues.setdefault(entity_id, deque())
        if len(queue) >= self._teleport_threshold:
            queue.clear()
            return
        tween = MovementTween(
            from_x=from_tile[0], from_y=from_tile[1],
            to_x=to_tile[0], to_y=to_tile[1],
            duration_ms=duration_ms,
        )
        queue.append(tween)

    def tick(self, dt_ms: float) -> None:
        """Advance all active tweens by `dt_ms` and pop completed ones."""
        for queue in self._queues.values():
            remaining = dt_ms
            while queue and remaining > 0:
                active = queue[0]
                slot = active.duration_ms - active.elapsed_ms
                if remaining < slot:
                    active.elapsed_ms += remaining
                    remaining = 0.0
                else:
                    active.elapsed_ms = active.duration_ms
                    queue.popleft()
                    remaining -= slot

    def visual_offset(self, entity_id: str) -> tuple[float, float]:
        """Return the current tile-space offset to apply to the sprite.

        Returns `(0.0, 0.0)` when the entity has no active tween.
        """
        queue = self._queues.get(entity_id)
        if not queue:
            return (0.0, 0.0)
        active = queue[0]
        return active.current_offset()

    def depth(self, entity_id: str) -> int:
        """Return the queued tween count for an entity (testing aid)."""
        queue = self._queues.get(entity_id)
        return len(queue) if queue else 0

    def clear(self, entity_id: str | None = None) -> None:
        """Drop all queued tweens (per-entity or globally)."""
        if entity_id is None:
            self._queues.clear()
        elif entity_id in self._queues:
            self._queues[entity_id].clear()
