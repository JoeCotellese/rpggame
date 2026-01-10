# ABOUTME: Unit tests for visual rendering components used in the 2D client.
# ABOUTME: Tests arcade Color creation from lighting tints to prevent API regressions.

"""Tests for visual rendering utilities.

These tests verify that arcade rendering components work correctly,
particularly Color creation from lighting tint tuples.
"""


from arcade.types import Color
from client_2d.core.constants import LightingState

# Lighting tint colors (RGB multipliers as 0-255) - mirrors visual_test.py
LIGHTING_TINTS = {
    LightingState.UNEXPLORED: None,  # Don't render
    LightingState.DARK: (60, 60, 80),  # Dark blue-gray (memory)
    LightingState.DIM: (160, 160, 180),  # Dimmed
    LightingState.BRIGHT: (255, 255, 255),  # Full brightness
}


class TestArcadeColorCreation:
    """Tests for creating arcade Color objects from tint tuples."""

    def test_color_from_rgb_tuple(self):
        """Color should be creatable from RGB tuple with alpha."""
        tint = (128, 128, 128)
        color = Color(*tint, 255)

        assert color.r == 128
        assert color.g == 128
        assert color.b == 128
        assert color.a == 255

    def test_color_has_normalized_attribute(self):
        """Color must have .normalized attribute for arcade.draw_texture_rect."""
        tint = (200, 150, 100)
        color = Color(*tint, 255)

        # This is the attribute that caused the original bug
        assert hasattr(color, "normalized")
        # normalized should return floats in 0-1 range
        normalized = color.normalized
        assert len(normalized) == 4
        assert all(0.0 <= v <= 1.0 for v in normalized)

    def test_all_lighting_tints_create_valid_colors(self):
        """All non-None lighting tints should create valid Color objects."""
        for state, tint in LIGHTING_TINTS.items():
            if tint is None:
                continue

            color = Color(*tint, 255)

            # Verify color was created successfully
            assert color.r == tint[0], f"Failed for {state}"
            assert color.g == tint[1], f"Failed for {state}"
            assert color.b == tint[2], f"Failed for {state}"
            # Verify normalized works (required by arcade.draw_texture_rect)
            assert hasattr(color, "normalized"), f"No normalized attr for {state}"

    def test_dark_tint_color(self):
        """DARK tint should create correct blue-gray color."""
        tint = LIGHTING_TINTS[LightingState.DARK]
        color = Color(*tint, 255)

        assert color.r == 60
        assert color.g == 60
        assert color.b == 80

    def test_dim_tint_color(self):
        """DIM tint should create correct dimmed color."""
        tint = LIGHTING_TINTS[LightingState.DIM]
        color = Color(*tint, 255)

        assert color.r == 160
        assert color.g == 160
        assert color.b == 180

    def test_bright_tint_color(self):
        """BRIGHT tint should create full white color."""
        tint = LIGHTING_TINTS[LightingState.BRIGHT]
        color = Color(*tint, 255)

        assert color.r == 255
        assert color.g == 255
        assert color.b == 255

    def test_unexplored_tint_is_none(self):
        """UNEXPLORED tint should be None (don't render)."""
        assert LIGHTING_TINTS[LightingState.UNEXPLORED] is None
