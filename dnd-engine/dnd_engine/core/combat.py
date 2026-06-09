# ABOUTME: Combat engine for resolving attacks and damage in D&D 5E
# ABOUTME: Handles attack rolls, critical hits, damage calculation, and applying damage to creatures

from dataclasses import dataclass
from typing import Any

from dnd_engine.core.combat_geometry import attack_reach_for, is_ranged_action
from dnd_engine.core.creature import Cover, Creature
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.distance import distance_in_feet
from dnd_engine.rules.damage import apply_damage_adjustments, apply_damage_modifiers
from dnd_engine.systems.d20 import d20_test
from dnd_engine.systems.perception import VisibilityRelation
from dnd_engine.utils.events import Event, EventType


@dataclass
class AttackResult:
    """
    Result of an attack roll.

    Contains all information about an attack: the roll, bonuses, hit/miss status,
    damage dealt, and special conditions (critical hit, advantage, sneak attack, etc.).
    """

    attacker_name: str
    defender_name: str
    attack_roll: int  # The natural die roll (1-20)
    attack_bonus: int
    target_ac: int
    hit: bool
    damage: int
    critical_hit: bool
    advantage: bool
    disadvantage: bool
    sneak_attack_damage: int = 0  # Additional damage from sneak attack
    sneak_attack_dice: str | None = None  # Sneak attack dice notation (e.g., "2d6")
    # SRD § Playing the Game › D20 Tests › Step 5: signed
    # circumstantial bonus/penalty applied to the attack roll
    # (Bless, Bane, cover, environment, class features, etc.).
    circumstantial: int = 0

    @property
    def total_attack(self) -> int:
        """Calculate total attack (roll + bonus + circumstantial)"""
        return self.attack_roll + self.attack_bonus + self.circumstantial

    @property
    def total_damage(self) -> int:
        """Calculate total damage including sneak attack"""
        return self.damage + self.sneak_attack_damage

    def __str__(self) -> str:
        """String representation of the attack result"""
        hit_status = "CRITICAL HIT" if self.critical_hit else ("HIT" if self.hit else "MISS")
        adv_status = ""

        if self.advantage:
            adv_status = " (advantage)"
        elif self.disadvantage:
            adv_status = " (disadvantage)"

        result = f"{self.attacker_name} attacks {self.defender_name}: "
        result += (
            f"{self.attack_roll}+{self.attack_bonus}={self.total_attack} vs AC {self.target_ac} "
        )
        result += f"- {hit_status}{adv_status}"

        if self.hit:
            if self.sneak_attack_damage > 0:
                result += f" for {self.damage} damage + {self.sneak_attack_damage} sneak attack = {self.total_damage} total"
            else:
                result += f" for {self.damage} damage"

        return result


