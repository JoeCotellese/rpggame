# ABOUTME: Unit tests for the shared MenuList widget logic core.
# ABOUTME: Tests navigation, selection, disabled-row skipping, and key handling.

"""Tests for the MenuList widget (arcade-free logic core)."""

from client_2d.ui.menu_list import (
    KEY_2,
    KEY_3,
    KEY_9,
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_S,
    KEY_SPACE,
    KEY_UP,
    KEY_W,
    MenuEvent,
    MenuItem,
    MenuList,
)


def make_menu(*specs, number_keys_confirm=True):
    """Build a MenuList from (label, value[, enabled]) tuples."""
    items = []
    for spec in specs:
        if len(spec) == 3:
            label, value, enabled = spec
        else:
            label, value = spec
            enabled = True
        items.append(MenuItem(label=label, value=value, enabled=enabled))
    return MenuList(items=items, number_keys_confirm=number_keys_confirm)


class TestDefaultHighlight:
    """Initial selection behaviour."""

    def test_first_enabled_is_highlighted(self):
        menu = make_menu(("New", "new"), ("Load", "load"))
        assert menu.selected_index == 0
        assert menu.selected_item.value == "new"

    def test_skips_leading_disabled(self):
        menu = make_menu(("Continue", "cont", False), ("New", "new", True))
        assert menu.selected_index == 1
        assert menu.selected_item.value == "new"

    def test_all_disabled_has_no_selection(self):
        menu = make_menu(("a", "a", False), ("b", "b", False))
        assert menu.has_enabled is False
        assert menu.selected_item is None


class TestEmpty:
    """Empty-list safety (three-state support)."""

    def test_empty_is_empty(self):
        menu = MenuList(items=[])
        assert menu.is_empty is True
        assert menu.selected_item is None

    def test_empty_navigation_is_noop(self):
        menu = MenuList(items=[])
        assert menu.handle_key(KEY_DOWN) is None
        assert menu.handle_key(KEY_ENTER) is None

    def test_empty_escape_still_backs_out(self):
        menu = MenuList(items=[])
        assert menu.handle_key(KEY_ESCAPE) is MenuEvent.BACK


class TestNavigation:
    """Highlight movement, wrapping, and disabled skipping."""

    def test_move_down_advances(self):
        menu = make_menu(("a", "a"), ("b", "b"), ("c", "c"))
        assert menu.handle_key(KEY_DOWN) is MenuEvent.MOVED
        assert menu.selected_index == 1

    def test_move_down_wraps_to_first(self):
        menu = make_menu(("a", "a"), ("b", "b"))
        menu.handle_key(KEY_DOWN)  # -> 1
        menu.handle_key(KEY_DOWN)  # wrap -> 0
        assert menu.selected_index == 0

    def test_move_up_wraps_to_last(self):
        menu = make_menu(("a", "a"), ("b", "b"), ("c", "c"))
        assert menu.handle_key(KEY_UP) is MenuEvent.MOVED
        assert menu.selected_index == 2

    def test_navigation_skips_disabled(self):
        menu = make_menu(("a", "a", True), ("b", "b", False), ("c", "c", True))
        menu.handle_key(KEY_DOWN)  # skip disabled b -> c
        assert menu.selected_index == 2

    def test_w_and_s_mirror_arrows(self):
        menu = make_menu(("a", "a"), ("b", "b"), ("c", "c"))
        assert menu.handle_key(KEY_S) is MenuEvent.MOVED
        assert menu.selected_index == 1
        assert menu.handle_key(KEY_W) is MenuEvent.MOVED
        assert menu.selected_index == 0


class TestConfirm:
    """Enter / Space confirm the current row."""

    def test_enter_confirms_current(self):
        menu = make_menu(("New", "new"), ("Load", "load"))
        menu.handle_key(KEY_DOWN)
        assert menu.handle_key(KEY_ENTER) is MenuEvent.CONFIRM
        assert menu.selected_item.value == "load"

    def test_space_confirms(self):
        menu = make_menu(("New", "new"))
        assert menu.handle_key(KEY_SPACE) is MenuEvent.CONFIRM


class TestBack:
    """Escape backs out."""

    def test_escape_backs_out(self):
        menu = make_menu(("New", "new"))
        assert menu.handle_key(KEY_ESCAPE) is MenuEvent.BACK


class TestNumberKeys:
    """Number-key accelerators."""

    def test_number_selects_and_confirms_by_default(self):
        menu = make_menu(("a", "a"), ("b", "b"), ("c", "c"))
        result = menu.handle_key(KEY_2)
        assert menu.selected_index == 1
        assert result is MenuEvent.CONFIRM

    def test_number_moves_only_when_confirm_disabled(self):
        menu = make_menu(("a", "a"), ("b", "b"), ("c", "c"), number_keys_confirm=False)
        result = menu.handle_key(KEY_3)
        assert menu.selected_index == 2
        assert result is MenuEvent.MOVED

    def test_number_out_of_range_is_noop(self):
        menu = make_menu(("a", "a"), ("b", "b"))
        assert menu.handle_key(KEY_9) is None
        assert menu.selected_index == 0

    def test_number_on_disabled_row_is_noop(self):
        menu = make_menu(("a", "a", True), ("b", "b", False))
        assert menu.handle_key(KEY_2) is None
        assert menu.selected_index == 0


class TestUnknownKey:
    """Unmapped keys are ignored."""

    def test_unknown_key_returns_none(self):
        menu = make_menu(("a", "a"))
        assert menu.handle_key(999999) is None
