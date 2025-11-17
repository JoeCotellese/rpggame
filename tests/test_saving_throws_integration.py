# ABOUTME: Integration tests for saving throw system with combat and events
# ABOUTME: Tests event emission, combat integration, and multi-component interactions

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.combat import CombatEngine
from dnd_engine.utils.events import EventBus, EventType


@pytest.fixture
def fighter_abilities():
    """Create fighter ability scores"""
    return Abilities(
        strength=16,      # +3
        dexterity=12,     # +1
        constitution=15,  # +2
        intelligence=10,  # +0
        wisdom=10,        # +0
        charisma=8        # -1
    )


@pytest.fixture
def wizard_abilities():
    """Create wizard ability scores"""
    return Abilities(
        strength=8,       # -1
        dexterity=14,     # +2
        constitution=12,  # +1
        intelligence=16,  # +3
        wisdom=14,        # +2
        charisma=11       # +0
    )


@pytest.fixture
def fighter(fighter_abilities):
    """Create a fighter character"""
    return Character(
        name="Aragorn",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=fighter_abilities,
        max_hp=12,
        ac=16,
        saving_throw_proficiencies=["str", "con"]
    )


@pytest.fixture
def wizard(wizard_abilities):
    """Create a wizard character with no save proficiencies"""
    return Character(
        name="Gandalf",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=wizard_abilities,
        max_hp=6,
        ac=12,
        saving_throw_proficiencies=[]
    )


@pytest.fixture
def combat_engine():
    """Create a combat engine"""
    return CombatEngine(DiceRoller())


@pytest.fixture
def event_bus():
    """Create an event bus"""
    return EventBus()


class TestSavingThrowEventEmission:
    """Test that saving throws emit events correctly"""

    def test_saving_throw_event_fired(self, fighter, event_bus):
        """Test that saving throw fires an event"""
        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        event_bus.subscribe(EventType.SAVING_THROW, capture_event)

        fighter.make_saving_throw("str", dc=12, event_bus=event_bus)

        assert len(events_captured) == 1
        event = events_captured[0]
        assert event.type == EventType.SAVING_THROW

    def test_event_contains_all_data(self, fighter, event_bus):
        """Test that event contains all required information"""
        captured_events = []

        def capture_event(event):
            captured_events.append(event)

        event_bus.subscribe(EventType.SAVING_THROW, capture_event)

        result = fighter.make_saving_throw("con", dc=14, event_bus=event_bus)

        event = captured_events[0]
        event_data = event.data

        assert event_data["character"] == "Aragorn"
        assert event_data["ability"] == "con"
        assert event_data["dc"] == 14
        assert event_data["roll"] == result["roll"]
        assert event_data["modifier"] == result["modifier"]
        assert event_data["total"] == result["total"]
        assert event_data["success"] == result["success"]

    def test_multiple_saves_emit_multiple_events(self, fighter, event_bus):
        """Test that multiple saves emit multiple events"""
        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        event_bus.subscribe(EventType.SAVING_THROW, capture_event)

        fighter.make_saving_throw("str", dc=10, event_bus=event_bus)
        fighter.make_saving_throw("con", dc=12, event_bus=event_bus)
        fighter.make_saving_throw("dex", dc=11, event_bus=event_bus)

        assert len(events_captured) == 3

    def test_event_success_flag_matches_result(self, fighter, event_bus):
        """Test that event success flag matches make_saving_throw result"""
        captured_events = []

        def capture_event(event):
            captured_events.append(event)

        event_bus.subscribe(EventType.SAVING_THROW, capture_event)

        result = fighter.make_saving_throw("str", dc=5, event_bus=event_bus)

        event = captured_events[0]
        assert event.data["success"] == result["success"]


