"""
Unit tests for spell attack mechanics.

Tests spell attack bonus, spell save DC, cantrip scaling, spell slot management,
and spell attack resolution in combat.
"""

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.combat import CombatEngine
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.core.dice import DiceRoller


@pytest.fixture
def wizard_abilities():
    """Create abilities for a wizard (high INT)."""
    return Abilities(
        strength=8,      # -1
        dexterity=12,    # +1
        constitution=14, # +2
        intelligence=16, # +3
        wisdom=10,       # +0
        charisma=10      # +0
    )


@pytest.fixture
def cleric_abilities():
    """Create abilities for a cleric (high WIS)."""
    return Abilities(
        strength=14,     # +2
        dexterity=10,    # +0
        constitution=14, # +2
        intelligence=8,  # -1
        wisdom=16,       # +3
        charisma=12      # +1
    )


@pytest.fixture
def level_1_wizard(wizard_abilities):
    """Create a level 1 wizard."""
    wizard = Character(
        name="Gandalf",
        character_class=CharacterClass.WIZARD,
        level=1,
        abilities=wizard_abilities,
        max_hp=8,
        ac=12
    )
    # Add spell slots
    wizard.add_resource_pool(ResourcePool(
        name="spell_slots_level_1",
        current=2,
        maximum=2,
        recovery_type="long_rest"
    ))
    return wizard


@pytest.fixture
def level_5_wizard(wizard_abilities):
    """Create a level 5 wizard (for cantrip scaling tests)."""
    wizard = Character(
        name="Merlin",
        character_class=CharacterClass.WIZARD,
        level=5,
        abilities=wizard_abilities,
        max_hp=30,
        ac=12
    )
    return wizard


@pytest.fixture
def level_1_cleric(cleric_abilities):
    """Create a level 1 cleric."""
    cleric = Character(
        name="Caduceus",
        character_class=CharacterClass.CLERIC,
        level=1,
        abilities=cleric_abilities,
        max_hp=10,
        ac=16
    )
    # Add spell slots
    cleric.add_resource_pool(ResourcePool(
        name="spell_slots_level_1",
        current=2,
        maximum=2,
        recovery_type="long_rest"
    ))
    return cleric


@pytest.fixture
def goblin():
    """Create a goblin enemy."""
    return Creature(
        name="Goblin",
        max_hp=7,
        ac=15,
        abilities=Abilities(10, 14, 10, 10, 8, 8)
    )


@pytest.fixture
def fire_bolt_spell():
    """Fire Bolt cantrip spell data."""
    return {
        "id": "fire_bolt",
        "name": "Fire Bolt",
        "level": 0,
        "damage": {
            "dice": "1d10",
            "damage_type": "fire"
        },
        "attack_type": "ranged"
    }


@pytest.fixture
def magic_missile_spell():
    """Magic Missile 1st-level spell data."""
    return {
        "id": "magic_missile",
        "name": "Magic Missile",
        "level": 1,
        "damage": {
            "dice": "3d4+3",
            "damage_type": "force"
        },
        "attack_type": None  # Auto-hit
    }


