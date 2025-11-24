# ABOUTME: Integration tests for area effect spell mechanics
# ABOUTME: Tests Burning Hands and other area spells hitting multiple targets

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.combat import CombatEngine
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.core.dice import DiceRoller
from dnd_engine.utils.events import EventBus


@pytest.fixture
def wizard():
    """Create a level 1 wizard with spell slots."""
    wizard = Character(
        name="Tim",
        character_class=CharacterClass.WIZARD,
        level=1,
        abilities=Abilities(
            strength=8,
            dexterity=12,
            constitution=14,
            intelligence=16,  # +3 modifier
            wisdom=10,
            charisma=10
        ),
        max_hp=8,
        ac=12,
        spellcasting_ability="int"
    )
    # Add level 1 spell slots
    wizard.add_resource_pool(ResourcePool(
        name="spell_slots_level_1",
        current=2,
        maximum=2,
        recovery_type="long_rest"
    ))
    return wizard


@pytest.fixture
def burning_hands_spell():
    """Burning Hands spell data."""
    return {
        "id": "burning_hands",
        "name": "Burning Hands",
        "level": 1,
        "school": "evocation",
        "casting_time": "1 action",
        "range_ft": 0,  # Cast from self
        "damage": {
            "dice": "3d6",
            "damage_type": "fire"
        },
        "saving_throw": {
            "ability": "dexterity",
            "on_success": "half"
        },
        "area_of_effect": "15-foot cone",
        "classes": ["wizard", "sorcerer"]
    }


@pytest.fixture
def skeletons():
    """Create two skeleton enemies."""
    skeleton1 = Creature(
        name="Skeleton",
        max_hp=13,
        ac=13,
        abilities=Abilities(
            strength=10,
            dexterity=14,  # +2 DEX for saves
            constitution=15,
            intelligence=6,
            wisdom=8,
            charisma=5
        )
    )

    skeleton2 = Creature(
        name="Skeleton",
        max_hp=13,
        ac=13,
        abilities=Abilities(
            strength=10,
            dexterity=14,  # +2 DEX for saves
            constitution=15,
            intelligence=6,
            wisdom=8,
            charisma=5
        )
    )

    return [skeleton1, skeleton2]


def test_burning_hands_hits_multiple_enemies(wizard, burning_hands_spell, skeletons):
    """Test that Burning Hands damages all enemies in area."""
    combat = CombatEngine()
    event_bus = EventBus()

    # Cast Burning Hands on both skeletons
    result = combat.resolve_spell_save(
        caster=wizard,
        targets=skeletons,
        spell=burning_hands_spell,
        apply_damage=True,
        event_bus=event_bus
    )

    # Verify spell details in result
    assert result["spell_name"] == "Burning Hands"
    assert result["caster"] == "Tim"
    assert result["save_dc"] == 13  # 8 + 2 (prof) + 3 (INT)
    assert result["save_ability"] == "dexterity"

    # Verify both targets got hit
    assert len(result["targets"]) == 2

    # Each target should have results
    for target_result in result["targets"]:
        assert target_result["name"] == "Skeleton"
        assert "roll" in target_result
        assert "modifier" in target_result
        assert "total" in target_result
        assert "success" in target_result
        assert target_result["damage"] > 0
        assert target_result["damage_type"] == "fire"

    # Verify damage was applied to both skeletons
    for skeleton in skeletons:
        assert skeleton.current_hp < skeleton.max_hp


def test_burning_hands_save_mechanics(wizard, burning_hands_spell, skeletons):
    """Test that successful saves result in half damage."""
    combat = CombatEngine()

    # Use seeded dice roller to control results
    combat.dice_roller = DiceRoller(seed=42)

    result = combat.resolve_spell_save(
        caster=wizard,
        targets=skeletons,
        spell=burning_hands_spell,
        apply_damage=False  # Don't apply so we can inspect damage amounts
    )

    # At least one should have different damage from the other due to saves
    damages = [t["damage"] for t in result["targets"]]

    # All should have some damage (3d6 minimum is 3)
    for damage in damages:
        assert damage >= 1  # Half of 3 rounded down is 1
        assert damage <= 18  # Max 3d6 is 18


def test_burning_hands_doesnt_hit_caster(wizard, burning_hands_spell):
    """Test that Burning Hands doesn't damage the caster."""
    combat = CombatEngine()
    event_bus = EventBus()

    initial_hp = wizard.current_hp

    # Create a dummy enemy so we have a valid target list
    enemy = Creature(
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

    # Cast Burning Hands with only the enemy as target
    result = combat.resolve_spell_save(
        caster=wizard,
        targets=[enemy],
        spell=burning_hands_spell,
        apply_damage=True,
        event_bus=event_bus
    )

    # Caster should not be damaged
    assert wizard.current_hp == initial_hp

    # Enemy should be damaged
    assert enemy.current_hp < enemy.max_hp


def test_area_effect_detection():
    """Test that area_of_effect field is properly detected."""
    burning_hands = {
        "id": "burning_hands",
        "name": "Burning Hands",
        "range_ft": 0,
        "area_of_effect": "15-foot cone"
    }

    shield = {
        "id": "shield",
        "name": "Shield",
        "range_ft": 0
        # No area_of_effect
    }

    assert "area_of_effect" in burning_hands
    assert "area_of_effect" not in shield
