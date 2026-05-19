# ABOUTME: Unit tests for weapon range parsing utilities.
# ABOUTME: Tests parse_weapon_range() and get_attack_range() for various weapon types.

"""Tests for the range utility functions in game.py."""

from client_2d.game import get_attack_range, parse_weapon_range


class TestParseWeaponRange:
    """Tests for parse_weapon_range() function."""

    def test_none_returns_melee_range(self):
        """None input should return melee range (5/5 ft)."""
        assert parse_weapon_range(None) == (5, 5)

    def test_empty_string_returns_melee_range(self):
        """Empty string should return melee range (5/5 ft)."""
        assert parse_weapon_range("") == (5, 5)

    def test_standard_ranged_weapon(self):
        """Parse standard 'normal/max' format like '150/600'."""
        assert parse_weapon_range("150/600") == (150, 600)

    def test_light_crossbow_range(self):
        """Parse light crossbow range '80/320'."""
        assert parse_weapon_range("80/320") == (80, 320)

    def test_thrown_weapon_range(self):
        """Parse thrown weapon range '20/60' (dagger)."""
        assert parse_weapon_range("20/60") == (20, 60)

    def test_single_value_range(self):
        """Single value should use same value for normal and max."""
        assert parse_weapon_range("30") == (30, 30)

    def test_heavy_crossbow_range(self):
        """Parse heavy crossbow range '100/400'."""
        assert parse_weapon_range("100/400") == (100, 400)


class TestGetAttackRange:
    """Tests for get_attack_range() function."""

    def test_none_weapon_returns_unarmed_range(self):
        """None weapon (unarmed) should return melee range."""
        assert get_attack_range(None) == (5, 5)

    def test_empty_weapon_returns_melee_range(self):
        """Empty dict should return melee range."""
        assert get_attack_range({}) == (5, 5)

    def test_melee_weapon_without_thrown(self):
        """Melee weapon without thrown property returns 5 ft only."""
        weapon = {
            "name": "Longsword",
            "category": "melee",
            "damage": "1d8",
            "properties": ["versatile"],
        }
        assert get_attack_range(weapon) == (5, 5)

    def test_thrown_melee_weapon(self):
        """Melee weapon with thrown property returns its range."""
        weapon = {
            "name": "Dagger",
            "category": "melee",
            "damage": "1d4",
            "properties": ["finesse", "light", "thrown"],
            "range": "20/60",
        }
        assert get_attack_range(weapon) == (20, 60)

    def test_ranged_weapon_longbow(self):
        """Ranged weapon should return its range values."""
        weapon = {
            "name": "Longbow",
            "category": "ranged",
            "damage": "1d8",
            "properties": ["ammunition", "heavy", "two-handed"],
            "range": "150/600",
        }
        assert get_attack_range(weapon) == (150, 600)

    def test_ranged_weapon_light_crossbow(self):
        """Light crossbow should return 80/320 range."""
        weapon = {
            "name": "Light Crossbow",
            "category": "ranged",
            "damage": "1d8",
            "properties": ["ammunition", "loading", "two-handed"],
            "range": "80/320",
        }
        assert get_attack_range(weapon) == (80, 320)

    def test_handaxe_thrown(self):
        """Handaxe (melee with thrown) should return 20/60 range."""
        weapon = {
            "name": "Handaxe",
            "category": "melee",
            "damage": "1d6",
            "properties": ["light", "thrown"],
            "range": "20/60",
        }
        assert get_attack_range(weapon) == (20, 60)

    def test_melee_weapon_missing_range_property(self):
        """Melee weapon with thrown but no range returns melee only."""
        weapon = {
            "name": "Broken Dagger",
            "category": "melee",
            "damage": "1d4",
            "properties": ["finesse", "light", "thrown"],
            # No range property - should fall back to melee
        }
        # thrown without range = melee only
        assert get_attack_range(weapon) == (5, 5)

    def test_ranged_weapon_missing_range(self):
        """Ranged weapon without range defaults to 5/5 (edge case)."""
        weapon = {
            "name": "Broken Bow",
            "category": "ranged",
            "damage": "1d6",
            "properties": ["ammunition"],
            # No range property
        }
        # Edge case: ranged without range specified
        assert get_attack_range(weapon) == (5, 5)

    def test_melee_weapon_with_no_properties(self):
        """Melee weapon with empty properties returns melee range."""
        weapon = {
            "name": "Club",
            "category": "melee",
            "damage": "1d4",
            "properties": [],
        }
        assert get_attack_range(weapon) == (5, 5)

    def test_melee_weapon_missing_properties_key(self):
        """Weapon missing properties key should still work."""
        weapon = {
            "name": "Improvised Weapon",
            "category": "melee",
            "damage": "1d4",
        }
        assert get_attack_range(weapon) == (5, 5)
