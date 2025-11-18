# ABOUTME: Unit tests for combat item condition application via data-driven applies_condition field
# ABOUTME: Tests that items like alchemist's fire apply conditions from item data, not hardcoded logic

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.utils.events import EventBus


class TestCombatItemConditionApplication:
    """Test that combat items apply conditions via applies_condition field"""

    @pytest.fixture
    def setup_combat(self):
        """Setup a combat scenario with attacker and defender"""
        event_bus = EventBus()
        loader = DataLoader()
        dice_roller = DiceRoller()

        # Load items data
        items_data = loader.load_items()

        # Create attacker character
        abilities = Abilities(10, 14, 10, 10, 10, 10)  # DEX 14 for attack
        character = Character(
            name="Attacker",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=12,
            ac=16
        )

        # Give character alchemist's fire
        character.inventory.add_item("alchemists_fire", "consumables", 1)

        # Create party
        party = Party(characters=[character])

        # Create game state
        game_state = GameState(
            party=party,
            dungeon_name="goblin_warren",
            event_bus=event_bus,
            data_loader=loader,
            dice_roller=dice_roller
        )

        # Create a target creature
        target = Creature(
            name="Target",
            max_hp=20,
            ac=5,  # Low AC to ensure hits in tests
            abilities=Abilities(10, 10, 10, 10, 10, 10)
        )

        # Start combat
        game_state.in_combat = True
        game_state.active_enemies = [target]

        # Setup initiative tracker
        from dnd_engine.systems.initiative import InitiativeTracker
        tracker = InitiativeTracker(dice_roller=dice_roller)
        tracker.add_combatant(character)
        tracker.add_combatant(target)
        game_state.initiative_tracker = tracker

        return {
            'game_state': game_state,
            'character': character,
            'target': target,
            'loader': loader,
            'items_data': items_data
        }

    def test_alchemists_fire_applies_on_fire_condition_on_hit(self, setup_combat):
        """Test that alchemist's fire applies on_fire condition when it hits"""
        game_state = setup_combat['game_state']
        character = setup_combat['character']
        target = setup_combat['target']

        # Use alchemist's fire (low AC should guarantee hit)
        result = game_state.use_combat_attack_item(
            user=character,
            target=target,
            item_id="alchemists_fire"
        )

        # Verify the attack succeeded
        assert result.success is True
        assert result.attack_result is not None

        # If hit, verify on_fire condition was applied
        if result.attack_result.hit:
            assert target.has_condition("on_fire")
            assert "on_fire" in result.special_effects
        else:
            # If miss (unlikely with AC 5), condition should not be applied
            assert not target.has_condition("on_fire")
            assert "on_fire" not in result.special_effects

    def test_alchemists_fire_no_condition_on_miss(self, setup_combat):
        """Test that alchemist's fire doesn't apply condition when it misses"""
        game_state = setup_combat['game_state']
        character = setup_combat['character']
        target = setup_combat['target']

        # Set target AC very high to force miss
        target.ac = 30

        # Use alchemist's fire
        result = game_state.use_combat_attack_item(
            user=character,
            target=target,
            item_id="alchemists_fire"
        )

        # Verify the attack was attempted
        assert result.success is True
        assert result.attack_result is not None

        # Verify on_fire condition was NOT applied on miss
        assert not target.has_condition("on_fire")
        assert "on_fire" not in result.special_effects

    def test_acid_vial_does_not_apply_condition(self, setup_combat):
        """Test that acid vial (no applies_condition) doesn't apply any condition"""
        game_state = setup_combat['game_state']
        character = setup_combat['character']
        target = setup_combat['target']

        # Give character acid vial
        character.inventory.add_item("acid_vial", "consumables", 1)

        # Use acid vial
        result = game_state.use_combat_attack_item(
            user=character,
            target=target,
            item_id="acid_vial"
        )

        # Verify the attack succeeded
        assert result.success is True

        # Verify no conditions were applied (acid vial has no applies_condition)
        assert not target.has_condition("on_fire")
        assert len(result.special_effects) == 0

    def test_applies_condition_field_is_data_driven(self, setup_combat):
        """Test that applies_condition comes from item data, not hardcoded"""
        items_data = setup_combat['items_data']

        # Verify alchemist's fire has applies_condition in data
        alchemists_fire_data = items_data["consumables"]["alchemists_fire"]
        assert "applies_condition" in alchemists_fire_data
        assert alchemists_fire_data["applies_condition"] == "on_fire"

        # Verify acid vial does not have applies_condition
        acid_vial_data = items_data["consumables"]["acid_vial"]
        assert "applies_condition" not in acid_vial_data

    def test_condition_applied_to_special_effects_list(self, setup_combat):
        """Test that applied condition appears in special_effects list"""
        game_state = setup_combat['game_state']
        character = setup_combat['character']
        target = setup_combat['target']

        # Use alchemist's fire
        result = game_state.use_combat_attack_item(
            user=character,
            target=target,
            item_id="alchemists_fire"
        )

        # If hit, verify special_effects contains the condition
        if result.attack_result and result.attack_result.hit:
            assert result.special_effects is not None
            assert "on_fire" in result.special_effects
            assert len(result.special_effects) == 1

    def test_multiple_uses_stack_condition(self, setup_combat):
        """Test that using alchemist's fire multiple times doesn't break anything"""
        game_state = setup_combat['game_state']
        character = setup_combat['character']
        target = setup_combat['target']

        # Add multiple alchemist's fire to inventory
        character.inventory.add_item("alchemists_fire", "consumables", 2)

        # Use first alchemist's fire
        result1 = game_state.use_combat_attack_item(
            user=character,
            target=target,
            item_id="alchemists_fire"
        )

        # If hit, should have condition
        if result1.attack_result and result1.attack_result.hit:
            assert target.has_condition("on_fire")

        # Reset turn for second use
        game_state.initiative_tracker.next_turn()
        game_state.initiative_tracker.next_turn()  # Cycle back to character

        # Use second alchemist's fire
        result2 = game_state.use_combat_attack_item(
            user=character,
            target=target,
            item_id="alchemists_fire"
        )

        # Should still work (condition system handles duplicates)
        if result2.attack_result and result2.attack_result.hit:
            assert target.has_condition("on_fire")
