# ABOUTME: Tests for SRD A/B/C starting equipment options, pack expansion, and legacy fallback
# ABOUTME: Covers _resolve_starting_items helper, apply_starting_equipment option_index, and create_character threading

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import EquipmentSlot


class TestPacksData:
    """Verify the new packs category exists in items.json with expected entries."""

    def test_packs_category_present(self):
        items = DataLoader().load_items()
        assert "packs" in items

    def test_expected_packs_defined(self):
        packs = DataLoader().load_items()["packs"]
        for pack_id in ("dungeoneers_pack", "explorers_pack", "burglars_pack", "scholars_pack"):
            assert pack_id in packs, f"missing pack: {pack_id}"

    def test_dungeoneers_pack_contents(self):
        pack = DataLoader().load_items()["packs"]["dungeoneers_pack"]
        assert "contents" in pack
        contents = pack["contents"]
        assert contents.get("rations") == 10
        assert contents.get("torch") == 10
        assert contents.get("piton") == 10
        assert contents.get("backpack") == 1
        assert contents.get("rope_hempen") == 1
        assert contents.get("waterskin") == 1
        assert contents.get("tinderbox") == 1
        assert contents.get("crowbar") == 1
        assert contents.get("hammer") == 1

    def test_scholars_pack_contents(self):
        pack = DataLoader().load_items()["packs"]["scholars_pack"]
        contents = pack["contents"]
        assert contents.get("book") == 1
        assert contents.get("parchment") == 10
        assert contents.get("ink") == 1

    def test_burglars_pack_contents(self):
        """Burglar's Pack contents must match the SRD description (issue #384)."""
        pack = DataLoader().load_items()["packs"]["burglars_pack"]
        contents = pack["contents"]
        assert contents.get("backpack") == 1
        assert contents.get("ball_bearings") == 1
        assert contents.get("string") == 1
        assert contents.get("bell") == 1
        assert contents.get("candle") == 5
        assert contents.get("crowbar") == 1
        assert contents.get("hammer") == 1
        assert contents.get("piton") == 10
        assert contents.get("lantern_hooded") == 1
        assert contents.get("oil_flask") == 2
        assert contents.get("rations") == 5
        assert contents.get("tinderbox") == 1
        assert contents.get("waterskin") == 1
        assert contents.get("rope_hempen") == 1
        # Torch is NOT in the SRD Burglar's Pack — was a copy-paste from Dungeoneer's Pack
        assert "torch" not in contents

    def test_all_pack_referenced_items_exist(self):
        """All items referenced by any pack.contents must exist in items.json."""
        items = DataLoader().load_items()
        # Flatten all non-pack categories into a single ID set
        all_item_ids: set[str] = set()
        for category, entries in items.items():
            if category == "packs":
                continue
            all_item_ids.update(entries.keys())
        for pack_id, pack in items["packs"].items():
            for item_id in pack["contents"]:
                assert item_id in all_item_ids, (
                    f"{pack_id} references missing item: {item_id}"
                )


class TestResolveStartingItems:
    """Verify _resolve_starting_items resolves options, expands packs, and falls back to legacy."""

    def test_legacy_class_data_returns_flat_list(self):
        """Class data with only legacy `starting_equipment` is honored as a single option."""
        items = DataLoader().load_items()
        class_data = {"starting_equipment": ["longsword", "chain_mail"]}

        resolved = CharacterFactory._resolve_starting_items(class_data, items, option_index=0)

        # Each item is a (item_id, quantity) tuple
        assert ("longsword", 1) in resolved
        assert ("chain_mail", 1) in resolved
        assert len(resolved) == 2

    def test_options_field_selects_by_index(self):
        items = DataLoader().load_items()
        class_data = {
            "starting_equipment_options": [
                {"name": "A", "items": ["longsword"], "gold": 1},
                {"name": "B", "items": ["shortsword"], "gold": 2},
            ]
        }

        resolved_a = CharacterFactory._resolve_starting_items(class_data, items, option_index=0)
        resolved_b = CharacterFactory._resolve_starting_items(class_data, items, option_index=1)

        assert ("longsword", 1) in resolved_a
        assert ("shortsword", 1) not in resolved_a
        assert ("shortsword", 1) in resolved_b
        assert ("longsword", 1) not in resolved_b

    def test_option_index_above_range_raises(self):
        """option_index >= len(options) must raise ValueError."""
        items = DataLoader().load_items()
        class_data = {
            "starting_equipment_options": [
                {"name": "A", "items": ["longsword"], "gold": 0},
                {"name": "B", "items": ["shortsword"], "gold": 0},
            ]
        }
        with pytest.raises(ValueError, match="out of range"):
            CharacterFactory._resolve_starting_items(class_data, items, option_index=99)

    def test_option_index_negative_raises(self):
        """Negative option_index must raise ValueError instead of silently wrapping."""
        items = DataLoader().load_items()
        class_data = {
            "starting_equipment_options": [
                {"name": "A", "items": ["longsword"], "gold": 0},
            ]
        }
        with pytest.raises(ValueError, match="out of range"):
            CharacterFactory._resolve_starting_items(class_data, items, option_index=-1)

    def test_pack_item_expands_to_contents(self):
        items = DataLoader().load_items()
        class_data = {
            "starting_equipment_options": [
                {"name": "A", "items": ["dungeoneers_pack"], "gold": 0},
            ]
        }

        resolved = CharacterFactory._resolve_starting_items(class_data, items, option_index=0)

        resolved_dict = dict(resolved)
        # Pack itself should not be in resolved items — only its contents
        assert "dungeoneers_pack" not in resolved_dict
        assert resolved_dict.get("rations") == 10
        assert resolved_dict.get("torch") == 10
        assert resolved_dict.get("backpack") == 1

    def test_options_with_empty_items_returns_empty_list(self):
        """Gold-only option (e.g. SRD Option C) resolves to no items."""
        items = DataLoader().load_items()
        class_data = {
            "starting_equipment_options": [
                {"name": "Gold Only", "items": [], "gold": 155},
            ]
        }

        resolved = CharacterFactory._resolve_starting_items(class_data, items, option_index=0)
        assert resolved == []


