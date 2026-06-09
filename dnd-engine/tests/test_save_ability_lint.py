# ABOUTME: Unit tests for the advisory save-ability lint that compares declared
# ABOUTME: saving throws in spell/monster JSON against the SRD examples table.

from __future__ import annotations

from dnd_engine.validation.save_ability_lint import (
    OVERRIDE_KEY,
    SaveAbilityDivergence,
    lint_monsters,
    lint_spells,
    lint_srd_save_abilities,
)


def test_clean_dodge_spell_produces_no_divergence():
    """Fireball-shaped entry: DEX save, fire damage, evocation -> clean."""
    spells = {
        "fireball": {
            "saving_throw": {"ability": "dexterity"},
            "damage": {"damage_type": "fire"},
            "school": "evocation",
            "tags": ["damage", "aoe"],
            "description": "A bright streak flashes...",
        }
    }
    assert lint_spells(spells) == []


def test_poison_damage_with_strength_save_is_flagged():
    """Poison damage points at CON (endure); declared STR should flag."""
    spells = {
        "fake_poison_spell": {
            "saving_throw": {"ability": "strength"},
            "damage": {"damage_type": "poison"},
            "school": "necromancy",
            "description": "Toxic green mist.",
        }
    }
    divs = lint_spells(spells)
    assert len(divs) == 1
    assert divs[0].entry == "fake_poison_spell"
    assert divs[0].declared == "strength"
    assert divs[0].expected == "constitution"


def test_override_reason_suppresses_divergence():
    """An explicit `srd_save_override_reason` justifies a divergence."""
    spells = {
        "fake_poison_spell": {
            "saving_throw": {"ability": "strength"},
            "damage": {"damage_type": "poison"},
            "school": "necromancy",
            "description": "Toxic green mist.",
            OVERRIDE_KEY: ("GM ruling: target braces against gut-cramp via STR."),
        }
    }
    assert lint_spells(spells) == []


def test_override_on_saving_throw_block_also_suppresses():
    """Override may live on the saving_throw sub-object as well."""
    spells = {
        "fake_poison_spell": {
            "saving_throw": {
                "ability": "strength",
                OVERRIDE_KEY: "deliberate SRD divergence",
            },
            "damage": {"damage_type": "poison"},
            "school": "necromancy",
            "description": "Toxic green mist.",
        }
    }
    assert lint_spells(spells) == []


def test_short_ability_codes_are_normalized():
    """`dex` and `dexterity` are treated as the same declared save."""
    spells = {
        "x": {
            "saving_throw": {"ability": "dex"},
            "damage": {"damage_type": "fire"},
            "school": "evocation",
        }
    }
    assert lint_spells(spells) == []


def test_monster_action_save_is_flagged_by_paralysis_keyword():
    """A monster action that paralyzes points at CON; CHA save flags."""
    monsters = {
        "fake_thing": {
            "actions": [
                {
                    "name": "Touch",
                    "saving_throw": {"ability": "charisma"},
                    "damage_type": "slashing",
                    "special": "Target must save or be paralyzed.",
                }
            ]
        }
    }
    divs = lint_monsters(monsters)
    assert len(divs) == 1
    assert divs[0].entry == "fake_thing.Touch"
    assert divs[0].declared == "charisma"


def test_spell_with_no_save_is_ignored():
    """Spells without a `saving_throw` block are skipped silently."""
    spells = {"magic_missile": {"damage": {"damage_type": "force"}}}
    assert lint_spells(spells) == []


def test_weak_signal_does_not_produce_false_positive():
    """When no signal fires, the lint stays silent rather than guess."""
    spells = {
        "obscure_thing": {
            "saving_throw": {"ability": "wisdom"},
            "school": "transmutation",
            "description": "Something happens.",
        }
    }
    assert lint_spells(spells) == []


def test_srd_data_lint_is_clean():
    """Shipped SRD data ships clean (no unjustified divergences)."""
    divs = lint_srd_save_abilities()
    assert divs == [], "Unjustified save-ability divergences in shipped SRD data:\n" + "\n".join(
        f"  {d.entry}: declared={d.declared}, expected={d.expected} ({d.reason})" for d in divs
    )


def test_divergence_is_a_dataclass_with_expected_fields():
    """Public dataclass contract: entry/declared/expected/reason."""
    d = SaveAbilityDivergence(entry="x", declared="strength", expected="constitution", reason="r")
    assert d.entry == "x"
    assert d.declared == "strength"
    assert d.expected == "constitution"
    assert d.reason == "r"
