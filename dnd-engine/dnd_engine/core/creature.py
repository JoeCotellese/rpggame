# ABOUTME: Base Creature class representing any living entity in the game
# ABOUTME: Handles HP, abilities, conditions, damage, and healing

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from dnd_engine.core.position import Position
from dnd_engine.systems.d20 import d20_test


class Size(str, Enum):
    """
    SRD creature size categories (SRD § Creature Statistics › Size).

    The canonical string value matches the lowercase form used in
    `monsters.json` so values round-trip cleanly through JSON. Size
    drives map footprint and reach geometry in plan-03; this enum is
    the data-model foundation those systems read.
    """

    TINY = "tiny"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    HUGE = "huge"
    GARGANTUAN = "gargantuan"

    @property
    def footprint(self) -> int:
        """
        Width, in 5-ft tiles, of the square space this size occupies.

        Per the SRD Creature Size and Space table, Tiny/Small/Medium each
        fit within a single tile, Large fills a 2x2 block, Huge a 3x3, and
        Gargantuan a 4x4. The returned value is the side length of that
        square; the full set of tiles a creature claims is that length
        squared (see `SpatialIndex.footprint_tiles`).
        """
        return {
            Size.TINY: 1,
            Size.SMALL: 1,
            Size.MEDIUM: 1,
            Size.LARGE: 2,
            Size.HUGE: 3,
            Size.GARGANTUAN: 4,
        }[self]


class MovementMode(str, Enum):
    """
    SRD movement modes (SRD § Playing the Game › Movement › Movement Modes).

    The canonical string value matches the lowercase form that monsters.json
    is expected to use for any future per-mode `speeds` dict, so values
    round-trip cleanly through JSON. Drives per-mode movement-cost logic
    later in plan-03; this enum is the data-model foundation those systems
    read alongside `Creature.speeds`.
    """

    WALK = "walk"
    CLIMB = "climb"
    SWIM = "swim"
    CRAWL = "crawl"
    JUMP = "jump"
    FLY = "fly"
    BURROW = "burrow"


@dataclass
class Abilities:
    """
    D&D 5E ability scores (STR, DEX, CON, INT, WIS, CHA).

    Ability scores typically range from 1-20 for player characters and monsters.
    Each score provides a modifier calculated as: (score - 10) // 2
    """

    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    @property
    def str_mod(self) -> int:
        """Calculate Strength modifier"""
        return (self.strength - 10) // 2

    @property
    def dex_mod(self) -> int:
        """Calculate Dexterity modifier"""
        return (self.dexterity - 10) // 2

    @property
    def con_mod(self) -> int:
        """Calculate Constitution modifier"""
        return (self.constitution - 10) // 2

    @property
    def int_mod(self) -> int:
        """Calculate Intelligence modifier"""
        return (self.intelligence - 10) // 2

    @property
    def wis_mod(self) -> int:
        """Calculate Wisdom modifier"""
        return (self.wisdom - 10) // 2

    @property
    def cha_mod(self) -> int:
        """Calculate Charisma modifier"""
        return (self.charisma - 10) // 2


