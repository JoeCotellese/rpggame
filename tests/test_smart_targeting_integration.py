# ABOUTME: Integration tests for smart enemy targeting based on intelligence.
# ABOUTME: Verifies targeting behavior works correctly in combat flow.

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.game_state import CombatEvent
from dnd_engine.systems.ai.enemy_ai import EnemyAI


@pytest.fixture
def low_int_monster():
    """Create a wolf-like creature with bestial intelligence (INT 3)."""
    abilities = Abilities(
        strength=12,
        dexterity=15,
        constitution=12,
        intelligence=3,  # Bestial - should use random targeting
        wisdom=12,
        charisma=6,
    )
    return Creature(name="Wolf", max_hp=11, ac=13, abilities=abilities)


@pytest.fixture
def medium_int_monster():
    """Create a goblin with basic tactical intelligence (INT 10)."""
    abilities = Abilities(
        strength=8,
        dexterity=14,
        constitution=10,
        intelligence=10,  # Basic tactics - should use lowest HP
        wisdom=8,
        charisma=8,
    )
    return Creature(name="Goblin", max_hp=7, ac=15, abilities=abilities)


@pytest.fixture
def high_int_monster():
    """Create a mind flayer with high intelligence (INT 19)."""
    abilities = Abilities(
        strength=11,
        dexterity=12,
        constitution=12,
        intelligence=19,  # Tactical - should use lowest HP with low retaliation
        wisdom=17,
        charisma=17,
    )
    return Creature(name="Mind Flayer", max_hp=71, ac=15, abilities=abilities)


@pytest.fixture
def party_members():
    """Create party with varied HP for testing targeting."""
    fighter_abilities = Abilities(
        strength=16, dexterity=10, constitution=14, intelligence=10, wisdom=12, charisma=10
    )
    wizard_abilities = Abilities(
        strength=8, dexterity=14, constitution=12, intelligence=17, wisdom=13, charisma=10
    )
    rogue_abilities = Abilities(
        strength=10, dexterity=17, constitution=12, intelligence=13, wisdom=10, charisma=14
    )

    fighter = Character(
        name="Fighter",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=fighter_abilities,
        max_hp=30,
        ac=18,
        weapon_proficiencies=["simple", "martial"],
        armor_proficiencies=["light", "medium", "heavy", "shields"],
    )
    fighter.current_hp = 30  # Full health

    wizard = Character(
        name="Wizard",
        character_class=CharacterClass.WIZARD,
        level=1,
        abilities=wizard_abilities,
        max_hp=15,
        ac=12,
        weapon_proficiencies=["dagger", "dart", "sling", "quarterstaff", "light crossbow"],
        armor_proficiencies=[],
    )
    wizard.current_hp = 5  # Low health - should be target for tactical enemies

    rogue = Character(
        name="Rogue",
        character_class=CharacterClass.ROGUE,
        level=1,
        abilities=rogue_abilities,
        max_hp=20,
        ac=14,
        weapon_proficiencies=["simple", "hand crossbow", "longsword", "rapier", "shortsword"],
        armor_proficiencies=["light"],
    )
    rogue.current_hp = 15  # Medium health

    return [fighter, wizard, rogue]


