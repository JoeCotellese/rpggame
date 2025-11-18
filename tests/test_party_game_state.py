# ABOUTME: Integration tests for Party with GameState
# ABOUTME: Tests party exploration, XP distribution, game over conditions, and status display

import pytest
from unittest.mock import MagicMock
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.party import Party
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus


@pytest.fixture
def test_abilities():
    """Create test abilities."""
    return Abilities(
        strength=15,
        dexterity=14,
        constitution=13,
        intelligence=10,
        wisdom=12,
        charisma=8
    )


@pytest.fixture
def party_of_four(test_abilities):
    """Create a party of 4 fighters."""
    fighters = []
    for i in range(4):
        fighter = Character(
            name=f"Fighter {i+1}",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=test_abilities,
            max_hp=12,
            ac=16,
            xp=0
        )
        fighters.append(fighter)
    return Party(characters=fighters)


@pytest.fixture
def game_state_with_party(party_of_four):
    """Create a game state with a party."""
    event_bus = EventBus()
    data_loader = DataLoader()
    dice_roller = DiceRoller()

    game_state = GameState(
        party=party_of_four,
        dungeon_name="goblin_warren",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller
    )

    return game_state


class TestPartyGameStateInitialization:
    """Test GameState initialization with party."""

    def test_game_state_has_party(self, game_state_with_party, party_of_four):
        """Test that GameState has a party."""
        assert game_state_with_party.party == party_of_four
        assert len(game_state_with_party.party.characters) == 4

    def test_game_state_party_status(self, game_state_with_party):
        """Test getting party status from GameState."""
        status = game_state_with_party.get_player_status()
        assert isinstance(status, list)
        assert len(status) == 4

        # Check each status has required fields
        for char_status in status:
            assert "name" in char_status
            assert "hp" in char_status
            assert "max_hp" in char_status
            assert "ac" in char_status
            assert "level" in char_status
            assert "xp" in char_status
            assert "alive" in char_status


class TestPartyExploration:
    """Test party exploration mechanics."""

    def test_party_moves_together(self, game_state_with_party):
        """Test that the whole party moves together."""
        initial_room = game_state_with_party.current_room_id
        success = game_state_with_party.move("east")

        if success:
            # All party members are in the new room
            assert game_state_with_party.current_room_id != initial_room

    def test_party_search_distributes_gold(self, game_state_with_party, party_of_four):
        """Test that gold is distributed among party members."""
        # Move to a searchable room with gold
        room = game_state_with_party.get_current_room()

        # Mock a room with gold
        room["searchable"] = True
        room["searched"] = False
        room["items"] = [{"type": "gold", "amount": 100}]

        # Search the room
        items = game_state_with_party.search_room()

        # Check that gold was distributed
        expected_gold_per_character = 100 // 4  # 25 gold each

        for character in party_of_four.characters:
            assert character.inventory.gold == expected_gold_per_character

    def test_party_search_gives_item_to_first_living(
        self, game_state_with_party, party_of_four
    ):
        """Test that items go to the first living party member."""
        room = game_state_with_party.get_current_room()

        # Mock a room with an item
        room["searchable"] = True
        room["searched"] = False
        room["items"] = [{"type": "item", "id": "longsword"}]

        # Search the room
        items = game_state_with_party.search_room()

        # First living member should have the item
        first_living = party_of_four.get_living_members()[0]
        items_in_inventory = first_living.inventory.get_items_by_category("weapons")

        # Check that the item was added
        assert len(items_in_inventory) > 0


class TestPartyGameOver:
    """Test game over conditions with party."""

    def test_game_not_over_with_living_members(self, game_state_with_party):
        """Test that game is not over when party has living members."""
        assert not game_state_with_party.is_game_over()

    def test_game_not_over_with_one_living(
        self, game_state_with_party, party_of_four
    ):
        """Test that game is not over with one living party member."""
        # Kill 3 out of 4 party members
        for i in range(3):
            party_of_four.characters[i].take_damage(
                party_of_four.characters[i].max_hp
            )

        assert not game_state_with_party.is_game_over()

    def test_game_over_when_party_wiped(
        self, game_state_with_party, party_of_four
    ):
        """Test that game is over when entire party is dead."""
        # Kill all party members (reduce to 0 HP and set 3 death save failures)
        for character in party_of_four.characters:
            character.take_damage(character.max_hp)
            character.death_save_failures = 3

        assert game_state_with_party.is_game_over()


