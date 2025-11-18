# ABOUTME: Unit and integration tests for Phase 4 item usage (targeting allies in combat)
# ABOUTME: Tests range validation, targeting mechanics, and unconscious ally support

import pytest
from unittest.mock import MagicMock, patch
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.ui.cli import CLI
from dnd_engine.systems.action_economy import TurnState


class TestItemUsagePhase4:
    """Test item usage on other characters during combat (Phase 4)."""

    @pytest.fixture
    def abilities(self):
        """Create test abilities."""
        return Abilities(
            strength=10,
            dexterity=14,
            constitution=12,
            intelligence=10,
            wisdom=10,
            charisma=8
        )

    @pytest.fixture
    def fighter1(self, abilities):
        """Create first test fighter."""
        char = Character(
            name="Alice",
            race="human",
            character_class=CharacterClass.FIGHTER,
            abilities=abilities,
            level=1,
            max_hp=20,
            ac=16,
            current_hp=10  # Injured
        )
        return char

    @pytest.fixture
    def fighter2(self, abilities):
        """Create second test fighter."""
        char = Character(
            name="Bob",
            race="human",
            character_class=CharacterClass.FIGHTER,
            abilities=abilities,
            level=1,
            max_hp=20,
            ac=16,
            current_hp=20  # Full health
        )
        return char

    @pytest.fixture
    def unconscious_fighter(self, abilities):
        """Create unconscious fighter."""
        char = Character(
            name="Charlie",
            race="human",
            character_class=CharacterClass.FIGHTER,
            abilities=abilities,
            level=1,
            max_hp=20,
            ac=16,
            current_hp=0
        )
        # Mark as unconscious
        char._is_unconscious = True
        return char

    @pytest.fixture
    def party(self, fighter1, fighter2, unconscious_fighter):
        """Create party with multiple characters."""
        party = Party()
        party.add_character(fighter1)
        party.add_character(fighter2)
        party.add_character(unconscious_fighter)
        return party

    @pytest.fixture
    def game_state(self, party):
        """Create game state with party."""
        game_state = GameState(party=party, dungeon_name="goblin_warren")
        return game_state

    @pytest.fixture
    def cli(self, game_state):
        """Create CLI instance."""
        return CLI(game_state, auto_save_enabled=False)

    def test_prompt_combat_ally_selection_shows_all_allies(self, cli, fighter1, fighter2, unconscious_fighter):
        """Test that ally selection shows all party members including unconscious."""
        item_data = {"name": "Potion of Healing", "range": 5}

        with patch('questionary.select') as mock_select:
            mock_result = MagicMock()
            mock_result.ask.return_value = fighter2
            mock_select.return_value = mock_result

            result = cli._prompt_combat_ally_selection("Potion of Healing", item_data, fighter1)

            # Verify questionary was called
            assert mock_select.called
            call_args = mock_select.call_args
            choices = call_args[1]['choices']

            # Should have 3 allies + 1 cancel option = 4 choices
            assert len(choices) == 4

            # Verify result is the selected character
            assert result == fighter2

    def test_prompt_combat_ally_selection_includes_unconscious(self, cli, fighter1, unconscious_fighter):
        """Test that unconscious allies are included in selection."""
        item_data = {"name": "Potion of Healing", "range": 5}

        with patch('questionary.select') as mock_select:
            mock_result = MagicMock()
            mock_result.ask.return_value = unconscious_fighter
            mock_select.return_value = mock_result

            result = cli._prompt_combat_ally_selection("Potion of Healing", item_data, fighter1)

            # Can select unconscious ally
            assert result == unconscious_fighter

    def test_prompt_combat_ally_selection_shows_unconscious_indicator(self, cli, fighter1, unconscious_fighter):
        """Test that unconscious allies are marked with indicator."""
        item_data = {"name": "Potion of Healing", "range": 5}

        with patch('questionary.select') as mock_select:
            mock_result = MagicMock()
            mock_result.ask.return_value = None
            mock_select.return_value = mock_result

            cli._prompt_combat_ally_selection("Potion of Healing", item_data, fighter1)

            # Check that unconscious indicator appears in choice text
            call_args = mock_select.call_args
            choices = call_args[1]['choices']

            # Find the unconscious character's choice
            unconscious_choice = None
            for choice in choices:
                if hasattr(choice, 'value') and choice.value == unconscious_fighter:
                    unconscious_choice = choice
                    break

            assert unconscious_choice is not None
            assert "UNCONSCIOUS" in unconscious_choice.title

    def test_handle_use_item_combat_with_target_on_other_ally(self, cli, fighter1, fighter2):
        """Test using item on another ally during combat."""
        # Add potion to fighter1's inventory
        fighter1.inventory.add_item("potion_of_healing", "consumables", 1)

        item_data = {
            "name": "Potion of Healing",
            "action_required": "action",
            "effect_type": "healing",
            "healing": "2d4+2",
            "target_type": "any",
            "range": 5
        }

        # Mock initiative tracker and turn state
        cli.game_state.in_combat = True
        cli.game_state.initiative_tracker = MagicMock()
        turn_state = TurnState()
        cli.game_state.initiative_tracker.get_current_turn_state.return_value = turn_state

        initial_hp = fighter2.current_hp

        # Use potion on fighter2
        cli.handle_use_item_combat_with_target("potion_of_healing", item_data, fighter1, fighter2)

        # Fighter2 should be healed (or stay at max HP if already full)
        assert fighter2.current_hp >= initial_hp

        # Potion should be consumed from fighter1's inventory
        remaining_potions = fighter1.inventory.get_items_by_category("consumables")
        potion_count = sum(1 for item in remaining_potions if item.item_id == "potion_of_healing")
        assert potion_count == 0

    def test_handle_use_item_combat_with_target_on_unconscious_ally(self, cli, fighter1, unconscious_fighter):
        """Test using healing potion on unconscious ally."""
        # Add potion to fighter1's inventory
        fighter1.inventory.add_item("potion_of_healing", "consumables", 1)

        item_data = {
            "name": "Potion of Healing",
            "action_required": "action",
            "effect_type": "healing",
            "healing": "2d4+2",
            "target_type": "any",
            "range": 5
        }

        # Mock initiative tracker and turn state
        cli.game_state.in_combat = True
        cli.game_state.initiative_tracker = MagicMock()
        turn_state = TurnState()
        cli.game_state.initiative_tracker.get_current_turn_state.return_value = turn_state

        assert unconscious_fighter.current_hp == 0

        # Use potion on unconscious ally
        cli.handle_use_item_combat_with_target("potion_of_healing", item_data, fighter1, unconscious_fighter)

        # Unconscious ally should be healed
        assert unconscious_fighter.current_hp > 0

    def test_handle_use_item_combat_with_target_shows_hp_change(self, cli, fighter1, fighter2, capsys):
        """Test that HP change is displayed when healing."""
        # Set fighter2 to be injured
        fighter2.current_hp = 10

        # Add potion to fighter1's inventory
        fighter1.inventory.add_item("potion_of_healing", "consumables", 1)

        item_data = {
            "name": "Potion of Healing",
            "action_required": "action",
            "effect_type": "healing",
            "healing": "2d4+2",  # Min 4, max 10
            "target_type": "any",
            "range": 5
        }

        # Mock initiative tracker and turn state
        cli.game_state.in_combat = True
        cli.game_state.initiative_tracker = MagicMock()
        turn_state = TurnState()
        cli.game_state.initiative_tracker.get_current_turn_state.return_value = turn_state

        # Use potion on fighter2
        cli.handle_use_item_combat_with_target("potion_of_healing", item_data, fighter1, fighter2)

        # Check that HP change was displayed
        # Note: The actual output goes through rich console, so we just verify the HP increased
        assert fighter2.current_hp > 10

    def test_handle_use_item_combat_with_target_consumes_action(self, cli, fighter1, fighter2):
        """Test that using item on ally consumes appropriate action."""
        # Add potion to fighter1's inventory
        fighter1.inventory.add_item("potion_of_healing", "consumables", 1)

        item_data = {
            "name": "Potion of Healing",
            "action_required": "action",
            "effect_type": "healing",
            "healing": "2d4+2",
            "target_type": "any",
            "range": 5
        }

        # Mock initiative tracker and turn state
        cli.game_state.in_combat = True
        cli.game_state.initiative_tracker = MagicMock()
        turn_state = TurnState()
        cli.game_state.initiative_tracker.get_current_turn_state.return_value = turn_state

        assert turn_state.action_available is True

        # Use potion
        cli.handle_use_item_combat_with_target("potion_of_healing", item_data, fighter1, fighter2)

        # Action should be consumed
        assert turn_state.action_available is False

    def test_handle_use_item_combat_with_target_on_self(self, cli, fighter1):
        """Test that using item on self works (user == target)."""
        # Set fighter1 to be injured
        fighter1.current_hp = 10

        # Add potion to fighter1's inventory
        fighter1.inventory.add_item("potion_of_healing", "consumables", 1)

        item_data = {
            "name": "Potion of Healing",
            "action_required": "action",
            "effect_type": "healing",
            "healing": "2d4+2",
            "target_type": "any",
            "range": 5
        }

        # Mock initiative tracker and turn state
        cli.game_state.in_combat = True
        cli.game_state.initiative_tracker = MagicMock()
        turn_state = TurnState()
        cli.game_state.initiative_tracker.get_current_turn_state.return_value = turn_state

        initial_hp = fighter1.current_hp

        # Use potion on self
        cli.handle_use_item_combat_with_target("potion_of_healing", item_data, fighter1, fighter1)

        # Should be healed
        assert fighter1.current_hp > initial_hp


