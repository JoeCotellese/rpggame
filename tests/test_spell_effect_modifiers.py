# ABOUTME: Tests for spell effect modifiers (AC, attack bonuses, etc.)
# ABOUTME: Validates that active effects from spells correctly modify character stats

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.game_state import GameState
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.time_manager import ActiveEffect, EffectType, ModifierType
from dnd_engine.utils.events import EventBus


@pytest.fixture
def wizard():
    """Create a wizard for testing"""
    abilities = Abilities(
        strength=8,
        dexterity=14,  # +2 modifier
        constitution=12,
        intelligence=16,
        wisdom=10,
        charisma=10,
    )
    return Character(
        name="Gandalf",
        character_class=CharacterClass.WIZARD,
        level=3,
        abilities=abilities,
        max_hp=18,
        ac=10,  # Base AC (no armor)
        spellcasting_ability="intelligence",
    )


@pytest.fixture
def game_state_with_wizard(wizard):
    """Create a GameState with a wizard"""
    from dnd_engine.core.dice import DiceRoller
    from dnd_engine.core.party import Party

    data_loader = DataLoader()
    event_bus = EventBus()
    dice_roller = DiceRoller()
    party = Party()
    party.add_character(wizard)

    game_state = GameState(
        party=party,
        dungeon_name="test_dungeon",
        event_bus=event_bus,
        data_loader=data_loader,
        dice_roller=dice_roller,
    )
    return game_state


class TestEffectiveACCalculation:
    """Test effective AC calculation with spell modifiers"""

    def test_base_ac_without_effects(self, game_state_with_wizard, wizard):
        """Test that base AC is returned when no effects are active"""
        effective_ac = game_state_with_wizard.get_effective_ac(wizard)
        assert effective_ac == 10

    def test_mage_armor_sets_ac(self, game_state_with_wizard, wizard):
        """Test that Mage Armor sets AC to 13 + DEX"""
        # Add Mage Armor effect (8 hours duration)
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Mage Armor",
            duration_type="hours",
            duration_value=8,
            remaining_value=8,
            target_name=wizard.name,
            description="Base AC becomes 13 + DEX",
            concentration=False,
            effect_data={
                "modifier_type": ModifierType.AC_SET_BASE.value,
                "formula": "13 + dex_mod",
            },
        )
        game_state_with_wizard.time_manager.add_effect(effect)

        # Effective AC should be 13 + 2 (DEX) = 15
        effective_ac = game_state_with_wizard.get_effective_ac(wizard)
        assert effective_ac == 15

    def test_shield_adds_bonus(self, game_state_with_wizard, wizard):
        """Test that Shield spell adds +5 to AC"""
        # Add Shield effect (1 round duration)
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Shield",
            duration_type="rounds",
            duration_value=1,
            remaining_value=1,
            target_name=wizard.name,
            description="+5 AC until start of your next turn",
            concentration=False,
            effect_data={"modifier_type": ModifierType.AC_BONUS.value, "value": 5},
        )
        game_state_with_wizard.time_manager.add_effect(effect)

        # Effective AC should be 10 + 5 = 15
        effective_ac = game_state_with_wizard.get_effective_ac(wizard)
        assert effective_ac == 15

    def test_mage_armor_plus_shield(self, game_state_with_wizard, wizard):
        """Test that Mage Armor and Shield stack correctly"""
        # Add Mage Armor
        mage_armor = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Mage Armor",
            duration_type="hours",
            duration_value=8,
            remaining_value=8,
            target_name=wizard.name,
            description="Base AC becomes 13 + DEX",
            concentration=False,
            effect_data={
                "modifier_type": ModifierType.AC_SET_BASE.value,
                "formula": "13 + dex_mod",
            },
        )
        game_state_with_wizard.time_manager.add_effect(mage_armor)

        # Add Shield
        shield = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Shield",
            duration_type="rounds",
            duration_value=1,
            remaining_value=1,
            target_name=wizard.name,
            description="+5 AC",
            concentration=False,
            effect_data={"modifier_type": ModifierType.AC_BONUS.value, "value": 5},
        )
        game_state_with_wizard.time_manager.add_effect(shield)

        # Effective AC should be 13 + 2 (DEX) + 5 (Shield) = 20
        effective_ac = game_state_with_wizard.get_effective_ac(wizard)
        assert effective_ac == 20

    def test_multiple_ac_set_base_only_first_applies(self, game_state_with_wizard, wizard):
        """Test that only the first AC set_base effect applies"""
        # Add Mage Armor (13 + DEX)
        mage_armor = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Mage Armor",
            duration_type="hours",
            duration_value=8,
            remaining_value=8,
            target_name=wizard.name,
            description="Base AC becomes 13 + DEX",
            concentration=False,
            effect_data={
                "modifier_type": ModifierType.AC_SET_BASE.value,
                "formula": "13 + dex_mod",
            },
        )
        game_state_with_wizard.time_manager.add_effect(mage_armor)

        # Add a second set_base effect (should be ignored)
        barkskin = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Barkskin",
            duration_type="minutes",
            duration_value=60,
            remaining_value=60,
            target_name=wizard.name,
            description="Base AC becomes 16",
            concentration=True,
            caster_name=wizard.name,
            effect_data={"modifier_type": ModifierType.AC_SET_BASE.value, "formula": "16"},
        )
        game_state_with_wizard.time_manager.add_effect(barkskin)

        # Only Mage Armor should apply: 13 + 2 = 15
        effective_ac = game_state_with_wizard.get_effective_ac(wizard)
        assert effective_ac == 15

    def test_shield_expires_after_one_round(self, game_state_with_wizard, wizard):
        """Test that Shield effect expires after 1 combat round"""
        # Add Shield effect
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Shield",
            duration_type="rounds",
            duration_value=1,
            remaining_value=1,
            target_name=wizard.name,
            description="+5 AC",
            concentration=False,
            effect_data={"modifier_type": ModifierType.AC_BONUS.value, "value": 5},
        )
        game_state_with_wizard.time_manager.add_effect(effect)

        # AC should be boosted initially
        assert game_state_with_wizard.get_effective_ac(wizard) == 15  # 10 + 5

        # Advance one round
        expired = game_state_with_wizard.time_manager.advance_round(1)

        # Shield should have expired
        assert len(expired) == 1
        assert expired[0].source == "Shield"
        assert game_state_with_wizard.get_effective_ac(wizard) == 10  # Back to base AC

    def test_mage_armor_not_affected_by_rounds(self, game_state_with_wizard, wizard):
        """Test that time-based effects (Mage Armor) don't expire with round advancement"""
        # Add Mage Armor (time-based, not round-based)
        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source="Mage Armor",
            duration_type="hours",
            duration_value=8,
            remaining_value=8,
            target_name=wizard.name,
            description="Base AC becomes 13 + DEX",
            concentration=False,
            effect_data={
                "modifier_type": ModifierType.AC_SET_BASE.value,
                "formula": "13 + dex_mod",
            },
        )
        game_state_with_wizard.time_manager.add_effect(effect)

        # AC should be boosted
        assert game_state_with_wizard.get_effective_ac(wizard) == 15  # 13 + 2

        # Advance 10 combat rounds - should NOT affect time-based effects
        expired = game_state_with_wizard.time_manager.advance_round(10)

        # Mage Armor should still be active
        assert len(expired) == 0
        assert game_state_with_wizard.get_effective_ac(wizard) == 15  # Still boosted


