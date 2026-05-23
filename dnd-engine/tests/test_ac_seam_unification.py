# ABOUTME: Tests for AC seam unification migrating AC_SET_BASE to the alt base-AC formula seam.
# ABOUTME: Validates that Mage Armor and Barkskin register/activate formulas instead of using AC_SET_BASE.

import json
from pathlib import Path

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.ac_formulas import (
    BASE_AC_FORMULAS,
    _barkskin_formula,
    _mage_armor_formula,
    get_base_ac_formula,
)
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.utils.events import EventBus


@pytest.fixture
def wizard():
    """Wizard with no armor: base AC 10, DEX 14 (+2)."""
    abilities = Abilities(
        strength=8,
        dexterity=14,
        constitution=12,
        intelligence=16,
        wisdom=10,
        charisma=10,
    )
    wiz = Character(
        name="Gandalf",
        character_class=CharacterClass.WIZARD,
        level=3,
        abilities=abilities,
        max_hp=18,
        ac=10,
        spellcasting_ability="intelligence",
        known_spells=["mage_armor"],
        prepared_spells=["mage_armor"],
    )
    wiz.add_resource_pool(
        ResourcePool(name="spell_slots_level_1", current=4, maximum=4, recovery_type="long_rest")
    )
    return wiz


@pytest.fixture
def game_state(wizard):
    data_loader = DataLoader()
    event_bus = EventBus()
    dice_roller = DiceRoller()
    party = Party()
    party.add_character(wizard)
    return GameState(
        party=party,
        dungeon_name="test_dungeon",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller,
    )


class TestACFormulaRegistry:
    """The named formula registry is the single source of truth for alt base-AC math."""

    def test_mage_armor_formula_returns_13_plus_dex(self, wizard):
        """SRD: Mage Armor sets base AC to 13 + Dexterity modifier."""
        assert _mage_armor_formula(wizard) == 15  # 13 + 2

    def test_barkskin_formula_acts_as_floor_of_17(self, wizard):
        """SRD: Barkskin gives AC 17 if creature's AC is lower than that."""
        # Wizard's stored base AC is 10, so floor raises it to 17.
        assert _barkskin_formula(wizard) == 17

    def test_barkskin_formula_does_not_lower_higher_base_ac(self):
        """A heavily armored creature's higher base AC isn't lowered to 17."""
        abilities = Abilities(
            strength=14, dexterity=10, constitution=14, intelligence=10, wisdom=10, charisma=10
        )
        # Plate-armor base AC 18 is higher than 17.
        knight = Character(
            name="Knight",
            character_class=CharacterClass.FIGHTER,
            level=3,
            abilities=abilities,
            max_hp=30,
            ac=18,
        )
        assert _barkskin_formula(knight) == 18

    def test_registry_contains_mage_armor_and_barkskin(self):
        """spells.json data refers to these formula IDs."""
        assert "mage_armor" in BASE_AC_FORMULAS
        assert "barkskin" in BASE_AC_FORMULAS

    def test_get_base_ac_formula_returns_none_for_unknown(self):
        assert get_base_ac_formula("not_a_real_formula") is None


class TestCastingMageArmorUsesAltFormulaSeam:
    """Casting Mage Armor must register/activate the alt formula on the target."""

    def test_casting_mage_armor_activates_alt_formula(self, game_state, wizard):
        """After cast, `active_base_ac_formula == 'mage_armor'`."""
        assert wizard.active_base_ac_formula is None

        result = game_state.cast_spell_exploration("Gandalf", "mage_armor")
        assert result["success"] is True

        assert wizard.active_base_ac_formula == "mage_armor"
        assert wizard.has_base_ac_formula("mage_armor")

    def test_mage_armor_yields_expected_effective_ac(self, game_state, wizard):
        """End-to-end: effective AC reflects 13 + DEX after cast."""
        assert game_state.get_effective_ac(wizard) == 10

        game_state.cast_spell_exploration("Gandalf", "mage_armor")

        # 13 + 2 (DEX) = 15
        assert game_state.get_effective_ac(wizard) == 15