class TestSpellAttackBonus:
    """Test spell attack bonus calculation."""

    def test_wizard_spell_attack_bonus_level_1(self, level_1_wizard):
        """Test wizard spell attack bonus at level 1 with INT 16."""
        # Proficiency bonus at level 1 = +2
        # INT modifier = +3
        # Total = +5
        assert level_1_wizard.get_spell_attack_bonus("int") == 5

    def test_wizard_spell_attack_bonus_with_intelligence(self, level_1_wizard):
        """Test spell attack bonus accepts full ability name."""
        assert level_1_wizard.get_spell_attack_bonus("intelligence") == 5

    def test_cleric_spell_attack_bonus(self, level_1_cleric):
        """Test cleric spell attack bonus with WIS 16."""
        # Proficiency bonus at level 1 = +2
        # WIS modifier = +3
        # Total = +5
        assert level_1_cleric.get_spell_attack_bonus("wis") == 5

    def test_invalid_ability_raises_error(self, level_1_wizard):
        """Test invalid ability name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid ability name"):
            level_1_wizard.get_spell_attack_bonus("invalid")


class TestSpellSaveDC:
    """Test spell save DC calculation."""

    def test_wizard_spell_save_dc(self, level_1_wizard):
        """Test wizard spell save DC at level 1."""
        # DC = 8 + proficiency + INT mod
        # DC = 8 + 2 + 3 = 13
        assert level_1_wizard.get_spell_save_dc("int") == 13

    def test_cleric_spell_save_dc(self, level_1_cleric):
        """Test cleric spell save DC at level 1."""
        # DC = 8 + proficiency + WIS mod
        # DC = 8 + 2 + 3 = 13
        assert level_1_cleric.get_spell_save_dc("wis") == 13

    def test_spell_save_dc_with_full_name(self, level_1_wizard):
        """Test spell save DC accepts full ability name."""
        assert level_1_wizard.get_spell_save_dc("intelligence") == 13


class TestCantripDamageScaling:
    """Test cantrip damage scaling by character level."""

    def test_cantrip_level_1_to_4(self, level_1_wizard):
        """Test cantrip damage at levels 1-4 (no scaling)."""
        assert level_1_wizard.scale_cantrip_damage("1d10") == "1d10"
        assert level_1_wizard.scale_cantrip_damage("1d8") == "1d8"

    def test_cantrip_level_5(self, level_5_wizard):
        """Test cantrip damage at level 5 (2x dice)."""
        assert level_5_wizard.scale_cantrip_damage("1d10") == "2d10"
        assert level_5_wizard.scale_cantrip_damage("1d8") == "2d8"

    def test_cantrip_level_11(self, wizard_abilities):
        """Test cantrip damage at level 11 (3x dice)."""
        wizard = Character(
            name="Test",
            character_class=CharacterClass.WIZARD,
            level=11,
            abilities=wizard_abilities,
            max_hp=50,
            ac=12
        )
        assert wizard.scale_cantrip_damage("1d10") == "3d10"

    def test_cantrip_level_17(self, wizard_abilities):
        """Test cantrip damage at level 17 (4x dice)."""
        wizard = Character(
            name="Test",
            character_class=CharacterClass.WIZARD,
            level=17,
            abilities=wizard_abilities,
            max_hp=70,
            ac=12
        )
        assert wizard.scale_cantrip_damage("1d10") == "4d10"

    def test_cantrip_with_modifier(self, level_5_wizard):
        """Test cantrip scaling preserves modifiers."""
        assert level_5_wizard.scale_cantrip_damage("1d8+2") == "2d8+2"
        assert level_5_wizard.scale_cantrip_damage("1d10-1") == "2d10-1"

    def test_cantrip_multiple_dice(self, level_5_wizard):
        """Test cantrip scaling with multiple base dice."""
        assert level_5_wizard.scale_cantrip_damage("2d6") == "4d6"


class TestSpellSlotManagement:
    """Test spell slot tracking and usage."""

    def test_get_available_spell_slots(self, level_1_wizard):
        """Test getting available spell slots."""
        assert level_1_wizard.get_available_spell_slots(1) == 2

    def test_no_spell_slots_for_level(self, level_1_wizard):
        """Test getting spell slots for unavailable level returns 0."""
        assert level_1_wizard.get_available_spell_slots(2) == 0
        assert level_1_wizard.get_available_spell_slots(9) == 0

    def test_use_spell_slot_success(self, level_1_wizard):
        """Test successfully using a spell slot."""
        assert level_1_wizard.use_spell_slot(1) is True
        assert level_1_wizard.get_available_spell_slots(1) == 1

    def test_use_spell_slot_failure(self, level_1_wizard):
        """Test using spell slot when none available."""
        # Use both slots
        level_1_wizard.use_spell_slot(1)
        level_1_wizard.use_spell_slot(1)
        # Third use should fail
        assert level_1_wizard.use_spell_slot(1) is False
        assert level_1_wizard.get_available_spell_slots(1) == 0

    def test_use_invalid_spell_level(self, level_1_wizard):
        """Test using invalid spell slot level returns False."""
        assert level_1_wizard.use_spell_slot(0) is False  # Cantrips don't use slots
        assert level_1_wizard.use_spell_slot(10) is False  # Level too high


class TestLevelToOrdinal:
    """Test spell level to ordinal string conversion."""

    def test_cantrip(self):
        """Test cantrip (level 0)."""
        assert Character._level_to_ordinal(0) == "cantrip"

    def test_first_level(self):
        """Test 1st level."""
        assert Character._level_to_ordinal(1) == "1st"

    def test_second_level(self):
        """Test 2nd level."""
        assert Character._level_to_ordinal(2) == "2nd"

    def test_third_level(self):
        """Test 3rd level."""
        assert Character._level_to_ordinal(3) == "3rd"

    def test_higher_levels(self):
        """Test 4th+ levels."""
        assert Character._level_to_ordinal(4) == "4th"
        assert Character._level_to_ordinal(5) == "5th"
        assert Character._level_to_ordinal(9) == "9th"


class TestSpellAttackResolution:
    """Test spell attack resolution in combat."""

    def test_spell_attack_hit(self, level_1_wizard, goblin, fire_bolt_spell, monkeypatch):
        """Test successful spell attack."""
        # Mock dice roller to always roll 15
        def mock_roll(self, notation, advantage=False, disadvantage=False):
            from dnd_engine.core.dice import DiceRoll
            return DiceRoll(rolls=[15], notation=notation, modifier=0)

        monkeypatch.setattr(DiceRoller, "roll", mock_roll)

        combat_engine = CombatEngine()
        result = combat_engine.resolve_spell_attack(
            caster=level_1_wizard,
            target=goblin,
            spell=fire_bolt_spell,
            spellcasting_ability="int",
            apply_damage=False
        )

        # Attack roll: 15 + 5 (spell attack bonus) = 20
        # Target AC: 15
        # Should hit
        assert result.hit is True
        assert result.attack_roll == 15
        assert result.attack_bonus == 5
        assert result.total_attack == 20

    def test_spell_attack_miss(self, level_1_wizard, goblin, fire_bolt_spell, monkeypatch):
        """Test missed spell attack."""
        # Mock dice roller to always roll 5
        def mock_roll(self, notation, advantage=False, disadvantage=False):
            from dnd_engine.core.dice import DiceRoll
            return DiceRoll(rolls=[5], notation=notation, modifier=0)

        monkeypatch.setattr(DiceRoller, "roll", mock_roll)

        combat_engine = CombatEngine()
        result = combat_engine.resolve_spell_attack(
            caster=level_1_wizard,
            target=goblin,
            spell=fire_bolt_spell,
            spellcasting_ability="int",
            apply_damage=False
        )

        # Attack roll: 5 + 5 = 10
        # Target AC: 15
        # Should miss
        assert result.hit is False
        assert result.damage == 0

    def test_spell_attack_cantrip_scaling(self, level_5_wizard, goblin, fire_bolt_spell):
        """Test cantrip damage scales with caster level."""
        combat_engine = CombatEngine()

        # Level 5 wizard should do 2d10 instead of 1d10
        result = combat_engine.resolve_spell_attack(
            caster=level_5_wizard,
            target=goblin,
            spell=fire_bolt_spell,
            spellcasting_ability="int",
            apply_damage=False
        )

        # Can't test exact damage due to randomness, but if it hits,
        # damage should be in range 2-20 (2d10) not 1-10 (1d10)
        if result.hit:
            assert result.damage >= 2
            # This could fail rarely if both dice roll 1, but statistically unlikely

    def test_spell_attack_critical_hit(self, level_1_wizard, goblin, fire_bolt_spell, monkeypatch):
        """Test spell attack critical hit doubles damage dice."""
        # Mock dice roller to always roll nat 20
        roll_count = 0

        def mock_roll(self, notation, advantage=False, disadvantage=False):
            nonlocal roll_count
            from dnd_engine.core.dice import DiceRoll
            roll_count += 1
            if roll_count == 1:
                # Attack roll - natural 20
                return DiceRoll(rolls=[20], notation=notation, modifier=0)
            else:
                # Damage roll - return max damage for consistency
                # For 2d10 (doubled 1d10), return 20
                return DiceRoll(rolls=[10, 10], notation=notation, modifier=0)

        monkeypatch.setattr(DiceRoller, "roll", mock_roll)

        combat_engine = CombatEngine()
        result = combat_engine.resolve_spell_attack(
            caster=level_1_wizard,
            target=goblin,
            spell=fire_bolt_spell,
            spellcasting_ability="int",
            apply_damage=False
        )

        assert result.critical_hit is True
        assert result.hit is True
        assert result.damage == 20  # Max damage on 2d10

    def test_spell_attack_applies_damage(self, level_1_wizard, goblin, fire_bolt_spell):
        """Test spell attack applies damage to target."""
        initial_hp = goblin.current_hp

        combat_engine = CombatEngine()
        result = combat_engine.resolve_spell_attack(
            caster=level_1_wizard,
            target=goblin,
            spell=fire_bolt_spell,
            spellcasting_ability="int",
            apply_damage=True
        )

        if result.hit:
            assert goblin.current_hp < initial_hp
            assert goblin.current_hp == initial_hp - result.damage

    def test_spell_attack_without_spell_attack_bonus_raises_error(self, goblin, fire_bolt_spell):
        """Test casting spell from non-caster raises error."""
        # Creature doesn't have get_spell_attack_bonus method
        non_caster = Creature(
            name="Fighter",
            max_hp=20,
            ac=16,
            abilities=Abilities(16, 10, 14, 10, 10, 10)
        )

        combat_engine = CombatEngine()

        with pytest.raises(ValueError, match="cannot cast spells"):
            combat_engine.resolve_spell_attack(
                caster=non_caster,
                target=goblin,
                spell=fire_bolt_spell,
                spellcasting_ability="int",
                apply_damage=False
            )


class TestSpellAttackEvents:
    """Test event emission for spell attacks."""

    def test_spell_attack_emits_event(self, level_1_wizard, goblin, fire_bolt_spell):
        """Test that spell attacks emit proper events."""
        from dnd_engine.utils.events import EventBus, EventType

        event_bus = EventBus()
        events_received = []

        def capture_event(event):
            events_received.append(event)

        event_bus.subscribe(EventType.ATTACK_ROLL, capture_event)

        combat_engine = CombatEngine()
        combat_engine.resolve_spell_attack(
            caster=level_1_wizard,
            target=goblin,
            spell=fire_bolt_spell,
            spellcasting_ability="int",
            apply_damage=False,
            event_bus=event_bus
        )

        # Should have emitted an attack roll event
        assert len(events_received) == 1
        event = events_received[0]
        assert event.type == EventType.ATTACK_ROLL
        assert event.data["attacker"] == "Gandalf"
        assert event.data["target"] == "Goblin"
        assert event.data["spell"] == "Fire Bolt"
        assert event.data["attack_type"] == "spell"
        assert "damage_type" in event.data
        assert event.data["damage_type"] == "fire"
