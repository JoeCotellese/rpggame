# ABOUTME: Tests for exploration movement and room transitions (#637) -
# ABOUTME: direction keys grid-move; transitions fire only on exit/door tiles.

"""Tests for room-transition behavior in GameSession.

Issue #637: pressing a direction key that matched any room exit used to
teleport the player to the destination room from anywhere. These tests
pin the fixed behavior: direction keys always perform one-tile grid
moves, and a room transition only fires when the player steps onto the
exit/door tile itself (gated by the SRD door-state passability seam).

The engine GameState is faked with a tiny two-room graph; room layouts
come from the loader's procedural fallback (generate_basic_room), which
places real DOOR tiles at the wall border for each exit.
"""

from __future__ import annotations

import pytest


class FakeGameState:
    """Minimal stand-in for the engine GameState room graph."""

    def __init__(self, rooms: dict[str, dict] | None = None) -> None:
        self.dungeon_name = "fake_dungeon"
        self.campaign_id = "fake_campaign"
        self.current_room_id = "entry"
        self.in_combat = False
        self.active_enemies: list = []
        self.rooms = rooms or {
            "entry": {"name": "Entry Hall", "exits": {"north": "north_room"}},
            "north_room": {"name": "North Room", "exits": {"south": "entry"}},
        }

    def get_current_room(self) -> dict:
        return self.rooms[self.current_room_id]

    def move(self, direction: str) -> bool:
        dest = self.get_current_room().get("exits", {}).get(direction)
        if isinstance(dest, dict):
            if dest.get("hidden", False):
                return False
            dest = dest.get("destination")
        if dest:
            self.current_room_id = dest
            return True
        return False


def make_session(rooms: dict[str, dict] | None = None):
    """GameSession wired to a FakeGameState two-room graph.

    The layout loader's file lookup is redirected to the fake room
    dicts so load_room_with_fallback generates layouts (with DOOR
    tiles) from the fake exits instead of reading dungeon JSON.
    """
    from client_2d.session import GameSession

    s = GameSession(enable_mcp=False, dev_mode=True)
    fake = FakeGameState(rooms)
    s.engine._game_state = fake
    s.layout_loader.get_room_data = (  # type: ignore[method-assign]
        lambda dungeon_name, room_id, campaign_id=None: fake.rooms.get(room_id)
    )
    s._load_room_layout()
    return s, fake


@pytest.fixture
def session_and_state():
    return make_session()


class TestGridMovement:
    """Direction keys always grid-move within the room (#637)."""

    def test_move_toward_exit_direction_is_one_tile_step(self, session_and_state) -> None:
        """Pressing north mid-room must NOT teleport to the north room."""
        session, fake = session_and_state
        start_x, start_y = session.player_x, session.player_y

        session._move_player("north")

        assert fake.current_room_id == "entry"
        assert (session.player_x, session.player_y) == (start_x, start_y - 1)

    def test_backtracking_returns_to_starting_tile(self, session_and_state) -> None:
        """South then north lands back on the original tile, same room."""
        session, fake = session_and_state
        start = (session.player_x, session.player_y)

        session._move_player("south")
        session._move_player("north")

        assert fake.current_room_id == "entry"
        assert (session.player_x, session.player_y) == start

    def test_walking_onto_exit_tile_transitions(self, session_and_state) -> None:
        """Stepping onto the north door tile fires the room transition."""
        session, fake = session_and_state
        door_x, door_y = session.room_layout.spawn_points.exits["north"]
        # Place the player one tile inside the door, then step onto it.
        session.player_x, session.player_y = door_x, door_y + 1

        session._move_player("north")

        assert fake.current_room_id == "north_room"

    def test_lateral_step_onto_door_tile_transitions_in_door_direction(self) -> None:
        """Approaching a door tile sideways still uses that door's exit."""
        from client_2d.integration.layout_schema import RoomLayout, TileType

        session, fake = make_session()
        # Hand-craft a layout where the north door tile is reachable
        # from the side (inset one row, floor neighbors on the row).
        f, d, w = TileType.FLOOR.value, TileType.DOOR.value, TileType.WALL.value
        session.room_layout = RoomLayout(
            width=5,
            height=5,
            tiles=[
                [w, w, w, w, w],
                [w, f, d, f, w],
                [w, f, f, f, w],
                [w, f, f, f, w],
                [w, w, w, w, w],
            ],
            spawn_points={"player": (2, 2), "exits": {"north": (2, 1)}},
        )
        session.player_x, session.player_y = 1, 1  # beside the door

        session._move_player("east")

        assert fake.current_room_id == "north_room"
