# ABOUTME: Integration tests for ammunition tracking with ranged weapons
# ABOUTME: Tests the full flow of ammunition consumption during ranged combat

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import EquipmentSlot, Inventory


@pytest.fixture
def data_loader():
    """Load game data"""
    return DataLoader()


@pytest.fixture
def items_data(data_loader):
    """Load items data"""
    return data_loader.load_items()


@pytest.fixture
def classes_data(data_loader):
    """Load classes data"""
    return data_loader.load_classes()


@pytest.fixture
def archer():
    """Create a DEX-focused character with a shortbow"""
    abilities = Abilities(
        strength=10,
        dexterity=16,  # +3 modifier
        constitution=14,
        intelligence=10,
        wisdom=12,
        charisma=10
    )
    archer = Character(
        name="Archer",
        character_class=CharacterClass.ROGUE,
        level=1,
        abilities=abilities,
        max_hp=10,
        ac=13,
        weapon_proficiencies=["simple"],
        armor_proficiencies=["light"]
    )
    # Equip shortbow
    archer.inventory.add_item("shortbow", "weapons", 1)
    archer.inventory.equip_item("shortbow", EquipmentSlot.WEAPON)
    return archer


@pytest.fixture
def game_state(archer):
    """Create a game state for testing with the archer in the party"""
    party = Party([archer])
    return GameState(
        party=party,
        dungeon_name="crypt",
        campaign_id="the_unquiet_dead",
    )


@pytest.fixture
def enemy():
    """Create a generic enemy for testing"""
    abilities = Abilities(
        strength=10,
        dexterity=10,
        constitution=11,
        intelligence=3,
        wisdom=10,
        charisma=3
    )
    return Creature(
        name="Goblin",
        max_hp=100,  # High HP so it survives multiple attacks
        ac=10,  # Low AC for reliable hits
        abilities=abilities
    )


class TestStartingAmmunition:
    """Tests for automatic ammunition in starting equipment"""

    def test_rogue_receives_arrows_with_shortbow(
        self, classes_data, items_data
    ):
        """Rogues starting with shortbow should automatically get arrows"""
        abilities = Abilities(
            strength=10,
            dexterity=16,
            constitution=14,
            intelligence=12,
            wisdom=13,
            charisma=8
        )
        rogue = Character(
            name="Test Rogue",
            character_class=CharacterClass.ROGUE,
            level=1,
            abilities=abilities,
            max_hp=8,
            ac=14,
            inventory=Inventory()
        )

        # Apply starting equipment
        rogue_data = classes_data["rogue"]
        CharacterFactory.apply_starting_equipment(rogue, rogue_data, items_data)

        # Check that arrows were auto-added
        assert rogue.inventory.has_item("arrows")
        # Standard arrow quiver is 20 arrows
        assert rogue.inventory.get_ammo_count("arrows") == 20

    def test_fighter_with_longbow_receives_arrows(self, items_data):
        """Characters given longbow via starting equipment should get arrows"""
        abilities = Abilities(
            strength=12,
            dexterity=16,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=10
        )
        fighter = Character(
            name="Archer Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=10,
            inventory=Inventory()
        )

        # Simulate class data that includes a longbow
        class_data = {
            "starting_equipment": ["longbow", "leather_armor"],
            "starting_gold": 10
        }

        CharacterFactory.apply_starting_equipment(fighter, class_data, items_data)

        # Check that arrows were auto-added
        assert fighter.inventory.has_item("arrows")
        assert fighter.inventory.get_ammo_count("arrows") == 20

    def test_crossbow_user_receives_bolts(self, items_data):
        """Characters with crossbow should get bolts, not arrows"""
        abilities = Abilities(
            strength=10,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=10
        )
        character = Character(
            name="Crossbowman",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=10,
            inventory=Inventory()
        )

        class_data = {
            "starting_equipment": ["light_crossbow"],
            "starting_gold": 10
        }

        CharacterFactory.apply_starting_equipment(character, class_data, items_data)

        # Check that bolts were auto-added (not arrows)
        assert character.inventory.has_item("bolts")
        assert not character.inventory.has_item("arrows")
        assert character.inventory.get_ammo_count("bolts") == 20

    def test_melee_weapon_does_not_receive_ammo(self, items_data):
        """Characters with only melee weapons should not get ammunition"""
        abilities = Abilities(
            strength=16,
            dexterity=10,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=10
        )
        fighter = Character(
            name="Melee Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=10,
            inventory=Inventory()
        )

        class_data = {
            "starting_equipment": ["longsword", "chain_mail"],
            "starting_gold": 10
        }

        CharacterFactory.apply_starting_equipment(fighter, class_data, items_data)

        # Should not have any ammunition
        assert not fighter.inventory.has_item("arrows")
        assert not fighter.inventory.has_item("bolts")