class TestMissingWeaponsAndSpellbook:
    """Verify new SRD weapons + spellbook are loadable."""

    def test_greatsword_loaded(self):
        weapons = DataLoader().load_items()["weapons"]
        assert "greatsword" in weapons
        assert weapons["greatsword"]["damage"] == "2d6"
        assert weapons["greatsword"]["damage_type"] == "slashing"
        assert "heavy" in weapons["greatsword"]["properties"]
        assert "two-handed" in weapons["greatsword"]["properties"]

    def test_scimitar_loaded(self):
        weapons = DataLoader().load_items()["weapons"]
        assert "scimitar" in weapons
        assert weapons["scimitar"]["damage"] == "1d6"
        assert "finesse" in weapons["scimitar"]["properties"]
        assert "light" in weapons["scimitar"]["properties"]

    def test_javelin_loaded(self):
        weapons = DataLoader().load_items()["weapons"]
        assert "javelin" in weapons
        assert "thrown" in weapons["javelin"]["properties"]
        assert weapons["javelin"]["range"] == "30/120"

    def test_light_hammer_loaded(self):
        weapons = DataLoader().load_items()["weapons"]
        assert "light_hammer" in weapons
        assert weapons["light_hammer"]["damage"] == "1d4"
        assert "thrown" in weapons["light_hammer"]["properties"]

    def test_flail_loaded(self):
        weapons = DataLoader().load_items()["weapons"]
        assert "flail" in weapons
        assert weapons["flail"]["damage"] == "1d8"
        assert weapons["flail"]["damage_type"] == "bludgeoning"

    def test_spellbook_loaded(self):
        equipment = DataLoader().load_items()["equipment"]
        assert "spellbook" in equipment


def _new_blank_character(klass: CharacterClass = CharacterClass.FIGHTER) -> Character:
    return Character(
        name="Test",
        character_class=klass,
        level=1,
        abilities=Abilities(10, 10, 10, 10, 10, 10),
        max_hp=10,
        ac=10,
    )


class TestApplyStartingEquipmentWithOptions:
    """Verify apply_starting_equipment honors option_index and gold."""

    def test_default_option_index_zero_preserves_legacy_loadout(self):
        """Fighter Option 0 must equal current loadout for test-compat."""
        loader = DataLoader()
        items = loader.load_items()
        classes = loader.load_classes()
        character = _new_blank_character()

        CharacterFactory.apply_starting_equipment(character, classes["fighter"], items)

        assert character.inventory.has_item("longsword")
        assert character.inventory.has_item("chain_mail")
        assert character.inventory.get_item_quantity("potion_of_healing") == 5
        assert character.inventory.gold == 10

    def test_option_index_one_grants_alternate_loadout_and_gold(self):
        """A synthetic class with two options grants the chosen option's items + gold."""
        items = DataLoader().load_items()
        class_data = {
            "starting_equipment_options": [
                {"name": "A", "items": ["longsword"], "gold": 5},
                {"name": "B", "items": ["shortsword"], "gold": 99},
            ],
        }
        character = _new_blank_character()

        CharacterFactory.apply_starting_equipment(character, class_data, items, option_index=1)

        assert character.inventory.has_item("shortsword")
        assert not character.inventory.has_item("longsword")
        assert character.inventory.gold == 99

    def test_legacy_class_data_ignores_option_index(self):
        """Classes without options field still work; option_index is ignored."""
        items = DataLoader().load_items()
        class_data = {
            "starting_equipment": ["longsword"],
            "starting_gold": 7,
        }
        character = _new_blank_character()

        CharacterFactory.apply_starting_equipment(character, class_data, items, option_index=5)

        assert character.inventory.has_item("longsword")
        assert character.inventory.gold == 7

    def test_pack_item_in_option_expands_into_inventory(self):
        items = DataLoader().load_items()
        class_data = {
            "starting_equipment_options": [
                {"name": "Packer", "items": ["dungeoneers_pack"], "gold": 0},
            ],
        }
        character = _new_blank_character()

        CharacterFactory.apply_starting_equipment(character, class_data, items, option_index=0)

        # Pack should NOT exist as an item; its contents should
        assert not character.inventory.has_item("dungeoneers_pack")
        assert character.inventory.has_item("backpack")
        assert character.inventory.get_item_quantity("rations") == 10
        assert character.inventory.get_item_quantity("torch") == 10


