# ABOUTME: Unit tests for the GameView / GameWindow host split (issue #624).
# ABOUTME: Verifies the View subclass, window-geometry delegation, and host wiring.

"""Tests for the GameView(arcade.View) extraction from GameWindow.

These cover the new seams created by the refactor without needing a real
GL window: the class hierarchy, the width/height delegation to the host
window, and that the thin GameWindow host shows a GameView on construction.
The gameplay rendering/input itself is verified by manual windowed
playtest and by ``test_targeting.py`` (the moved pure methods).
"""

from unittest.mock import MagicMock, patch

import arcade
from client_2d.game import GameView, GameWindow


class TestClassHierarchy:
    """The split must produce an arcade View hosted by an arcade Window."""

    def test_gameview_is_arcade_view(self):
        """GameView must be an arcade.View so the window can show_view it."""
        assert issubclass(GameView, arcade.View)

    def test_gamewindow_is_arcade_window(self):
        """GameWindow remains the arcade.Window host."""
        assert issubclass(GameWindow, arcade.Window)


class TestWindowGeometryDelegation:
    """GameView has no surface of its own; width/height come from the window."""

    def test_width_delegates_to_window(self):
        """self.width reads through to the host window's width."""
        view = MagicMock()
        view.window.width = 1280
        assert GameView.width.fget(view) == 1280

    def test_height_delegates_to_window(self):
        """self.height reads through to the host window's height."""
        view = MagicMock()
        view.window.height = 900
        assert GameView.height.fget(view) == 900


class TestHostShowsGameView:
    """The thin host constructs and shows a GameView on startup."""

    def test_window_shows_gameview_on_init(self):
        """GameWindow.__init__ must show exactly one GameView with the
        MCP/dev arguments forwarded, without rendering anything itself."""
        with (
            patch("arcade.Window.__init__", return_value=None),
            patch("client_2d.game.arcade.set_background_color"),
            patch("client_2d.game.GameView") as mock_view_cls,
            patch.object(GameWindow, "show_view") as mock_show_view,
        ):
            GameWindow(
                width=800,
                height=600,
                enable_mcp=True,
                mcp_port=9000,
                dev_mode=True,
            )

        mock_view_cls.assert_called_once_with(
            enable_mcp=True,
            mcp_port=9000,
            dev_mode=True,
        )
        mock_show_view.assert_called_once_with(mock_view_cls.return_value)
