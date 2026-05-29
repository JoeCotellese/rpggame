# ABOUTME: SRD conformance for the engine-side visibility model (plan-05 slice A).
# ABOUTME: Parametrized observer/target matrix → VisibilityRelation + obscurement.

"""SRD conformance: engine-side Vision, Stealth & Special Senses.

This is the executable form of plan-05's test matrix. Each row pairs an
observer (with a set of senses) against a target (with a state) under a
lighting / obscurement condition and asserts the resulting
``VisibilityRelation``. The relation is the engine's first-class answer
to "can this observer perceive this target, and how" — the rule that the
``client-2d`` rendering layer mimics today for display only.

SRD references:
- Playing the Game › Vision and Light › Obscured Areas (Lightly / Heavily).
- The rules glossary entries for Blindsight, Darkvision, Tremorsense, and
  Truesight.
"""

from __future__ import annotations

import pytest

from dnd_engine.core.creature import Abilities, Creature
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.perception import (
    LightLevel,
    Obscurement,
    Sense,
    VisibilityRelation,
    compute_visibility,
    effective_obscurement,
    observer_senses,
    parse_senses,
)

pytestmark = pytest.mark.srd(
    "playing-the-game/vision-and-light.md",
    lines="1537-1578",
)


def _creature(
    name: str = "C",
    *,
    senses: dict[Sense, int] | None = None,
    conditions: tuple[str, ...] = (),
) -> Creature:
    """Build a bare Creature with optional special senses and conditions."""
    abilities = Abilities(
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
    )
    creature = Creature(name=name, max_hp=10, ac=10, abilities=abilities)
    if senses:
        creature.senses = dict(senses)
    for condition in conditions:
        creature.add_condition(condition)
    return creature


# (label, observer senses, target conditions, light, obscurement, distance,
#  target_on_ground, expected relation)
_MATRIX = [
    (
        "sight/normal/bright/clear",
        {},
        (),
        LightLevel.BRIGHT,
        Obscurement.CLEAR,
        30.0,
        True,
        VisibilityRelation.SEEN,
    ),
    (
        "sight/normal/dim/clear",
        {},
        (),
        LightLevel.DIM,
        Obscurement.CLEAR,
        30.0,
        True,
        VisibilityRelation.SEEN,
    ),
    (
        "sight/normal/dark/clear",
        {},
        (),
        LightLevel.DARK,
        Obscurement.CLEAR,
        30.0,
        True,
        VisibilityRelation.UNSEEN,
    ),
    (
        "sight/normal/bright/lightly",
        {},
        (),
        LightLevel.BRIGHT,
        Obscurement.LIGHTLY,
        30.0,
        True,
        VisibilityRelation.SEEN,
    ),
    (
        "sight/normal/bright/heavily",
        {},
        (),
        LightLevel.BRIGHT,
        Obscurement.HEAVILY,
        30.0,
        True,
        VisibilityRelation.UNSEEN,
    ),
    (
        "darkvision60/normal/dark<=60/clear",
        {Sense.DARKVISION: 60},
        (),
        LightLevel.DARK,
        Obscurement.CLEAR,
        30.0,
        True,
        VisibilityRelation.SEEN,
    ),
    (
        "darkvision60/normal/dark>60/clear",
        {Sense.DARKVISION: 60},
        (),
        LightLevel.DARK,
        Obscurement.CLEAR,
        90.0,
        True,
        VisibilityRelation.UNSEEN,
    ),
    (
        "blindsight60/hidden/dark/clear",
        {Sense.BLINDSIGHT: 60},
        ("hidden",),
        LightLevel.DARK,
        Obscurement.CLEAR,
        30.0,
        True,
        VisibilityRelation.SEEN,
    ),
    (
        "tremorsense30/flying/dark/clear",
        {Sense.TREMORSENSE: 30},
        (),
        LightLevel.DARK,
        Obscurement.CLEAR,
        20.0,
        False,
        VisibilityRelation.UNSEEN,
    ),
    (
        "tremorsense30/grounded/dark/clear",
        {Sense.TREMORSENSE: 30},
        (),
        LightLevel.DARK,
        Obscurement.CLEAR,
        20.0,
        True,
        VisibilityRelation.UNSEEN_BUT_SENSED,
    ),
    (
        "truesight60/invisible/dark/clear",
        {Sense.TRUESIGHT: 60},
        ("invisible",),
        LightLevel.DARK,
        Obscurement.CLEAR,
        30.0,
        True,
        VisibilityRelation.SEEN,
    ),
    (
        "sight/invisible/bright/clear",
        {},
        ("invisible",),
        LightLevel.BRIGHT,
        Obscurement.CLEAR,
        30.0,
        True,
        VisibilityRelation.UNSEEN,
    ),
]