class TestClassOptionsPopulated:
    """Verify the three classes have three options each and Option 0 matches legacy loadout."""

    def test_fighter_has_three_options(self):
        classes = DataLoader().load_classes()
        opts = classes["fighter"].get("starting_equipment_options")
        assert opts is not None and len(opts) == 3

    def test_rogue_has_three_options(self):
        classes = DataLoader().load_classes()
        opts = classes["rogue"].get("starting_equipment_options")
        assert opts is not None and len(opts) == 3

    def test_wizard_has_three_options(self):
        classes = DataLoader().load_classes()
        opts = classes["wizard"].get("starting_equipment_options")
        assert opts is not None and len(opts) == 3

    def test_fighter_option_zero_matches_legacy(self):
        classes = DataLoader().load_classes()
        opt0 = classes["fighter"]["starting_equipment_options"][0]
        # Must produce: longsword, chain_mail, 5 potions, 10 gp
        assert "longsword" in opt0["items"]
        assert "chain_mail" in opt0["items"]
        assert opt0["items"].count("potion_of_healing") == 5
        assert opt0["gold"] == 10

    def test_rogue_option_zero_matches_legacy(self):
        classes = DataLoader().load_classes()
        opt0 = classes["rogue"]["starting_equipment_options"][0]
        assert "rapier" in opt0["items"]
        assert "shortbow" in opt0["items"]
        assert "leather_armor" in opt0["items"]
        assert "thieves_tools" in opt0["items"]
        assert opt0["items"].count("potion_of_healing") == 2
        assert opt0["gold"] == 15

    def test_wizard_option_zero_matches_legacy(self):
        classes = DataLoader().load_classes()
        opt0 = classes["wizard"]["starting_equipment_options"][0]
        assert "quarterstaff" in opt0["items"]
        assert "dagger" in opt0["items"]
        assert opt0["items"].count("potion_of_healing") == 1
        assert opt0["gold"] == 5

    def test_each_class_third_option_is_gold_only(self):
        classes = DataLoader().load_classes()
        for class_id in ("fighter", "rogue", "wizard"):
            opt2 = classes[class_id]["starting_equipment_options"][2]
            assert opt2["items"] == [], f"{class_id} option 2 should be gold-only"
            assert opt2["gold"] > 0, f"{class_id} option 2 should grant gold"


class TestCreateCharacterWithOptionIndex:
    """Verify create_character threads option_index through to inventory and AC."""

    def test_create_character_default_option_index(self):
        """Default (no option_index passed) creates the legacy Fighter."""
        loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        character = factory.create_character(
            class_name="fighter",
            race_name="human",
            data_loader=loader,
            level=1,
            name="Default Fighter",
            abilities={
                "strength": 15,
                "dexterity": 12,
                "constitution": 14,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            },
        )

        assert character.inventory.has_item("longsword")
        assert character.inventory.has_item("chain_mail")
        assert character.inventory.gold == 10

    def test_create_character_option_index_two_is_gold_only_fighter(self):
        """Fighter option 2 (gold-only) creates a character with 155 gp and no armor."""
        loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        character = factory.create_character(
            class_name="fighter",
            race_name="human",
            data_loader=loader,
            level=1,
            name="Mercenary",
            abilities={
                "strength": 15,
                "dexterity": 14,
                "constitution": 14,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            },
            option_index=2,
        )

        assert character.inventory.get_equipped_item(EquipmentSlot.ARMOR) is None
        assert character.inventory.gold == 155
        # AC = 10 + dex_mod (no armor); dex 14 → +2 → AC 12
        assert character.ac == 12
