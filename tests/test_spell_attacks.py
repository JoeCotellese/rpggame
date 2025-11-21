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
        ac=12,
        spellcasting_ability="int"
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
        ac=16,
        spellcasting_ability="wis"
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
        assert level_1_wizard.get_spell_save_dc() == 13

    def test_cleric_spell_save_dc(self, level_1_cleric):
        """Test cleric spell save DC at level 1."""
        # DC = 8 + proficiency + WIS mod
        # DC = 8 + 2 + 3 = 13
        assert level_1_cleric.get_spell_save_dc() == 13

    def test_spell_save_dc_with_full_name(self, level_1_wizard):
        """Test spell save DC uses character's spellcasting ability."""
        assert level_1_wizard.get_spell_save_dc() == 13


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


class TestGetCastableSpells:
    """Test Character.get_castable_spells() method."""

    def test_wizard_shows_prepared_spells_only(self, wizard_abilities):
        """Wizard should only see prepared spells, not all known spells.

        In D&D 5E, wizards must prepare spells from their spellbook each day.
        Cantrips are always prepared once known.
        """
        wizard = Character("Gandalf", CharacterClass.WIZARD, level=1, abilities=wizard_abilities, max_hp=8, ac=12)

        # Set up spellcasting
        wizard.spellcasting_ability = "intelligence"
        wizard.known_spells = ["fire_bolt", "ray_of_frost", "magic_missile", "shield", "mage_armor"]
        # Cantrips (fire_bolt) + prepared leveled spells
        wizard.prepared_spells = ["fire_bolt", "magic_missile", "shield"]

        # Mock spells data
        spells_data = {
            "fire_bolt": {"name": "Fire Bolt", "level": 0, "attack_type": "ranged_spell_attack", "damage": {"dice": "1d10"}},
            "ray_of_frost": {"name": "Ray of Frost", "level": 0, "attack_type": "ranged_spell_attack", "damage": {"dice": "1d8"}},
            "magic_missile": {"name": "Magic Missile", "level": 1, "damage": {"dice": "1d4+1"}},
            "shield": {"name": "Shield", "level": 1, "casting_time": "1 reaction"},
            "mage_armor": {"name": "Mage Armor", "level": 1},  # No damage/attack/save/reaction
        }

        castable = wizard.get_castable_spells(spells_data)
        castable_ids = [spell_id for spell_id, _ in castable]

        # Should only show prepared spells that are combat-relevant
        assert "fire_bolt" in castable_ids  # Cantrip - always prepared once known
        assert "magic_missile" in castable_ids  # Prepared and has damage
        assert "shield" in castable_ids  # Prepared and is a reaction
        assert "ray_of_frost" not in castable_ids  # Known cantrip but not in prepared list
        assert "mage_armor" not in castable_ids  # Known but not prepared

    def test_includes_attack_spells(self, wizard_abilities):
        """Should include spells with attack_type."""
        wizard = Character("Gandalf", CharacterClass.WIZARD, level=1, abilities=wizard_abilities, max_hp=8, ac=12)
        wizard.spellcasting_ability = "intelligence"
        wizard.prepared_spells = ["fire_bolt", "scorching_ray"]

        spells_data = {
            "fire_bolt": {"name": "Fire Bolt", "level": 0, "attack_type": "ranged_spell_attack"},
            "scorching_ray": {"name": "Scorching Ray", "level": 2, "attack_type": "ranged_spell_attack"},
        }

        castable = wizard.get_castable_spells(spells_data)
        assert len(castable) == 2

    def test_includes_saving_throw_spells(self, wizard_abilities):
        """Should include spells with saving_throw_type."""
        wizard = Character("Gandalf", CharacterClass.WIZARD, level=1, abilities=wizard_abilities, max_hp=8, ac=12)
        wizard.spellcasting_ability = "intelligence"
        wizard.prepared_spells = ["burning_hands", "thunderwave"]

        spells_data = {
            "burning_hands": {"name": "Burning Hands", "level": 1, "saving_throw_type": "dexterity", "damage": {"dice": "3d6"}},
            "thunderwave": {"name": "Thunderwave", "level": 1, "saving_throw_type": "constitution", "damage": {"dice": "2d8"}},
        }

        castable = wizard.get_castable_spells(spells_data)
        assert len(castable) == 2

    def test_includes_damage_spells_without_attack(self, wizard_abilities):
        """Should include spells with damage even if no attack_type (like Magic Missile)."""
        wizard = Character("Gandalf", CharacterClass.WIZARD, level=1, abilities=wizard_abilities, max_hp=8, ac=12)
        wizard.spellcasting_ability = "intelligence"
        wizard.prepared_spells = ["magic_missile"]

        spells_data = {
            "magic_missile": {"name": "Magic Missile", "level": 1, "damage": {"dice": "1d4+1"}},
        }

        castable = wizard.get_castable_spells(spells_data)
        assert len(castable) == 1
        assert castable[0][0] == "magic_missile"

    def test_includes_reaction_spells(self, wizard_abilities):
        """Should include reaction spells like Shield."""
        wizard = Character("Gandalf", CharacterClass.WIZARD, level=1, abilities=wizard_abilities, max_hp=8, ac=12)
        wizard.spellcasting_ability = "intelligence"
        wizard.prepared_spells = ["shield", "counterspell"]

        spells_data = {
            "shield": {"name": "Shield", "level": 1, "casting_time": "1 reaction"},
            "counterspell": {"name": "Counterspell", "level": 3, "casting_time": "1 reaction"},
        }

        castable = wizard.get_castable_spells(spells_data)
        assert len(castable) == 2

    def test_excludes_non_combat_spells(self, wizard_abilities):
        """Should exclude non-combat utility spells."""
        wizard = Character("Gandalf", CharacterClass.WIZARD, level=1, abilities=wizard_abilities, max_hp=8, ac=12)
        wizard.spellcasting_ability = "intelligence"
        wizard.prepared_spells = ["mage_armor", "detect_magic", "identify"]

        spells_data = {
            "mage_armor": {"name": "Mage Armor", "level": 1},  # No combat properties
            "detect_magic": {"name": "Detect Magic", "level": 1, "ritual": True},
            "identify": {"name": "Identify", "level": 1, "ritual": True},
        }

        castable = wizard.get_castable_spells(spells_data)
        assert len(castable) == 0

    def test_sorted_by_spell_level(self, wizard_abilities):
        """Should sort spells by level (cantrips first)."""
        wizard = Character("Gandalf", CharacterClass.WIZARD, level=3, abilities=wizard_abilities, max_hp=24, ac=12)
        wizard.spellcasting_ability = "intelligence"
        wizard.prepared_spells = ["fireball", "magic_missile", "fire_bolt", "scorching_ray"]

        spells_data = {
            "fireball": {"name": "Fireball", "level": 3, "damage": {"dice": "8d6"}},
            "magic_missile": {"name": "Magic Missile", "level": 1, "damage": {"dice": "1d4+1"}},
            "fire_bolt": {"name": "Fire Bolt", "level": 0, "attack_type": "ranged_spell_attack"},
            "scorching_ray": {"name": "Scorching Ray", "level": 2, "attack_type": "ranged_spell_attack"},
        }

        castable = wizard.get_castable_spells(spells_data)
        levels = [spell_data["level"] for _, spell_data in castable]

        assert levels == [0, 1, 2, 3]  # Sorted by level

    def test_wizard_with_empty_prepared_spells(self, wizard_abilities):
        """Wizard with empty prepared_spells should show no spells.

        Prepared casters (Wizard, Cleric) with no prepared spells cannot cast
        any leveled spells or cantrips until they prepare them.
        """
        wizard = Character("Gandalf", CharacterClass.WIZARD, level=1, abilities=wizard_abilities, max_hp=8, ac=12)
        wizard.spellcasting_ability = "intelligence"
        wizard.known_spells = ["fire_bolt", "magic_missile"]
        wizard.prepared_spells = []  # Empty - hasn't prepared anything

        spells_data = {
            "fire_bolt": {"name": "Fire Bolt", "level": 0, "attack_type": "ranged_spell_attack"},
            "magic_missile": {"name": "Magic Missile", "level": 1, "damage": {"dice": "1d4+1"}},
        }

        castable = wizard.get_castable_spells(spells_data)
        assert len(castable) == 0  # No spells prepared means nothing castable

    def test_cantrips_always_show_in_prepared_spells(self, wizard_abilities):
        """Cantrips should show if they're in prepared_spells."""
        wizard = Character("Gandalf", CharacterClass.WIZARD, level=1, abilities=wizard_abilities, max_hp=8, ac=12)
        wizard.spellcasting_ability = "intelligence"
        wizard.known_spells = ["fire_bolt", "ray_of_frost", "magic_missile"]
        wizard.prepared_spells = ["fire_bolt", "ray_of_frost", "magic_missile"]  # Cantrips + 1st level

        spells_data = {
            "fire_bolt": {"name": "Fire Bolt", "level": 0, "attack_type": "ranged_spell_attack", "damage": {"dice": "1d10"}},
            "ray_of_frost": {"name": "Ray of Frost", "level": 0, "attack_type": "ranged_spell_attack", "damage": {"dice": "1d8"}},
            "magic_missile": {"name": "Magic Missile", "level": 1, "damage": {"dice": "1d4+1"}},
        }

        castable = wizard.get_castable_spells(spells_data)
        castable_ids = [spell_id for spell_id, _ in castable]

        # Should show all prepared spells including cantrips
        assert "fire_bolt" in castable_ids
        assert "ray_of_frost" in castable_ids
        assert "magic_missile" in castable_ids
        assert len(castable) == 3

    def test_wizard_with_none_prepared_spells(self, wizard_abilities):
        """Wizard with None prepared_spells should handle gracefully."""
        wizard = Character("Gandalf", CharacterClass.WIZARD, level=1, abilities=wizard_abilities, max_hp=8, ac=12)
        wizard.spellcasting_ability = "intelligence"
        wizard.known_spells = ["fire_bolt", "magic_missile"]
        wizard.prepared_spells = None  # Not [], but None

        spells_data = {
            "fire_bolt": {"name": "Fire Bolt", "level": 0, "attack_type": "ranged_spell_attack"},
            "magic_missile": {"name": "Magic Missile", "level": 1, "damage": {"dice": "1d4+1"}},
        }

        castable = wizard.get_castable_spells(spells_data)
        assert len(castable) == 0  # Should return empty list, not crash

    def test_cleric_uses_prepared_spells(self, wizard_abilities):
        """Cleric should use prepared_spells like Wizard (prepared caster)."""
        cleric = Character("Healer", CharacterClass.CLERIC, level=1, abilities=wizard_abilities, max_hp=10, ac=16)
        cleric.spellcasting_ability = "wisdom"
        cleric.known_spells = ["sacred_flame", "cure_wounds", "bless", "shield_of_faith"]
        cleric.prepared_spells = ["sacred_flame", "cure_wounds"]  # Only 2 prepared

        spells_data = {
            "sacred_flame": {"name": "Sacred Flame", "level": 0, "saving_throw_type": "dexterity", "damage": {"dice": "1d8"}},
            "cure_wounds": {"name": "Cure Wounds", "level": 1, "damage": {"dice": "1d8"}},  # Healing is damage for filtering
            "bless": {"name": "Bless", "level": 1},  # No combat properties
            "shield_of_faith": {"name": "Shield of Faith", "level": 1},  # No combat properties
        }

        castable = cleric.get_castable_spells(spells_data)
        castable_ids = [spell_id for spell_id, _ in castable]

        # Should only show prepared combat-relevant spells
        assert "sacred_flame" in castable_ids
        assert "cure_wounds" in castable_ids
        assert "bless" not in castable_ids  # Not prepared
        assert "shield_of_faith" not in castable_ids  # Not prepared

    def test_non_caster_uses_known_spells(self, wizard_abilities):
        """Non-caster classes (Fighter, Rogue) should use known_spells if they have any.

        This is for edge cases like Eldritch Knight or Arcane Trickster subclasses.
        """
        fighter = Character("Warrior", CharacterClass.FIGHTER, level=3, abilities=wizard_abilities, max_hp=30, ac=18)
        fighter.spellcasting_ability = "intelligence"
        fighter.known_spells = ["fire_bolt", "shield"]  # Eldritch Knight knows these
        fighter.prepared_spells = None  # Fighters don't prepare spells

        spells_data = {
            "fire_bolt": {"name": "Fire Bolt", "level": 0, "attack_type": "ranged_spell_attack"},
            "shield": {"name": "Shield", "level": 1, "casting_time": "1 reaction"},
        }

        castable = fighter.get_castable_spells(spells_data)
        castable_ids = [spell_id for spell_id, _ in castable]

        # Should use known_spells for non-prepared caster classes
        assert "fire_bolt" in castable_ids
        assert "shield" in castable_ids
        assert len(castable) == 2
