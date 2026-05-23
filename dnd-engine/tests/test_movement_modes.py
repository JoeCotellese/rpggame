# ABOUTME: Tests for MovementMode enum and Creature.speeds dict data shape
# ABOUTME: Covers backward-compat with legacy `speed: int` and DataLoader wiring

from unittest.mock import patch

import pytest

from dnd_engine.core.creature import Abilities, Creature, MovementMode
from dnd_engine.rules.loader import DataLoader


@pytest.fixture
def abilities() -> Abilities:
    """Baseline ability scores for a generic Medium humanoid."""
    return Abilities(
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )


class TestMovementModeEnum:
    """MovementMode enum shape — values, membership, JSON round-trip."""

    def test_enum_has_all_seven_members(self):
        """All seven SRD-relevant movement modes are present."""
        expected = {"WALK", "CLIMB", "SWIM", "CRAWL", "JUMP", "FLY", "BURROW"}
        actual = {member.name for member in MovementMode}
        assert actual == expected

    def test_enum_values_are_lowercase_strings(self):
        """Values are lowercase strings for JSON-friendly serialization."""
        assert MovementMode.WALK.value == "walk"
        assert MovementMode.CLIMB.value == "climb"
        assert MovementMode.SWIM.value == "swim"
        assert MovementMode.CRAWL.value == "crawl"
        assert MovementMode.JUMP.value == "jump"
        assert MovementMode.FLY.value == "fly"
        assert MovementMode.BURROW.value == "burrow"

    def test_enum_round_trips_through_string_value(self):
        """`MovementMode("swim")` resolves back to the same member identity."""
        assert MovementMode("swim") is MovementMode.SWIM
        assert MovementMode("fly") is MovementMode.FLY

    def test_enum_is_string_subclass(self):
        """Members compare equal to their string value (JSON friendliness)."""
        assert MovementMode.WALK == "walk"


class TestCreatureSpeedsDefault:
    """Backward compat: passing only `speed=...` derives speeds = {WALK: speed}."""

    def test_default_speed_populates_walk_in_speeds_dict(self, abilities):
        """A creature built with legacy `speed=30` exposes both `speed` and `speeds`."""
        creature = Creature(
            name="Generic",
            max_hp=10,
            ac=10,
            abilities=abilities,
            speed=30,
        )
        assert creature.speed == 30
        assert creature.speeds == {MovementMode.WALK: 30}

    def test_speed_zero_still_populates_walk(self, abilities):
        """A creature with speed=0 (e.g. statue) gets {WALK: 0}, not an empty dict."""
        creature = Creature(
            name="Statue",
            max_hp=10,
            ac=10,
            abilities=abilities,
            speed=0,
        )
        assert creature.speed == 0
        assert creature.speeds == {MovementMode.WALK: 0}

    def test_default_speed_when_kwarg_omitted(self, abilities):
        """The default `speed=30` kwarg also flows into the speeds dict."""
        creature = Creature(name="Default", max_hp=10, ac=10, abilities=abilities)
        assert creature.speed == 30
        assert creature.speeds == {MovementMode.WALK: 30}


class TestCreatureSpeedsExplicit:
    """When `speeds` is passed explicitly, it overrides the auto-derivation."""

    def test_explicit_speeds_with_walk_sets_both_fields(self, abilities):
        """speeds={WALK: 25, SWIM: 25} populates both `speeds` and legacy `speed`."""
        creature = Creature(
            name="Merfolk",
            max_hp=10,
            ac=10,
            abilities=abilities,
            speeds={MovementMode.WALK: 25, MovementMode.SWIM: 25},
        )
        assert creature.speed == 25
        assert creature.speeds == {MovementMode.WALK: 25, MovementMode.SWIM: 25}

    def test_explicit_speeds_without_walk_keeps_legacy_speed(self, abilities):
        """speeds={FLY: 60} with speed=0 keeps speed=0 — no WALK auto-injection."""
        creature = Creature(
            name="Flying Snake",
            max_hp=10,
            ac=10,
            abilities=abilities,
            speed=0,
            speeds={MovementMode.FLY: 60},
        )
        assert creature.speed == 0
        assert creature.speeds == {MovementMode.FLY: 60}
        assert MovementMode.WALK not in creature.speeds

    def test_explicit_speeds_with_walk_overrides_speed_kwarg(self, abilities):
        """When speeds includes WALK, the legacy `speed` attribute mirrors it."""
        creature = Creature(
            name="OverriddenWalker",
            max_hp=10,
            ac=10,
            abilities=abilities,
            speed=30,
            speeds={MovementMode.WALK: 40, MovementMode.CLIMB: 20},
        )
        assert creature.speed == 40
        assert creature.speeds == {MovementMode.WALK: 40, MovementMode.CLIMB: 20}


class TestDataLoaderSpeeds:
    """DataLoader.create_monster wires `speed` / `speeds` into the Creature."""

    def test_goblin_has_walk_speed_only(self):
        """Goblin in monsters.json has `speed: 30` and no `speeds` dict."""
        loader = DataLoader()
        goblin = loader.create_monster("goblin")
        assert goblin.speed == 30
        assert goblin.speeds == {MovementMode.WALK: 30}

    def test_loader_parses_speeds_dict_when_present(self):
        """When a monster entry carries a `speeds` dict, the loader parses it."""
        loader = DataLoader()
        fake_monster_catalog = {
            "merfolk": {
                "name": "Merfolk",
                "abilities": {
                    "str": 10,
                    "dex": 13,
                    "con": 12,
                    "int": 11,
                    "wis": 11,
                    "cha": 12,
                },
                "hp": "2d8",
                "ac": 11,
                "speed": 10,
                "speeds": {"walk": 10, "swim": 40},
            }
        }
        with patch.object(loader, "load_monsters", return_value=fake_monster_catalog):
            merfolk = loader.create_monster("merfolk")
        assert merfolk.speeds == {MovementMode.WALK: 10, MovementMode.SWIM: 40}
        # Legacy `speed` attribute mirrors WALK from the speeds dict.
        assert merfolk.speed == 10
