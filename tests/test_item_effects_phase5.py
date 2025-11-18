# ABOUTME: Unit tests for Phase 5 item effect types (damage, buff, condition_removal, spell)
# ABOUTME: Tests new effect handlers added to item_effects.py

import pytest
from dnd_engine.systems.item_effects import apply_item_effect, ItemEffectResult
from dnd_engine.core.creature import Creature, Abilities
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.dice import DiceRoller
from dnd_engine.utils.events import EventBus, EventType


class TestDamageEffect:
    """Test damage effect type"""

    @pytest.fixture
    def abilities(self):
        """Create test abilities"""
        return Abilities(
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10
        )

    @pytest.fixture
    def target_creature(self, abilities):
        """Create a creature to damage"""
        return Creature(
            name="Target",
            max_hp=20,
            ac=15,
            abilities=abilities,
            current_hp=20
        )

    def test_apply_damage_effect(self, target_creature):
        """Test applying damage to a creature"""
        item_info = {
            "name": "Alchemist's Fire",
            "effect_type": "damage",
            "damage": "1d4",
            "damage_type": "fire"
        }

        dice_roller = DiceRoller()
        result = apply_item_effect(item_info, target_creature, dice_roller)

        assert result.success is True
        assert result.effect_type == "damage"
        assert result.amount > 0  # Should have dealt damage
        assert result.amount <= 4  # Max 1d4
        assert target_creature.current_hp < 20  # Should be damaged
        assert "fire damage" in result.message.lower()

    def test_damage_effect_kills_creature(self, target_creature):
        """Test damage effect killing a creature"""
        # Set creature to low HP
        target_creature.current_hp = 1

        item_info = {
            "name": "Acid Vial",
            "effect_type": "damage",
            "damage": "10d10",  # Guaranteed kill
            "damage_type": "acid"
        }

        result = apply_item_effect(item_info, target_creature)

        assert result.success is True
        assert target_creature.current_hp == 0
        assert not target_creature.is_alive
        assert "KILLED" in result.message

    def test_damage_effect_emits_event(self, target_creature):
        """Test damage effect emits DAMAGE_DEALT event"""
        event_bus = EventBus()
        events_received = []

        def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(EventType.DAMAGE_DEALT, capture_event)

        item_info = {
            "name": "Alchemist's Fire",
            "effect_type": "damage",
            "damage": "1d4",
            "damage_type": "fire"
        }

        apply_item_effect(item_info, target_creature, event_bus=event_bus)

        assert len(events_received) == 1
        event = events_received[0]
        assert event.type == EventType.DAMAGE_DEALT
        assert event.data["target"] == "Target"
        assert event.data["item"] == "Alchemist's Fire"
        assert event.data["damage_type"] == "fire"


class TestConditionRemovalEffect:
    """Test condition removal effect type"""

    @pytest.fixture
    def abilities(self):
        """Create test abilities"""
        return Abilities(
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10
        )

    @pytest.fixture
    def poisoned_creature(self, abilities):
        """Create a poisoned creature"""
        creature = Creature(
            name="Poisoned Fighter",
            max_hp=20,
            ac=15,
            abilities=abilities
        )
        creature.add_condition("poisoned")
        creature.add_condition("diseased")
        return creature

    def test_remove_single_condition(self, poisoned_creature):
        """Test removing a single condition"""
        item_info = {
            "name": "Antidote",
            "effect_type": "condition_removal",
            "removes_conditions": ["poisoned"]
        }

        result = apply_item_effect(item_info, poisoned_creature)

        assert result.success is True
        assert result.effect_type == "condition_removal"
        assert result.amount == 1
        assert not poisoned_creature.has_condition("poisoned")
        assert poisoned_creature.has_condition("diseased")  # Should still have this
        assert "poisoned" in result.message.lower()

    def test_remove_multiple_conditions(self, poisoned_creature):
        """Test removing multiple conditions"""
        item_info = {
            "name": "Elixir of Health",
            "effect_type": "condition_removal",
            "removes_conditions": ["poisoned", "diseased"]
        }

        result = apply_item_effect(item_info, poisoned_creature)

        assert result.success is True
        assert result.amount == 2
        assert not poisoned_creature.has_condition("poisoned")
        assert not poisoned_creature.has_condition("diseased")
        assert "poisoned" in result.message.lower()
        assert "diseased" in result.message.lower()

    def test_remove_nonexistent_condition(self, abilities):
        """Test removing condition that creature doesn't have"""
        creature = Creature(
            name="Healthy Fighter",
            max_hp=20,
            ac=15,
            abilities=abilities
        )

        item_info = {
            "name": "Antidote",
            "effect_type": "condition_removal",
            "removes_conditions": ["poisoned"]
        }

        result = apply_item_effect(item_info, creature)

        assert result.success is False
        assert result.amount == 0
        assert "has none of the conditions" in result.message.lower()

    def test_condition_removal_emits_event(self, poisoned_creature):
        """Test condition removal emits CONDITION_REMOVED event"""
        event_bus = EventBus()
        events_received = []

        def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(EventType.CONDITION_REMOVED, capture_event)

        item_info = {
            "name": "Elixir of Health",
            "effect_type": "condition_removal",
            "removes_conditions": ["poisoned", "diseased"]
        }

        apply_item_effect(item_info, poisoned_creature, event_bus=event_bus)

        assert len(events_received) == 1
        event = events_received[0]
        assert event.type == EventType.CONDITION_REMOVED
        assert event.data["target"] == "Poisoned Fighter"
        assert event.data["item"] == "Elixir of Health"
        assert "poisoned" in event.data["conditions_removed"]
        assert "diseased" in event.data["conditions_removed"]


