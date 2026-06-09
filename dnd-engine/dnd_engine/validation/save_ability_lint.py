# ABOUTME: Advisory lint that compares declared saving-throw abilities in SRD
# ABOUTME: spell and monster JSON against the SRD Saving Throw Examples table.

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# Override field name: when an entry intentionally diverges from the SRD
# Saving Throw Examples table, content authors annotate the source JSON
# with this key (a non-empty string explaining why). The lint treats the
# divergence as justified and excludes the entry from its report.
OVERRIDE_KEY = "srd_save_override_reason"

# SRD § Playing the Game › Saving Throws › Saving Throw Examples
# Strength    -- Physically resist direct force
# Dexterity   -- Dodge out of harm's way
# Constitution-- Endure a toxic hazard
# Intelligence-- Recognize an illusion as fake
# Wisdom      -- Resist a mental assault
# Charisma    -- Assert your identity
_CATEGORY_TO_ABILITY = {
    "force": "strength",
    "dodge": "dexterity",
    "endurance": "constitution",
    "illusion": "intelligence",
    "mental": "wisdom",
    "identity": "charisma",
}

# Damage types that point at a specific ability via the SRD examples table.
#   * poison / necrotic / acid  -> endurance (CON)
#   * psychic                   -> mental (WIS)
#   * thunder                   -> endurance (CON, shockwave)
#   * fire / cold / lightning / radiant / force -> dodge (DEX)
#   * bludgeoning / piercing / slashing         -> dodge (DEX) -- or
#     force (STR) for a knock-prone style hit, which the keyword
#     heuristic below handles separately.
_DAMAGE_TYPE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "poison": ("endurance",),
    "necrotic": ("endurance",),
    "acid": ("endurance",),
    "psychic": ("mental",),
    "thunder": ("endurance", "dodge"),
    "fire": ("dodge",),
    "cold": ("dodge", "endurance"),
    "lightning": ("dodge",),
    "radiant": ("dodge",),
    "force": ("dodge", "force"),
    "bludgeoning": ("dodge", "force"),
    "piercing": ("dodge",),
    "slashing": ("dodge",),
}

# Magical schools that point at a specific ability category.
_SCHOOL_CATEGORIES: dict[str, tuple[str, ...]] = {
    "enchantment": ("mental",),
    "illusion": ("mental", "illusion"),
    "necromancy": ("endurance", "mental"),
    "abjuration": ("identity",),
}

# Condition / status keywords that are commonly imposed by save effects.
# These map to SRD examples-table categories. They are advisory: when
# any plausible category from any signal matches the declared save, the
# entry is considered consistent.
_KEYWORD_CATEGORIES: list[tuple[str, str]] = [
    ("charm", "mental"),
    ("frighten", "mental"),
    ("fear", "mental"),
    ("dominate", "mental"),
    ("possess", "identity"),
    ("banish", "identity"),
    ("illusion", "illusion"),
    ("disbelieve", "illusion"),
    ("poison", "endurance"),
    ("disease", "endurance"),
    ("paralyz", "endurance"),
    ("stun", "endurance"),
    ("petrif", "endurance"),
    ("knock prone", "force"),
    ("shoved", "force"),
    ("grapple", "force"),
    ("pushed", "force"),
]


@dataclass(frozen=True)
class SaveAbilityDivergence:
    """One advisory lint hit.

    `entry` is a stable identifier (spell key, or
    ``"<monster>.<action>"``). `declared` is the saving-throw ability
    found in JSON. `expected` is one ability the SRD examples table
    suggests for the inferred effect category. `reason` lists every
    signal the lint observed and the resulting plausible categories.
    """

    entry: str
    declared: str
    expected: str
    reason: str