class TestMageArmorExpiryClearsAltFormula:
    """When Mage Armor expires the alt selection must be cleared."""

    def test_mage_armor_expiry_deactivates_formula(self, game_state, wizard):
        """Advancing past 8 hours removes Mage Armor and clears the selection."""
        game_state.cast_spell_exploration("Gandalf", "mage_armor")
        assert wizard.active_base_ac_formula == "mage_armor"
        assert game_state.get_effective_ac(wizard) == 15

        # Mage Armor lasts 8 hours; advance 9 hours = 540 minutes.
        expired = game_state.time_manager.advance_time(60 * 9, reason="long_rest")

        assert any(e.source == "Mage Armor" for e in expired)
        assert wizard.active_base_ac_formula is None
        assert game_state.get_effective_ac(wizard) == 10


class TestAltFormulaWinsOverACSetBaseLegacy:
    """SRD § 'Only One Base AC' — the alt-formula selection is the single source of truth.

    Regression guard against the silent-overwrite footgun the AC_SET_BASE
    consumer used to introduce: with `get_effective_ac` consulting only
    `Creature.get_base_ac()`, a manually pre-registered alt formula on a
    creature must determine the base AC even if the migrated spell would
    also try to register a different formula. This test pins down the
    invariant that the seam (not the effect stack) is authoritative.
    """

    def test_alt_formula_replaces_pre_existing_base(self, game_state, wizard):
        """A registered+selected alt formula is the only base AC source."""
        wizard.register_base_ac_formula(
            "dragonborn_resilience", lambda c: 13 + c.abilities.con_mod
        )
        wizard.active_base_ac_formula = "dragonborn_resilience"

        # 13 + 1 (CON 12 = +1) = 14
        assert game_state.get_effective_ac(wizard) == 14

        # Casting Mage Armor switches the selection to mage_armor (one
        # base AC at a time). 13 + 2 (DEX) = 15.
        game_state.cast_spell_exploration("Gandalf", "mage_armor")
        assert wizard.active_base_ac_formula == "mage_armor"
        assert game_state.get_effective_ac(wizard) == 15


class TestACSetBaseLintData:
    """No new effect data may use the removed `ac_set_base` modifier_type.

    The migration moves Mage Armor (and Barkskin) onto the alt-formula
    seam. To prevent regressions, scan spells.json / items.json for
    `ac_set_base` modifier_type entries.
    """

    DATA_ROOT = Path(__file__).resolve().parents[1] / "dnd_engine" / "data" / "srd"

    def _scan_for_ac_set_base(self, data: object) -> list[str]:
        """Recursively collect any object with modifier_type == 'ac_set_base'."""
        hits: list[str] = []

        def walk(node, path):
            if isinstance(node, dict):
                if node.get("modifier_type") == "ac_set_base":
                    hits.append(path)
                for k, v in node.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    walk(item, f"{path}[{i}]")

        walk(data, "<root>")
        return hits

    def test_no_ac_set_base_modifier_in_spells_json(self):
        spells_file = self.DATA_ROOT / "spells.json"
        with open(spells_file) as f:
            spells = json.load(f)
        hits = self._scan_for_ac_set_base(spells)
        assert not hits, (
            "spells.json must not use the removed 'ac_set_base' modifier_type; "
            "use 'register_base_ac_formula' with a 'formula_id' referencing "
            "dnd_engine.rules.ac_formulas.BASE_AC_FORMULAS instead. Found at: "
            f"{hits}"
        )

    def test_no_ac_set_base_modifier_in_items_json(self):
        items_file = self.DATA_ROOT / "items.json"
        if not items_file.exists():
            return
        with open(items_file) as f:
            items = json.load(f)
        hits = self._scan_for_ac_set_base(items)
        assert not hits, (
            "items.json must not use the removed 'ac_set_base' modifier_type; "
            "use 'register_base_ac_formula' with a 'formula_id' referencing "
            "dnd_engine.rules.ac_formulas.BASE_AC_FORMULAS instead. Found at: "
            f"{hits}"
        )
