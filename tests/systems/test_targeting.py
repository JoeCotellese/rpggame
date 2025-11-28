# ABOUTME: Unit tests for the targeting requirements service
# ABOUTME: Tests that CLI can query targeting requirements without interpreting game data directly

from dnd_engine.systems.targeting import (
    TargetingRequirements,
    ValidTargets,
    get_item_targeting_requirements,
    get_spell_targeting_requirements,
)


class TestValidTargetsEnum:
    """Tests for the ValidTargets enum."""

    def test_valid_targets_has_expected_values(self):
        """ValidTargets enum should have all expected target types."""
        assert ValidTargets.SELF.value == "self"
        assert ValidTargets.ALLY.value == "ally"
        assert ValidTargets.ENEMY.value == "enemy"
        assert ValidTargets.AREA.value == "area"
        assert ValidTargets.ANY.value == "any"


class TestTargetingRequirements:
    """Tests for the TargetingRequirements dataclass."""

    def test_self_target_does_not_need_selection(self):
        """Self-targeting spells/items should not need target selection."""
        req = TargetingRequirements(
            valid_targets=ValidTargets.SELF,
            needs_target_selection=False,
            can_target_self=True,
            is_area_effect=False,
        )
        assert not req.needs_target_selection
        assert req.can_target_self

    def test_enemy_target_needs_selection(self):
        """Enemy-targeting spells/items should need target selection."""
        req = TargetingRequirements(
            valid_targets=ValidTargets.ENEMY,
            needs_target_selection=True,
            can_target_self=False,
            is_area_effect=False,
        )
        assert req.needs_target_selection
        assert not req.can_target_self

    def test_area_effect_does_not_need_selection(self):
        """Area effect spells should not need target selection."""
        req = TargetingRequirements(
            valid_targets=ValidTargets.AREA,
            needs_target_selection=False,
            can_target_self=False,
            is_area_effect=True,
        )
        assert not req.needs_target_selection
        assert req.is_area_effect


class TestGetSpellTargetingRequirements:
    """Tests for get_spell_targeting_requirements function."""

    def test_enemy_spell_returns_enemy_requirements(self):
        """Spell with target_type='enemy' should return enemy targeting requirements."""
        spell_data = {
            "name": "Fire Bolt",
            "target_type": "enemy",
            "level": 0,
        }
        req = get_spell_targeting_requirements(spell_data)

        assert req.valid_targets == ValidTargets.ENEMY
        assert req.needs_target_selection is True
        assert req.can_target_self is False
        assert req.is_area_effect is False

    def test_self_spell_returns_self_requirements(self):
        """Spell with target_type='self' should return self targeting requirements."""
        spell_data = {
            "name": "Shield",
            "target_type": "self",
            "level": 1,
        }
        req = get_spell_targeting_requirements(spell_data)

        assert req.valid_targets == ValidTargets.SELF
        assert req.needs_target_selection is False
        assert req.can_target_self is True
        assert req.is_area_effect is False

    def test_ally_spell_returns_ally_requirements(self):
        """Spell with target_type='ally' should return ally targeting requirements."""
        spell_data = {
            "name": "Cure Wounds",
            "target_type": "ally",
            "level": 1,
        }
        req = get_spell_targeting_requirements(spell_data)

        assert req.valid_targets == ValidTargets.ALLY
        assert req.needs_target_selection is True
        assert req.can_target_self is True  # Can heal yourself
        assert req.is_area_effect is False

    def test_area_spell_returns_area_requirements(self):
        """Spell with target_type='area' should return area targeting requirements."""
        spell_data = {
            "name": "Burning Hands",
            "target_type": "area",
            "level": 1,
        }
        req = get_spell_targeting_requirements(spell_data)

        assert req.valid_targets == ValidTargets.AREA
        assert req.needs_target_selection is False
        assert req.can_target_self is False
        assert req.is_area_effect is True

    def test_any_spell_returns_any_requirements(self):
        """Spell with target_type='any' should return any targeting requirements."""
        spell_data = {
            "name": "Light",
            "target_type": "any",
            "level": 0,
        }
        req = get_spell_targeting_requirements(spell_data)

        assert req.valid_targets == ValidTargets.ANY
        assert req.needs_target_selection is True
        assert req.can_target_self is True  # Can target yourself
        assert req.is_area_effect is False

    def test_missing_target_type_defaults_to_enemy(self):
        """Spell without target_type should default to enemy targeting."""
        spell_data = {
            "name": "Unknown Spell",
            "level": 1,
            # No target_type field
        }
        req = get_spell_targeting_requirements(spell_data)

        assert req.valid_targets == ValidTargets.ENEMY
        assert req.needs_target_selection is True
        # Should include warning flag for missing target_type
        assert req.missing_target_type is True


