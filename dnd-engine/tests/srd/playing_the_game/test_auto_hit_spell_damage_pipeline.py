# ABOUTME: SRD tests that auto-hit spell damage (Magic Missile) honors damage-type modifiers.
# ABOUTME: Guards #595 — auto-hit spells must route through the canonical damage pipeline.

"""Auto-hit spell damage must respect damage-type modifiers.

Magic Missile deals force damage that automatically hits. SRD Immunity,
Resistance, and Vulnerability apply to it like any other typed damage.
Before #595 the auto-hit resolver applied the raw roll directly, so a
force-immune or force-resistant target took full damage. These tests pin
the fix: auto-hit damage is routed through
`rules.damage.apply_damage_modifiers`.
"""

from __future__ import annotations

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.game_state import GameState
from dnd_engine.core.party import Party
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.resources import ResourcePool
from dnd_engine.utils.events import EventBus

_SEED = 42


def _wizard() -> Character:
    wizard = Character(
        name="Gandalf",
        character_class=CharacterClass.WIZARD,
        level=3,
        abilities=Abilities(8, 12, 14, 16, 10, 10),
        max_hp=18,
        ac=12,
        spellcasting_ability="int",
        known_spells=["magic_missile"],
        prepared_spells=["magic_missile"],
    )
    wizard.add_resource_pool(
        ResourcePool(name="spell_slots_level_1", current=4, maximum=4, recovery_type="long_rest")
    )
    return wizard


def _make_target(name: str) -> Creature:
    return Creature(name=name, max_hp=100, ac=10, abilities=Abilities(10, 10, 10, 10, 10, 10))


def _cast_magic_missile_at(target: Creature):
    """Cast Magic Missile (auto-hit, 1d4+1 force) at target; return CombatSpellResult."""
    wizard = _wizard()
    game_state = GameState(
        party=Party([wizard]),
        dungeon_name="test_dungeon",
        event_bus=EventBus(),
        data_loader=DataLoader(),
        dice_roller=DiceRoller(seed=_SEED),
    )
    game_state.active_enemies = [target]
    spell_data = DataLoader().load_spells()["magic_missile"]
    return game_state.cast_spell_combat(
        caster=wizard, spell_data=spell_data, target=target, spellcasting_ability="int"
    )


class TestAutoHitImmunity:
    """SRD § Immunity: a force-immune target takes no Magic Missile damage."""

    def test_force_immune_takes_zero(self) -> None:
        target = _make_target("ForceImmune")
        target.add_condition("has_immunity_force")

        result = _cast_magic_missile_at(target)

        assert result.total_damage == 0
        assert target.current_hp == 100


class TestAutoHitResistance:
    """SRD § Resistance: force-resistant target halves Magic Missile damage."""

    def test_force_resistant_halves(self) -> None:
        # Same seed → identical roll; resistant total must be floor(raw / 2).
        baseline = _make_target("Baseline")
        raw = _cast_magic_missile_at(baseline).total_damage
        assert raw > 0, "Baseline Magic Missile should deal nonzero force damage."

        resistant = _make_target("Resistant")
        resistant.add_condition("has_resistance_force")
        reduced = _cast_magic_missile_at(resistant).total_damage

        assert reduced == raw // 2
        assert resistant.current_hp == 100 - (raw // 2)
