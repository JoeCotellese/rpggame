"""End-to-end tests for character creation system"""

import pytest
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party
from dnd_engine.core.game_state import GameState
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import EquipmentSlot
from dnd_engine.utils.events import EventBus


class TestCharacterCreationE2E:
    """End-to-end tests for character creation and game integration"""

    def test_data_files_exist_and_valid(self):
        """Verify all required data files exist and are valid"""
        data_loader = DataLoader()

        # Load races
        races_data = data_loader.load_races()
        assert "human" in races_data
        assert "mountain_dwarf" in races_data
        assert "high_elf" in races_data
        assert "halfling" in races_data

        # Verify race structure
        for race_id, race in races_data.items():
            assert "name" in race
            assert "ability_bonuses" in race
            assert "description" in race

        # Load classes
        classes_data = data_loader.load_classes()
        assert "fighter" in classes_data

        # Verify class has ability_priorities
        fighter = classes_data["fighter"]
        assert "ability_priorities" in fighter
        assert len(fighter["ability_priorities"]) == 6
        assert "strength" in fighter["ability_priorities"]

        # Verify starting equipment is a list
        assert "starting_equipment" in fighter
        assert isinstance(fighter["starting_equipment"], list)

        # Load items
        items_data = data_loader.load_items()
        assert "weapons" in items_data
        assert "armor" in items_data
        assert "consumables" in items_data

    def test_create_character_and_start_game(self):
        """Test creating a character and starting a game"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        # Create a character programmatically (not interactive)
        all_rolls = factory.roll_all_abilities(factory.dice_roller)
        scores = [score for score, _ in all_rolls]

        classes_data = data_loader.load_classes()
        races_data = data_loader.load_races()
        items_data = data_loader.load_items()

        abilities = factory.auto_assign_abilities(scores, classes_data["fighter"])
        abilities = factory.apply_racial_bonuses(abilities, races_data["mountain_dwarf"])

        abilities_obj = Abilities(
            strength=abilities["strength"],
            dexterity=abilities["dexterity"],
            constitution=abilities["constitution"],
            intelligence=abilities["intelligence"],
            wisdom=abilities["wisdom"],
            charisma=abilities["charisma"]
        )

        con_modifier = factory.calculate_ability_modifier(abilities["constitution"])
        hp = factory.calculate_hp(classes_data["fighter"], con_modifier)

        armor_data = items_data["armor"]["chain_mail"]
        ac = factory.calculate_ac(armor_data, abilities_obj.dex_mod)

        character = Character(
            name="E2E Test Hero",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities_obj,
            max_hp=hp,
            ac=ac,
            race="mountain_dwarf"
        )

        factory.apply_starting_equipment(character, classes_data["fighter"], items_data)

        # Create party with character
        party = Party(characters=[character])

        # Create game state
        event_bus = EventBus()
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus
        )

        # Verify game state is valid
        assert game_state.party is not None
        assert len(game_state.party.characters) == 1
        assert game_state.party.characters[0].name == "E2E Test Hero"
        assert not game_state.is_game_over()

    def test_created_character_can_explore(self):
        """Test that a created character can explore the dungeon"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        # Create character
        all_rolls = factory.roll_all_abilities(factory.dice_roller)
        scores = [score for score, _ in all_rolls]

        classes_data = data_loader.load_classes()
        races_data = data_loader.load_races()
        items_data = data_loader.load_items()

        abilities = factory.auto_assign_abilities(scores, classes_data["fighter"])
        abilities = factory.apply_racial_bonuses(abilities, races_data["human"])

        abilities_obj = Abilities(
            strength=abilities["strength"],
            dexterity=abilities["dexterity"],
            constitution=abilities["constitution"],
            intelligence=abilities["intelligence"],
            wisdom=abilities["wisdom"],
            charisma=abilities["charisma"]
        )

        con_modifier = factory.calculate_ability_modifier(abilities["constitution"])
        hp = factory.calculate_hp(classes_data["fighter"], con_modifier)

        armor_data = items_data["armor"]["chain_mail"]
        ac = factory.calculate_ac(armor_data, abilities_obj.dex_mod)

        character = Character(
            name="Explorer",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities_obj,
            max_hp=hp,
            ac=ac,
            race="human"
        )

        factory.apply_starting_equipment(character, classes_data["fighter"], items_data)

        # Create game state
        party = Party(characters=[character])
        event_bus = EventBus()
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus
        )

        # Test exploration
        room_desc = game_state.get_room_description()
        assert room_desc is not None
        assert len(room_desc) > 0

        # Test player status
        status = game_state.get_player_status()
        assert len(status) == 1
        assert status[0]["name"] == "Explorer"
        assert status[0]["alive"] is True

    def test_created_character_can_fight(self):
        """Test that a created character can engage in combat"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        # Create a strong character for testing
        abilities_obj = Abilities(
            strength=18,  # High STR for reliable hits
            dexterity=14,
            constitution=16,
            intelligence=10,
            wisdom=12,
            charisma=8
        )

        character = Character(
            name="Warrior",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities_obj,
            max_hp=13,
            ac=16,
            race="human"
        )

        # Apply equipment
        classes_data = data_loader.load_classes()
        items_data = data_loader.load_items()
        factory.apply_starting_equipment(character, classes_data["fighter"], items_data)

        # Create game state
        party = Party(characters=[character])
        event_bus = EventBus()
        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus
        )

        # Verify character has combat capabilities
        assert character.melee_attack_bonus >= 2
        assert character.melee_damage_bonus >= 0
        assert character.proficiency_bonus == 2
        assert character.is_alive

    def test_all_races_create_valid_characters(self):
        """Test that all races can create valid, playable characters"""
        data_loader = DataLoader()
        factory = CharacterFactory(dice_roller=DiceRoller(seed=42))

        races_data = data_loader.load_races()
        classes_data = data_loader.load_classes()
        items_data = data_loader.load_items()

        for race_id in races_data.keys():
            # Create character with this race
            all_rolls = factory.roll_all_abilities(factory.dice_roller)
            scores = [score for score, _ in all_rolls]

            abilities = factory.auto_assign_abilities(scores, classes_data["fighter"])
            abilities = factory.apply_racial_bonuses(abilities, races_data[race_id])

            abilities_obj = Abilities(
                strength=abilities["strength"],
                dexterity=abilities["dexterity"],
                constitution=abilities["constitution"],
                intelligence=abilities["intelligence"],
                wisdom=abilities["wisdom"],
                charisma=abilities["charisma"]
            )

            con_modifier = factory.calculate_ability_modifier(abilities["constitution"])
            hp = factory.calculate_hp(classes_data["fighter"], con_modifier)

            armor_data = items_data["armor"]["chain_mail"]
            ac = factory.calculate_ac(armor_data, abilities_obj.dex_mod)

            character = Character(
                name=f"Test {race_id}",
                character_class=CharacterClass.FIGHTER,
                level=1,
                abilities=abilities_obj,
                max_hp=hp,
                ac=ac,
                race=race_id
            )

            factory.apply_starting_equipment(character, classes_data["fighter"], items_data)

            # Verify character is valid
            assert character.name == f"Test {race_id}"
            assert character.race == race_id
            assert character.is_alive
            assert character.max_hp >= 1
            assert character.ac >= 10
            assert character.inventory.get_equipped_item(EquipmentSlot.WEAPON) is not None

    def test_character_creation_with_different_seeds(self):
        """Test that different seeds produce different but valid characters"""
        data_loader = DataLoader()

        classes_data = data_loader.load_classes()
        races_data = data_loader.load_races()
        items_data = data_loader.load_items()

        characters = []

        # Create 5 characters with different seeds
        for seed in [1, 2, 3, 4, 5]:
            factory = CharacterFactory(dice_roller=DiceRoller(seed=seed))

            all_rolls = factory.roll_all_abilities(factory.dice_roller)
            scores = [score for score, _ in all_rolls]

            abilities = factory.auto_assign_abilities(scores, classes_data["fighter"])
            abilities = factory.apply_racial_bonuses(abilities, races_data["human"])

            abilities_obj = Abilities(
                strength=abilities["strength"],
                dexterity=abilities["dexterity"],
                constitution=abilities["constitution"],
                intelligence=abilities["intelligence"],
                wisdom=abilities["wisdom"],
                charisma=abilities["charisma"]
            )

            con_modifier = factory.calculate_ability_modifier(abilities["constitution"])
            hp = factory.calculate_hp(classes_data["fighter"], con_modifier)

            armor_data = items_data["armor"]["chain_mail"]
            ac = factory.calculate_ac(armor_data, abilities_obj.dex_mod)

            character = Character(
                name=f"Hero {seed}",
                character_class=CharacterClass.FIGHTER,
                level=1,
                abilities=abilities_obj,
                max_hp=hp,
                ac=ac,
                race="human"
            )

            characters.append(character)

        # Verify all characters are valid
        for character in characters:
            assert character.is_alive
            assert character.max_hp >= 1

        # Verify at least some variation in stats (not all identical)
        hp_values = [c.max_hp for c in characters]
        assert len(set(hp_values)) > 1  # At least some different HP values