def _normalize_ability(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    short = {
        "str": "strength",
        "dex": "dexterity",
        "con": "constitution",
        "int": "intelligence",
        "wis": "wisdom",
        "cha": "charisma",
    }
    return short.get(v, v)


def _classify_all(
    *,
    damage_type: str | None,
    school: str | None,
    tags: Iterable[str] | None,
    text_blobs: Iterable[str | None],
) -> tuple[set[str], list[str]]:
    """Return (plausible category set, signal-trace list).

    The lint flags a divergence only when the set is non-empty and the
    declared save is *outside* it -- i.e. every signal we picked up
    points elsewhere. Empty set means the lint stays silent.
    """
    categories: set[str] = set()
    trace: list[str] = []

    if school:
        s = school.strip().lower()
        if s in _SCHOOL_CATEGORIES:
            for c in _SCHOOL_CATEGORIES[s]:
                categories.add(c)
            trace.append(f"school '{s}' -> {_SCHOOL_CATEGORIES[s]}")

    if damage_type:
        dt = damage_type.lower()
        # Split compound damage like "bludgeoning and cold".
        tokens = [t.strip() for t in dt.replace(" and ", ",").replace("/", ",").split(",")]
        for token in tokens:
            if token in _DAMAGE_TYPE_CATEGORIES:
                for c in _DAMAGE_TYPE_CATEGORIES[token]:
                    categories.add(c)
                trace.append(f"damage '{token}' -> {_DAMAGE_TYPE_CATEGORIES[token]}")

    haystack_parts: list[str] = []
    for blob in text_blobs:
        if blob:
            haystack_parts.append(blob.lower())
    if tags:
        haystack_parts.extend(t.lower() for t in tags)
    haystack = " ".join(haystack_parts)

    for keyword, category in _KEYWORD_CATEGORIES:
        if keyword in haystack:
            categories.add(category)
            trace.append(f"keyword '{keyword}' -> {category}")

    return categories, trace


def _check_entry(
    *,
    entry_id: str,
    declared_ability: str | None,
    override_reason: str | None,
    damage_type: str | None,
    school: str | None,
    tags: Iterable[str] | None,
    text_blobs: Iterable[str | None],
) -> SaveAbilityDivergence | None:
    if override_reason:
        return None
    declared = _normalize_ability(declared_ability)
    if declared is None:
        return None
    categories, trace = _classify_all(
        damage_type=damage_type,
        school=school,
        tags=tags,
        text_blobs=text_blobs,
    )
    if not categories:
        return None
    plausible_abilities = {_CATEGORY_TO_ABILITY[c] for c in categories}
    if declared in plausible_abilities:
        return None
    # Pick the first stable category for the suggested ability.
    expected = sorted(plausible_abilities)[0]
    return SaveAbilityDivergence(
        entry=entry_id,
        declared=declared,
        expected=expected,
        reason="; ".join(trace),
    )


def lint_spells(spells: dict) -> list[SaveAbilityDivergence]:
    """Walk a spells.json-style mapping and return unjustified divergences."""
    out: list[SaveAbilityDivergence] = []
    for key, spell in spells.items():
        if not isinstance(spell, dict):
            continue
        save = spell.get("saving_throw")
        if not isinstance(save, dict):
            continue
        damage = spell.get("damage") or {}
        damage_type = damage.get("damage_type") if isinstance(damage, dict) else None
        hit = _check_entry(
            entry_id=key,
            declared_ability=save.get("ability"),
            override_reason=spell.get(OVERRIDE_KEY) or save.get(OVERRIDE_KEY),
            damage_type=damage_type,
            school=spell.get("school"),
            tags=spell.get("tags"),
            text_blobs=[spell.get("description")],
        )
        if hit is not None:
            out.append(hit)
    return out


def lint_monsters(monsters: dict) -> list[SaveAbilityDivergence]:
    """Walk a monsters.json-style mapping and return unjustified divergences.

    Saves on monsters live on individual actions (e.g. a Claws attack
    that imposes paralysis), so the entry id is ``"<monster>.<action>"``.
    """
    out: list[SaveAbilityDivergence] = []
    for mk, monster in monsters.items():
        if not isinstance(monster, dict):
            continue
        for action in monster.get("actions") or []:
            if not isinstance(action, dict):
                continue
            save = action.get("saving_throw")
            if not isinstance(save, dict):
                continue
            entry_id = f"{mk}.{action.get('name', '?')}"
            hit = _check_entry(
                entry_id=entry_id,
                declared_ability=save.get("ability"),
                override_reason=action.get(OVERRIDE_KEY) or save.get(OVERRIDE_KEY),
                damage_type=action.get("damage_type"),
                school=None,
                tags=None,
                text_blobs=[action.get("special"), action.get("name")],
            )
            if hit is not None:
                out.append(hit)
    return out


def _default_data_dir() -> Path:
    # dnd_engine/validation/save_ability_lint.py -> dnd_engine/data/srd/
    return Path(__file__).resolve().parent.parent / "data" / "srd"


def lint_srd_save_abilities(
    data_dir: Path | None = None,
) -> list[SaveAbilityDivergence]:
    """Load spells.json + monsters.json from `data_dir` and lint both.

    Defaults to the package's bundled SRD data. Returns the merged list
    of unjustified divergences; an empty list means the data is clean
    (or every divergence has an explicit `srd_save_override_reason`).
    """
    base = data_dir or _default_data_dir()
    spells_path = base / "spells.json"
    monsters_path = base / "monsters.json"
    spells = json.loads(spells_path.read_text())
    monsters = json.loads(monsters_path.read_text())
    return lint_spells(spells) + lint_monsters(monsters)