class TestItemUsagePhase4Integration:
    """Integration tests for Phase 4 item usage with full combat flow."""

    @pytest.fixture
    def abilities(self):
        """Create test abilities."""
        return Abilities(
            strength=10,
            dexterity=14,
            constitution=12,
            intelligence=10,
            wisdom=10,
            charisma=8
        )

    @pytest.fixture
    def healer(self, abilities):
        """Create healer character with potions."""
        char = Character(
            name="Healer",
            race="human",
            character_class=CharacterClass.FIGHTER,
            abilities=abilities,
            level=1,
            max_hp=20,
            ac=16,
            current_hp=20
        )
        # Add healing potions
        char.inventory.add_item("potion_of_healing", "consumables", 3)
        return char

    @pytest.fixture
    def injured_ally(self, abilities):
        """Create injured ally."""
        char = Character(
            name="Injured",
            race="human",
            character_class=CharacterClass.FIGHTER,
            abilities=abilities,
            level=1,
            max_hp=20,
            ac=16,
            current_hp=5  # Badly injured
        )
        return char

    @pytest.fixture
    def party_with_healer(self, healer, injured_ally):
        """Create party with healer and injured ally."""
        party = Party()
        party.add_character(healer)
        party.add_character(injured_ally)
        return party

    @pytest.fixture
    def game_state_healer(self, party_with_healer):
        """Create game state."""
        return GameState(party=party_with_healer, dungeon_name="goblin_warren")

    def test_full_combat_healing_workflow(self, game_state_healer, healer, injured_ally):
        """Test complete workflow of healing ally in combat."""
        cli = CLI(game_state_healer, auto_save_enabled=False)

        # Set up combat manually
        from dnd_engine.core.creature import Creature, Abilities
        from dnd_engine.systems.initiative import InitiativeTracker
        from unittest.mock import MagicMock

        goblin_abilities = Abilities(
            strength=8, dexterity=14, constitution=10,
            intelligence=10, wisdom=8, charisma=8
        )
        goblin = Creature(name="Goblin", max_hp=7, ac=13, abilities=goblin_abilities)

        # Set up combat state
        game_state_healer.in_combat = True
        game_state_healer.active_enemies = [goblin]
        game_state_healer.initiative_tracker = InitiativeTracker()

        # Add combatants to initiative
        game_state_healer.initiative_tracker.add_combatant(healer)
        game_state_healer.initiative_tracker.add_combatant(injured_ally)
        game_state_healer.initiative_tracker.add_combatant(goblin)

        # Sort by initiative
        game_state_healer.initiative_tracker._sort_initiative()

        # Find healer's turn
        current = game_state_healer.initiative_tracker.get_current_combatant()
        while current and current.creature != healer:
            game_state_healer.initiative_tracker.next_turn()
            current = game_state_healer.initiative_tracker.get_current_combatant()

        # Verify it's healer's turn
        assert current is not None
        assert current.creature == healer

        # Get potion data
        items_data = game_state_healer.data_loader.load_items()
        item_data = items_data["consumables"]["potion_of_healing"]

        initial_hp = injured_ally.current_hp
        assert initial_hp == 5

        # Healer uses potion on injured ally
        cli.handle_use_item_combat_with_target(
            "potion_of_healing",
            item_data,
            healer,
            injured_ally
        )

        # Injured ally should be healed
        assert injured_ally.current_hp > initial_hp

        # Healer should have one less potion
        remaining = healer.inventory.get_items_by_category("consumables")
        potion_count = sum(item.quantity for item in remaining if item.item_id == "potion_of_healing")
        assert potion_count == 2
