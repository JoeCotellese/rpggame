# ABOUTME: SRD conformance audit for "Playing the Game > Underwater Combat".
# ABOUTME: Cross-references docs/srd/playing-the-game/underwater-combat.md against engine code.

"""SRD conformance: Underwater Combat.

Maps every rule in `docs/srd/playing-the-game/underwater-combat.md` to
a test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

A common finding for this section: the engine has no concept of an
"underwater" environment. Rooms carry `lighting` but no `environment`
field; `Creature` exposes a single scalar `speed` with no Swim Speed
split (tracked by #432); weapon catalog data carries `damage_type` but
no caller filters on the Piercing carve-out for underwater melee. All
three SRD rules in this section share the same root architectural gap:
no environment flag, no swim-speed model.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from dnd_engine.core.combat import CombatEngine
from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.systems.item_effects import _apply_damage_effect

pytestmark = pytest.mark.srd(
    "playing-the-game/underwater-combat.md",
    lines="2153-2171",
)


ITEMS_JSON = (
    Path(__file__).resolve().parents[3]
    / "dnd_engine"
    / "data"
    / "srd"
    / "items.json"
)


def _make_creature(name: str = "Subject", hp: int = 50) -> Creature:
    """Plain creature with no special speeds, no resistances."""
    abilities = Abilities(
        strength=14,
        dexterity=14,
        constitution=12,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    return Creature(name=name, max_hp=hp, ac=14, abilities=abilities)


def _all_weapon_entries(items: dict) -> list[dict]:
    """Walk items.json and return every entry that carries a damage_type.

    `items.json` is keyed by category (weapons, armor, consumables, …);
    weapons live at varying nesting depths. Collect all entries that
    declare both `name` and `damage_type` so the tests can filter by
    Piercing vs other types.
    """
    found: list[dict] = []

    def walk(obj):
        if isinstance(obj, dict):
            if "damage_type" in obj and "name" in obj:
                found.append(obj)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for entry in obj:
                walk(entry)

    walk(items)
    return found


class TestUnderwaterCombat_Intro:
    """SRD § Playing the Game › Underwater Combat › Intro.

    > A fight underwater follows these rules.
    """

    def test_engine_has_an_underwater_environment_flag(self) -> None:
        pytest.skip(
            "GAP: there is no 'underwater' environment in the engine. "
            "`rg -i underwater dnd_engine/` returns zero hits, and "
            "room schemas under `dnd_engine/data/campaigns/` carry "
            "`lighting` but no `environment` field. Without an "
            "environment flag, none of the three Underwater Combat "
            "rules can fire. Tracked by issue #514 (root architectural "
            "seam shared with #516 and #518)."
        )


class TestUnderwaterCombat_ImpededMelee:
    """SRD § Playing the Game › Underwater Combat › Impeded Weapons (melee).

    > When making a melee attack roll with a weapon underwater, a
    > creature that lacks a Swim Speed has Disadvantage on the attack
    > roll unless the weapon deals Piercing damage.
    """

    def test_weapon_damage_type_data_exists_for_piercing_carveout(self) -> None:
        """Data-parity: `items.json` declares `damage_type: piercing`.

        The SRD's "unless the weapon deals Piercing damage" carve-out
        requires per-weapon damage-type data. The catalog already
        carries it: at least one weapon entry in `items.json` declares
        `damage_type: 'piercing'` (e.g., dagger, spear). This guards
        the data layer that an underwater-melee rule would consume.
        """
        items = json.loads(ITEMS_JSON.read_text())
        weapons = _all_weapon_entries(items)
        piercing = [w for w in weapons if w["damage_type"] == "piercing"]
        non_piercing = [
            w for w in weapons if w["damage_type"] in {"slashing", "bludgeoning"}
        ]
        assert piercing, (
            "Expected at least one weapon with damage_type='piercing' "
            "in items.json so the SRD's underwater piercing carve-out "
            "has a real data anchor."
        )
        assert non_piercing, (
            "Expected at least one weapon with damage_type in "
            "{slashing, bludgeoning} so the SRD's 'disadvantage unless "
            "piercing' rule has a contrastable counter-example."
        )

    def test_creature_lacks_a_swim_speed_attribute(self) -> None:
        """Source-level guard: `Creature` does not separate Swim Speed.

        The SRD melee-underwater rule keys on "a creature that lacks a
        Swim Speed." `Creature.__init__` exposes a single scalar
        `speed` (`dnd_engine/core/creature.py`) with no Swim Speed
        split, so the engine cannot answer "does this creature have a
        Swim Speed?" — making the carve-out unenforceable. This test
        pins the absence so that the moment a `swim_speed` field is
        added, the test will fail and prompt removing the related
        skips below.

        Closing this gap is issue #432 (Special speeds modeling).
        """
        creature = _make_creature()
        assert not hasattr(creature, "swim_speed"), (
            "Creature now has a `swim_speed` attribute — the special-"
            "speeds gap (#432) appears to be closing. Flip the related "
            "underwater-melee skips into real assertions."
        )

    def test_melee_underwater_imposes_disadvantage_without_swim_speed(self) -> None:
        pytest.skip(
            "GAP: `CombatEngine.resolve_attack` (`dnd_engine/core/"
            "combat.py:91-115`) does not derive `disadvantage` from "
            "environment + creature swim-speed + weapon damage type. "
            "It accepts a `disadvantage: bool = False` flag, but no "
            "caller computes the underwater-melee condition. The "
            "weapon data exists (`items.json` carries `damage_type`) "
            "and the engine surface accepts the flag — only the "
            "underwater-resolver helper is missing. Tracked by issue "
            "#514 (depends on #432 swim speed)."
        )

    def test_piercing_weapon_avoids_underwater_disadvantage(self) -> None:
        pytest.skip(
            "GAP: same as above — no underwater-melee resolver to "
            "implement the piercing carve-out. The weapon catalog "
            "already carries `damage_type: 'piercing'` for daggers, "
            "spears, etc. (validated by "
            "`test_weapon_damage_type_data_exists_for_piercing_"
            "carveout` above), so the data is ready. Tracked by "
            "issue #514."
        )

    def test_creature_with_swim_speed_avoids_underwater_disadvantage(self) -> None:
        pytest.skip(
            "GAP: same as above — `Creature` has no Swim Speed "
            "concept (`dnd_engine/core/creature.py`). Monster catalog "
            "`speed` is a single int. Aquatic monsters (e.g., sahuagin "
            "in the SRD bestiary) cannot declare a separate Swim "
            "Speed today. Tracked by issues #432 (swim speed model) "
            "and #514 (underwater carve-out)."
        )

    def test_resolve_attack_accepts_a_disadvantage_flag(self) -> None:
        """Engine surface honors `disadvantage=True` on resolve_attack().

        The plumbing for the underwater-melee rule's *effect* is in
        place: `CombatEngine.resolve_attack` reads the `disadvantage`
        flag and produces a disadvantaged roll. Only the upstream
        caller that *sets* the flag based on underwater context is
        missing. This test guards the seam so when the underwater
        helper lands it can rely on the existing flag.
        """
        engine = CombatEngine(DiceRoller(seed=7))
        attacker = _make_creature("Attacker")
        defender = _make_creature("Defender")

        result = engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=4,
            damage_dice="1d6+2",
            disadvantage=True,
        )

        assert result.disadvantage is True
        assert 1 <= result.attack_roll <= 20


class TestUnderwaterCombat_ImpededRanged:
    """SRD § Playing the Game › Underwater Combat › Impeded Weapons (ranged).

    > A ranged attack roll with a weapon underwater automatically
    > misses a target beyond the weapon's normal range, and the attack
    > roll has Disadvantage against a target within normal range.
    """

    def test_ranged_underwater_auto_miss_beyond_normal_range(self) -> None:
        pytest.skip(
            "GAP: the 'auto-miss beyond normal range underwater' "
            "override does not exist. Normal vs long range is "
            "computed at the client layer — `client-2d/src/client_2d/"
            "session.py:993` and `dnd_engine/scenarios/script_executor."
            "py:270` both set `in_long_range = distance > normal_"
            "range` and merely impose disadvantage. Neither short-"
            "circuits to a miss the way underwater requires. "
            "`CombatEngine.resolve_attack` has no auto-miss code path "
            "at all — even the `disadvantage` flag just re-rolls, it "
            "doesn't force a missed `AttackResult`. Tracked by issue "
            "#516 (depends on #514 environment seam)."
        )

    def test_ranged_underwater_imposes_disadvantage_within_normal_range(self) -> None:
        pytest.skip(
            "GAP: no underwater context is consulted when deriving "
            "ranged disadvantage. The existing close-combat helper "
            "`is_close_combat_ranged_disadvantage` (`dnd_engine/"
            "systems/ranged_attacks.py:22`) imposes disadvantage for "
            "adjacent threatening enemies but is silent on underwater. "
            "There is no `is_underwater_ranged_disadvantage` parallel. "
            "Tracked by issue #516."
        )

    def test_normal_range_is_known_per_weapon(self) -> None:
        """Source-level guard: weapon data exposes a range string.

        The underwater ranged rule keys on "normal range." The
        existing range-parsing path lives in
        `dnd_engine/scenarios/script_executor._parse_weapon_range`,
        which extracts `(normal_range, max_range)` from a weapon's
        `range` data field. This is the seam an underwater ranged
        resolver would consume. Pin the helper's existence so the
        underwater-rule citation stays accurate.
        """
        from dnd_engine.scenarios import script_executor

        assert callable(getattr(script_executor, "_parse_weapon_range", None)), (
            "Weapon-range parsing helper must remain available so the "
            "underwater ranged rule has a normal-range source to "
            "consume."
        )
        src = inspect.getsource(script_executor._parse_weapon_range)
        assert "normal" in src.lower() or "range" in src.lower(), (
            "`_parse_weapon_range` must surface a normal-range value "
            "for the SRD's 'beyond the weapon's normal range' clause "
            "to have something to read."
        )

    def test_engine_has_no_auto_miss_path_in_resolve_attack(self) -> None:
        """Source-level guard: `resolve_attack` cannot short-circuit a miss.

        The SRD's auto-miss override needs the engine to be able to
        return a missed `AttackResult` *without rolling*. The current
        `CombatEngine.resolve_attack` signature accepts `advantage` /
        `disadvantage` flags but no `auto_miss` parameter. This guard
        pins the absence so the moment an `auto_miss` path is added,
        the related skips above can be turned into real assertions.
        """
        sig = inspect.signature(CombatEngine.resolve_attack)
        assert "auto_miss" not in sig.parameters, (
            "`CombatEngine.resolve_attack` now accepts `auto_miss` — "
            "the underwater-ranged gap (#516) is closing. Flip the "
            "skips above to real assertions."
        )


class TestUnderwaterCombat_FireResistance:
    """SRD § Playing the Game › Underwater Combat › Fire Resistance.

    > Anything underwater has Resistance to Fire damage (explained in
    > "Damage and Healing").
    """

    def test_resistance_pipeline_halves_fire_damage_with_resistance_condition(self) -> None:
        """The Resistance *mechanism* exists — fire is halved if flagged.

        `systems/item_effects._apply_damage_effect` halves fire damage
        when the target carries the `has_resistance_fire` condition.
        This is the mechanism an underwater-fire-resistance rule would
        consume — only the *automatic application* of the condition
        in an underwater environment is missing.
        """
        target = _make_creature(hp=50)
        target.add_condition("has_resistance_fire")

        result = _apply_damage_effect(
            item_info={
                "name": "Alchemist's Fire",
                "damage": "0d4+10",  # fixed 10 fire damage
                "damage_type": "fire",
            },
            target=target,
            dice_roller=DiceRoller(seed=1),
            event_bus=None,
        )
        assert result.amount == 5, (
            "SRD: Resistance halves damage of that type (floor). "
            "10 fire → 5 with the condition active."
        )

    def test_underwater_creature_automatically_gains_fire_resistance(self) -> None:
        """Environment-granted Fire Resistance via the chokepoint (#518).

        The chokepoint `CombatEngine._apply_damage_modifiers` takes an
        optional `environment` argument. When that argument is
        "underwater" and the damage type is fire, the Resistance stage
        halves the damage — without the target carrying any
        `has_resistance_fire` condition or catalog entry.
        """
        target = _make_creature(hp=50)
        engine = CombatEngine(DiceRoller(seed=1))

        # No condition, no catalog entry — only the environment.
        assert not target.has_condition("has_resistance_fire")
        assert not getattr(target, "damage_resistances", None)

        result = engine._apply_damage_modifiers(
            target, raw_damage=10, damage_type="fire", environment="underwater"
        )
        assert result == 5, (
            "SRD: Anything underwater has Resistance to Fire damage — "
            "10 fire damage should halve to 5 from the environment "
            "alone."
        )

    def test_fire_resistance_in_attack_pipeline_underwater(self) -> None:
        """End-to-end: a fire weapon attack in an underwater room halves.

        Driving `CombatEngine.resolve_attack` with a stub `game_state`
        whose `creature_environment` returns "underwater" exercises the
        full integration path: the chokepoint is consulted, environment
        is sourced via the game_state seam, and the damage applied to
        the defender is halved.
        """
        engine = CombatEngine(DiceRoller(seed=7))
        attacker = _make_creature("Attacker")
        defender = _make_creature("Defender", hp=50)

        class _StubGameState:
            """Minimal game_state stub for the chokepoint env seam."""

            def get_effective_ac(self, creature):
                return creature._base_ac

            def creature_environment(self, creature):
                return "underwater"

        # Fixed 10 fire damage ("0d4+10") removes the dice-roll
        # noise; we care that 10 underwater fire halves to 5.
        starting_hp = defender.current_hp
        engine.resolve_attack(
            attacker=attacker,
            defender=defender,
            attack_bonus=100,  # guarantee a hit
            damage_dice="0d4+10",
            apply_damage=True,
            damage_type="fire",
            game_state=_StubGameState(),
        )
        # Underwater env grants Fire Resistance → 10 halves to 5.
        assert starting_hp - defender.current_hp == 5, (
            "SRD: Fire damage against a creature in an underwater room "
            "must route through Resistance halving via the chokepoint."
        )


class TestUnderwaterCombat_EngineSurface_NoEnvironmentalContext:
    """Cross-cut: combat does not consult environmental context.

    All three Underwater Combat rules share a root: `CombatEngine` and
    its callers have no notion of where the combat is taking place. A
    single source-level guard pins that absence so future audits can
    cite this anchor.
    """

    def test_resolve_attack_signature_takes_no_environment_or_room(self) -> None:
        """`CombatEngine.resolve_attack` has no environment parameter.

        SRD rules that key on environment (Underwater Combat, future
        Mounted Combat, future Aerial Combat) all need an `environment`
        or `room` parameter that doesn't exist today.
        """
        sig = inspect.signature(CombatEngine.resolve_attack)
        for forbidden in ("environment", "room", "terrain", "underwater"):
            assert forbidden not in sig.parameters, (
                f"`resolve_attack` now takes `{forbidden}` — the "
                "environment seam appears to be opening up. Flip the "
                "underwater skips into real assertions."
            )

    def test_apply_damage_effect_honors_underwater_fire_resistance(self) -> None:
        """Item-driven fire damage is halved in an underwater environment (#595).

        The item damage path (alchemist's fire and other thrown damage
        items) now accepts an `environment` argument and routes the
        rolled damage through the canonical pipeline. When the
        environment is "underwater" and the damage is fire, the SRD's
        "anything underwater has Resistance to Fire damage" carve-out
        halves the damage — with no `has_resistance_fire` condition on
        the target.
        """
        target = _make_creature(hp=50)
        assert not target.has_condition("has_resistance_fire")

        result = _apply_damage_effect(
            item_info={
                "name": "Alchemist's Fire",
                "damage": "0d4+10",  # fixed 10 fire damage
                "damage_type": "fire",
            },
            target=target,
            dice_roller=DiceRoller(seed=1),
            event_bus=None,
            environment="underwater",
        )
        assert result.amount == 5, (
            "SRD: Anything underwater has Resistance to Fire damage — "
            "10 fire from a thrown item should halve to 5 from the "
            "environment alone."
        )