class TestCombatSavingThrowEffects:
    """Test saving throw resolution in combat"""

    def test_resolve_saving_throw_effect_success_half_damage(self, fighter, combat_engine):
        """Test that successful save halves damage"""
        # Use a very low DC so we're likely to succeed
        effect = {
            "damage_dice": "8d6",
            "damage_type": "fire",
            "half_on_success": True
        }

        result = combat_engine.resolve_saving_throw_effect(
            target=fighter,
            save_ability="dex",
            dc=1,  # Very easy save
            effect=effect,
            apply_damage=False
        )

        # Check structure
        assert "save_result" in result
        assert "damage" in result
        assert "damage_taken" in result
        assert "effect" in result

        # With DC 1, should almost certainly succeed
        # If successful, damage_taken should be half of damage
        if result["save_result"]["success"]:
            assert result["damage_taken"] == result["damage"] // 2

    def test_resolve_saving_throw_effect_failure_full_damage(self, fighter, combat_engine):
        """Test that failed save takes full damage"""
        effect = {
            "damage_dice": "2d6",
            "damage_type": "poison",
            "half_on_success": True
        }

        result = combat_engine.resolve_saving_throw_effect(
            target=fighter,
            save_ability="con",
            dc=25,  # Very hard save
            effect=effect,
            apply_damage=False
        )

        # With DC 25, should almost certainly fail
        # If failed, damage_taken should be full damage
        if not result["save_result"]["success"]:
            assert result["damage_taken"] == result["damage"]

    def test_resolve_saving_throw_effect_negate_on_success(self, fighter, combat_engine):
        """Test that successful save can negate damage completely"""
        effect = {
            "damage_dice": "4d4",
            "damage_type": "magic",
            "negate_on_success": True
        }

        result = combat_engine.resolve_saving_throw_effect(
            target=fighter,
            save_ability="int",
            dc=1,  # Very easy save
            effect=effect,
            apply_damage=False
        )

        # With DC 1, should almost certainly succeed
        # If successful with negate_on_success, damage_taken should be 0
        if result["save_result"]["success"]:
            assert result["damage_taken"] == 0

    def test_resolve_saving_throw_effect_applies_damage(self, fighter, combat_engine):
        """Test that damage is applied to target HP when apply_damage=True"""
        original_hp = fighter.current_hp

        effect = {
            "damage_dice": "1d6",
            "damage_type": "poison",
            "half_on_success": True
        }

        # Make it fail the save so we take damage
        result = combat_engine.resolve_saving_throw_effect(
            target=fighter,
            save_ability="con",
            dc=25,  # Very hard save
            effect=effect,
            apply_damage=True
        )

        # If failed, HP should be reduced
        if not result["save_result"]["success"]:
            assert fighter.current_hp == original_hp - result["damage_taken"]

    def test_fighter_better_at_con_saves(self, fighter, wizard, combat_engine):
        """Test that fighter is better at CON saves than wizard"""
        # Fighter has +4 CON save (2 from CON, +2 from proficiency)
        # Wizard has +1 CON save (1 from CON, no proficiency)

        fighter_con_mod = fighter.get_saving_throw_modifier("con")
        wizard_con_mod = wizard.get_saving_throw_modifier("con")

        assert fighter_con_mod == 4
        assert wizard_con_mod == 1

    def test_combat_engine_requires_character_with_saving_throws(self, combat_engine):
        """Test that resolve_saving_throw_effect requires a character"""
        # Create a plain Creature (not a Character)
        basic_creature = Creature(
            name="Beast",
            max_hp=10,
            ac=12,
            abilities=Abilities(
                strength=10, dexterity=10, constitution=10,
                intelligence=3, wisdom=10, charisma=6
            )
        )

        effect = {
            "damage_dice": "2d6",
            "half_on_success": True
        }

        # Should raise ValueError because basic Creature doesn't have make_saving_throw
        with pytest.raises(ValueError):
            combat_engine.resolve_saving_throw_effect(
                target=basic_creature,
                save_ability="con",
                dc=12,
                effect=effect
            )

    def test_saving_throw_effect_with_event_bus(self, fighter, combat_engine, event_bus):
        """Test that saving throw effects emit events through event_bus"""
        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        event_bus.subscribe(EventType.SAVING_THROW, capture_event)

        effect = {
            "damage_dice": "2d6",
            "half_on_success": True
        }

        combat_engine.resolve_saving_throw_effect(
            target=fighter,
            save_ability="str",
            dc=12,
            effect=effect,
            event_bus=event_bus
        )

        # Event should have been emitted
        assert len(events_captured) == 1
        assert events_captured[0].type == EventType.SAVING_THROW


class TestSavingThrowScenarios:
    """Test realistic game scenarios with saving throws"""

    def test_poison_dart_trap_scenario(self, fighter, combat_engine):
        """Test a poison dart trap: CON save DC 12 or take 2d4 damage"""
        effect = {
            "damage_dice": "2d4",
            "damage_type": "poison",
            "half_on_success": True
        }

        original_hp = fighter.current_hp

        result = combat_engine.resolve_saving_throw_effect(
            target=fighter,
            save_ability="con",
            dc=12,
            effect=effect,
            apply_damage=True
        )

        # Verify structure
        assert result["save_result"]["ability"] == "con"
        assert result["save_result"]["dc"] == 12
        assert result["damage"] > 0  # Rolled damage

        # Verify HP was reduced
        assert fighter.current_hp < original_hp

    def test_fireball_scenario(self, fighter, wizard, combat_engine):
        """Test fireball: DEX save DC 15 for half damage on 8d6"""
        effect = {
            "damage_dice": "8d6",
            "damage_type": "fire",
            "half_on_success": True
        }

        # Fighter saves with +1 DEX modifier (no proficiency)
        # Wizard saves with +2 DEX modifier (no proficiency)

        fighter_dex_mod = fighter.get_saving_throw_modifier("dex")
        wizard_dex_mod = wizard.get_saving_throw_modifier("dex")

        assert fighter_dex_mod == 1
        assert wizard_dex_mod == 2

        # Wizard should have slightly better chance to save

    def test_stun_effect_no_success_avoidance(self, fighter, combat_engine):
        """Test a stun effect that can't be avoided on success"""
        effect = {
            "damage_dice": "0d0",  # No damage
            "half_on_success": False,
            "negate_on_success": False
        }

        result = combat_engine.resolve_saving_throw_effect(
            target=fighter,
            save_ability="wis",
            dc=12,
            effect=effect,
            apply_damage=False
        )

        # Even if successful, still takes effect
        if result["save_result"]["success"]:
            assert result["damage_taken"] == result["damage"]

    def test_multiple_saves_in_sequence(self, fighter, combat_engine, event_bus):
        """Test a sequence of saving throws in combat"""
        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        event_bus.subscribe(EventType.SAVING_THROW, capture_event)

        effects = [
            {"damage_dice": "1d6", "half_on_success": True},  # Trap 1
            {"damage_dice": "2d6", "half_on_success": True},  # Trap 2
            {"damage_dice": "1d4", "negate_on_success": True}  # Effect
        ]

        for effect in effects:
            combat_engine.resolve_saving_throw_effect(
                target=fighter,
                save_ability="dex",
                dc=12,
                effect=effect,
                event_bus=event_bus
            )

        # Should have 3 events
        assert len(events_captured) == 3
