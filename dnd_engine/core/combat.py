# ABOUTME: Combat engine for resolving attacks and damage in D&D 5E
# ABOUTME: Handles attack rolls, critical hits, damage calculation, and applying damage to creatures

from dataclasses import dataclass
from typing import Dict, Any, Optional
from dnd_engine.core.dice import DiceRoller
from dnd_engine.core.creature import Creature
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
    sneak_attack_dice: Optional[str] = None  # Sneak attack dice notation (e.g., "2d6")

    @property
    def total_attack(self) -> int:
        """Calculate total attack (roll + bonus)"""
        return self.attack_roll + self.attack_bonus

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
        result += f"{self.attack_roll}+{self.attack_bonus}={self.total_attack} vs AC {self.target_ac} "
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

    def resolve_attack(
        self,
        attacker: Creature,
        defender: Creature,
        attack_bonus: int,
        damage_dice: str,
        advantage: bool = False,
        disadvantage: bool = False,
        apply_damage: bool = False,
        event_bus = None,
        action: dict | None = None
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
        8. Apply damage if requested

        Args:
            attacker: The attacking creature
            defender: The defending creature
            attack_bonus: Total attack bonus (proficiency + ability mod + magic, etc.)
            damage_dice: Damage dice notation (e.g., "1d8+3")
            advantage: Roll with advantage (take higher of 2d20)
            disadvantage: Roll with disadvantage (take lower of 2d20)
            apply_damage: If True, apply damage to defender's HP
            event_bus: Optional EventBus instance for event emission

        Returns:
            AttackResult containing full attack details including sneak attack if applicable
        """
        # Roll attack (1d20 + bonus)
        attack_roll_result = self.dice_roller.roll(
            "1d20",
            advantage=advantage,
            disadvantage=disadvantage
        )
        attack_roll = attack_roll_result.total  # The actual d20 result (without bonus)

        # Determine critical hit/miss
        critical_hit = attack_roll == 20
        critical_miss = attack_roll == 1

        # Determine hit/miss
        total_attack = attack_roll + attack_bonus
        hit = total_attack >= defender.ac

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
            if hasattr(attacker, 'can_sneak_attack'):
                if attacker.can_sneak_attack(has_advantage=advantage, has_disadvantage=disadvantage):
                    sneak_attack_dice = attacker.get_sneak_attack_dice()
                    if sneak_attack_dice:
                        sneak_attack_damage = self._calculate_damage(sneak_attack_dice, critical_hit=False)

                        # Emit sneak attack event
                        if event_bus is not None:
                            event = Event(
                                type=EventType.SNEAK_ATTACK,
                                data={
                                    "character": attacker.name,
                                    "dice": sneak_attack_dice,
                                    "damage": sneak_attack_damage
                                }
                            )
                            event_bus.emit(event)

            if apply_damage:
                # Pass event_bus to take_damage for Character instances (death save handling)
                if hasattr(defender, 'take_damage') and hasattr(defender.__class__, 'take_damage'):
                    # Check if defender.take_damage accepts event_bus parameter
                    import inspect
                    sig = inspect.signature(defender.take_damage)
                    if 'event_bus' in sig.parameters:
                        defender.take_damage(damage + sneak_attack_damage, event_bus=event_bus)
                    else:
                        defender.take_damage(damage + sneak_attack_damage)
                else:
                    defender.take_damage(damage + sneak_attack_damage)

            # Process saving throw effects (e.g., ghoul paralysis)
            if action and "saving_throw" in action:
                self._process_saving_throw_effect(
                    action["saving_throw"],
                    attacker,
                    defender,
                    event_bus
                )

        return AttackResult(
            attacker_name=attacker.name,
            defender_name=defender.name,
            attack_roll=attack_roll,
            attack_bonus=attack_bonus,
            target_ac=defender.ac,
            hit=hit,
            damage=damage,
            critical_hit=critical_hit,
            advantage=advantage,
            disadvantage=disadvantage,
            sneak_attack_damage=sneak_attack_damage,
            sneak_attack_dice=sneak_attack_dice
        )

    def _calculate_damage(self, damage_dice: str, critical_hit: bool) -> int:
        """
        Calculate damage from dice notation.

        For critical hits, damage dice are doubled (but not modifiers).
        Example: 1d8+3 becomes 2d8+3 on a crit.

        Args:
            damage_dice: Damage dice notation (e.g., "1d8+3")
            critical_hit: Whether this is a critical hit

        Returns:
            Total damage
        """
        if critical_hit:
            # Double the dice (but not the modifier)
            damage_dice = self._double_damage_dice(damage_dice)

        damage_roll = self.dice_roller.roll(damage_dice)
        return damage_roll.total

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
        pattern = re.compile(r'^(\d*)d(\d+)(([+-])(\d+))?$', re.IGNORECASE)
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

    def resolve_saving_throw_effect(
        self,
        target: Creature,
        save_ability: str,
        dc: int,
        effect: Dict[str, Any],
        apply_damage: bool = False,
        event_bus=None
    ) -> Dict[str, Any]:
        """
        Resolve an effect that requires a saving throw.

        Handles saving throw mechanics for spells, traps, and environmental hazards.
        If the target succeeds, damage can be reduced or negated based on the effect.

        Args:
            target: The creature making the saving throw
            save_ability: Ability to save with (e.g., "str", "dex", "con", "int", "wis", "cha")
            dc: Difficulty class for the save
            effect: Dictionary containing effect details:
                - "damage_dice": str (e.g., "8d6") - damage dice notation
                - "damage_type": str (e.g., "fire", "poison") - optional, for description
                - "half_on_success": bool (optional) - if True, success halves damage
                - "negate_on_success": bool (optional) - if True, success negates all damage
            apply_damage: If True, apply damage to target's HP
            event_bus: Optional EventBus instance for event emission

        Returns:
            Dictionary with:
            - "save_result": dict (result from make_saving_throw)
            - "damage": int (damage dealt or would be dealt)
            - "damage_taken": int (actual damage taken, considering success/failure)
            - "effect": str (description of what happened)

        Raises:
            ValueError: If target doesn't have make_saving_throw method
        """
        # Check if target is a Character with make_saving_throw capability
        if not hasattr(target, 'make_saving_throw'):
            raise ValueError(f"{target.name} cannot make saving throws")

        # Make the saving throw
        save_result = target.make_saving_throw(
            ability=save_ability,
            dc=dc,
            event_bus=event_bus
        )

        # Calculate damage
        damage_dice = effect.get("damage_dice", "1d6")
        damage = self._calculate_damage(damage_dice, critical_hit=False)

        # Determine damage taken based on save result
        damage_taken = damage
        effect_description = ""

        if save_result["success"]:
            if effect.get("negate_on_success", False):
                # Success completely negates the effect
                damage_taken = 0
                effect_description = f"Success! The effect is completely negated."
            elif effect.get("half_on_success", False):
                # Success halves the damage
                damage_taken = damage // 2
                effect_description = f"Success! Damage reduced to {damage_taken} (half of {damage})."
            else:
                # Success but still full damage (rare but possible)
                effect_description = f"Success on the save, but the effect still deals {damage} damage."
        else:
            # Failure takes full damage
            effect_description = f"Failed save. Takes {damage} damage."

        # Apply damage if requested
        if apply_damage:
            # Pass event_bus to take_damage for Character instances (death save handling)
            if hasattr(target, 'take_damage'):
                import inspect
                sig = inspect.signature(target.take_damage)
                if 'event_bus' in sig.parameters:
                    target.take_damage(damage_taken, event_bus=event_bus)
                else:
                    target.take_damage(damage_taken)
            else:
                target.take_damage(damage_taken)

        return {
            "save_result": save_result,
            "damage": damage,
            "damage_taken": damage_taken,
            "effect": effect_description
        }

    def _process_saving_throw_effect(
        self,
        saving_throw_data: dict,
        attacker: Creature,
        defender: Creature,
        event_bus=None
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

        save_result = defender.make_saving_throw(
            ability=ability,
            dc=dc,
            event_bus=event_bus
        )

        # Emit saving throw event
        if event_bus:
            event_bus.emit(Event(
                type=EventType.SAVING_THROW,
                data={
                    "creature": defender.name,
                    "ability": ability,
                    "dc": dc,
                    "result": save_result
                }
            ))

        # Apply effect on failure
        if not save_result["success"]:
            on_fail = saving_throw_data.get("on_fail", {})
            condition = on_fail.get("condition")

            if condition:
                # Apply condition with metadata
                defender.apply_condition_with_metadata(
                    condition=condition,
                    duration_type=on_fail.get("duration_type", "permanent"),
                    duration=on_fail.get("duration", 0),
                    dc=dc,
                    ability=ability,
                    allow_repeat_save=on_fail.get("allow_repeat_save", False),
                    repeat_timing=on_fail.get("repeat_timing", "end_of_turn")
                )

                # Emit condition applied event
                if event_bus:
                    event_bus.emit(Event(
                        type=EventType.CONDITION_APPLIED,
                        data={
                            "creature": defender.name,
                            "condition": condition,
                            "source": attacker.name,
                            "duration_type": on_fail.get("duration_type"),
                            "duration": on_fail.get("duration")
                        }
                    ))

                return {
                    "save_result": save_result,
                    "condition_applied": condition
                }

        return {
            "save_result": save_result,
            "condition_applied": None
        }

    def resolve_spell_attack(
        self,
        caster: Creature,
        target: Creature,
        spell: Dict[str, Any],
        spellcasting_ability: str,
        advantage: bool = False,
        disadvantage: bool = False,
        apply_damage: bool = False,
        event_bus=None
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
        if not hasattr(caster, 'get_spell_attack_bonus'):
            raise ValueError(f"{caster.name} cannot cast spells (no spell attack bonus)")

        spell_attack_bonus = caster.get_spell_attack_bonus(spellcasting_ability)

        # Get damage dice from spell
        damage_data = spell.get("damage", {})
        base_damage_dice = damage_data.get("dice", "1d6")
        damage_type = damage_data.get("damage_type", "force")

        # Scale cantrip damage if this is a cantrip (level 0)
        if spell.get("level", 0) == 0 and hasattr(caster, 'scale_cantrip_damage'):
            damage_dice = caster.scale_cantrip_damage(base_damage_dice)
        else:
            damage_dice = base_damage_dice

        # Use the existing resolve_attack method for the mechanics
        result = self.resolve_attack(
            attacker=caster,
            defender=target,
            attack_bonus=spell_attack_bonus,
            damage_dice=damage_dice,
            advantage=advantage,
            disadvantage=disadvantage,
            apply_damage=apply_damage,
            event_bus=event_bus
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
                    "target_ac": target.ac,
                    "hit": result.hit,
                    "critical_hit": result.critical_hit,
                    "damage": result.damage,
                    "damage_type": damage_type,
                    "attack_type": "spell"
                }
            )
            event_bus.emit(event)

        return result

    def resolve_spell_save(
        self,
        caster,
        targets: list,
        spell,
        upcast_level: Optional[int] = None,
        apply_damage: bool = False,
        event_bus=None
    ) -> Dict[str, Any]:
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
        if hasattr(spell, 'name'):
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
        if hasattr(save_info, 'ability'):
            save_ability = save_info.ability
            on_success = save_info.on_success
        else:
            save_ability = save_info.get("ability")
            on_success = save_info.get("on_success", "half")

        # Get caster's spell save DC
        if not hasattr(caster, 'get_spell_save_dc'):
            raise ValueError(f"{caster.name} cannot cast spells (no spell save DC)")

        save_dc = caster.get_spell_save_dc()

        # Determine actual spell slot level (for upcasting)
        actual_level = upcast_level if upcast_level is not None else spell_level

        # Roll damage once for the spell
        base_damage = self._roll_spell_save_damage(spell, damage_info, spell_level, actual_level)

        # Process each target
        target_results = []
        for target in targets:
            # Target makes saving throw
            save_result = target.make_saving_throw(
                ability=save_ability,
                dc=save_dc,
                advantage=False,
                disadvantage=False,
                event_bus=event_bus
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

            # Apply damage if requested
            if apply_damage and damage > 0:
                # Check if target's take_damage accepts event_bus (Character) or not (Creature)
                if hasattr(target.take_damage, '__code__') and 'event_bus' in target.take_damage.__code__.co_varnames:
                    target.take_damage(damage, event_bus=event_bus)
                else:
                    target.take_damage(damage)

            # Get damage type
            if damage_info:
                damage_type = damage_info.get("damage_type") if isinstance(damage_info, dict) else damage_info.damage_type
            else:
                damage_type = None

            target_results.append({
                "name": target.name,
                "roll": save_result["roll"],
                "modifier": save_result["modifier"],
                "total": save_result["total"],
                "success": save_result["success"],
                "damage": damage,
                "damage_type": damage_type
            })

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
                    "targets": target_results
                }
            )
            event_bus.emit(event)

        return {
            "spell_name": spell_name,
            "caster": caster.name,
            "save_dc": save_dc,
            "save_ability": save_ability,
            "targets": target_results
        }

    def _roll_spell_save_damage(
        self,
        spell,
        damage_info,
        base_level: int,
        cast_level: int
    ) -> int:
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
        if hasattr(damage_info, 'dice'):
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
            dice_match = re.search(r'(\d+d\d+)', higher_levels)
            if dice_match:
                extra_dice = dice_match.group(1)
                for _ in range(extra_levels):
                    extra_roll = self.dice_roller.roll(extra_dice)
                    total_damage += extra_roll.total

        return total_damage
