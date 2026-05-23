# ABOUTME: SRD conformance audit for "Playing the Game > Healing".
# ABOUTME: Cross-references docs/srd/playing-the-game/healing.md against engine code.

"""SRD conformance: Healing.

Maps every rule in `docs/srd/playing-the-game/healing.md` to a test.
Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.item_effects import apply_item_effect

pytestmark = pytest.mark.srd(
    "playing-the-game/healing.md",
    lines="2294-2320",
)


ITEMS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "items.json"
)
SPELLS_JSON = (
    Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd" / "spells.json"
)


def _make_abilities() -> Abilities:
    return Abilities(
        strength=14, dexterity=12, constitution=13, intelligence=10, wisdom=11, charisma=8
    )


def _make_character(*, max_hp: int = 20, current_hp: int | None = None) -> Character:
    return Character(
        name="TestHero",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=_make_abilities(),
        max_hp=max_hp,
        ac=16,
        current_hp=current_hp if current_hp is not None else max_hp,
    )


class TestHealing_SourcesOfHealing:
    """SRD § Playing the Game › Healing › Sources.

    > Hit Points can be restored by magic, such as the Cure Wounds spell
    > or a Potion of Healing, or by a Short or Long Rest (see "Rules
    > Glossary").
    """

    def test_potion_of_healing_is_in_catalog_as_healing_item(self) -> None:
        """items.json declares Potion of Healing with `effect_type=healing`.

        Data-parity check: the SRD names Potion of Healing as a canonical
        healing source. `dnd_engine/data/srd/items.json:419-431` carries
        the entry with `effect_type=healing` and a `healing` dice
        notation, consumed by
        `dnd_engine/systems/item_effects._apply_healing_effect`
        (`item_effects.py:94-162`).
        """
        items = json.loads(ITEMS_JSON.read_text())
        potion = items["consumables"]["potion_of_healing"]
        assert potion["effect_type"] == "healing"
        assert potion["healing"] == "2d4+2"

    def test_cure_wounds_spell_is_in_catalog_with_healing_dice(self) -> None:
        """spells.json declares Cure Wounds with `healing.dice`.

        Data-parity check: the SRD names Cure Wounds as a canonical
        healing source. `dnd_engine/data/srd/spells.json:238-258` ships
        it with `healing.dice = 1d8`, consumed by
        `cast_spell_exploration` (`game_state.py:1944-1976`).
        """
        spells = json.loads(SPELLS_JSON.read_text())
        cure = spells["cure_wounds"]
        assert cure["healing"]["dice"] == "1d8"

    def test_potion_of_healing_restores_hp(self) -> None:
        """`apply_item_effect` rolls the healing dice and applies them.

        End-to-end proof for the SRD's "Hit Points can be restored by
        magic ... Potion of Healing" rule. The healing path lives at
        `dnd_engine/systems/item_effects._apply_healing_effect`
        (`item_effects.py:94-162`) — rolls `healing` dice, calls
        `target.recover_hp` (or `Creature.heal`), and returns the
        actual amount healed.
        """
        items = json.loads(ITEMS_JSON.read_text())
        potion = items["consumables"]["potion_of_healing"]
        target = _make_character(max_hp=20, current_hp=5)
        roller = DiceRoller(seed=42)
        result = apply_item_effect(potion, target, roller)
        # 2d4+2: minimum 4, maximum 10 — always positive on a wounded target.
        assert result.success is True
        assert result.amount >= 4
        assert target.current_hp > 5

    def test_long_rest_restores_full_hp(self) -> None:
        """`Character.take_long_rest` recovers all HP for a living character.

        SRD: "by a Short or Long Rest." The body is at
        `dnd_engine/core/character.py:1236-1280` — long rest calls
        `recover_hp()` (full heal). Short rest does not heal in this
        engine (no Hit Dice spend implemented).
        """
        character = _make_character(max_hp=20, current_hp=5)
        result = character.take_long_rest()
        assert result["hp_recovered"] == 15
        assert character.current_hp == 20


class TestHealing_KnockingOutACreature:
    """SRD § Playing the Game › Healing › Knocking Out a Creature.

    > When you would reduce a creature to 0 Hit Points with a melee
    > attack, you can instead reduce the creature to 1 Hit Point and
    > give it the Unconscious condition. It then starts a Short Rest,
    > at the end of which that condition ends on it. The condition ends
    > early if the creature regains any Hit Points or if someone takes
    > an action to administer first aid to it, making a successful DC 10
    > Wisdom (Medicine) check.
    """

    def test_melee_attacker_can_choose_nonlethal_to_knock_out(self) -> None:
        pytest.skip(
            "GAP: there is no nonlethal / knockout option on the "
            "attack surface. `CombatEngine.resolve_attack` "
            "(dnd_engine/core/combat.py:91-221) has no `nonlethal` or "
            "`knockout` parameter, and `Character.take_damage` "
            "(dnd_engine/core/character.py:1100-1148) unconditionally "
            "drops the target to 0 HP and starts death saves. A player "
            "cannot declare a knockout attack. Tracked by issue #485."
        )

    def test_knocked_out_creature_starts_a_short_rest(self) -> None:
        pytest.skip(
            "GAP: depends on the knockout option above. There is no "
            "linkage from a KO event to `Character.take_short_rest` "
            "(dnd_engine/core/character.py:1202-1234) and no rest-bound "
            "Unconscious condition. Tracked by issue #485."
        )

    def test_unconscious_ends_when_creature_regains_hp(self) -> None:
        pytest.skip(
            "GAP: `Character.recover_hp` "
            "(dnd_engine/core/character.py:1150-1174) resets death "
            "saves when leaving 0 HP but does NOT clear the Unconscious "
            "condition tied to the SRD knockout path. The general "
            "Unconscious condition (added via `apply_condition_with_metadata`) "
            "is not consulted by recover_hp. Tracked by issue #485."
        )

    def test_first_aid_dc10_medicine_check_ends_unconscious(self) -> None:
        pytest.skip(
            "GAP: there is no first-aid action. The Wisdom (Medicine) "
            "check primitive exists "
            "(`Character.make_skill_check('medicine', dc=10, ...)` in "
            "dnd_engine/core/character.py:726) but no action dispatcher "
            "invokes it to end the Unconscious condition from a KO. "
            "The existing stabilization plumbing "
            "(dnd_engine/core/character.py:1340-1380) is keyed to "
            "death-saves, not to the SRD knockout rest. Tracked by "
            "issue #485."
        )


class TestHealing_ApplyHealingAndCapAtMax:
    """SRD § Playing the Game › Healing › Apply and Cap.

    > When you receive healing, add the restored Hit Points to your
    > current Hit Points. Your Hit Points can't exceed your Hit Point
    > maximum, so any Hit Points regained in excess of the maximum are
    > lost. For example, if you receive 8 Hit Points of healing and have
    > 14 Hit Points and a Hit Point maximum of 20, you regain 6 Hit
    > Points, not 8.
    """

    def test_creature_heal_adds_to_current_hp(self) -> None:
        """`Creature.heal` adds restored HP to current HP.

        Source: `dnd_engine/core/creature.py:226-240`. Healing 4 HP on
        a creature with 10/20 HP raises current_hp to 14.
        """
        creature = Creature(
            name="Goblin", max_hp=20, ac=12, abilities=_make_abilities(), current_hp=10
        )
        creature.heal(4)
        assert creature.current_hp == 14

    def test_creature_heal_caps_at_max_hp(self) -> None:
        """`Creature.heal` clamps the result at max_hp.

        Source: `dnd_engine/core/creature.py:240` — `min(self.max_hp,
        self.current_hp + amount)`. Healing 8 on a 14/20 target yields
        20 (gained 6, not 8), matching the SRD's worked example
        verbatim.
        """
        creature = Creature(
            name="Goblin", max_hp=20, ac=12, abilities=_make_abilities(), current_hp=14
        )
        creature.heal(8)
        assert creature.current_hp == 20

    def test_character_recover_hp_caps_at_max_and_returns_actual_amount(self) -> None:
        """`Character.recover_hp` returns the actually-healed amount.

        Source: `dnd_engine/core/character.py:1150-1174`. With
        max_hp=20 and current_hp=14, calling `recover_hp(8)` returns 6
        (the actual amount healed) and current_hp is now 20. This is
        the SRD's worked example, with the engine returning the
        post-cap amount to the caller.
        """
        character = _make_character(max_hp=20, current_hp=14)
        actually_healed = character.recover_hp(8)
        assert actually_healed == 6
        assert character.current_hp == 20

    def test_healing_potion_overheal_is_lost_not_carried(self) -> None:
        """End-to-end: a Potion of Healing overheal is capped.

        Source-level proof: `_apply_healing_effect`
        (`dnd_engine/systems/item_effects.py:118-125`) routes through
        `Character.recover_hp` whose cap returns the *actual* healing
        amount. A near-full target receives no carryover.
        """
        items = json.loads(ITEMS_JSON.read_text())
        potion = items["consumables"]["potion_of_healing"]
        target = _make_character(max_hp=20, current_hp=19)
        roller = DiceRoller(seed=42)
        result = apply_item_effect(potion, target, roller)
        # Only 1 HP can be regained; the potion rolls 2d4+2 (>= 4 always).
        assert result.amount == 1
        assert target.current_hp == 20
