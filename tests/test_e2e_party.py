# ABOUTME: End-to-end tests for party playthrough
# ABOUTME: Tests complete party scenarios including combat, exploration, and item management

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus


@pytest.fixture
def default_party():
    """Create a default party of 4 fighters like in main.py."""
    thorin = Character(
        name="Thorin Ironshield",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=16,
            dexterity=12,
            constitution=15,
            intelligence=10,
            wisdom=12,
            charisma=8
        ),
        max_hp=12,
        ac=16,
        xp=0,
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"]
    )

    bjorn = Character(
        name="Bjorn Axebearer",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=15,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=10
        ),
        max_hp=12,
        ac=16,
        xp=0,
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"]
    )

    eldric = Character(
        name="Eldric Swiftblade",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=14,
            dexterity=16,
            constitution=13,
            intelligence=10,
            wisdom=12,
            charisma=8
        ),
        max_hp=11,
        ac=16,
        xp=0,
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"]
    )

    gareth = Character(
        name="Gareth Stormwind",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=Abilities(
            strength=15,
            dexterity=12,
            constitution=16,
            intelligence=10,
            wisdom=10,
            charisma=10
        ),
        max_hp=13,
        ac=16,
        xp=0,
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"]
    )

    return Party(characters=[thorin, bjorn, eldric, gareth])


@pytest.fixture
def game_with_default_party(default_party):
    """Create a game state with the default party."""
    event_bus = EventBus()
    data_loader = DataLoader()
    dice_roller = DiceRoller()

    game_state = GameState(
        party=default_party,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    return game_state


class TestPartyPlaythrough:
    """End-to-end tests for party playthrough."""

    def test_party_starts_game(self, game_with_default_party, default_party):
        """Test that the party starts the game correctly."""
        assert len(game_with_default_party.party.characters) == 4
        assert game_with_default_party.party == default_party
        assert not game_with_default_party.is_game_over()

        # All party members should be alive
        assert len(game_with_default_party.party.get_living_members()) == 4

    def test_party_status_display(self, game_with_default_party):
        """Test that party status shows all members correctly."""
        status = game_with_default_party.get_player_status()

        assert len(status) == 4

        # Check names
        expected_names = [
            "Thorin Ironshield",
            "Bjorn Axebearer",
            "Eldric Swiftblade",
            "Gareth Stormwind"
        ]

        for i, name in enumerate(expected_names):
            assert status[i]["name"] == name
            assert status[i]["alive"] is True
            assert status[i]["level"] == 1
            assert status[i]["xp"] == 0

    def test_party_combat_scenario(self, game_with_default_party, default_party):
        """Test a complete combat scenario with the party."""
        # Create enemies
        goblins = []
        for i in range(2):
            goblin = Creature(
                name=f"Goblin {i+1}",
                max_hp=7,
                ac=15,
                abilities=Abilities(
                    strength=8,
                    dexterity=14,
                    constitution=10,
                    intelligence=10,
                    wisdom=8,
                    charisma=8
                )
            )
            goblins.append(goblin)

        # Start combat
        game_with_default_party.active_enemies = goblins
        game_with_default_party._start_combat()

        assert game_with_default_party.in_combat
        assert len(game_with_default_party.initiative_tracker.get_all_combatants()) == 6  # 4 party + 2 goblins

        # Simulate combat: party attacks goblins
        for goblin in goblins:
            # Multiple party members attack until goblin dies
            for character in default_party.characters:
                if goblin.is_alive:
                    result = game_with_default_party.combat_engine.resolve_attack(
                        attacker=character,
                        defender=goblin,
                        attack_bonus=character.melee_attack_bonus,
                        damage_dice="1d8+10",  # High damage to ensure kill
                        apply_damage=True
                    )

        # Check combat end
        game_with_default_party._check_combat_end()

        # Combat should be over, party should have won
        assert not game_with_default_party.in_combat
        assert not default_party.is_wiped()

    def test_party_with_casualties_continues(
        self, game_with_default_party, default_party
    ):
        """Test that party continues fighting after losing members."""
        # Create a strong enemy
        ogre = Creature(
            name="Ogre",
            max_hp=59,
            ac=12,
            abilities=Abilities(
                strength=19,
                dexterity=8,
                constitution=16,
                intelligence=5,
                wisdom=7,
                charisma=7
            )
        )

        game_with_default_party.active_enemies = [ogre]
        game_with_default_party._start_combat()

        # Kill 2 party members
        default_party.characters[0].take_damage(default_party.characters[0].max_hp)
        default_party.characters[1].take_damage(default_party.characters[1].max_hp)

        # Remove from initiative
        game_with_default_party.initiative_tracker.remove_combatant(default_party.characters[0])
        game_with_default_party.initiative_tracker.remove_combatant(default_party.characters[1])

        # Game should not be over
        assert not game_with_default_party.is_game_over()
        assert len(default_party.get_living_members()) == 2

        # Combat should continue
        assert not game_with_default_party.initiative_tracker.is_combat_over()

    def test_party_wipe_ends_game(self, game_with_default_party, default_party):
        """Test that party wipe ends the game."""
        # Kill all party members
        for character in default_party.characters:
            character.take_damage(character.max_hp)

        # Game should be over
        assert game_with_default_party.is_game_over()
        assert default_party.is_wiped()
        assert len(default_party.get_living_members()) == 0

    def test_party_xp_distribution(self, game_with_default_party, default_party):
        """Test that XP is distributed correctly to all party members."""
        # Create and defeat a goblin
        goblin = Creature(
            name="Goblin",
            max_hp=7,
            ac=15,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=10,
                intelligence=10,
                wisdom=8,
                charisma=8
            )
        )

        game_with_default_party.active_enemies = [goblin]
        game_with_default_party._start_combat()

        # Kill goblin
        goblin.take_damage(goblin.max_hp)

        # End combat (distributes XP)
        game_with_default_party._end_combat()

        # All party members should have equal XP
        xp_values = [char.xp for char in default_party.characters]
        assert all(xp == xp_values[0] for xp in xp_values)
        assert all(xp >= 0 for xp in xp_values)

    def test_party_gold_distribution(self, game_with_default_party, default_party):
        """Test that gold is distributed among party members."""
        room = game_with_default_party.get_current_room()

        # Mock a room with 100 gold
        room["searchable"] = True
        room["searched"] = False
        room["items"] = [{"type": "gold", "amount": 100}]

        # Search room
        game_with_default_party.search_room()

        # Each party member should get 25 gold
        for character in default_party.characters:
            assert character.inventory.gold == 25

    def test_party_item_pickup(self, game_with_default_party, default_party):
        """Test that items go to first living party member."""
        room = game_with_default_party.get_current_room()

        # Mock a room with an item
        room["searchable"] = True
        room["searched"] = False
        room["items"] = [{"type": "item", "id": "longsword"}]

        # Search room
        game_with_default_party.search_room()

        # First living member should have the item
        first_living = default_party.get_living_members()[0]
        weapons = first_living.inventory.get_items_by_category("weapons")

        # Should have at least the longsword
        assert len(weapons) > 0

    def test_party_exploration(self, game_with_default_party):
        """Test that party can explore the dungeon."""
        initial_room = game_with_default_party.current_room_id

        # Try to move (direction depends on dungeon layout)
        success = game_with_default_party.move("east")

        # If move was successful, room should change
        if success:
            assert game_with_default_party.current_room_id != initial_room

    def test_party_survives_multiple_combats(
        self, game_with_default_party, default_party
    ):
        """Test that party can survive multiple combat encounters."""
        # First combat
        goblin1 = Creature(
            name="Goblin 1",
            max_hp=7,
            ac=15,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=10,
                intelligence=10,
                wisdom=8,
                charisma=8
            )
        )

        game_with_default_party.active_enemies = [goblin1]
        game_with_default_party._start_combat()
        goblin1.take_damage(goblin1.max_hp)
        game_with_default_party._check_combat_end()

        assert not game_with_default_party.in_combat

        # Second combat
        goblin2 = Creature(
            name="Goblin 2",
            max_hp=7,
            ac=15,
            abilities=Abilities(
                strength=8,
                dexterity=14,
                constitution=10,
                intelligence=10,
                wisdom=8,
                charisma=8
            )
        )

        game_with_default_party.active_enemies = [goblin2]
        game_with_default_party._start_combat()
        goblin2.take_damage(goblin2.max_hp)
        game_with_default_party._check_combat_end()

        # Party should still be alive
        assert not game_with_default_party.is_game_over()
        assert not default_party.is_wiped()