class TestAmmunitionConsumptionInCombat:
    """Tests for ammunition consumption during ranged attacks"""

    def test_ranged_attack_consumes_one_arrow(self, archer, enemy, game_state):
        """Attacking with shortbow should consume one arrow"""
        # Give archer some arrows
        archer.inventory.add_item("arrows", "ammunition", quantity=20)
        initial_count = archer.inventory.get_ammo_count("arrows")

        # Execute attack
        result = game_state.execute_player_attack(archer, enemy)

        # Attack should succeed
        assert result.success is True
        assert result.error is None

        # One arrow should be consumed
        assert archer.inventory.get_ammo_count("arrows") == initial_count - 1

    def test_multiple_attacks_consume_multiple_arrows(
        self, archer, enemy, game_state
    ):
        """Multiple attacks should consume one arrow each"""
        archer.inventory.add_item("arrows", "ammunition", quantity=5)

        # Execute 3 attacks
        for i in range(3):
            result = game_state.execute_player_attack(archer, enemy)
            assert result.success is True
            assert archer.inventory.get_ammo_count("arrows") == 5 - (i + 1)

        # Should have 2 arrows remaining
        assert archer.inventory.get_ammo_count("arrows") == 2

    def test_attack_fails_without_ammunition(self, archer, enemy, game_state):
        """Attack should fail gracefully when out of ammunition"""
        # Archer has no arrows
        assert archer.inventory.get_ammo_count("arrows") == 0

        # Execute attack
        result = game_state.execute_player_attack(archer, enemy)

        # Attack should fail with appropriate error
        assert result.success is False
        assert result.error is not None
        assert "ammunition" in result.error.lower() or "ammo" in result.error.lower()

    def test_last_arrow_can_be_used(self, archer, enemy, game_state):
        """Character should be able to fire their last arrow"""
        archer.inventory.add_item("arrows", "ammunition", quantity=1)

        # First attack should succeed
        result = game_state.execute_player_attack(archer, enemy)
        assert result.success is True

        # Now out of ammo
        assert archer.inventory.get_ammo_count("arrows") == 0

        # Second attack should fail
        result = game_state.execute_player_attack(archer, enemy)
        assert result.success is False

    def test_melee_attack_does_not_consume_ammo(self, enemy):
        """Melee weapon attacks should not require or consume ammunition"""
        abilities = Abilities(
            strength=16,
            dexterity=10,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=10
        )
        fighter = Character(
            name="Melee Fighter",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=10,
            weapon_proficiencies=["simple", "martial"],
            armor_proficiencies=["light", "medium", "heavy", "shields"]
        )
        fighter.inventory.add_item("longsword", "weapons", 1)
        fighter.inventory.equip_item("longsword", EquipmentSlot.WEAPON)

        # Create game_state with fighter
        party = Party([fighter])
        game_state = GameState(party=party, dungeon_name="crypt", campaign_id="the_unquiet_dead")

        # Execute melee attack
        result = game_state.execute_player_attack(fighter, enemy)

        # Attack should succeed without needing ammunition
        assert result.success is True
        assert result.error is None


class TestAmmunitionWithDifferentWeapons:
    """Tests for ammunition compatibility with different weapon types"""

    def test_arrows_work_with_longbow(self, enemy):
        """Arrows should work with longbow"""
        abilities = Abilities(
            strength=10,
            dexterity=16,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=10
        )
        archer = Character(
            name="Longbow Archer",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=10,
            weapon_proficiencies=["simple", "martial"]
        )
        archer.inventory.add_item("longbow", "weapons", 1)
        archer.inventory.equip_item("longbow", EquipmentSlot.WEAPON)
        archer.inventory.add_item("arrows", "ammunition", quantity=20)

        party = Party([archer])
        game_state = GameState(party=party, dungeon_name="crypt", campaign_id="the_unquiet_dead")

        result = game_state.execute_player_attack(archer, enemy)

        assert result.success is True
        assert archer.inventory.get_ammo_count("arrows") == 19

    def test_bolts_work_with_crossbow(self, enemy):
        """Bolts should work with crossbow"""
        abilities = Abilities(
            strength=10,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=10
        )
        crossbowman = Character(
            name="Crossbowman",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=10,
            weapon_proficiencies=["simple", "martial"]
        )
        crossbowman.inventory.add_item("light_crossbow", "weapons", 1)
        crossbowman.inventory.equip_item("light_crossbow", EquipmentSlot.WEAPON)
        crossbowman.inventory.add_item("bolts", "ammunition", quantity=20)

        party = Party([crossbowman])
        game_state = GameState(party=party, dungeon_name="crypt", campaign_id="the_unquiet_dead")

        result = game_state.execute_player_attack(crossbowman, enemy)

        assert result.success is True
        assert crossbowman.inventory.get_ammo_count("bolts") == 19

    def test_wrong_ammo_type_fails(self, enemy):
        """Using wrong ammo type should fail (bolts with bow)"""
        abilities = Abilities(
            strength=10,
            dexterity=16,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=10
        )
        archer = Character(
            name="Confused Archer",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=10,
            weapon_proficiencies=["simple", "martial"]
        )
        archer.inventory.add_item("shortbow", "weapons", 1)
        archer.inventory.equip_item("shortbow", EquipmentSlot.WEAPON)
        # Give bolts instead of arrows
        archer.inventory.add_item("bolts", "ammunition", quantity=20)

        party = Party([archer])
        game_state = GameState(party=party, dungeon_name="crypt", campaign_id="the_unquiet_dead")

        result = game_state.execute_player_attack(archer, enemy)

        # Should fail because bolts aren't compatible with shortbow
        assert result.success is False
        assert result.error is not None