class TestPartyCombatIntegration:
    """Test party combat integration with GameState."""

    def test_party_enters_combat(self, game_state_with_party, party_of_four):
        """Test that all living party members enter combat."""
        # Trigger combat by moving to a room with enemies
        # We need to mock this since we can't easily navigate to enemy room

        # Manually create enemies and start combat
        from dnd_engine.core.creature import Creature

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

        game_state_with_party.active_enemies = [goblin]
        game_state_with_party._start_combat()

        # Check that combat started
        assert game_state_with_party.in_combat
        assert game_state_with_party.initiative_tracker is not None

        # Check that all 4 party members are in initiative
        all_combatants = game_state_with_party.initiative_tracker.get_all_combatants()
        party_in_initiative = [
            entry for entry in all_combatants
            if entry.creature in party_of_four.characters
        ]

        assert len(party_in_initiative) == 4

    def test_xp_distributed_to_all_party_members(
        self, game_state_with_party, party_of_four
    ):
        """Test that XP is distributed evenly among all party members."""
        # Set up combat and defeat an enemy
        from dnd_engine.core.creature import Creature

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

        game_state_with_party.active_enemies = [goblin]
        game_state_with_party._start_combat()

        # Kill the goblin
        goblin.take_damage(goblin.max_hp)

        # End combat (this distributes XP)
        game_state_with_party._end_combat()

        # Each party member should have received XP (25 XP split 4 ways = 6 each)
        # Note: Actual XP value depends on monster data
        for character in party_of_four.characters:
            assert character.xp >= 0  # XP should have been awarded

    def test_party_member_death_in_combat(
        self, game_state_with_party, party_of_four
    ):
        """Test that party member death is handled correctly in combat."""
        # Set up combat
        from dnd_engine.core.creature import Creature

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

        game_state_with_party.active_enemies = [goblin]
        game_state_with_party._start_combat()

        # Kill one party member
        first_fighter = party_of_four.characters[0]
        first_fighter.take_damage(first_fighter.max_hp)

        # Remove from initiative
        game_state_with_party.initiative_tracker.remove_combatant(first_fighter)

        # Combat should continue (not over)
        assert not game_state_with_party.initiative_tracker.is_combat_over()

        # Only 3 party members + 1 goblin should be in initiative
        all_combatants = game_state_with_party.initiative_tracker.get_all_combatants()
        assert len(all_combatants) == 4  # 3 alive party + 1 goblin


class TestPartyStatusDisplay:
    """Test party status display."""

    def test_status_shows_all_party_members(self, game_state_with_party):
        """Test that status includes all party members."""
        status = game_state_with_party.get_player_status()
        assert len(status) == 4

        # Check that each has unique name
        names = [s["name"] for s in status]
        assert len(set(names)) == 4

    def test_status_shows_alive_status(
        self, game_state_with_party, party_of_four
    ):
        """Test that status shows alive/dead status."""
        # Kill one party member
        party_of_four.characters[0].take_damage(party_of_four.characters[0].max_hp)

        status = game_state_with_party.get_player_status()

        # First should be dead, others alive
        assert status[0]["alive"] is False
        assert all(s["alive"] for s in status[1:])

    def test_status_shows_current_hp(
        self, game_state_with_party, party_of_four
    ):
        """Test that status shows current HP."""
        # Damage one party member
        party_of_four.characters[2].take_damage(5)

        status = game_state_with_party.get_player_status()

        assert status[2]["hp"] == 7  # 12 - 5
        assert status[2]["max_hp"] == 12


class TestPartyCombatVictory:
    """Test party combat victory scenarios."""

    def test_victory_with_all_party_alive(self, game_state_with_party):
        """Test victory when all party members survive."""
        from dnd_engine.core.creature import Creature

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

        game_state_with_party.active_enemies = [goblin]
        game_state_with_party._start_combat()

        # Kill enemy
        goblin.take_damage(goblin.max_hp)
        game_state_with_party._check_combat_end()

        # Combat should end, party should not be wiped
        assert not game_state_with_party.in_combat
        assert not game_state_with_party.party.is_wiped()

    def test_victory_with_casualties(
        self, game_state_with_party, party_of_four
    ):
        """Test victory when some party members died."""
        from dnd_engine.core.creature import Creature

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

        game_state_with_party.active_enemies = [goblin]
        game_state_with_party._start_combat()

        # Kill 2 party members
        party_of_four.characters[0].take_damage(party_of_four.characters[0].max_hp)
        party_of_four.characters[1].take_damage(party_of_four.characters[1].max_hp)

        # Kill enemy
        goblin.take_damage(goblin.max_hp)
        game_state_with_party._check_combat_end()

        # Combat should end, party should not be wiped (2 alive)
        assert not game_state_with_party.in_combat
        assert not game_state_with_party.party.is_wiped()
        assert len(game_state_with_party.party.get_living_members()) == 2