class TestVisibilityRelation:
    """plan-05 matrix: (observer, target, environment) → VisibilityRelation."""

    @pytest.mark.parametrize(
        "label,senses,conditions,light,obscurement,distance,on_ground,expected",
        _MATRIX,
        ids=[row[0] for row in _MATRIX],
    )
    def test_matrix(
        self,
        label,
        senses,
        conditions,
        light,
        obscurement,
        distance,
        on_ground,
        expected,
    ):
        observer = _creature("Observer", senses=senses)
        target = _creature("Target", conditions=conditions)
        relation = compute_visibility(
            observer,
            target,
            light_level=light,
            obscurement=obscurement,
            distance=distance,
            target_on_ground=on_ground,
        )
        assert relation == expected, label

    def test_total_cover_blocks_even_blindsight(self):
        """No line of sight (total cover) defeats sight and blindsight alike."""
        observer = _creature("Observer", senses={Sense.BLINDSIGHT: 60})
        target = _creature("Target")
        relation = compute_visibility(
            observer,
            target,
            light_level=LightLevel.BRIGHT,
            obscurement=Obscurement.CLEAR,
            distance=10.0,
            has_line_of_sight=False,
        )
        assert relation == VisibilityRelation.UNSEEN

    def test_blinded_observer_cannot_use_sight(self):
        """A Blinded observer fails all sight-based perception (SRD: Blinded)."""
        observer = _creature("Observer", conditions=("blinded",))
        target = _creature("Target")
        relation = compute_visibility(
            observer,
            target,
            light_level=LightLevel.BRIGHT,
            obscurement=Obscurement.CLEAR,
            distance=10.0,
        )
        assert relation == VisibilityRelation.UNSEEN


class TestObserverSenses:
    """`observer_senses` reconciles the senses dict with legacy attrs."""

    def test_legacy_darkvision_range_attr_is_merged(self):
        observer = _creature("Observer")
        observer.darkvision_range = 60
        senses = observer_senses(observer)
        assert senses.get(Sense.DARKVISION) == 60

    def test_senses_dict_keys_may_be_strings_or_enums(self):
        observer = _creature("Observer")
        observer.senses = {"blindsight": 30, Sense.TREMORSENSE: 15}
        senses = observer_senses(observer)
        assert senses.get(Sense.BLINDSIGHT) == 30
        assert senses.get(Sense.TREMORSENSE) == 15

    def test_wider_range_wins_when_attr_and_dict_disagree(self):
        observer = _creature("Observer", senses={Sense.DARKVISION: 30})
        observer.darkvision_range = 120
        senses = observer_senses(observer)
        assert senses.get(Sense.DARKVISION) == 120


class TestEffectiveObscurement:
    """SRD § Obscured Areas: Dim Light → Lightly, Darkness → Heavily."""

    @pytest.mark.parametrize(
        "light,ambient,expected",
        [
            (LightLevel.BRIGHT, Obscurement.CLEAR, Obscurement.CLEAR),
            (LightLevel.DIM, Obscurement.CLEAR, Obscurement.LIGHTLY),
            (LightLevel.DARK, Obscurement.CLEAR, Obscurement.HEAVILY),
            # Ambient obscurement never improves on the lighting-derived one.
            (LightLevel.BRIGHT, Obscurement.HEAVILY, Obscurement.HEAVILY),
            (LightLevel.DIM, Obscurement.HEAVILY, Obscurement.HEAVILY),
            (LightLevel.BRIGHT, Obscurement.LIGHTLY, Obscurement.LIGHTLY),
            (LightLevel.DIM, Obscurement.LIGHTLY, Obscurement.LIGHTLY),
        ],
    )
    def test_worst_of_light_and_ambient_wins(self, light, ambient, expected):
        assert effective_obscurement(light, ambient) == expected


class TestParseSenses:
    """`parse_senses` reads SRD stat-block `senses` strings."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("darkvision 60 ft., passive Perception 9", {Sense.DARKVISION: 60}),
            ("darkvision 120 ft., passive Perception 10", {Sense.DARKVISION: 120}),
            (
                "blindsight 60 ft. (blind beyond this radius), passive Perception 6",
                {Sense.BLINDSIGHT: 60},
            ),
            ("tremorsense 30 ft., passive Perception 11", {Sense.TREMORSENSE: 30}),
            ("truesight 120 ft., passive Perception 14", {Sense.TRUESIGHT: 120}),
            (
                "blindsight 10 ft., darkvision 60 ft., passive Perception 12",
                {Sense.BLINDSIGHT: 10, Sense.DARKVISION: 60},
            ),
            ("passive Perception 13", {}),
            ("", {}),
            (None, {}),
        ],
    )
    def test_parses_special_senses_and_ignores_passive_perception(self, text, expected):
        assert parse_senses(text) == expected


class TestMonsterCatalogSenses:
    """SRD § Special Senses are imported from monsters.json (#495).

    The monster catalog already carries a free-form `senses` stat-block
    string. `DataLoader.create_monster` now parses it into the canonical
    `Creature.senses` map so `compute_visibility` works for monsters.
    """

    def test_goblin_imports_darkvision_60(self):
        goblin = DataLoader().create_monster("goblin")
        assert goblin.senses.get(Sense.DARKVISION) == 60

    def test_animated_armor_imports_blindsight_60(self):
        armor = DataLoader().create_monster("animated_armor")
        assert armor.senses.get(Sense.BLINDSIGHT) == 60

    def test_bearded_devil_imports_darkvision_120(self):
        devil = DataLoader().create_monster("bearded_devil")
        assert devil.senses.get(Sense.DARKVISION) == 120

    def test_imported_senses_drive_visibility_in_the_dark(self):
        """A blindsight monster Sees a target in darkness within range."""
        armor = DataLoader().create_monster("animated_armor")
        target = _creature("Hero")
        relation = compute_visibility(
            armor,
            target,
            light_level=LightLevel.DARK,
            distance=30.0,
        )
        assert relation == VisibilityRelation.SEEN

    def test_sight_is_never_stored_as_a_special_sense(self):
        """Ordinary sight is implicit — it is never put in the senses map."""
        rat = DataLoader().create_monster("giant_rat")
        assert Sense.SIGHT not in rat.senses
