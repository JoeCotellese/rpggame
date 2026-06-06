# ABOUTME: Unit tests for MovementTweenQueue — per-entity sprite tween smoothing (#647).
# ABOUTME: Verifies ease-out interpolation, tick advancement, and teleport degradation.

from __future__ import annotations

from client_2d.animation.movement_tween import (
    DEFAULT_DURATION_MS,
    TELEPORT_THRESHOLD,
    MovementTween,
    MovementTweenQueue,
)


class TestMovementTween:
    def test_progress_starts_at_zero(self):
        tween = MovementTween(from_x=0, from_y=0, to_x=1, to_y=0)
        assert tween.progress == 0.0
        assert tween.is_complete is False

    def test_progress_reaches_one_after_duration(self):
        tween = MovementTween(from_x=0, from_y=0, to_x=1, to_y=0, duration_ms=100.0)
        tween.elapsed_ms = 100.0
        assert tween.progress == 1.0
        assert tween.is_complete is True

    def test_offset_zero_at_start(self):
        tween = MovementTween(from_x=0, from_y=0, to_x=5, to_y=0)
        dx, dy = tween.current_offset()
        assert dx == 0.0
        assert dy == 0.0

    def test_offset_full_delta_at_end(self):
        tween = MovementTween(from_x=0, from_y=0, to_x=5, to_y=3, duration_ms=100.0)
        tween.elapsed_ms = 100.0
        dx, dy = tween.current_offset()
        assert dx == 5.0
        assert dy == 3.0

    def test_ease_out_progresses_faster_than_linear_early(self):
        tween = MovementTween(from_x=0, from_y=0, to_x=1, to_y=0, duration_ms=100.0)
        tween.elapsed_ms = 50.0  # halfway
        # Linear would be 0.5; ease-out cubic at t=0.5 is 1 - 0.5^3 = 0.875.
        assert tween.eased_progress > 0.7


class TestMovementTweenQueue:
    def test_initially_no_offset(self):
        q = MovementTweenQueue()
        assert q.visual_offset("goblin_1") == (0.0, 0.0)
        assert q.depth("goblin_1") == 0

    def test_enqueue_adds_tween(self):
        q = MovementTweenQueue()
        q.enqueue("goblin_1", (0, 0), (1, 0))
        assert q.depth("goblin_1") == 1

    def test_tick_advances_and_completes_tween(self):
        q = MovementTweenQueue()
        q.enqueue("goblin_1", (0, 0), (1, 0), duration_ms=100.0)
        q.tick(100.0)
        # Completed tweens pop out of the queue.
        assert q.depth("goblin_1") == 0
        assert q.visual_offset("goblin_1") == (0.0, 0.0)

    def test_tick_partial_offset_in_progress(self):
        q = MovementTweenQueue()
        q.enqueue("goblin_1", (0, 0), (1, 0), duration_ms=100.0)
        q.tick(50.0)  # halfway
        dx, dy = q.visual_offset("goblin_1")
        # Ease-out: progress > 0.5 at t=0.5.
        assert 0.5 < dx < 1.0
        assert dy == 0.0

    def test_multiple_tweens_chain(self):
        q = MovementTweenQueue()
        q.enqueue("g", (0, 0), (1, 0), duration_ms=100.0)
        q.enqueue("g", (1, 0), (2, 0), duration_ms=100.0)
        assert q.depth("g") == 2
        # Complete first tween.
        q.tick(100.0)
        assert q.depth("g") == 1
        # Complete second tween.
        q.tick(100.0)
        assert q.depth("g") == 0

    def test_tick_overflow_into_next_tween(self):
        """When dt > remaining slot, the surplus advances the next tween."""
        q = MovementTweenQueue()
        q.enqueue("g", (0, 0), (1, 0), duration_ms=100.0)
        q.enqueue("g", (1, 0), (2, 0), duration_ms=100.0)
        q.tick(150.0)  # consumes the first (100ms) and 50ms into the second
        assert q.depth("g") == 1
        # The active second tween has 50ms elapsed → offset > 0.
        dx, _ = q.visual_offset("g")
        assert dx > 0.0

    def test_teleport_threshold_drops_queue(self):
        """At queue depth >= TELEPORT_THRESHOLD, new enqueues clear and snap."""
        q = MovementTweenQueue()
        for i in range(TELEPORT_THRESHOLD):
            q.enqueue("g", (i, 0), (i + 1, 0))
        assert q.depth("g") == TELEPORT_THRESHOLD
        # Next enqueue triggers degradation: queue is cleared.
        q.enqueue("g", (TELEPORT_THRESHOLD, 0), (TELEPORT_THRESHOLD + 1, 0))
        assert q.depth("g") == 0
        # Visual offset returns to neutral (sprite snaps).
        assert q.visual_offset("g") == (0.0, 0.0)

    def test_unknown_entity_has_zero_offset(self):
        q = MovementTweenQueue()
        q.enqueue("g", (0, 0), (1, 0))
        assert q.visual_offset("other") == (0.0, 0.0)

    def test_clear_per_entity(self):
        q = MovementTweenQueue()
        q.enqueue("a", (0, 0), (1, 0))
        q.enqueue("b", (0, 0), (1, 0))
        q.clear("a")
        assert q.depth("a") == 0
        assert q.depth("b") == 1

    def test_clear_global(self):
        q = MovementTweenQueue()
        q.enqueue("a", (0, 0), (1, 0))
        q.enqueue("b", (0, 0), (1, 0))
        q.clear()
        assert q.depth("a") == 0
        assert q.depth("b") == 0

    def test_default_duration_is_responsive(self):
        """Sanity: default duration is in the responsive range for tile movement."""
        assert 50.0 <= DEFAULT_DURATION_MS <= 300.0
