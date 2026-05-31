# ABOUTME: Shared keyboard-driven vertical menu widget for the launch screen.
# ABOUTME: Arcade-free navigation/selection logic core plus a draw() render method.

"""A reusable vertical menu list for the 2D client's launch-screen views.

The widget follows the same pattern as ``input_handler``: an arcade-free logic
core (navigation, selection, key handling) with its own integer ``KEY_*``
constants matching ``arcade.key.*`` values, so it can be unit-tested without
importing arcade. The ``draw`` method is the only part that touches arcade and is
verified manually.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from client_2d.core.constants import FONT_SIZE_BODY, UIColors

# Key code constants (matching arcade.key.* values for arcade-free testing).
KEY_UP = 65362
KEY_DOWN = 65364
KEY_W = 119
KEY_S = 115
KEY_ENTER = 65293
KEY_SPACE = 32
KEY_ESCAPE = 65307
KEY_1 = 49
KEY_2 = 50
KEY_3 = 51
KEY_4 = 52
KEY_5 = 53
KEY_6 = 54
KEY_7 = 55
KEY_8 = 56
KEY_9 = 57

_UP_KEYS = {KEY_UP, KEY_W}
_DOWN_KEYS = {KEY_DOWN, KEY_S}
_CONFIRM_KEYS = {KEY_ENTER, KEY_SPACE}


class MenuEvent(Enum):
    """The outcome of a key press handled by a :class:`MenuList`."""

    MOVED = auto()
    CONFIRM = auto()
    BACK = auto()


@dataclass
class MenuItem:
    """A single selectable row in a menu.

    Attributes:
        label: Display text for the row.
        value: Identifier the consuming view acts on (e.g. "new_game").
        enabled: Whether the row can be highlighted/selected.
        annotation: Optional secondary text (e.g. "Recommended" or a grayed
            reason), rendered dim beside the label.
    """

    label: str
    value: Any
    enabled: bool = True
    annotation: str | None = None


@dataclass
class MenuList:
    """A keyboard-navigable vertical menu.

    Navigation moves between enabled rows only (wrapping at the ends) and is a
    safe no-op when the list is empty or has no enabled rows. ``handle_key``
    translates key codes into :class:`MenuEvent` values; the consuming view reads
    :attr:`selected_item` on ``CONFIRM``.

    Attributes:
        items: The rows, in display order.
        selected_index: Index of the highlighted row, or -1 when none is
            selectable. Initialized to the first enabled row.
        number_keys_confirm: When True (default), number keys 1-9 select the
            matching row and confirm it (accelerator). When False, they only move
            the highlight.
    """

    items: list[MenuItem] = field(default_factory=list)
    selected_index: int = 0
    number_keys_confirm: bool = True

    def __post_init__(self) -> None:
        """Highlight the first enabled row, or -1 if none is enabled."""
        self.selected_index = self._first_enabled_index()

    # -- state -----------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        """True when the menu has no rows at all."""
        return len(self.items) == 0

    @property
    def has_enabled(self) -> bool:
        """True when at least one row can be selected."""
        return any(item.enabled for item in self.items)

    @property
    def selected_item(self) -> MenuItem | None:
        """The currently highlighted row, or None when nothing is selectable."""
        if 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None

    # -- navigation ------------------------------------------------------------

    def move_up(self) -> bool:
        """Move the highlight to the previous enabled row, wrapping."""
        return self._step(-1)

    def move_down(self) -> bool:
        """Move the highlight to the next enabled row, wrapping."""
        return self._step(1)

    def select_index(self, index: int) -> bool:
        """Highlight ``index`` if it is a valid, enabled row.

        Returns True if the highlight was set, False otherwise.
        """
        if 0 <= index < len(self.items) and self.items[index].enabled:
            self.selected_index = index
            return True
        return False

    # -- input -----------------------------------------------------------------

    def handle_key(self, key: int) -> MenuEvent | None:
        """Translate a key code into a :class:`MenuEvent`.

        Returns None for keys that produce no action (including navigation on an
        empty / fully-disabled list and out-of-range or disabled number keys).
        """
        if key == KEY_ESCAPE:
            return MenuEvent.BACK

        if key in _UP_KEYS:
            return MenuEvent.MOVED if self.move_up() else None

        if key in _DOWN_KEYS:
            return MenuEvent.MOVED if self.move_down() else None

        if key in _CONFIRM_KEYS:
            return MenuEvent.CONFIRM if self.selected_item is not None else None

        if KEY_1 <= key <= KEY_9:
            index = key - KEY_1
            if self.select_index(index):
                return MenuEvent.CONFIRM if self.number_keys_confirm else MenuEvent.MOVED
            return None

        return None

    # -- rendering (manual QA; not unit-tested) --------------------------------

    def draw(
        self,
        center_x: float,
        top_y: float,
        *,
        row_height: float = 36.0,
        font_size: int = FONT_SIZE_BODY,
        empty_message: str = "Nothing here yet.",
    ) -> None:
        """Render the menu with arcade.

        The active row shows a caret and the torchlight-gold highlight colour
        (never colour alone); disabled rows use the dimmed/disabled text colour;
        annotations render dim beside the label. When the menu is empty, the
        empty-state message is drawn instead. Verified manually.
        """
        import arcade

        if self.is_empty:
            arcade.draw_text(
                empty_message,
                center_x,
                top_y,
                UIColors.TEXT_DIM,
                font_size=font_size,
                anchor_x="center",
            )
            return

        for row, item in enumerate(self.items):
            y = top_y - row * row_height
            is_active = row == self.selected_index
            if not item.enabled:
                color = UIColors.TEXT_DISABLED
            elif is_active:
                color = UIColors.HIGHLIGHT
            else:
                color = UIColors.TEXT

            text = f"▸ {item.label}" if is_active else f"  {item.label}"
            arcade.draw_text(
                text,
                center_x,
                y,
                color,
                font_size=font_size,
                anchor_x="center",
            )
            if item.annotation:
                arcade.draw_text(
                    item.annotation,
                    center_x,
                    y - font_size - 2,
                    UIColors.TEXT_DIM,
                    font_size=max(font_size - 2, 8),
                    anchor_x="center",
                )

    # -- internals -------------------------------------------------------------

    def _first_enabled_index(self) -> int:
        for index, item in enumerate(self.items):
            if item.enabled:
                return index
        return -1

    def _step(self, direction: int) -> bool:
        """Advance the highlight to the next enabled row in ``direction``."""
        if not self.has_enabled:
            return False
        count = len(self.items)
        start = self.selected_index if self.selected_index >= 0 else 0
        for offset in range(1, count + 1):
            candidate = (start + direction * offset) % count
            if self.items[candidate].enabled:
                self.selected_index = candidate
                return True
        return False
