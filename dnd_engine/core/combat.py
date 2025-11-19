# ABOUTME: Combat engine for resolving attacks and damage in D&D 5E
# ABOUTME: Handles attack rolls, critical hits, damage calculation, and applying damage to creatures

from dataclasses import dataclass
from typing import Dict, Any, Optional
from dnd_engine.core.dice import DiceRoller, DiceRoll
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
        event_bus = None
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

    def resolve_spell_save(
        self,
        caster,
        targets: list,
        spell_data: Dict[str, Any],
        upcast_level: Optional[int] = None,
        apply_damage: bool = False,
        event_bus=None
    ) -> Dict[str, Any]:
        """
        Resolve a spell that requires saving throws.

        Handles spell save mechanics including:
        - Calculating spell save DC from caster
        - Rolling damage (with upcasting support)
        - Applying saves for each target
        - Half damage on success or negating effects

        Args:
            caster: Character casting the spell (must have spell_save_dc property)
            targets: List of creatures targeted by the spell
            spell_data: Dictionary containing spell information (from spells.json)
            upcast_level: Spell slot level used (None = base spell level)
            apply_damage: If True, apply damage to targets
            event_bus: Optional EventBus instance for event emission

        Returns:
            Dictionary with:
            - "spell_id": str (spell ID)
            - "spell_name": str (spell name)
            - "caster": str (caster name)
            - "save_dc": int (DC for the save)
            - "save_ability": str (ability used for save)
            - "targets": list of dicts, each containing:
                - "name": str (target name)
                - "save_result": dict (result from make_saving_throw)
                - "damage_rolled": int (damage before save)
                - "damage_taken": int (actual damage taken)
                - "effect": str (description of what happened)

        Raises:
            ValueError: If spell doesn't have saving throw, or caster lacks spell_save_dc
        """
        # Validate spell has saving throw
        if "saving_throw" not in spell_data or spell_data["saving_throw"] is None:
            raise ValueError(f"Spell '{spell_data.get('name', 'unknown')}' does not require a saving throw")

        # Get spell save DC from caster
        if not hasattr(caster, 'spell_save_dc'):
            raise ValueError(f"{caster.name} does not have spell save DC (not a spellcaster)")

        spell_id = spell_data["id"]
        spell_name = spell_data["name"]
        spell_level = spell_data["level"]
        save_dc = caster.spell_save_dc
        save_ability = spell_data["saving_throw"]["ability"]
        on_success = spell_data["saving_throw"]["on_success"]

        # Roll damage once (all targets get the same damage roll)
        damage_rolled = 0
        damage_type = None
        if "damage" in spell_data and spell_data["damage"] is not None:
            damage_rolled = self._roll_spell_save_damage(
                spell_data,
                spell_level,
                upcast_level
            )
            damage_type = spell_data["damage"].get("damage_type", "")

        # Process each target
        target_results = []
        for target in targets:
            # Check if target can make saving throws
            if not hasattr(target, 'make_saving_throw'):
                # Skip targets that can't make saves (objects, etc.)
                continue

            # Make saving throw
            save_result = target.make_saving_throw(
                ability=save_ability,
                dc=save_dc,
                event_bus=event_bus
            )

            # Determine damage taken based on save result and spell effect
            damage_taken = damage_rolled
            effect_description = ""

            if save_result["success"]:
                if on_success == "half":
                    # Success halves damage
                    damage_taken = damage_rolled // 2
                    effect_description = f"Saved! Takes {damage_taken} {damage_type} damage (half of {damage_rolled})"
                elif on_success == "none" or on_success == "negates":
                    # Success negates all damage/effects
                    damage_taken = 0
                    effect_description = f"Saved! No damage taken"
                else:
                    # Other effects (rare)
                    effect_description = f"Saved, but takes {damage_taken} {damage_type} damage"
            else:
                # Failed save - full damage
                effect_description = f"Failed save! Takes {damage_taken} {damage_type} damage"

            # Apply damage if requested
            if apply_damage and damage_taken > 0:
                import inspect
                if hasattr(target, 'take_damage'):
                    sig = inspect.signature(target.take_damage)
                    if 'event_bus' in sig.parameters:
                        target.take_damage(damage_taken, event_bus=event_bus)
                    else:
                        target.take_damage(damage_taken)

            target_results.append({
                "name": target.name,
                "save_result": save_result,
                "damage_rolled": damage_rolled,
                "damage_taken": damage_taken,
                "effect": effect_description
            })

        # Emit spell save event
        if event_bus is not None:
            from dnd_engine.utils.events import Event, EventType
            event = Event(
                type=EventType.SPELL_CAST,
                data={
                    "caster": caster.name,
                    "spell_id": spell_id,
                    "spell_name": spell_name,
                    "spell_level": spell_level,
                    "upcast_level": upcast_level,
                    "save_dc": save_dc,
                    "save_ability": save_ability,
                    "targets": [
                        {
                            "name": tr["name"],
                            "saved": tr["save_result"]["success"],
                            "damage": tr["damage_taken"]
                        }
                        for tr in target_results
                    ]
                }
            )
            event_bus.emit(event)

        return {
            "spell_id": spell_id,
            "spell_name": spell_name,
            "caster": caster.name,
            "save_dc": save_dc,
            "save_ability": save_ability,
            "targets": target_results
        }

    def _roll_spell_save_damage(
        self,
        spell_data: Dict[str, Any],
        base_level: int,
        upcast_level: Optional[int] = None
    ) -> int:
        """
        Roll damage for a spell with saving throw.

        Handles damage scaling when casting at higher levels (upcasting).

        Args:
            spell_data: Dictionary containing spell information
            base_level: Base level of the spell
            upcast_level: Level of spell slot used (None = base level)

        Returns:
            Total damage rolled

        Raises:
            ValueError: If spell has no damage
        """
        if "damage" not in spell_data or spell_data["damage"] is None:
            raise ValueError(f"Spell '{spell_data.get('name', 'unknown')}' has no damage")

        damage_info = spell_data["damage"]
        base_dice = damage_info["dice"]

        # Check if spell is being upcast
        actual_level = upcast_level if upcast_level is not None else base_level

        # Calculate additional damage from upcasting
        if actual_level > base_level and "higher_levels" in damage_info:
            higher_levels_text = damage_info["higher_levels"]
            # Parse the higher_levels text to determine scaling
            # Common formats: "1d6 per slot level above 3rd", "1d8 for each slot level above 1st"

            import re
            # Match patterns like "1d6 per slot level" or "1d8 for each slot level"
            match = re.search(r'(\d+d\d+)\s+(?:per|for each)\s+(?:slot )?level', higher_levels_text, re.IGNORECASE)

            if match:
                bonus_dice = match.group(1)
                levels_above = actual_level - base_level

                # Roll base damage + bonus damage for each level above
                total_damage = self.dice_roller.roll(base_dice).total
                for _ in range(levels_above):
                    total_damage += self.dice_roller.roll(bonus_dice).total

                return total_damage

        # No upcasting or couldn't parse - just roll base damage
        return self.dice_roller.roll(base_dice).total

    def _get_targets_in_area(
        self,
        all_targets: list,
        area_description: str,
        selected_targets: Optional[list] = None
    ) -> list:
        """
        Get targets affected by an area of effect spell.

        MVP implementation: Returns selected targets (player chooses who is affected).
        Future: Automatically calculate based on positioning and area shape.

        Args:
            all_targets: All possible targets (enemies, allies, etc.)
            area_description: Description of AOE (e.g., "20-foot radius sphere")
            selected_targets: Targets selected by player (None = all targets)

        Returns:
            List of creatures in the affected area
        """
        # MVP: Return selected targets or all targets
        if selected_targets is not None:
            return selected_targets
        else:
            return all_targets