class TestACFormulaEvaluation:
    """Test AC formula parsing and evaluation"""

    def test_simple_constant_formula(self, game_state_with_wizard, wizard):
        """Test formula with just a constant"""
        result = game_state_with_wizard._evaluate_ac_formula("16", wizard)
        assert result == 16

    def test_constant_plus_dex(self, game_state_with_wizard, wizard):
        """Test formula with constant + dex_mod"""
        result = game_state_with_wizard._evaluate_ac_formula("13 + dex_mod", wizard)
        assert result == 15  # 13 + 2

    def test_formula_with_spaces(self, game_state_with_wizard, wizard):
        """Test that formula handles extra spaces"""
        result = game_state_with_wizard._evaluate_ac_formula("  13  +  dex_mod  ", wizard)
        assert result == 15

    def test_multiple_ability_modifiers(self, game_state_with_wizard, wizard):
        """Test formula with multiple ability modifiers"""
        result = game_state_with_wizard._evaluate_ac_formula("10 + dex_mod + con_mod", wizard)
        assert result == 13  # 10 + 2 (DEX) + 1 (CON)


class TestSpellCastingACModifierIntegration:
    """Integration tests: verify casting spells through cast_spell_exploration applies AC modifiers"""

    @pytest.fixture
    def wizard_with_shield(self):
        """Create a wizard who knows Shield"""
        from dnd_engine.systems.resources import ResourcePool

        abilities = Abilities(
            strength=8,
            dexterity=14,  # +2 modifier
            constitution=12,
            intelligence=16,
            wisdom=10,
            charisma=10,
        )
        wizard = Character(
            name="Thalia",
            character_class=CharacterClass.WIZARD,
            level=3,
            abilities=abilities,
            max_hp=18,
            ac=10,  # Base AC (no armor)
            spellcasting_ability="int",
            known_spells=["shield", "mage_armor"],
            prepared_spells=["shield", "mage_armor"],
        )
        # Add spell slots
        wizard.add_resource_pool(
            ResourcePool(name="spell_slots_level_1", current=4, maximum=4, recovery_type="long_rest")
        )
        return wizard

    @pytest.fixture
    def game_state_with_spell_caster(self, wizard_with_shield):
        """Create a GameState with a wizard who can cast Shield"""
        from dnd_engine.core.dice import DiceRoller
        from dnd_engine.core.party import Party

        data_loader = DataLoader()
        event_bus = EventBus()
        dice_roller = DiceRoller()
        party = Party()
        party.add_character(wizard_with_shield)

        game_state = GameState(
            party=party,
            dungeon_name="test_dungeon",
            event_bus=event_bus,
            data_loader=data_loader,
            dice_roller=dice_roller,
        )
        return game_state

    def test_casting_shield_applies_ac_bonus(self, game_state_with_spell_caster, wizard_with_shield):
        """Casting Shield through cast_spell_exploration should apply +5 AC bonus"""
        # Verify base AC before casting
        assert game_state_with_spell_caster.get_effective_ac(wizard_with_shield) == 10

        # Cast Shield
        result = game_state_with_spell_caster.cast_spell_exploration("Thalia", "shield")

        assert result["success"] is True
        assert result["spell_name"] == "Shield"

        # Verify AC is now boosted by +5
        effective_ac = game_state_with_spell_caster.get_effective_ac(wizard_with_shield)
        assert effective_ac == 15, f"Expected AC 15 (10 + 5), got {effective_ac}"

    def test_casting_mage_armor_sets_ac(self, game_state_with_spell_caster, wizard_with_shield):
        """Casting Mage Armor through cast_spell_exploration should set AC to 13 + DEX"""
        # Verify base AC before casting
        assert game_state_with_spell_caster.get_effective_ac(wizard_with_shield) == 10

        # Cast Mage Armor
        result = game_state_with_spell_caster.cast_spell_exploration("Thalia", "mage_armor")

        assert result["success"] is True
        assert result["spell_name"] == "Mage Armor"

        # Verify AC is now 13 + DEX (+2) = 15
        effective_ac = game_state_with_spell_caster.get_effective_ac(wizard_with_shield)
        assert effective_ac == 15, f"Expected AC 15 (13 + 2 DEX), got {effective_ac}"

    def test_casting_shield_and_mage_armor_stack(self, game_state_with_spell_caster, wizard_with_shield):
        """Casting both Shield and Mage Armor should stack correctly"""
        # Cast Mage Armor first
        result1 = game_state_with_spell_caster.cast_spell_exploration("Thalia", "mage_armor")
        assert result1["success"] is True

        # Verify Mage Armor AC
        assert game_state_with_spell_caster.get_effective_ac(wizard_with_shield) == 15

        # Cast Shield
        result2 = game_state_with_spell_caster.cast_spell_exploration("Thalia", "shield")
        assert result2["success"] is True

        # Verify stacked AC: 13 + 2 (DEX) + 5 (Shield) = 20
        effective_ac = game_state_with_spell_caster.get_effective_ac(wizard_with_shield)
        assert effective_ac == 20, f"Expected AC 20 (13 + 2 DEX + 5 Shield), got {effective_ac}"

    def test_shield_effect_has_correct_metadata(self, game_state_with_spell_caster, wizard_with_shield):
        """Verify Shield creates an ActiveEffect with correct effect_data"""
        # Cast Shield
        game_state_with_spell_caster.cast_spell_exploration("Thalia", "shield")

        # Find the Shield effect
        effects = game_state_with_spell_caster.time_manager.get_effects_for_character("Thalia")
        shield_effects = [e for e in effects if e.source == "Shield"]

        assert len(shield_effects) == 1
        effect = shield_effects[0]

        # Verify effect metadata
        assert effect.effect_data.get("modifier_type") == "ac_bonus"
        assert effect.effect_data.get("value") == 5
        assert effect.duration_type == "rounds"
        assert effect.remaining_value == 1
