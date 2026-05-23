# ABOUTME: SRD conformance audit for "Playing the Game > Damage Types".
# ABOUTME: Cross-references docs/srd/playing-the-game/damage-types.md against engine code.

"""SRD conformance: Damage Types.

Maps every rule in `docs/srd/playing-the-game/damage-types.md` to a
test. Real tests verify enforcement at the engine layer; stubs
(`pytest.skip("GAP: ...")`) mark known gaps and cite where the rule is
enforced today (if elsewhere) or that it isn't implemented anywhere.

The conformance "report" is `pytest --collect-only -q tests/srd/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.srd(
    "playing-the-game/damage-types.md",
    lines="2247-2255",
)


SRD_DATA_DIR = Path(__file__).resolve().parents[3] / "dnd_engine" / "data" / "srd"
MONSTERS_JSON = SRD_DATA_DIR / "monsters.json"
SPELLS_JSON = SRD_DATA_DIR / "spells.json"
ITEMS_JSON = SRD_DATA_DIR / "items.json"


# The thirteen SRD damage types (SRD_CC_v5.2.1 Rules Glossary).
SRD_DAMAGE_TYPES: frozenset[str] = frozenset(
    {
        "acid",
        "bludgeoning",
        "cold",
        "fire",
        "force",
        "lightning",
        "necrotic",
        "piercing",
        "poison",
        "psychic",
        "radiant",
        "slashing",
        "thunder",
    }
)


class TestDamageTypes_EveryInstanceHasAType:
    """SRD § Playing the Game › Damage Types › Definition.

    > Each instance of damage has a type, like Fire or Slashing.
    """

    def test_every_damage_carrying_spell_declares_a_damage_type(self):
        """Each spell with a `damage` block names its `damage_type`.

        The SRD makes damage-type tagging mandatory at the rule layer.
        Spells are the cleanest data-parity check — every damage-dealing
        spell in `spells.json` must declare `damage.damage_type` so
        downstream Resistance / Vulnerability / Immunity logic has a
        type to key on.
        """
        spells: dict = json.loads(SPELLS_JSON.read_text())
        missing: list[str] = []
        for spell_id, spell in spells.items():
            damage = spell.get("damage")
            if not damage:
                continue
            if not damage.get("damage_type"):
                missing.append(spell_id)
        assert not missing, (
            f"Spells with a `damage` block but no `damage_type` "
            f"(SRD requires each damage instance to have a type): {missing}"
        )

    def test_every_weapon_with_damage_declares_a_damage_type(self):
        """Each item with damage dice carries a `damage_type`.

        Mirrors the spell check for weapons / damage-dealing items.
        Without a tagged type, Resistance / Vulnerability / Immunity
        cannot key on weapon attacks once they're wired up.
        """
        items: dict = json.loads(ITEMS_JSON.read_text())
        missing: list[str] = []
        for item_id, item in items.items():
            if not isinstance(item, dict):
                continue
            if item.get("damage") and not item.get("damage_type"):
                missing.append(item_id)
        assert not missing, (
            f"Items with `damage` dice but no `damage_type` "
            f"(SRD requires each damage instance to have a type): {missing}"
        )

    def test_monster_attack_actions_declare_a_damage_type(self):
        """Each monster attack action's damage entry names a type.

        Monsters express their attacks under `actions[*].damage`. Every
        attack that rolls damage must declare `damage_type` for the
        same downstream reasons. The audit also walks `reactions` and
        `legendary_actions` because those entries follow the same
        action shape and can carry damage rolls.
        """
        monsters: dict = json.loads(MONSTERS_JSON.read_text())
        missing: list[tuple[str, str, str]] = []
        for mid, mdata in monsters.items():
            for bucket in ("actions", "reactions", "legendary_actions"):
                for action in mdata.get(bucket) or []:
                    if not isinstance(action, dict):
                        continue
                    if action.get("damage") and not action.get("damage_type"):
                        missing.append((mid, bucket, action.get("name", "<unnamed>")))
        assert not missing, (
            f"Monster actions with `damage` dice but no `damage_type` "
            f"(SRD requires each damage instance to have a type): {missing}"
        )


class TestDamageTypes_EnumerationMatchesSRDGlossary:
    """SRD § Playing the Game › Damage Types › Glossary cross-reference.

    > Damage types are listed in "Rules Glossary" and have no rules of
    > their own, but other rules, such as Resistance, rely on damage
    > types.

    The Rules Glossary enumerates the canonical thirteen types: Acid,
    Bludgeoning, Cold, Fire, Force, Lightning, Necrotic, Piercing,
    Poison, Psychic, Radiant, Slashing, Thunder. Engine content must
    not drift from that vocabulary.
    """

    def test_spell_damage_types_are_drawn_from_the_srd_set(self):
        """Spells only declare SRD-listed damage types.

        Compound damage strings (e.g. `"bludgeoning and cold"`) are
        split on common separators so each component must still be a
        valid SRD type.
        """
        spells: dict = json.loads(SPELLS_JSON.read_text())
        offenders: list[tuple[str, str]] = []
        for spell_id, spell in spells.items():
            damage = spell.get("damage") or {}
            raw = damage.get("damage_type")
            if not raw:
                continue
            components = (
                raw.replace(" and ", ",").replace("/", ",").replace(" or ", ",").split(",")
            )
            for piece in components:
                token = piece.strip().lower()
                if not token:
                    continue
                if token not in SRD_DAMAGE_TYPES:
                    offenders.append((spell_id, token))
        assert not offenders, (
            f"Spell damage types outside the SRD glossary: {offenders}. "
            f"SRD set: {sorted(SRD_DAMAGE_TYPES)}."
        )

    def test_item_damage_types_are_drawn_from_the_srd_set(self):
        """Items only declare SRD-listed damage types.

        Recursive descent because some items nest damage info (e.g. a
        `damage` block on a thrown subentry).
        """
        items: dict = json.loads(ITEMS_JSON.read_text())

        def _collect_damage_types(node: object, sink: list[str]) -> None:
            if isinstance(node, dict):
                if "damage_type" in node and isinstance(node["damage_type"], str):
                    sink.append(node["damage_type"])
                for value in node.values():
                    _collect_damage_types(value, sink)
            elif isinstance(node, list):
                for entry in node:
                    _collect_damage_types(entry, sink)

        raw_types: list[str] = []
        _collect_damage_types(items, raw_types)
        offenders = sorted(
            {t.strip().lower() for t in raw_types if t.strip().lower() not in SRD_DAMAGE_TYPES}
        )
        assert not offenders, (
            f"Item damage types outside the SRD glossary: {offenders}. "
            f"SRD set: {sorted(SRD_DAMAGE_TYPES)}."
        )

    def test_monster_action_damage_types_are_drawn_from_the_srd_set(self):
        """Monster action damage_type values are SRD-listed types.

        Schema-lint guard against future drift: any monster action
        that carries a `damage_type` must name a single SRD glossary
        type. Compound strings (e.g. "fire/cold") are split on common
        separators so each component is validated independently, in
        line with the spell-level audit above.
        """
        monsters: dict = json.loads(MONSTERS_JSON.read_text())
        offenders: list[tuple[str, str, str, str]] = []
        for mid, mdata in monsters.items():
            for bucket in ("actions", "reactions", "legendary_actions"):
                for action in mdata.get(bucket) or []:
                    if not isinstance(action, dict):
                        continue
                    raw = action.get("damage_type")
                    if not raw:
                        continue
                    components = (
                        raw.replace(" and ", ",").replace("/", ",").replace(" or ", ",").split(",")
                    )
                    for piece in components:
                        token = piece.strip().lower()
                        if not token:
                            continue
                        if token not in SRD_DAMAGE_TYPES:
                            offenders.append(
                                (mid, bucket, action.get("name", "<unnamed>"), token)
                            )
        assert not offenders, (
            f"Monster action damage_type values outside the SRD glossary: "
            f"{offenders}. SRD set: {sorted(SRD_DAMAGE_TYPES)}."
        )

    def test_monster_damage_modifier_types_are_drawn_from_the_srd_set(self):
        """Monster damage_immunities / _resistances / _vulnerabilities
        cite only SRD-listed damage types.

        Compound entries like "bludgeoning, piercing, and slashing
        from nonmagical attacks that aren't silvered" are skipped
        because they describe conditional resistance and exceed plain
        type enumeration. Pure single-type entries (e.g. "fire",
        "poison") must be SRD-valid.
        """
        monsters: dict = json.loads(MONSTERS_JSON.read_text())
        offenders: list[tuple[str, str, str]] = []
        for mid, mdata in monsters.items():
            for field in (
                "damage_immunities",
                "damage_resistances",
                "damage_vulnerabilities",
            ):
                entries = mdata.get(field) or []
                for entry in entries:
                    token = entry.strip().lower()
                    # Skip compound clauses; only audit single-word types.
                    if " " in token or "," in token:
                        continue
                    if token not in SRD_DAMAGE_TYPES:
                        offenders.append((mid, field, token))
        assert not offenders, (
            f"Monster damage-modifier entries outside the SRD glossary: "
            f"{offenders}. SRD set: {sorted(SRD_DAMAGE_TYPES)}."
        )


class TestDamageTypes_NoIntrinsicRules:
    """SRD § Playing the Game › Damage Types › Behavior.

    > [Damage types] have no rules of their own, but other rules, such
    > as Resistance, rely on damage types.

    Damage types are purely tags; the engine must not branch on the
    type itself (e.g. "fire damage triggers X" hard-coded). All
    behavioral consequences belong in Resistance, Vulnerability,
    Immunity, or named features that explicitly cite a type.
    """

    def test_combat_engine_does_not_branch_on_damage_type(self):
        """`CombatEngine.resolve_attack` does not branch on damage_type.

        The SRD's "no rules of their own" clause means the damage-type
        tag is metadata for downstream systems (Resistance,
        Vulnerability, Immunity) and must not gate hit / damage
        calculation at the combat engine layer.

        `resolve_attack` now accepts a `damage_type` keyword (#461) so
        the per-type modifier chokepoint can scale damage, but the
        method itself must not conditionally branch on the *value* of
        damage_type (e.g., no `if damage_type == "fire": ...` inside
        the attack path). All type-keyed behaviour belongs in
        `_apply_damage_modifiers`.
        """
        import inspect
        import re

        from dnd_engine.core.combat import CombatEngine

        src = inspect.getsource(CombatEngine.resolve_attack)
        # The chokepoint is allowed to consume `damage_type`, but
        # resolve_attack itself must not test the value with an
        # equality / membership comparison against a literal type
        # name. This regex catches `damage_type == "fire"`,
        # `damage_type in ("fire",)`, etc.
        offenders = re.findall(
            r"damage_type\s*(?:==|in|!=)\s*[\"'(\[]", src
        )
        assert not offenders, (
            "CombatEngine.resolve_attack must not branch on the value "
            "of damage_type; type-specific behavior belongs in "
            "Resistance / Vulnerability / Immunity layers, not the "
            "attack path. Found: "
            f"{offenders}"
        )

    def test_resistance_system_keys_on_damage_type(self):
        """Resistance pipeline accepts a `damage_type` to key on.

        Confirms the "but other rules ... rely on damage types" half
        of the SRD sentence: the resistance code path consumes the
        type field to decide whether to halve.
        `systems/item_effects.py:_apply_damage_effect` is the lone
        production damage path that reads `damage_type` and consults a
        per-type resistance condition.
        """
        import inspect

        from dnd_engine.systems import item_effects

        src = inspect.getsource(item_effects._apply_damage_effect)
        assert 'item_info.get("damage_type"' in src, (
            "_apply_damage_effect must read damage_type from the item "
            "payload so resistance can key on it."
        )
        assert "has_resistance_" in src, (
            "_apply_damage_effect must build a per-type resistance "
            "condition string (e.g. has_resistance_fire) so type-keyed "
            "resistance can apply."
        )