class TestBuffEffect:
    """Test buff effect type"""

    @pytest.fixture
    def abilities(self):
        """Create test abilities"""
        return Abilities(
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10
        )

    @pytest.fixture
    def target_creature(self, abilities):
        """Create a creature to buff"""
        return Creature(
            name="Fighter",
            max_hp=20,
            ac=15,
            abilities=abilities
        )

    def test_apply_advantage_on_saves_buff(self, target_creature):
        """Test applying advantage on saves buff"""
        item_info = {
            "name": "Antitoxin",
            "effect_type": "buff",
            "buff_type": "advantage_on_saves",
            "save_type": "poison",
            "duration_minutes": 60
        }

        result = apply_item_effect(item_info, target_creature)

        assert result.success is True
        assert result.effect_type == "buff"
        assert result.amount == 60
        assert target_creature.has_condition("has_advantage_poison_saves")
        assert "60 minutes" in result.message or "1 hours" in result.message

    def test_apply_resistance_buff(self, target_creature):
        """Test applying damage resistance buff"""
        item_info = {
            "name": "Potion of Fire Resistance",
            "effect_type": "buff",
            "buff_type": "resistance",
            "damage_type": "fire",
            "duration_minutes": 60
        }

        result = apply_item_effect(item_info, target_creature)

        assert result.success is True
        assert target_creature.has_condition("has_resistance_fire")

    def test_apply_temporary_hp_buff(self, target_creature):
        """Test applying temporary HP buff"""
        item_info = {
            "name": "Potion of Heroism",
            "effect_type": "buff",
            "buff_type": "temporary_hp",
            "duration_minutes": 60
        }

        result = apply_item_effect(item_info, target_creature)

        assert result.success is True
        assert target_creature.has_condition("has_temporary_hp_buff")

    def test_apply_buff_with_extra_conditions(self, target_creature):
        """Test applying buff with additional conditions"""
        item_info = {
            "name": "Potion of Heroism",
            "effect_type": "buff",
            "buff_type": "temporary_hp",
            "duration_minutes": 60,
            "adds_conditions": ["immune_to_fear"]
        }

        result = apply_item_effect(item_info, target_creature)

        assert result.success is True
        assert target_creature.has_condition("has_temporary_hp_buff")
        assert target_creature.has_condition("immune_to_fear")

    def test_buff_emits_event(self, target_creature):
        """Test buff effect emits BUFF_APPLIED event"""
        event_bus = EventBus()
        events_received = []

        def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(EventType.BUFF_APPLIED, capture_event)

        item_info = {
            "name": "Antitoxin",
            "effect_type": "buff",
            "buff_type": "advantage_on_saves",
            "save_type": "poison",
            "duration_minutes": 60
        }

        apply_item_effect(item_info, target_creature, event_bus=event_bus)

        assert len(events_received) == 1
        event = events_received[0]
        assert event.type == EventType.BUFF_APPLIED
        assert event.data["target"] == "Fighter"
        assert event.data["item"] == "Antitoxin"
        assert event.data["buff_type"] == "advantage_on_saves"
        assert event.data["duration_minutes"] == 60

    def test_buff_without_buff_type_fails(self, target_creature):
        """Test that buff without buff_type specified fails"""
        item_info = {
            "name": "Invalid Buff",
            "effect_type": "buff",
            "duration_minutes": 60
        }

        result = apply_item_effect(item_info, target_creature)

        assert result.success is False
        assert "no buff_type specified" in result.message.lower()


class TestSpellEffect:
    """Test spell effect type (placeholder implementation)"""

    @pytest.fixture
    def abilities(self):
        """Create test abilities"""
        return Abilities(
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10
        )

    @pytest.fixture
    def target_character(self, abilities):
        """Create a character to use scroll"""
        return Character(
            name="Wizard",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=abilities,
            max_hp=10,
            ac=10
        )

    def test_spell_effect_not_implemented(self, target_character):
        """Test that spell effect returns not implemented message"""
        item_info = {
            "name": "Scroll of Magic Missile",
            "effect_type": "spell",
            "spell_id": "magic_missile",
            "spell_level": 1
        }

        result = apply_item_effect(item_info, target_character)

        assert result.success is False
        assert result.effect_type == "spell"
        assert "not yet implemented" in result.message.lower()
        assert "magic_missile" in result.message.lower()


class TestUnknownEffectType:
    """Test handling of unknown effect types"""

    @pytest.fixture
    def abilities(self):
        """Create test abilities"""
        return Abilities(
            strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10
        )

    @pytest.fixture
    def target_creature(self, abilities):
        """Create a test creature"""
        return Creature(
            name="Target",
            max_hp=20,
            ac=15,
            abilities=abilities
        )

    def test_unknown_effect_type_fails(self, target_creature):
        """Test that unknown effect types fail gracefully"""
        item_info = {
            "name": "Mystery Potion",
            "effect_type": "unknown_effect"
        }

        result = apply_item_effect(item_info, target_creature)

        assert result.success is False
        assert result.effect_type == "unknown_effect"
        assert "no implemented effect" in result.message.lower()

    def test_missing_effect_type_fails(self, target_creature):
        """Test that missing effect_type fails gracefully"""
        item_info = {
            "name": "Broken Potion"
        }

        result = apply_item_effect(item_info, target_creature)

        assert result.success is False
        assert "no implemented effect" in result.message.lower()