class TestGetItemTargetingRequirements:
    """Tests for get_item_targeting_requirements function."""

    def test_healing_potion_returns_any_requirements(self):
        """Healing potion with target_type='any' should return any targeting."""
        item_data = {
            "name": "Potion of Healing",
            "effect_type": "healing",
            "target_type": "any",
        }
        req = get_item_targeting_requirements(item_data)

        assert req.valid_targets == ValidTargets.ANY
        assert req.needs_target_selection is True
        assert req.can_target_self is True

    def test_self_buff_item_returns_self_requirements(self):
        """Self-targeting buff item should return self requirements."""
        item_data = {
            "name": "Antitoxin",
            "effect_type": "buff",
            "target_type": "self",
        }
        req = get_item_targeting_requirements(item_data)

        assert req.valid_targets == ValidTargets.SELF
        assert req.needs_target_selection is False
        assert req.can_target_self is True

    def test_attack_item_returns_enemy_requirements(self):
        """Attack item with target_type='enemy' should return enemy requirements."""
        item_data = {
            "name": "Alchemist's Fire",
            "effect_type": "damage",
            "target_type": "enemy",
        }
        req = get_item_targeting_requirements(item_data)

        assert req.valid_targets == ValidTargets.ENEMY
        assert req.needs_target_selection is True
        assert req.can_target_self is False

    def test_missing_target_type_defaults_to_self(self):
        """Item without target_type should default to self targeting."""
        item_data = {
            "name": "Unknown Potion",
            "effect_type": "buff",
            # No target_type field
        }
        req = get_item_targeting_requirements(item_data)

        # Items default to self (unlike spells which default to enemy)
        assert req.valid_targets == ValidTargets.SELF
        assert req.needs_target_selection is False
        assert req.can_target_self is True


class TestTargetingRequirementsHelperMethods:
    """Tests for helper methods on TargetingRequirements."""

    def test_is_valid_target_for_self_spell(self):
        """Self spells should only allow self as valid target."""
        req = TargetingRequirements(
            valid_targets=ValidTargets.SELF,
            needs_target_selection=False,
            can_target_self=True,
            is_area_effect=False,
        )
        assert req.is_valid_target_type("self")
        assert not req.is_valid_target_type("ally")
        assert not req.is_valid_target_type("enemy")

    def test_is_valid_target_for_ally_spell(self):
        """Ally spells should allow self and ally targets."""
        req = TargetingRequirements(
            valid_targets=ValidTargets.ALLY,
            needs_target_selection=True,
            can_target_self=True,
            is_area_effect=False,
        )
        assert req.is_valid_target_type("self")
        assert req.is_valid_target_type("ally")
        assert not req.is_valid_target_type("enemy")

    def test_is_valid_target_for_any_spell(self):
        """Any spells should allow all target types."""
        req = TargetingRequirements(
            valid_targets=ValidTargets.ANY,
            needs_target_selection=True,
            can_target_self=True,
            is_area_effect=False,
        )
        assert req.is_valid_target_type("self")
        assert req.is_valid_target_type("ally")
        assert req.is_valid_target_type("enemy")

    def test_prompt_type_for_enemy_targeting(self):
        """Enemy targeting should return 'enemy' prompt type."""
        req = TargetingRequirements(
            valid_targets=ValidTargets.ENEMY,
            needs_target_selection=True,
            can_target_self=False,
            is_area_effect=False,
        )
        assert req.get_prompt_type() == "enemy"

    def test_prompt_type_for_ally_targeting(self):
        """Ally targeting should return 'ally' prompt type."""
        req = TargetingRequirements(
            valid_targets=ValidTargets.ALLY,
            needs_target_selection=True,
            can_target_self=True,
            is_area_effect=False,
        )
        assert req.get_prompt_type() == "ally"

    def test_prompt_type_for_self_targeting(self):
        """Self targeting should return None (no prompt needed)."""
        req = TargetingRequirements(
            valid_targets=ValidTargets.SELF,
            needs_target_selection=False,
            can_target_self=True,
            is_area_effect=False,
        )
        assert req.get_prompt_type() is None

    def test_prompt_type_for_area_targeting(self):
        """Area targeting should return None (no prompt needed)."""
        req = TargetingRequirements(
            valid_targets=ValidTargets.AREA,
            needs_target_selection=False,
            can_target_self=False,
            is_area_effect=True,
        )
        assert req.get_prompt_type() is None