class TestPartyCharacteristics:
    """Test the characteristics of the default party."""

    def test_party_has_varied_stats(self, default_party):
        """Test that party members have varied ability scores."""
        # Check that Thorin has highest STR
        assert default_party.characters[0].abilities.strength == 16

        # Check that Eldric has highest DEX
        assert default_party.characters[2].abilities.dexterity == 16

        # Check that Gareth has highest CON
        assert default_party.characters[3].abilities.constitution == 16

    def test_party_hp_variation(self, default_party):
        """Test that party members have different HP based on CON."""
        # Gareth should have highest HP (13)
        assert default_party.characters[3].max_hp == 13

        # Eldric should have lowest HP (11)
        assert default_party.characters[2].max_hp == 11

    def test_all_party_members_are_fighters(self, default_party):
        """Test that all party members are fighters."""
        for character in default_party.characters:
            assert character.character_class == CharacterClass.FIGHTER
            assert character.level == 1

    def test_party_members_have_unique_names(self, default_party):
        """Test that all party members have unique names."""
        names = [char.name for char in default_party.characters]
        assert len(set(names)) == 4


class TestPartyRoomEntry:
    """Test party entering rooms with enemies."""

    def test_party_triggers_combat_on_enemy_room(self, game_with_default_party):
        """Test that entering a room with enemies starts combat."""
        # Get current room and add enemies
        room = game_with_default_party.get_current_room()
        room["enemies"] = ["goblin"]  # Add enemy ID

        # Manually trigger enemy check
        game_with_default_party._check_for_enemies()

        # Combat should have started
        if game_with_default_party.active_enemies:
            assert game_with_default_party.in_combat