class CombatEngine:
    """
    Handles combat resolution according to D&D 5E rules.

    Responsibilities:
    - Resolve attack rolls (1d20 + bonus vs AC)
    - Determine hit/miss
    - Handle critical hits (nat 20) and critical misses (nat 1)
    - Calculate damage (with critical hit doubling)
    - Apply damage to creatures
    - Support advantage/disadvantage
    """

    def __init__(self, dice_roller: DiceRoller | None = None):
        """
        Initialize the combat engine.

        Args:
            dice_roller: DiceRoller instance to use (creates new one if not provided)
        """
        self.dice_roller = dice_roller if dice_roller is not None else DiceRoller()

    def _apply_damage_modifiers(
        self,
        target: Creature,
        raw_damage: int,
        damage_type: str | None,
        environment: str | None = None,
    ) -> int:
        """
        Scale raw damage by the target's per-type Resistance, Immunity,
        Vulnerability, and flat adjustments.

        Thin delegate to the canonical pipeline in
        `dnd_engine.rules.damage.apply_damage_modifiers`, the single
        chokepoint shared with non-combat damage callers (condition
        ticks, auto-hit spells, thrown items). See that function for the
        full SRD ordering and source-resolution documentation.
        """
        return apply_damage_modifiers(target, raw_damage, damage_type, environment)

    def _apply_damage_adjustments(self, target: Creature, damage: int, damage_type: str) -> int:
        """
        Apply pre-Resistance flat adjustments to the running damage.

        Thin delegate to `dnd_engine.rules.damage.apply_damage_adjustments`,
        the "adjustments" stage of the canonical damage pipeline. Kept as
        a method so subclasses can still override the adjustments hook.
        See the rules function for the full hook contract.
        """
        return apply_damage_adjustments(target, damage, damage_type)

    def resolve_attack(
        self,
        attacker: Creature,
        defender: Creature,
        attack_bonus: int,
        damage_dice: str,
        advantage: bool = False,
        disadvantage: bool = False,
        apply_damage: bool = False,
        event_bus=None,
        action: dict | None = None,
        game_state=None,
        damage_type: str | None = None,
        attacker_sees_defender: VisibilityRelation | None = None,
        defender_sees_attacker: VisibilityRelation | None = None,
        circumstantial: int = 0,
        cover: Cover = Cover.NONE,
    ) -> AttackResult:
        """
        Resolve a complete attack.

        D&D 5E attack process:
        1. Roll 1d20 + attack bonus
        2. Compare to target's AC
        3. Natural 20 is always a hit (critical)
        4. Natural 1 is always a miss
        5. If hit: roll damage dice
        6. If critical hit: double the damage dice (not the modifier)
        7. Apply sneak attack damage if applicable (Rogue with advantage/ally nearby)
        8. Scale damage by target's per-type Resistance / Immunity via
           `_apply_damage_modifiers` (only when `damage_type` is given)
        9. Apply damage if requested

        Args:
            attacker: The attacking creature
            defender: The defending creature
            attack_bonus: Total attack bonus (proficiency + ability mod + magic, etc.)
            damage_dice: Damage dice notation (e.g., "1d8+3")
            advantage: Roll with advantage (take higher of 2d20)
            disadvantage: Roll with disadvantage (take lower of 2d20)
            apply_damage: If True, apply damage to defender's HP
            event_bus: Optional EventBus instance for event emission
            damage_type: SRD damage type (e.g. "fire", "slashing"). When
                provided, damage is routed through
                `_apply_damage_modifiers` so the defender's per-type
                Resistance / Immunity (from condition flags or the
                monster-catalog `damage_resistances` / `damage_immunities`
                fields) scales the final amount. Optional for backward
                compatibility — callers that haven't been migrated to
                tagged damage see the legacy untyped behavior. The
                damage_type itself does not branch any other logic in
                this method (SRD: "Damage types ... have no rules of
                their own"); it is purely a key for the modifier
                chokepoint.
            attacker_sees_defender: How the attacker perceives the
                defender (a `VisibilityRelation`). When the attacker
                can't see the target — `UNSEEN` or `UNSEEN_BUT_SENSED`
                (tremorsense locates but does not see) — the attack is
                made with Disadvantage (SRD § Unseen Attackers and
                Targets). `None` (default) leaves the roll unmodified.
            defender_sees_attacker: How the defender perceives the
                attacker. When the defender can't see the attacker, the
                attacker has Advantage. `None` leaves the roll
                unmodified. When both an unseen attacker and an unseen
                target apply, they cancel via the advantage/disadvantage
                rule below.
            circumstantial: Signed bonus/penalty from class features,
                spells, or "another rule" per SRD § Playing the Game ›
                D20 Tests › Step 5. Forwarded to the d20-test primitive
                and surfaced on ``AttackResult.circumstantial`` for
                telemetry. Hit determination uses
                ``attack_roll + attack_bonus + circumstantial`` so a
                Bless-like bonus can flip a borderline miss.
            cover: SRD § Playing the Game › Making an Attack › Cover.
                The caller resolves geometry (which obstacles sit
                between attacker and defender, whether a creature
                between them is two-sizes-smaller and therefore grants
                no cover, which of multiple obstacles wins under "most
                protective applies") and passes the single resulting
                degree. ``HALF`` / ``THREE_QUARTERS`` add +2 / +5 to
                the defender's effective AC for this attack only.
                ``TOTAL`` short-circuits the attack at Step 1 — the
                target "can't be targeted directly" — and the engine
                returns a sentinel ``AttackResult`` (``attack_roll=0``,
                ``hit=False``, ``damage=0``) with no dice rolled and
                no side effects (no hidden-state revelation, no Help
                consumption). Default ``Cover.NONE`` preserves legacy
                behavior for callers that don't compute geometry.

        Returns:
            AttackResult containing full attack details including sneak attack if applicable
        """
        # SRD § Cover › Total Cover: "a target with Total Cover can't
        # be targeted directly by an attack or a spell." Short-circuit
        # at Step 1 (Choose a Target) with a sentinel result mirroring
        # the reach-rejection shape (`attack_roll=0`). No dice are
        # rolled, no Hidden state is consumed, no Help is spent.
        if cover == Cover.TOTAL:
            return AttackResult(
                attacker_name=attacker.name,
                defender_name=defender.name,
                attack_roll=0,
                attack_bonus=attack_bonus,
                target_ac=defender._base_ac,
                hit=False,
                damage=0,
                critical_hit=False,
                advantage=advantage,
                disadvantage=disadvantage,
                circumstantial=circumstantial,
            )

        # SRD § Playing the Game › Melee Attacks › Reach: a melee attack
        # may only target a creature within the attacker's reach (5 ft
        # by default; greater for some creatures/weapons as noted on
        # the action). When the caller provides both spatial context
        # (``game_state``) and an authored action with a ``reach``
        # field, reject the attack before any side effects (dice roll,
        # hidden-state revelation, help-flag consumption) when the
        # defender sits beyond reach. Mirrors the seam #401 added for
        # ranged-attack range enforcement.
        #
        # Skipped when:
        #  - ``action`` is None — the caller (e.g. PC weapon attack at
        #    ``game_state.py:3204``, OAs at ``:1246``/``:5397``, item
        #    throws at ``:5676``) gates range upstream and intentionally
        #    omits ``action`` here.
        #  - ``game_state`` is None — unit tests without a spatial
        #    index can still exercise the engine; they would otherwise
        #    regress on a single-site change.
        #  - The action is ranged (declares ``range`` rather than
        #    ``reach``) — reach doesn't apply; range enforcement for
        #    ranged monster attacks is still a separate gap.
        #
        # The short-circuit emits an ``AttackResult`` with
        # ``attack_roll=0`` as a sentinel so callers / tests can
        # distinguish a gate rejection from a missed roll.
        if action is not None and game_state is not None and not is_ranged_action(action):
            attacker_pos = getattr(attacker, "position", None)
            defender_pos = getattr(defender, "position", None)
            if attacker_pos is not None and defender_pos is not None:
                reach_ft = attack_reach_for(action)
                distance_ft = distance_in_feet(
                    attacker_pos.x,
                    attacker_pos.y,
                    defender_pos.x,
                    defender_pos.y,
                )
                if distance_ft > reach_ft:
                    return AttackResult(
                        attacker_name=attacker.name,
                        defender_name=defender.name,
                        attack_roll=0,
                        attack_bonus=attack_bonus,
                        target_ac=defender._base_ac,
                        hit=False,
                        damage=0,
                        critical_hit=False,
                        advantage=advantage,
                        disadvantage=disadvantage,
                        circumstantial=circumstantial,
                    )

        # SRD § Actions › Dodge: a dodging defender imposes Disadvantage
        # on incoming attacks, unless they are Incapacitated or their
        # Speed is 0. Recomputed each call so revocation conditions are
        # honored live.
        if (
            getattr(defender, "is_dodging", False)
            and not defender.is_incapacitated()
            and defender.speed > 0
        ):
            disadvantage = True

        # SRD § Actions › Help: a creature receiving Help rolls its
        # next attack with Advantage; the one-shot grant is consumed
        # here whether or not the attack lands.
        if getattr(attacker, "pending_help_from", None) is not None:
            advantage = True
            attacker.pending_help_from = None

        # SRD § Hide: a hidden creature reveals its location when it
        # makes an attack roll. The unseen-attacker Advantage below is
        # derived from `defender_sees_attacker`, which the caller
        # captured *before* this attack, so clearing the Hidden
        # condition here preserves that one advantaged shot while
        # revealing the attacker for everything that follows.
        if hasattr(attacker, "has_condition") and attacker.has_condition("hidden"):
            attacker.remove_condition("hidden")

        # SRD § Combat › Unseen Attackers and Targets: an attacker the
        # target can't see has Advantage; a target the attacker can't
        # see is attacked with Disadvantage. Both UNSEEN and
        # UNSEEN_BUT_SENSED count as "can't see" — tremorsense locates a
        # creature but does not let you see it. When both apply they
        # cancel via the advantage/disadvantage rule below. A `None`
        # relation means the caller did not supply visibility state, so
        # the roll is left unmodified (backward compatibility).
        if defender_sees_attacker is not None and defender_sees_attacker != VisibilityRelation.SEEN:
            advantage = True
        if attacker_sees_defender is not None and attacker_sees_defender != VisibilityRelation.SEEN:
            disadvantage = True

        # SRD: "If circumstances cause a roll to have both advantage
        # and disadvantage, you're considered to have neither of them"
        # — they cancel. The dice roller raises on both-set, so the
        # cancellation must happen here before delegating.
        if advantage and disadvantage:
            advantage = False
            disadvantage = False

        # Roll attack via the unified D20Test primitive. `attack_bonus`
        # is the bundled to-hit number (ability + PB + magic); slice 1
        # passes the entire bundle as `ability_mod` to preserve the
        # legacy `AttackResult.attack_bonus` semantics. The fine-grained
        # PB-vs-magic split lands in plan-08 slice 2.
        roll = d20_test(
            ability_mod=attack_bonus,
            advantage=advantage,
            disadvantage=disadvantage,
            circumstantial=circumstantial,
            roller=self.dice_roller,
        )
        attack_roll = roll.d20  # The natural d20 result (1-20)

        # Determine critical hit/miss
        critical_hit = attack_roll == 20
        critical_miss = attack_roll == 1

        # Get effective AC (includes modifiers from spells/effects if game_state provided).
        # SRD § Cover: Half / Three-Quarters cover add +2 / +5 to the
        # defender's AC for this attack only; total cover was already
        # short-circuited above. The cover bump is owned by
        # `get_effective_ac` so a single place layers the bonus.
        if game_state is not None:
            defender_ac = game_state.get_effective_ac(defender, cover=cover)
        else:
            # Fallback to base AC if no game_state (e.g., in unit tests)
            defender_ac = defender._base_ac + cover.ac_bonus

        # Determine hit/miss. Circumstantial bonus/penalty is summed
        # into the attack total per SRD § Playing the Game › D20 Tests
        # › Step 5; the natural d20 outcome (`attack_roll`) is still
        # the gate for critical hit / fumble below.
        total_attack = attack_roll + attack_bonus + circumstantial
        hit = total_attack >= defender_ac

        # Natural 20 always hits, natural 1 always misses
        if critical_hit:
            hit = True
        elif critical_miss:
            hit = False

        # Calculate damage if hit
        damage = 0
        sneak_attack_damage = 0
        sneak_attack_dice = None

        if hit:
            damage = self._calculate_damage(damage_dice, critical_hit)

            # Check for sneak attack (Character-specific)
            if hasattr(attacker, "can_sneak_attack"):
                if attacker.can_sneak_attack(
                    has_advantage=advantage, has_disadvantage=disadvantage
                ):
                    sneak_attack_dice = attacker.get_sneak_attack_dice()
                    if sneak_attack_dice:
                        sneak_attack_damage = self._calculate_damage(
                            sneak_attack_dice, critical_hit=critical_hit
                        )

                        # Emit sneak attack event
                        if event_bus is not None:
                            event = Event(
                                type=EventType.SNEAK_ATTACK,
                                data={
                                    "character": attacker.name,
                                    "dice": sneak_attack_dice,
                                    "damage": sneak_attack_damage,
                                },
                            )
                            event_bus.emit(event)

            # Scale damage by target's per-type Resistance / Immunity.
            # Sneak-attack damage shares the weapon's damage type per
            # SRD ("Sneak Attack damage isn't a separate damage type"),
            # so both summands route through the same chokepoint as a
            # single total. When `damage_type` is None this is a no-op
            # and the legacy untyped behavior is preserved.
            # Environment context (SRD § Underwater Combat: underwater
            # grants Fire Resistance, #518) is sourced from game_state
            # when available; unit tests without a game_state see the
            # legacy no-environment behavior.
            environment = (
                game_state.creature_environment(defender)
                if game_state is not None and hasattr(game_state, "creature_environment")
                else None
            )
            total_pre_modifier = damage + sneak_attack_damage
            total_post_modifier = self._apply_damage_modifiers(
                defender, total_pre_modifier, damage_type, environment=environment
            )
            # Reflect the post-modifier values back onto the AttackResult.
            # When the target is immune both summands collapse to zero;
            # otherwise we scale them proportionally so the breakdown
            # (damage vs sneak_attack_damage) remains meaningful.
            if total_pre_modifier != total_post_modifier and total_pre_modifier > 0:
                damage_share = round(damage * total_post_modifier / total_pre_modifier)
                sneak_attack_damage = total_post_modifier - damage_share
                damage = damage_share

            if apply_damage:
                # Pass event_bus to take_damage for Character instances (death save handling)
                if hasattr(defender, "take_damage") and hasattr(defender.__class__, "take_damage"):
                    # Inspect the defender's `take_damage` signature so
                    # we surface the crit context only to callees that
                    # accept it (Character does; the base Creature
                    # does not). SRD § Death Saving Throws: a crit at
                    # 0 HP yields 2 failures instead of 1.
                    import inspect

                    sig = inspect.signature(defender.take_damage)
                    kwargs = {}
                    if "event_bus" in sig.parameters:
                        kwargs["event_bus"] = event_bus
                    if "critical_hit" in sig.parameters:
                        kwargs["critical_hit"] = critical_hit
                    defender.take_damage(total_post_modifier, **kwargs)
                else:
                    defender.take_damage(total_post_modifier)

            # Process saving throw effects (e.g., ghoul paralysis)
            if action and "saving_throw" in action:
                self._process_saving_throw_effect(
                    action["saving_throw"], attacker, defender, event_bus
                )

        return AttackResult(
            attacker_name=attacker.name,
            defender_name=defender.name,
            attack_roll=attack_roll,
            attack_bonus=attack_bonus,
            target_ac=defender_ac,
            hit=hit,
            damage=damage,
            critical_hit=critical_hit,
            advantage=advantage,
            disadvantage=disadvantage,
            sneak_attack_damage=sneak_attack_damage,
            sneak_attack_dice=sneak_attack_dice,
            circumstantial=circumstantial,
        )

    def _calculate_damage(self, damage_dice: str, critical_hit: bool) -> int:
        """
        Calculate damage from dice notation.

        For critical hits, damage dice are doubled (but not modifiers).
        Example: 1d8+3 becomes 2d8+3 on a crit.

        SRD § Playing the Game › Damage Rolls:
            "If there's a penalty to the damage, it's possible to deal
             0 damage but not negative damage."

        The result is clamped at 0 at the dice-roll site so that any
        downstream additive on-hit damage (sneak attack, divine smite)
        accumulates from 0 rather than from a negative base — i.e.,
        a -3 base + 4 sneak attack equals 4, not 1.

        Args:
            damage_dice: Damage dice notation (e.g., "1d8+3")
            critical_hit: Whether this is a critical hit

        Returns:
            Total damage, clamped at 0 (never negative)
        """
        if critical_hit:
            # Double the dice (but not the modifier)
            damage_dice = self._double_damage_dice(damage_dice)

        damage_roll = self.dice_roller.roll(damage_dice)
        # SRD clamp: penalties can reduce damage to 0 but not below.
        return max(0, damage_roll.total)

    def _double_damage_dice(self, damage_dice: str) -> str:
        """
        Double the dice for a critical hit.

        Converts "1d8+3" to "2d8+3", "2d6+2" to "4d6+2", etc.

        Args:
            damage_dice: Original damage dice notation

        Returns:
            Modified notation with doubled dice
        """
        # Parse the dice notation
        import re

        pattern = re.compile(r"^(\d*)d(\d+)(([+-])(\d+))?$", re.IGNORECASE)
        match = pattern.match(damage_dice.strip())

        if not match:
            # If we can't parse it, just return the original
            return damage_dice

        # Extract components
        count_str = match.group(1)
        count = int(count_str) if count_str else 1
        sides = match.group(2)
        modifier_part = match.group(3) if match.group(3) else ""

        # Double the count
        doubled_count = count * 2

        # Reconstruct the notation
        return f"{doubled_count}d{sides}{modifier_part}"

    def _process_saving_throw_effect(
        self, saving_throw_data: dict, attacker: Creature, defender: Creature, event_bus=None
    ) -> dict | None:
        """
        Process saving throw effects from monster actions (e.g., ghoul paralysis).

        Args:
            saving_throw_data: The saving_throw dict from monster action
            attacker: The attacking creature
            defender: The defending creature
            event_bus: Optional EventBus for emitting events

        Returns:
            Result dict with save_result and condition_applied, or None if not triggered
        """
        # Check trigger type
        trigger = saving_throw_data.get("trigger")
        if trigger != "on_hit":
            # For now, only support on_hit triggers
            # Future: start_of_turn, area_effect, etc.
            return None

        # Make the saving throw
        ability = saving_throw_data.get("ability")
        dc = saving_throw_data.get("dc")

        if not ability or not dc:
            return None

        save_result = defender.make_saving_throw(ability=ability, dc=dc, event_bus=event_bus)

        # Emit saving throw event
        if event_bus:
            event_bus.emit(
                Event(
                    type=EventType.SAVING_THROW,
                    data={
                        "creature": defender.name,
                        "ability": ability,
                        "dc": dc,
                        "result": save_result,
                    },
                )
            )

        # Apply effect on failure
        if not save_result["success"]:
            on_fail = saving_throw_data.get("on_fail", {})
            condition = on_fail.get("condition")

            if condition:
                # SRD § Playing the Game › Immunity: "Immunity to a
                # condition means you aren't affected by it." Skip the
                # on-fail condition (and its CONDITION_APPLIED event)
                # when the defender is immune. The general guard also
                # lives on `Creature.apply_condition_with_metadata`,
                # but checking here lets us report the truthful
                # `condition_applied: None` to callers and avoid
                # emitting a misleading event.
                if defender.is_immune_to_condition(condition):
                    return {"save_result": save_result, "condition_applied": None}

                # Apply condition with metadata
                defender.apply_condition_with_metadata(
                    condition=condition,
                    duration_type=on_fail.get("duration_type", "permanent"),
                    duration=on_fail.get("duration", 0),
                    dc=dc,
                    ability=ability,
                    allow_repeat_save=on_fail.get("allow_repeat_save", False),
                    repeat_timing=on_fail.get("repeat_timing", "end_of_turn"),
                )

                # Emit condition applied event
                if event_bus:
                    event_bus.emit(
                        Event(
                            type=EventType.CONDITION_APPLIED,
                            data={
                                "creature": defender.name,
                                "condition": condition,
                                "source": attacker.name,
                                "duration_type": on_fail.get("duration_type"),
                                "duration": on_fail.get("duration"),
                            },
                        )
                    )

                return {"save_result": save_result, "condition_applied": condition}

        return {"save_result": save_result, "condition_applied": None}

    def resolve_spell_attack(
        self,
        caster: Creature,
        target: Creature,
        spell: dict[str, Any],
        spellcasting_ability: str,
        advantage: bool = False,
        disadvantage: bool = False,
        apply_damage: bool = False,
        event_bus=None,
    ) -> AttackResult:
        """
        Resolve a spell attack roll.

        Handles spell attack mechanics:
        1. Calculate spell attack bonus (proficiency + spellcasting ability modifier)
        2. Roll attack (1d20 + spell attack bonus vs AC)
        3. Handle cantrip damage scaling based on caster level
        4. Roll damage on hit (critical hits double dice)
        5. Emit spell attack events
        6. Apply damage if requested

        Args:
            caster: The creature casting the spell (must be a Character for cantrip scaling)
            target: The target of the spell attack
            spell: Spell data dictionary containing:
                - "name": spell name
                - "damage": dict with "dice" and "damage_type"
                - "level": spell level (0 for cantrips)
            spellcasting_ability: Ability used for spellcasting (e.g., "int", "wis", "cha")
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage
            apply_damage: If True, apply damage to target's HP
            event_bus: Optional EventBus instance for event emission

        Returns:
            AttackResult with spell attack details

        Raises:
            ValueError: If caster doesn't have get_spell_attack_bonus method
        """
        from dnd_engine.utils.events import Event, EventType

        # Get spell attack bonus from caster
        if not hasattr(caster, "get_spell_attack_bonus"):
            raise ValueError(f"{caster.name} cannot cast spells (no spell attack bonus)")

        spell_attack_bonus = caster.get_spell_attack_bonus(spellcasting_ability)

        # Get damage dice from spell
        damage_data = spell.get("damage", {})
        base_damage_dice = damage_data.get("dice", "1d6")
        damage_type = damage_data.get("damage_type", "force")

        # Scale cantrip damage if this is a cantrip (level 0)
        if spell.get("level", 0) == 0 and hasattr(caster, "scale_cantrip_damage"):
            damage_dice = caster.scale_cantrip_damage(base_damage_dice)
        else:
            damage_dice = base_damage_dice

        # Use the existing resolve_attack method for the mechanics.
        # Pass through `damage_type` so the target's per-type
        # Resistance / Immunity scales spell-attack damage (e.g.,
        # Fire Bolt vs a bearded devil's fire immunity).
        result = self.resolve_attack(
            attacker=caster,
            defender=target,
            attack_bonus=spell_attack_bonus,
            damage_dice=damage_dice,
            advantage=advantage,
            disadvantage=disadvantage,
            apply_damage=apply_damage,
            event_bus=event_bus,
            damage_type=damage_type,
        )

        # Emit spell-specific attack event
        if event_bus is not None:
            event = Event(
                type=EventType.ATTACK_ROLL,
                data={
                    "attacker": caster.name,
                    "target": target.name,
                    "spell": spell.get("name", "Unknown Spell"),
                    "attack_roll": result.attack_roll,
                    "attack_bonus": spell_attack_bonus,
                    "total": result.total_attack,
                    "target_ac": result.target_ac,
                    "hit": result.hit,
                    "critical_hit": result.critical_hit,
                    "damage": result.damage,
                    "damage_type": damage_type,
                    "attack_type": "spell",
                },
            )
            event_bus.emit(event)

        return result

    def resolve_spell_save(
        self,
        caster,
        targets: list,
        spell,
        upcast_level: int | None = None,
        apply_damage: bool = False,
        event_bus=None,
        game_state=None,
    ) -> dict[str, Any]:
        """
        Resolve a spell that requires saving throws.

        Handles spell save mechanics:
        1. Calculate caster's spell save DC
        2. Each target makes a saving throw
        3. Roll damage for the spell
        4. Apply damage based on save result (full, half, or none)
        5. Emit spell save events

        Args:
            caster: The creature casting the spell (must have get_spell_save_dc method)
            targets: List of creatures targeted by the spell
            spell: Spell object or dict containing:
                - "name": spell name
                - "damage": dict with "dice" and "damage_type"
                - "saving_throw": dict with "ability" and "on_success"
                - "level": spell level
            upcast_level: Spell slot level used (for upcasting), defaults to spell's base level
            apply_damage: If True, apply damage to targets' HP
            event_bus: Optional EventBus instance for event emission
            game_state: Optional GameState used to source per-target
                environment context for the damage-modifier chokepoint
                (SRD § Underwater Combat: anything underwater has
                Resistance to Fire damage, #518). Optional for backward
                compatibility — callers without a game_state see the
                legacy no-environment behavior.

        Returns:
            Dictionary with spell cast results:
            {
                "spell_name": str,
                "caster": str,
                "save_dc": int,
                "save_ability": str,
                "targets": [
                    {
                        "name": str,
                        "roll": int,
                        "modifier": int,
                        "total": int,
                        "success": bool,
                        "damage": int,
                        "damage_type": str
                    },
                    ...
                ]
            }

        Raises:
            ValueError: If caster doesn't have spell save DC or spell lacks saving throw info
        """
        from dnd_engine.utils.events import Event, EventType

        # Get spell info
        if hasattr(spell, "name"):
            # Spell object
            spell_name = spell.name
            spell_level = spell.level
            spell_id = spell.id
            save_info = spell.saving_throw
            damage_info = spell.damage
        else:
            # Dict format
            spell_name = spell.get("name", "Unknown Spell")
            spell_level = spell.get("level", 1)
            spell_id = spell.get("id", "unknown")
            save_info = spell.get("saving_throw")
            damage_info = spell.get("damage")

        if not save_info:
            raise ValueError(f"Spell {spell_name} does not have saving throw information")

        # Get save ability and effect
        if hasattr(save_info, "ability"):
            save_ability = save_info.ability
            on_success = save_info.on_success
        else:
            save_ability = save_info.get("ability")
            on_success = save_info.get("on_success", "half")

        # Get caster's spell save DC
        if not hasattr(caster, "get_spell_save_dc"):
            raise ValueError(f"{caster.name} cannot cast spells (no spell save DC)")

        save_dc = caster.get_spell_save_dc()

        # Determine actual spell slot level (for upcasting)
        actual_level = upcast_level if upcast_level is not None else spell_level

        # Roll damage once for the spell
        base_damage = self._roll_spell_save_damage(spell, damage_info, spell_level, actual_level)

        # Resolve the spell's damage type once. The same tag is routed
        # to every target's per-type modifier chokepoint and surfaced
        # on each row of `target_results` for downstream consumers.
        if damage_info:
            spell_damage_type = (
                damage_info.get("damage_type")
                if isinstance(damage_info, dict)
                else damage_info.damage_type
            )
        else:
            spell_damage_type = None

        # Process each target
        target_results = []
        for target in targets:
            # Target makes saving throw
            save_result = target.make_saving_throw(
                ability=save_ability,
                dc=save_dc,
                advantage=False,
                disadvantage=False,
                event_bus=event_bus,
            )

            # Determine damage based on save result
            if save_result["success"]:
                if on_success == "half":
                    damage = base_damage // 2
                elif on_success == "none" or on_success == "negates":
                    damage = 0
                else:
                    damage = base_damage  # Unknown effect, take full damage
            else:
                damage = base_damage

            # Route the post-save damage through the per-type modifier
            # chokepoint so the target's Resistance / Immunity to the
            # spell's `damage_type` scales the final amount. SRD: the
            # save reduction (half-on-success) is a damage adjustment
            # that applies BEFORE Resistance per the Order-of-
            # Application rule; #468 will codify the ordering across
            # the full pipeline.
            # Environment context (SRD § Underwater Combat: underwater
            # grants Fire Resistance, #518) is sourced from game_state
            # when available.
            target_environment = (
                game_state.creature_environment(target)
                if game_state is not None and hasattr(game_state, "creature_environment")
                else None
            )
            damage = self._apply_damage_modifiers(
                target, damage, spell_damage_type, environment=target_environment
            )

            # Apply damage if requested
            if apply_damage and damage > 0:
                # Check if target's take_damage accepts event_bus (Character) or not (Creature)
                if (
                    hasattr(target.take_damage, "__code__")
                    and "event_bus" in target.take_damage.__code__.co_varnames
                ):
                    target.take_damage(damage, event_bus=event_bus)
                else:
                    target.take_damage(damage)

            target_results.append(
                {
                    "name": target.name,
                    "roll": save_result["roll"],
                    "modifier": save_result["modifier"],
                    "total": save_result["total"],
                    "success": save_result["success"],
                    "damage": damage,
                    "damage_type": spell_damage_type,
                }
            )

        # Emit spell save event
        if event_bus is not None:
            event = Event(
                type=EventType.SPELL_SAVE,
                data={
                    "spell_id": spell_id,
                    "spell_name": spell_name,
                    "caster": caster.name,
                    "spell_level": spell_level,
                    "slot_level": actual_level,
                    "save_dc": save_dc,
                    "save_ability": save_ability,
                    "targets": target_results,
                },
            )
            event_bus.emit(event)

        return {
            "spell_name": spell_name,
            "caster": caster.name,
            "save_dc": save_dc,
            "save_ability": save_ability,
            "targets": target_results,
        }

    def _roll_spell_save_damage(self, spell, damage_info, base_level: int, cast_level: int) -> int:
        """
        Roll damage for a save-based spell, handling upcasting.

        Args:
            spell: Spell object or dict
            damage_info: SpellDamage object or dict with damage information
            base_level: Base level of the spell
            cast_level: Level of spell slot used to cast

        Returns:
            Total damage rolled
        """
        if not damage_info:
            return 0

        # Get base damage dice
        if hasattr(damage_info, "dice"):
            base_dice = damage_info.dice
            higher_levels = damage_info.higher_levels
        else:
            base_dice = damage_info.get("dice", "1d6")
            higher_levels = damage_info.get("higher_levels")

        # Roll base damage
        damage_roll = self.dice_roller.roll(base_dice)
        total_damage = damage_roll.total

        # Handle upcasting
        if cast_level > base_level and higher_levels:
            extra_levels = cast_level - base_level

            # Parse higher_levels string for damage scaling
            # Common patterns: "1d6 per slot level above 1st", "2d6 per level above 3rd"
            import re

            dice_match = re.search(r"(\d+d\d+)", higher_levels)
            if dice_match:
                extra_dice = dice_match.group(1)
                for _ in range(extra_levels):
                    extra_roll = self.dice_roller.roll(extra_dice)
                    total_damage += extra_roll.total

        return total_damage

    def resolve_spell_hp_pool(
        self, caster, targets: list, spell, upcast_level: int | None = None, event_bus=None
    ) -> dict[str, Any]:
        """
        Resolve a spell that affects creatures based on an HP pool.

        Used for spells like Sleep and Color Spray that roll dice to determine
        how many HP worth of creatures are affected, then apply effects starting
        with the lowest HP creature.

        Args:
            caster: The creature casting the spell
            targets: List of creatures that could be affected
            spell: Spell object or dict containing:
                - "name": spell name
                - "hp_pool": dict with "dice" and optionally "higher_levels"
                - "effect": dict with condition to apply
                - "level": spell level
            upcast_level: Spell slot level used (for upcasting)
            event_bus: Optional EventBus instance for event emission

        Returns:
            Dictionary with spell cast results:
            {
                "spell_name": str,
                "caster": str,
                "hp_pool_rolled": int,
                "hp_pool_remaining": int,
                "affected_targets": [
                    {"name": str, "hp": int, "condition": str},
                    ...
                ],
                "unaffected_targets": [
                    {"name": str, "hp": int, "reason": str},
                    ...
                ]
            }
        """
        from dnd_engine.utils.events import Event, EventType

        # Get spell info
        if hasattr(spell, "name"):
            spell_name = spell.name
            spell_level = spell.level
            hp_pool_info = spell.hp_pool
            effect_info = spell.effect
        else:
            spell_name = spell.get("name", "Unknown Spell")
            spell_level = spell.get("level", 1)
            hp_pool_info = spell.get("hp_pool", {})
            effect_info = spell.get("effect", {})

        # Determine cast level for upcasting
        actual_level = upcast_level if upcast_level else spell_level

        # Roll HP pool
        base_dice = hp_pool_info.get("dice", "5d8")
        hp_pool_roll = self.dice_roller.roll(base_dice)
        hp_pool = hp_pool_roll.total

        # Handle upcasting (Sleep adds 2d8 per level above 1st)
        if actual_level > spell_level:
            extra_levels = actual_level - spell_level
            higher_levels_dice = hp_pool_info.get("higher_levels_dice", "2d8")
            for _ in range(extra_levels):
                extra_roll = self.dice_roller.roll(higher_levels_dice)
                hp_pool += extra_roll.total

        hp_pool_rolled = hp_pool

        # Get condition to apply
        condition = effect_info.get("condition", "unconscious")
        duration = effect_info.get("duration_rounds", 10)  # 1 minute = 10 rounds

        # Get immunity types (undead and constructs are immune to Sleep)
        immune_types = hp_pool_info.get("immune_types", ["undead", "construct"])

        # Filter and sort targets by current HP (ascending)
        valid_targets = []
        immune_targets = []

        for target in targets:
            if not target.is_alive:
                continue

            # Check creature type immunity
            creature_type = getattr(target, "creature_type", None) or getattr(target, "type", "")
            if isinstance(creature_type, str) and creature_type.lower() in immune_types:
                immune_targets.append(
                    {
                        "name": target.name,
                        "hp": target.current_hp,
                        "reason": f"immune ({creature_type})",
                    }
                )
                continue

            valid_targets.append(target)

        # Sort by current HP ascending
        valid_targets.sort(key=lambda t: t.current_hp)

        affected_targets = []
        unaffected_targets = list(immune_targets)  # Start with immune creatures

        # Apply effect to creatures until HP pool is exhausted
        for target in valid_targets:
            if hp_pool >= target.current_hp:
                # Affect this creature
                hp_pool -= target.current_hp

                # Apply the condition with duration
                if hasattr(target, "apply_condition_with_metadata"):
                    target.apply_condition_with_metadata(
                        condition=condition, duration_type="rounds", duration=duration
                    )
                elif hasattr(target, "add_condition"):
                    target.add_condition(condition)

                affected_targets.append(
                    {"name": target.name, "hp": target.current_hp, "condition": condition}
                )
            else:
                # Not enough HP pool remaining
                unaffected_targets.append(
                    {
                        "name": target.name,
                        "hp": target.current_hp,
                        "reason": "not enough HP pool remaining",
                    }
                )

        # Emit event
        if event_bus:
            event = Event(
                type=EventType.SPELL_CAST,
                data={
                    "spell_name": spell_name,
                    "caster": caster.name,
                    "spell_level": spell_level,
                    "slot_level": actual_level,
                    "hp_pool_rolled": hp_pool_rolled,
                    "affected_count": len(affected_targets),
                    "condition": condition,
                },
            )
            event_bus.emit(event)

        return {
            "spell_name": spell_name,
            "caster": caster.name,
            "hp_pool_rolled": hp_pool_rolled,
            "hp_pool_remaining": hp_pool,
            "affected_targets": affected_targets,
            "unaffected_targets": unaffected_targets,
        }
