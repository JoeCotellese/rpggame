# ABOUTME: Unit tests for Creature size data field and Size enum
# ABOUTME: Covers SRD size categories, defaulting behavior, and monster catalog loading

from unittest.mock import patch

import pytest

from dnd_engine.core.creature import Abilities, Creature, Size
from dnd_engine.rules.loader import DataLoader


class TestSizeEnum:
    """Test the Size enum covers all SRD creature sizes."""

    def test_all_srd_sizes_present(self):
        """Size enum should cover the six SRD creature sizes."""
        expected = {"tiny", "small", "medium", "large", "huge", "gargantuan"}
        actual = {member.value for member in Size}
        assert actual == expected

    def test_values_are_lowercase_strings(self):
        """Each Size member's .value should be the lowercase canonical string."""
        assert Size.TINY.value == "tiny"
        assert Size.SMALL.value == "small"
        assert Size.MEDIUM.value == "medium"
        assert Size.LARGE.value == "large"
        assert Size.HUGE.value == "huge"
        assert Size.GARGANTUAN.value == "gargantuan"

    def test_size_roundtrips_from_string(self):
        """Constructing Size from its canonical string should recover the member."""
        assert Size("tiny") is Size.TINY
        assert Size("small") is Size.SMALL
        assert Size("medium") is Size.MEDIUM
        assert Size("large").value == "large"
        assert Size("huge") is Size.HUGE
        assert Size("gargantuan") is Size.GARGANTUAN


class TestCreatureSizeField:
    """Test that the Creature class carries a size field defaulting to Medium."""

    def _abilities(self) -> Abilities:
        return Abilities(
            strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10
        )

    def test_creature_defaults_to_medium(self):
        """A bare Creature(...) should default to Size.MEDIUM."""
        creature = Creature(name="Tester", max_hp=10, ac=10, abilities=self._abilities())
        assert creature.size is Size.MEDIUM

    def test_creature_accepts_explicit_size(self):
        """Creature(...) should honor an explicit size argument."""
        creature = Creature(
            name="Big Tester",
            max_hp=10,
            ac=10,
            abilities=self._abilities(),
            size=Size.LARGE,
        )
        assert creature.size is Size.LARGE

    @pytest.mark.parametrize(
        "size",
        [Size.TINY, Size.SMALL, Size.MEDIUM, Size.LARGE, Size.HUGE, Size.GARGANTUAN],
    )
    def test_creature_size_round_trips(self, size: Size):
        """Every Size value should survive a Creature construction round-trip."""
        creature = Creature(
            name="Tester",
            max_hp=10,
            ac=10,
            abilities=self._abilities(),
            size=size,
        )
        assert creature.size is size


class TestDataLoaderMonsterSize:
    """Test that DataLoader.create_monster reads the size field from monsters.json."""

    def test_goblin_loads_as_small(self):
        """The SRD goblin entry is 'small' — loader should surface Size.SMALL."""
        loader = DataLoader()
        goblin = loader.create_monster("goblin")
        assert goblin.size is Size.SMALL

    def test_wolf_loads_as_medium(self):
        """The SRD wolf entry is 'medium' — loader should surface Size.MEDIUM."""
        loader = DataLoader()
        wolf = loader.create_monster("wolf")
        assert wolf.size is Size.MEDIUM

    def test_missing_size_defaults_to_medium(self):
        """A monster catalog entry without a size key should default to Medium."""
        # Stub monsters.json with one entry that omits "size" — exercises the
        # loader's .get(..., "medium") default branch without modifying real
        # catalog data.
        stub_monsters = {
            "sizeless_test_monster": {
                "name": "Sizeless Test Monster",
                "hp": "1d4",
                "ac": 10,
                "abilities": {
                    "str": 10,
                    "dex": 10,
                    "con": 10,
                    "int": 10,
                    "wis": 10,
                    "cha": 10,
                },
            }
        }
        loader = DataLoader()
        with patch.object(loader, "load_monsters", return_value=stub_monsters):
            creature = loader.create_monster("sizeless_test_monster")
        assert creature.size is Size.MEDIUM

    def test_size_string_is_case_insensitive(self):
        """An uppercase size string in the catalog should still load cleanly."""
        stub_monsters = {
            "shouting_giant": {
                "name": "Shouting Giant",
                "hp": "1d4",
                "ac": 10,
                "size": "HUGE",
                "abilities": {
                    "str": 10,
                    "dex": 10,
                    "con": 10,
                    "int": 10,
                    "wis": 10,
                    "cha": 10,
                },
            }
        }
        loader = DataLoader()
        with patch.object(loader, "load_monsters", return_value=stub_monsters):
            creature = loader.create_monster("shouting_giant")
        assert creature.size is Size.HUGE