class TestSmartTargetingIntegration:
    """Integration tests for smart targeting in combat context."""

    def test_tactical_creature_targets_lowest_hp(self, medium_int_monster, party_members):
        """Test that INT 10+ creatures consistently target lowest HP character."""
        ai = EnemyAI()

        # Run multiple times to ensure consistent behavior
        for _ in range(10):
            target = ai.select_target_smart(
                available_targets=party_members,
                enemy_intelligence=medium_int_monster.abilities.intelligence,
                combat_history=[],
                enemy_name=medium_int_monster.name,
                retaliation_weight=0,  # Disable retaliation for this test
            )
            assert target.name == "Wizard", "Tactical creature should target lowest HP"

    def test_bestial_creature_uses_random_targeting(self, low_int_monster, party_members):
        """Test that INT <= 4 creatures use random targeting."""
        ai = EnemyAI()

        # Track selections over many trials
        selection_counts = {char.name: 0 for char in party_members}
        num_trials = 100

        for _ in range(num_trials):
            target = ai.select_target_smart(
                available_targets=party_members,
                enemy_intelligence=low_int_monster.abilities.intelligence,
                combat_history=[],
                enemy_name=low_int_monster.name,
                retaliation_weight=0,  # Disable retaliation
            )
            selection_counts[target.name] += 1

        # With random targeting, we should see distribution across all targets
        # Not 100% Wizard like tactical targeting
        assert selection_counts["Fighter"] > 0, "Bestial creature should randomly target all"
        assert selection_counts["Rogue"] > 0, "Bestial creature should randomly target all"

    def test_retaliation_with_combat_history(self, medium_int_monster, party_members):
        """Test that creature retaliates against recent attacker."""
        ai = EnemyAI()

        # Create combat history where Fighter attacked the Goblin
        combat_history = [
            CombatEvent(
                timestamp=1.0,
                event_type="attack",
                attacker="Fighter",
                defender="Goblin",
                damage=8,
                description="Fighter hits Goblin for 8 damage",
            ),
        ]

        # With 100% retaliation, should target Fighter (not low HP Wizard)
        target = ai.select_target_smart(
            available_targets=party_members,
            enemy_intelligence=medium_int_monster.abilities.intelligence,
            combat_history=combat_history,
            enemy_name="Goblin",
            retaliation_weight=1.0,
        )

        assert target.name == "Fighter", "Should retaliate against recent attacker"

    def test_retaliation_ignores_dead_attacker(self, medium_int_monster, party_members):
        """Test that retaliation falls back when attacker is dead/unavailable."""
        ai = EnemyAI()

        # Create history where Cleric (not in party_members) attacked
        combat_history = [
            CombatEvent(
                timestamp=1.0,
                event_type="attack",
                attacker="Cleric",  # Not in available targets
                defender="Goblin",
                damage=5,
                description="Cleric hits Goblin",
            ),
        ]

        # Should fall back to lowest HP (Wizard) since Cleric is unavailable
        target = ai.select_target_smart(
            available_targets=party_members,
            enemy_intelligence=medium_int_monster.abilities.intelligence,
            combat_history=combat_history,
            enemy_name="Goblin",
            retaliation_weight=1.0,
        )

        assert target.name == "Wizard", "Should fall back to lowest HP when attacker unavailable"

    def test_spell_damage_triggers_retaliation(self, medium_int_monster, party_members):
        """Test that spell damage also triggers retaliation."""
        ai = EnemyAI()

        # Wizard cast a spell on the Goblin
        combat_history = [
            CombatEvent(
                timestamp=1.0,
                event_type="spell",
                attacker="Wizard",
                defender="Goblin",
                damage=12,
                description="Wizard casts Burning Hands on Goblin",
            ),
        ]

        target = ai.select_target_smart(
            available_targets=party_members,
            enemy_intelligence=medium_int_monster.abilities.intelligence,
            combat_history=combat_history,
            enemy_name="Goblin",
            retaliation_weight=1.0,
        )

        assert target.name == "Wizard", "Should retaliate against spell attacker"

    def test_misses_dont_trigger_retaliation(self, medium_int_monster, party_members):
        """Test that attacks dealing 0 damage don't trigger retaliation."""
        ai = EnemyAI()

        # Fighter attacked but missed (0 damage)
        combat_history = [
            CombatEvent(
                timestamp=1.0,
                event_type="attack",
                attacker="Fighter",
                defender="Goblin",
                damage=0,  # Miss!
                description="Fighter misses Goblin",
            ),
        ]

        target = ai.select_target_smart(
            available_targets=party_members,
            enemy_intelligence=medium_int_monster.abilities.intelligence,
            combat_history=combat_history,
            enemy_name="Goblin",
            retaliation_weight=1.0,
        )

        # No valid attacker, should fall back to lowest HP
        assert target.name == "Wizard", "Misses shouldn't trigger retaliation"

    def test_high_int_creature_has_low_retaliation(self, high_int_monster, party_members):
        """Test that high INT creatures have lower retaliation tendency."""
        ai = EnemyAI()

        # Mind Flayer was attacked by Fighter
        combat_history = [
            CombatEvent(
                timestamp=1.0,
                event_type="attack",
                attacker="Fighter",
                defender="Mind Flayer",
                damage=10,
                description="Fighter hits Mind Flayer",
            ),
        ]

        # Run many trials with default retaliation weight
        retaliation_count = 0
        num_trials = 100

        for _ in range(num_trials):
            target = ai.select_target_smart(
                available_targets=party_members,
                enemy_intelligence=high_int_monster.abilities.intelligence,
                combat_history=combat_history,
                enemy_name="Mind Flayer",
                # Use default retaliation weight (0.20 for INT >= 10)
            )
            if target.name == "Fighter":
                retaliation_count += 1

        # With 20% retaliation chance, we expect roughly 20 retaliations
        # Allow some variance for randomness
        assert 5 < retaliation_count < 50, (
            f"High INT creature should retaliate ~20% of the time, got {retaliation_count}%"
        )


class TestCombatHistoryInteraction:
    """Test interactions between combat history and targeting."""

    def test_most_recent_attacker_is_preferred(self, medium_int_monster, party_members):
        """Test that most recent attacker is the retaliation target."""
        ai = EnemyAI()

        # Multiple attacks - Rogue attacked most recently
        combat_history = [
            CombatEvent(
                timestamp=1.0,
                event_type="attack",
                attacker="Fighter",
                defender="Goblin",
                damage=5,
            ),
            CombatEvent(
                timestamp=2.0,
                event_type="attack",
                attacker="Rogue",
                defender="Goblin",
                damage=12,  # Sneak attack!
            ),
        ]

        target = ai.select_target_smart(
            available_targets=party_members,
            enemy_intelligence=medium_int_monster.abilities.intelligence,
            combat_history=combat_history,
            enemy_name="Goblin",
            retaliation_weight=1.0,
        )

        assert target.name == "Rogue", "Should retaliate against most recent attacker"

    def test_only_attacks_on_self_considered(self, medium_int_monster, party_members):
        """Test that attacks on other enemies don't trigger retaliation."""
        ai = EnemyAI()

        # Fighter attacked a Skeleton, not the Goblin
        combat_history = [
            CombatEvent(
                timestamp=1.0,
                event_type="attack",
                attacker="Fighter",
                defender="Skeleton",  # Different enemy
                damage=10,
            ),
        ]

        target = ai.select_target_smart(
            available_targets=party_members,
            enemy_intelligence=medium_int_monster.abilities.intelligence,
            combat_history=combat_history,
            enemy_name="Goblin",
            retaliation_weight=1.0,
        )

        # No attack on Goblin, should use base targeting
        assert target.name == "Wizard", "Should ignore attacks on other enemies"