class Creature:
    """
    Base class for all living entities (PCs, NPCs, monsters).

    Handles core D&D 5E mechanics: HP, AC, abilities, conditions, damage, and healing.
    """

    def __init__(
        self,
        name: str,
        max_hp: int,
        ac: int,
        abilities: Abilities,
        current_hp: int | None = None,
        speed: int = 30,
        size: Size = Size.MEDIUM,
        speeds: dict[MovementMode, int] | None = None,
        position: Position | None = None,
        cr: str | int | float | None = None,
    ):
        """
        Initialize a creature.

        Args:
            name: Creature's name
            max_hp: Maximum hit points
            ac: Armor class (target number for attacks)
            abilities: Ability scores (STR, DEX, CON, INT, WIS, CHA)
            current_hp: Starting HP (defaults to max_hp if not specified)
            cr: SRD Challenge Rating (monsters only). Drives
                :attr:`proficiency_bonus` via the SRD CR-to-PB table.
                Defaults to ``None`` for Characters and any creature
                constructed without a CR; ``proficiency_bonus`` then
                returns 0 and PC-side derivations remain authoritative.
            speed: Movement speed in feet per round (default 30 ft). The
                legacy single-int `speed` kwarg is preserved so existing
                callers and monsters.json (which carries a plain int)
                keep working. When `speeds` is omitted, it is derived as
                `{MovementMode.WALK: speed}` so per-mode consumers can
                always read `creature.speeds[MovementMode.WALK]`.
            size: SRD size category (default Medium). Drives map footprint
                and reach geometry in plan-03; defaulting to Medium keeps
                Characters and any creature constructed without an explicit
                size on the SRD baseline.
            speeds: Optional per-mode speed map (Walk/Climb/Swim/etc.).
                When provided, `self.speeds` is set to the supplied dict
                verbatim — no WALK auto-injection. The legacy `self.speed`
                attribute mirrors `speeds[MovementMode.WALK]` if present,
                otherwise falls back to the `speed` kwarg (this matters
                for fly-only creatures whose walk speed is 0).
            position: Optional grid position (x, y). Defaults to None for
                creatures not yet placed on a map.
        """
        self.name = name
        self.max_hp = max_hp
        self.current_hp = current_hp if current_hp is not None else max_hp
        # SRD § Playing the Game › Temporary Hit Points: a buffer pool,
        # separate from Hit Points, that absorbs damage before HP is
        # touched. Not Hit Points — healing cannot restore it and a
        # grant is not a heal. Defaults to 0 (no buffer).
        self.temporary_hit_points: int = 0
        self._base_ac = ac  # Store base AC (before modifiers from spells/effects)
        self.abilities = abilities
        self.size = size
        # Per-mode speeds (plan-03). When `speeds` is omitted, derive a
        # single-entry {WALK: speed} dict so downstream cost-multiplier
        # code (slices 3-4) can always index by MovementMode. When
        # `speeds` is provided, honor it as-is — a fly-only creature can
        # legitimately ship {FLY: 60} with no WALK entry.
        if speeds is None:
            self.speeds: dict[MovementMode, int] = {MovementMode.WALK: speed}
            self.speed = speed  # Movement speed in feet (5 ft = 1 grid square)
        else:
            self.speeds = speeds
            # Legacy `self.speed` mirrors WALK from the speeds dict when
            # present so existing callers reading `creature.speed` keep
            # working; otherwise fall back to the supplied `speed` kwarg.
            self.speed = speeds.get(MovementMode.WALK, speed)
        self.position = position
        # Condition tracking with metadata for duration and repeat saves
        # Maps condition name -> metadata dict
        self.active_conditions: dict[str, dict] = {}

        # SRD § Vision and Light › Special Senses: a map of special
        # senses to their range in feet (e.g. {Sense.BLINDSIGHT: 60}).
        # Ordinary sight is implicit and not stored here. Consumed by
        # `dnd_engine.systems.perception` to compute visibility; defaults
        # to empty (sight only). Keys may be `Sense` members or their
        # string values — `perception.observer_senses` normalizes them.
        self.senses: dict = {}

        # Alternate base-AC formulas (SRD § Playing the Game › Attack Rolls
        # › Armor Class › "Only One Base AC"). A creature may register
        # multiple ways to calculate its base AC (Mage Armor, Barbarian /
        # Monk Unarmored Defense, Draconic Resilience, etc.) but only the
        # one named in `active_base_ac_formula` is honored when computing
        # base AC. `None` means "use `_base_ac`" — the default unarmored
        # or armor-derived value supplied at construction time.
        self._alt_base_ac_formulas: dict[str, Callable[[Creature], int]] = {}
        self.active_base_ac_formula: str | None = None

        # SRD § Actions › Dodge: while True, attack rolls against this
        # creature have Disadvantage and their DEX saves have Advantage,
        # unless they are Incapacitated or their Speed is 0. Set by the
        # ``dodge`` action handler; cleared by ``InitiativeTracker.next_turn``
        # at the start of the dodger's own next turn.
        self.is_dodging: bool = False

        # SRD § Actions › Help: when non-None, names the helper whose
        # Help action grants this creature advantage on its next attack
        # roll or ability check. Cleared on first consumption (one-shot)
        # or by ``InitiativeTracker.next_turn`` at the start of the
        # helper's own next turn.
        self.pending_help_from: Creature | None = None

        # SRD § Playing the Game › Proficiency Bonus: a monster's PB is
        # derived from its Challenge Rating via the SRD table (see
        # ``dnd_engine.systems.proficiency``). Stored verbatim from the
        # catalog so downstream consumers (XP awards, encounter
        # balancing) can read the published CR without round-tripping
        # through the PB band.
        self.cr: str | int | float | None = cr

    @property
    def proficiency_bonus(self) -> int:
        """SRD § Proficiency Bonus — derived from Challenge Rating.

        Returns the SRD-table PB for ``self.cr`` (e.g., CR 1/4 → +2,
        CR 5 → +3, CR 17 → +6). Returns ``0`` when no CR was supplied
        — Characters override this via their own level-based property,
        and any creature constructed without a CR has no Proficiency
        Bonus to apply.
        """
        if self.cr is None:
            return 0
        from dnd_engine.systems.proficiency import proficiency_bonus_from_cr

        return proficiency_bonus_from_cr(self.cr)

    @property
    def is_alive(self) -> bool:
        """Check if the creature is alive (HP > 0)"""
        return self.current_hp > 0

    @property
    def is_bloodied(self) -> bool:
        """Whether the creature is Bloodied (SRD § Playing the Game › Hit Points).

        Per SRD: "If you have half your Hit Points or fewer, you're
        Bloodied, which has no game effect on its own but which might
        trigger other game effects."

        Pure derived flag — no stored state, no condition registered,
        no mechanical modifier attached. A creature at 0 HP is not
        Bloodied (it's Dying/Dead/Stable instead); a creature at full
        HP is not Bloodied. Threshold uses integer division, so a
        creature with `max_hp=21` is Bloodied at `current_hp <= 10`.

        Returns:
            True iff `0 < current_hp <= max_hp // 2`.
        """
        return 0 < self.current_hp <= self.max_hp // 2

    @property
    def initiative_modifier(self) -> int:
        """Initiative modifier (uses Dexterity)"""
        return self.abilities.dex_mod

    @property
    def ac(self) -> int:
        """
        Base armor class (without spell modifiers).

        Honors the "Only One Base AC" rule (SRD § Playing the Game ›
        Attack Rolls › Armor Class): if the creature has an alternate
        base-AC formula selected via `active_base_ac_formula`, that
        formula's value is returned; otherwise the stored `_base_ac`
        (the unarmored or armor-derived default) is returned.

        For effective AC including active effects like Mage Armor or
        Shield, use GameState.get_effective_ac(creature) instead — that
        path layers AC bonuses on top of this base value.
        """
        return self.get_base_ac()

    @ac.setter
    def ac(self, value: int) -> None:
        """Set base armor class."""
        self._base_ac = value

    def get_base_ac(self) -> int:
        """
        Return the creature's current base AC honoring the active alt formula.

        If `active_base_ac_formula` names a registered alternate formula,
        that callable is invoked with `self` and its return value is the
        base AC. Otherwise `_base_ac` (the stored default) is returned.

        The active formula is invoked on every call, so the result tracks
        live ability scores (e.g., a Mage-Armor or Unarmored-Defense
        formula reads the current DEX/CON/WIS modifier each time AC is
        queried). Callers that need to memoize must do so themselves.

        Per SRD "Only One Base AC", at most one alternate formula is in
        effect at a time even when several are registered — the active
        selection is the single source of truth.

        Interplay with `GameState.get_effective_ac`: that method seeds
        its layered-modifier stack with this value, then layers on
        `ModifierType.AC_BONUS` effects (Shield, Haste) — there is no
        longer a separate base-AC override path. Spells that change
        the base AC (Mage Armor, Barkskin) register a formula here and
        select it via `active_base_ac_formula`; layered bonuses stack
        on top of whichever base is active. Per SRD § Playing the Game
        › Attack Rolls › "Only One Base AC", the active alt-formula
        selection is the single source of truth for the base value.

        Returns:
            The base AC value to use for this creature.
        """
        if self.active_base_ac_formula is not None:
            formula = self._alt_base_ac_formulas.get(self.active_base_ac_formula)
            if formula is not None:
                return formula(self)
        return self._base_ac

    def register_base_ac_formula(self, name: str, formula: Callable[[Creature], int]) -> None:
        """
        Register an alternate base-AC formula on this creature.

        Registration alone does NOT change the creature's AC; the formula
        is dormant until `active_base_ac_formula` names it. This separation
        enforces the SRD "Only One Base AC" rule even when multiple
        features (e.g., Mage Armor + Barbarian Unarmored Defense) are
        present on the same creature.

        Args:
            name: Stable identifier for the formula (e.g.,
                "mage_armor", "barbarian_unarmored_defense"). Re-registering
                the same name overwrites the previous formula.
            formula: Callable taking the creature and returning its base AC.
        """
        self._alt_base_ac_formulas[name] = formula

    def unregister_base_ac_formula(self, name: str) -> None:
        """
        Remove a previously registered alternate base-AC formula.

        If the removed formula was the active selection, the selection is
        cleared so AC reverts to the stored `_base_ac` default.

        Args:
            name: Identifier passed to `register_base_ac_formula`.
        """
        self._alt_base_ac_formulas.pop(name, None)
        if self.active_base_ac_formula == name:
            self.active_base_ac_formula = None

    def has_base_ac_formula(self, name: str) -> bool:
        """
        Check whether a named alternate base-AC formula is registered.

        Args:
            name: Identifier to look up.

        Returns:
            True if the formula is registered (active or not).
        """
        return name in self._alt_base_ac_formulas

    def take_damage(self, amount: int) -> int:
        """
        Apply damage to the creature.

        SRD § Playing the Game › Temporary Hit Points › Lose Temp HP
        First: Temporary Hit Points are lost first, and any leftover
        damage carries over to Hit Points (e.g. 5 Temp HP + 7 damage =
        0 Temp HP, 2 HP lost). HP cannot go below 0.

        Args:
            amount: Amount of damage to apply

        Returns:
            The damage that actually landed on Hit Points — the
            carryover after the Temp HP buffer absorbed what it could.
            Equals `amount` when there is no Temp HP. Callers that drive
            death-save / massive-damage logic should key off this value
            rather than the raw incoming amount.
        """
        absorbed = min(self.temporary_hit_points, amount)
        self.temporary_hit_points -= absorbed
        carryover = amount - absorbed
        self.current_hp = max(0, self.current_hp - carryover)
        return carryover

    def heal(self, amount: int) -> None:
        """
        Heal the creature.

        Cannot heal dead creatures (HP = 0).
        Cannot exceed max HP.

        Args:
            amount: Amount of HP to restore
        """
        if not self.is_alive:
            # Dead creatures cannot be healed (would need resurrection)
            return

        self.current_hp = min(self.max_hp, self.current_hp + amount)

    def set_temporary_hit_points(self, amount: int, *, replace: bool = False) -> int:
        """
        Grant Temporary Hit Points to the creature.

        SRD § Playing the Game › Temporary Hit Points › Don't Stack:
        "Temporary Hit Points can't be added together. If you have
        Temporary Hit Points and receive more of them, you decide
        whether to keep the ones you have or to gain the new ones."

        The default resolution keeps the greater of the existing and new
        pools — the sensible automatic reading of "you decide" when no
        explicit choice is supplied. A caller honoring a player's choice
        to take the new pool (even when it is smaller) passes
        ``replace=True`` to install ``amount`` unconditionally. Either
        way the pools are never summed.

        This is NOT healing (SRD: "receiving Temporary Hit Points
        doesn't count as healing"): it never touches `current_hp`,
        works at full HP, and does not revive a creature at 0 HP. It
        emits no event and takes no event bus.

        Args:
            amount: Temp HP to grant. Negative values clamp to 0.
            replace: When True, install `amount` as the pool even if it
                is lower than the current value. When False (default),
                keep whichever pool is greater.

        Returns:
            The resulting Temporary Hit Points pool.
        """
        amount = max(0, amount)
        if replace:
            self.temporary_hit_points = amount
        else:
            self.temporary_hit_points = max(self.temporary_hit_points, amount)
        return self.temporary_hit_points

    def is_immune_to_condition(self, condition: str) -> bool:
        """
        Check whether this creature is immune to a named condition.

        SRD § Playing the Game › Immunity:
            "Immunity to a condition means you aren't affected by it."

        Two sources are honored, in parity with the damage-type
        immunity path in `CombatEngine._apply_damage_modifiers`:
          1. Catalog field `condition_immunities` — a list attribute
             populated by `DataLoader.create_monster` from
             monsters.json (e.g., bearded devil ships ["poisoned"]).
          2. Condition flag `has_immunity_{condition}` — matches the
             existing `has_immunity_{type}` convention used for
             damage-type immunity, so future spells/effects can grant
             condition immunity by attaching the flag.

        Args:
            condition: Name of the condition (case-insensitive).

        Returns:
            True if the creature is immune to the condition.
        """
        condition_name = condition.lower()
        catalog_immunities = [
            c.lower() for c in (getattr(self, "condition_immunities", None) or [])
        ]
        if condition_name in catalog_immunities:
            return True
        if self.has_condition(f"has_immunity_{condition_name}"):
            return True
        return False

    def add_condition(self, condition: str) -> None:
        """
        Add a basic condition to the creature (e.g., 'prone', 'stunned').
        For conditions with duration/repeat saves, use apply_condition_with_metadata().

        Immunity guard: if the creature is immune to the named
        condition (per `is_immune_to_condition`), the call is a no-op.
        SRD: "Immunity to a condition means you aren't affected by it."

        Args:
            condition: Name of the condition to add
        """
        condition_name = condition.lower()
        if self.is_immune_to_condition(condition_name):
            return
        if condition_name not in self.active_conditions:
            self.active_conditions[condition_name] = {}

    def apply_condition_with_metadata(
        self,
        condition: str,
        duration_type: str = "permanent",
        duration: int = 0,
        dc: int | None = None,
        ability: str | None = None,
        allow_repeat_save: bool = False,
        repeat_timing: str = "end_of_turn",
    ) -> None:
        """
        Apply a condition with full metadata for duration and repeat saves.

        Immunity guard: if the creature is immune to the named
        condition (per `is_immune_to_condition`), the call is a no-op.
        SRD: "Immunity to a condition means you aren't affected by it."

        Args:
            condition: Name of the condition (e.g., 'paralyzed', 'poisoned')
            duration_type: Type of duration ('rounds', 'minutes', 'hours', 'permanent')
            duration: Number of rounds/minutes/hours (ignored if permanent)
            dc: Difficulty class for repeat saves
            ability: Ability for repeat saves (e.g., 'constitution')
            allow_repeat_save: Whether creature can attempt saves to end condition
            repeat_timing: When repeat saves occur ('end_of_turn', 'start_of_turn')
        """
        condition_name = condition.lower()
        if self.is_immune_to_condition(condition_name):
            return
        self.active_conditions[condition_name] = {
            "duration_type": duration_type,
            "duration_remaining": duration,
            "dc": dc,
            "ability": ability,
            "allow_repeat_save": allow_repeat_save,
            "repeat_timing": repeat_timing,
        }

    def remove_condition(self, condition: str) -> None:
        """
        Remove a condition from the creature.

        Args:
            condition: Name of the condition to remove
        """
        condition_name = condition.lower()
        self.active_conditions.pop(condition_name, None)

    def has_condition(self, condition: str) -> bool:
        """
        Check if the creature has a specific condition.

        Args:
            condition: Name of the condition to check

        Returns:
            True if the creature has the condition
        """
        return condition.lower() in self.active_conditions

    def can_take_actions(self) -> bool:
        """
        Check if creature can take actions (not incapacitated or surprised).

        Incapacitating conditions: paralyzed, stunned, unconscious, petrified, surprised

        Returns:
            True if creature can act
        """
        incapacitating = ["paralyzed", "stunned", "unconscious", "petrified", "surprised"]
        return not any(cond in self.active_conditions for cond in incapacitating)

    def is_incapacitated(self) -> bool:
        """
        Check if the creature has the Incapacitated condition (per SRD glossary).

        Per SRD § Rules Glossary, Paralyzed, Petrified, Stunned, and Unconscious
        each impose Incapacitated. "Surprised" is its own action-economy
        restriction and is not the same as Incapacitated for SRD rules that
        explicitly key off the Incapacitated condition (e.g., Ranged Attacks
        in Close Combat).

        Returns:
            True if the creature is Incapacitated for SRD rule purposes.
        """
        incapacitated_conditions = (
            "incapacitated",
            "paralyzed",
            "stunned",
            "unconscious",
            "petrified",
        )
        return any(cond in self.active_conditions for cond in incapacitated_conditions)

    def process_end_of_turn_conditions(self, event_bus=None) -> list[dict]:
        """
        Process conditions at end of turn: duration countdown and repeat saves.

        Args:
            event_bus: Optional EventBus for emitting save events

        Returns:
            List of dicts describing save results and expired conditions
        """
        results = []

        # Surprised condition always ends at end of turn
        if "surprised" in self.active_conditions:
            self.remove_condition("surprised")
            results.append({"type": "condition_expired", "condition": "surprised"})

        for condition_name, metadata in list(self.active_conditions.items()):
            # Process repeat saves if allowed
            if metadata.get("allow_repeat_save") and metadata.get("repeat_timing") == "end_of_turn":
                if metadata.get("dc") and metadata.get("ability"):
                    save_result = self.make_saving_throw(
                        ability=metadata["ability"], dc=metadata["dc"], event_bus=event_bus
                    )

                    if save_result["success"]:
                        self.remove_condition(condition_name)
                        results.append(
                            {
                                "type": "repeat_save_success",
                                "condition": condition_name,
                                "save_result": save_result,
                            }
                        )
                    # Skip duration processing for conditions with repeat saves
                    # The repeat save is the primary mechanism for ending the condition
                    continue

            # Decrement duration for round-based conditions
            if metadata.get("duration_type") == "rounds":
                metadata["duration_remaining"] = metadata.get("duration_remaining", 0) - 1
                if metadata["duration_remaining"] <= 0:
                    self.remove_condition(condition_name)
                    results.append({"type": "duration_expired", "condition": condition_name})

        return results

    def get_condition_duration_minutes(self, condition: str) -> float:
        """
        Get the remaining duration of a condition in minutes.

        D&D 5E conversions:
        - 1 round = 6 seconds
        - 10 rounds = 1 minute

        Args:
            condition: Name of the condition

        Returns:
            Duration in minutes, or float('inf') for permanent conditions.
            Returns 0 if condition not found.
        """
        condition_name = condition.lower()
        if condition_name not in self.active_conditions:
            return 0

        metadata = self.active_conditions[condition_name]
        duration_type = metadata.get("duration_type", "permanent")
        duration_remaining = metadata.get("duration_remaining", 0)

        if duration_type == "permanent":
            return float("inf")
        elif duration_type == "rounds":
            # 10 rounds = 1 minute (6 seconds per round)
            return duration_remaining / 10.0
        elif duration_type == "minutes":
            return float(duration_remaining)
        elif duration_type == "hours":
            return duration_remaining * 60.0
        else:
            # Unknown duration type, treat as permanent to be safe
            return float("inf")

    def clear_expired_conditions(self) -> list[str]:
        """
        Clear all non-permanent conditions.

        Use this when time passes outside of combat (e.g., during rest)
        to remove temporary conditions that would have expired.

        Returns:
            List of condition names that were removed.
        """
        removed = []
        for condition_name, metadata in list(self.active_conditions.items()):
            duration_type = metadata.get("duration_type", "permanent")
            if duration_type != "permanent":
                self.remove_condition(condition_name)
                removed.append(condition_name)
        return removed

    def clear_conditions_by_max_duration(self, max_minutes: float) -> list[str]:
        """
        Clear conditions with remaining duration less than or equal to max_minutes.

        Use this for short rests to clear conditions that would expire
        within the rest duration.

        Args:
            max_minutes: Maximum duration in minutes. Conditions with
                        durations <= this value will be cleared.

        Returns:
            List of condition names that were removed.
        """
        removed = []
        for condition_name in list(self.active_conditions.keys()):
            duration_minutes = self.get_condition_duration_minutes(condition_name)
            if duration_minutes <= max_minutes:
                self.remove_condition(condition_name)
                removed.append(condition_name)
        return removed

    @property
    def conditions(self) -> set[str]:
        """
        Backward compatibility: return set of active condition names.

        Returns:
            Set of condition names
        """
        return set(self.active_conditions.keys())

    def make_saving_throw(
        self,
        ability: str,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False,
        circumstantial: int = 0,
        event_bus=None,
    ) -> dict:
        """
        Roll an ability saving throw against a DC.

        Basic implementation for creatures (monsters). Characters may override
        this to add proficiency bonuses.

        Args:
            ability: Ability to save with (e.g., "str", "dex", "con", "int", "wis", "cha")
            dc: Difficulty class to beat
            advantage: Roll with advantage (roll twice, take higher)
            disadvantage: Roll with disadvantage (roll twice, take lower)
            circumstantial: Signed bonus/penalty from class features,
                spells, or "another rule" per SRD § Playing the Game ›
                D20 Tests › Step 5. Forwarded to the d20-test primitive
                and surfaced on the returned dict for telemetry.
            event_bus: Optional EventBus instance to emit saving throw event

        Returns:
            Dictionary with:
            - "success": bool (total >= dc)
            - "roll": int (the d20 roll before modifier)
            - "modifier": int (ability modifier)
            - "total": int (roll + modifier + circumstantial)
            - "dc": int (the DC that was beaten)
            - "ability": str (the ability that was saved with, in short form)
            - "circumstantial": int (the signed bonus/penalty applied)

        Raises:
            ValueError: If ability name is invalid
        """
        # Normalize ability to short name
        short_to_full = {
            "str": "strength",
            "dex": "dexterity",
            "con": "constitution",
            "int": "intelligence",
            "wis": "wisdom",
            "cha": "charisma",
        }
        full_to_short = {
            "strength": "str",
            "dexterity": "dex",
            "constitution": "con",
            "intelligence": "int",
            "wisdom": "wis",
            "charisma": "cha",
        }

        ability_lower = ability.lower()
        if ability_lower in short_to_full:
            ability_short = ability_lower
            ability_full = short_to_full[ability_lower]
        elif ability_lower in full_to_short:
            ability_short = full_to_short[ability_lower]
            ability_full = ability_lower
        else:
            raise ValueError(f"Invalid ability name: {ability}")

        # SRD § Actions › Dodge: a dodging creature rolls DEX saves with
        # Advantage, unless they are Incapacitated or their Speed is 0.
        if (
            ability_short == "dex"
            and self.is_dodging
            and not self.is_incapacitated()
            and self.speed > 0
        ):
            advantage = True

        # Get ability modifier
        if ability_full == "strength":
            modifier = self.abilities.str_mod
        elif ability_full == "dexterity":
            modifier = self.abilities.dex_mod
        elif ability_full == "constitution":
            modifier = self.abilities.con_mod
        elif ability_full == "intelligence":
            modifier = self.abilities.int_mod
        elif ability_full == "wisdom":
            modifier = self.abilities.wis_mod
        elif ability_full == "charisma":
            modifier = self.abilities.cha_mod
        else:
            raise ValueError(f"Invalid ability name: {ability}")

        # Creatures have no proficient saves in the data model today
        # (PB-from-CR derivation is plan-08 slice 2). The primitive's
        # default roller (a fresh `DiceRoller`) matches the legacy
        # behavior of this method.
        result = d20_test(
            ability_mod=modifier,
            advantage=advantage,
            disadvantage=disadvantage,
            circumstantial=circumstantial,
        )

        return {
            "success": result.succeeds_against(dc),
            "roll": result.d20,
            "modifier": modifier,
            "total": result.total,
            "dc": dc,
            "ability": ability_short,
            "circumstantial": circumstantial,
        }

    def make_ability_check(
        self,
        ability: str,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False,
        circumstantial: int = 0,
        event_bus=None,
    ) -> dict:
        """
        Roll a raw ability check against a DC.

        Mirrors :meth:`Character.make_ability_check`. SRD § Playing
        the Game › Ability Checks: a monster rolls ``d20 + ability
        modifier`` for non-skill checks (escape a pit, push a boulder,
        puzzle out a glyph). Creatures don't yet carry skill or tool
        proficiencies, so the modifier here is just the ability mod.

        Args:
            ability: Ability name (short or full).
            dc: Difficulty class to beat.
            advantage: Roll 2d20, take higher.
            disadvantage: Roll 2d20, take lower.
            circumstantial: Signed bonus/penalty from class features,
                spells, or "another rule" per SRD § Playing the Game ›
                D20 Tests › Step 5. Forwarded to the d20-test primitive
                and surfaced on the returned dict for telemetry.
            event_bus: Optional EventBus to emit an ABILITY_CHECK event.

        Returns:
            Dict with success / roll / modifier / total / dc / ability /
            circumstantial.

        Raises:
            ValueError: If ability name is invalid.
        """
        from dnd_engine.utils.events import Event, EventType

        short_to_full = {
            "str": "strength",
            "dex": "dexterity",
            "con": "constitution",
            "int": "intelligence",
            "wis": "wisdom",
            "cha": "charisma",
        }
        full_to_short = {v: k for k, v in short_to_full.items()}

        ability_lower = ability.lower()
        if ability_lower in short_to_full:
            ability_short = ability_lower
        elif ability_lower in full_to_short:
            ability_short = full_to_short[ability_lower]
        else:
            raise ValueError(f"Invalid ability name: {ability}")

        ability_mod = getattr(self.abilities, f"{ability_short}_mod")

        result = d20_test(
            ability_mod=ability_mod,
            advantage=advantage,
            disadvantage=disadvantage,
            circumstantial=circumstantial,
        )

        success = result.succeeds_against(dc)
        result_dict = {
            "success": success,
            "roll": result.d20,
            "modifier": ability_mod,
            "total": result.total,
            "dc": dc,
            "ability": ability_short,
            "circumstantial": circumstantial,
        }

        if event_bus is not None:
            event_bus.emit(
                Event(
                    type=EventType.ABILITY_CHECK,
                    data={"creature": self.name, **result_dict},
                )
            )

        return result_dict

    def __str__(self) -> str:
        """String representation of the creature"""
        status = "alive" if self.is_alive else "dead"
        return f"{self.name} (HP: {self.current_hp}/{self.max_hp}, AC: {self._base_ac}, {status})"
