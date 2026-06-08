# ABOUTME: SRD conformance for monster Proficiency Bonus derived from CR.
# ABOUTME: Plan-08 slice 2 — pins the CR-to-PB table and Creature wiring.

"""SRD conformance: monster Proficiency Bonus from Challenge Rating.

The 2024 SRD pins a monster's Proficiency Bonus to its Challenge
Rating via a single table (CR up to 4 → +2, 5–8 → +3, … 29–30 → +9).
Slice 1 of plan-08 left ``Creature.make_saving_throw`` with a marker
comment deferring PB derivation to "slice 2"; this file is the
conformance pin for that slice.

Coverage:
- ``proficiency_bonus_from_cr`` — pure helper, every SRD row,
  fractional CR strings, numeric inputs, error on unknown CR.
- ``Creature.proficiency_bonus`` — derived property; defaults to 0
  when no CR was supplied (Characters / un-CR'd creatures).
- ``DataLoader.create_monster`` — threads the JSON ``cr`` field
  through to the constructed ``Creature``.
- ``monsters.json`` data parity — every published save/skill total
  is consistent with ``ability_mod + N·PB`` for N ∈ {1, 2}, the only
  two options the SRD permits (proficient or expertise).
"""

from __future__ import annotations

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.proficiency import proficiency_bonus_from_cr

pytestmark = pytest.mark.srd(
    "playing-the-game/proficiency.md",
)


# --- 1. Helper: CR → PB table ----------------------------------------------


@pytest.mark.parametrize(
    "cr, expected_pb",
    [
        # CR up to 4 → +2
        ("0", 2),
        ("1/8", 2),
        ("1/4", 2),
        ("1/2", 2),
        ("1", 2),
        ("2", 2),
        ("3", 2),
        ("4", 2),
        # CR 5–8 → +3
        ("5", 3),
        ("6", 3),
        ("8", 3),
        # CR 9–12 → +4
        ("9", 4),
        ("12", 4),
        # CR 13–16 → +5
        ("13", 5),
        ("16", 5),
        # CR 17–20 → +6
        ("17", 6),
        ("20", 6),
        # CR 21–24 → +7
        ("21", 7),
        ("24", 7),
        # CR 25–28 → +8
        ("25", 8),
        ("28", 8),
        # CR 29–30 → +9
        ("29", 9),
        ("30", 9),
    ],
)
def test_pb_from_cr_table(cr, expected_pb):
    assert proficiency_bonus_from_cr(cr) == expected_pb


@pytest.mark.parametrize(
    "cr, expected_pb",
    [
        (0, 2),
        (0.125, 2),
        (0.25, 2),
        (0.5, 2),
        (1, 2),
        (5, 3),
        (12, 4),
        (30, 9),
    ],
)
def test_pb_from_cr_accepts_numeric(cr, expected_pb):
    assert proficiency_bonus_from_cr(cr) == expected_pb


def test_pb_from_cr_raises_on_unknown():
    with pytest.raises(ValueError):
        proficiency_bonus_from_cr("31")
    with pytest.raises(ValueError):
        proficiency_bonus_from_cr("nonsense")


# --- 2. Creature.proficiency_bonus property --------------------------------


def _stub_abilities() -> Abilities:
    return Abilities(
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )


def test_creature_proficiency_bonus_uses_cr():
    creature = Creature(
        name="Test Bear",
        max_hp=10,
        ac=12,
        abilities=_stub_abilities(),
        cr="5",
    )
    assert creature.cr == "5"
    assert creature.proficiency_bonus == 3


def test_creature_without_cr_returns_zero():
    creature = Creature(
        name="Test Blob",
        max_hp=10,
        ac=10,
        abilities=_stub_abilities(),
    )
    assert creature.cr is None
    assert creature.proficiency_bonus == 0


def test_creature_fractional_cr_resolves_to_two():
    creature = Creature(
        name="Test Sprite",
        max_hp=2,
        ac=15,
        abilities=_stub_abilities(),
        cr="1/8",
    )
    assert creature.proficiency_bonus == 2


# --- 3. DataLoader wiring ---------------------------------------------------


def test_create_monster_threads_cr_from_json():
    loader = DataLoader()
    goblin = loader.create_monster("goblin")
    assert goblin.cr == "1/4"
    assert goblin.proficiency_bonus == 2


# --- 4. monsters.json data parity ------------------------------------------


_ABILITY_KEYS = ("str", "dex", "con", "int", "wis", "cha")


def _ability_mod(score: int) -> int:
    # SRD: floor((score - 10) / 2). Using math floor for negatives.
    return (score - 10) // 2 if score >= 10 else -((10 - score + 1) // 2)


def _skill_to_ability() -> dict[str, str]:
    return DataLoader().load_skills()


def test_monster_skill_save_totals_match_cr_derived_pb():
    """Each non-null save/skill total in monsters.json equals
    ``ability_mod + N·PB`` for N ∈ {1, 2} — the only two SRD-legal
    options (proficient or expertise). Any mismatch indicates a bad
    catalog entry, an incorrect CR, or an effect the data model does
    not yet capture; surface the full mismatch list so it can be
    triaged."""
    loader = DataLoader()
    monsters = loader.load_monsters()
    skills_catalog = loader.load_skills()

    mismatches: list[str] = []

    for monster_id, data in monsters.items():
        cr = data.get("cr")
        if cr is None:
            continue
        pb = proficiency_bonus_from_cr(cr)
        abilities = {k: data["abilities"][k] for k in _ABILITY_KEYS}
        ability_mods = {k: _ability_mod(v) for k, v in abilities.items()}

        # Saving throws: {"str": +3, ...} — keyed by ability short code.
        saves = data.get("saving_throws") or {}
        for ability_short, total in saves.items():
            mod = ability_mods[ability_short]
            if total not in (mod + pb, mod + 2 * pb):
                mismatches.append(
                    f"{monster_id} save {ability_short}={total} "
                    f"(ability_mod={mod}, PB={pb}; "
                    f"expected {mod + pb} or {mod + 2 * pb})"
                )

        # Skills: {"stealth": +6, ...} — keyed by skill name; resolve
        # ability via the SRD skills catalog (skills.json).
        skills = data.get("skills") or {}
        for skill_name, total in skills.items():
            skill_meta = skills_catalog.get(skill_name)
            if skill_meta is None:
                mismatches.append(
                    f"{monster_id} skill {skill_name}: not found in skills catalog"
                )
                continue
            ability_short = skill_meta["ability"]
            mod = ability_mods[ability_short]
            if total not in (mod + pb, mod + 2 * pb):
                mismatches.append(
                    f"{monster_id} skill {skill_name}={total} "
                    f"(ability {ability_short} mod={mod}, PB={pb}; "
                    f"expected {mod + pb} or {mod + 2 * pb})"
                )

    assert not mismatches, "monsters.json save/skill totals are not PB-consistent:\n" + "\n".join(
        mismatches
    )
