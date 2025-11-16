# ABOUTME: Combat engine for resolving attacks and damage in D&D 5E
# ABOUTME: Handles attack rolls, critical hits, damage calculation, and applying damage to creatures

from dataclasses import dataclass
from dnd_engine.core.dice import DiceRoller, DiceRoll
from dnd_engine.core.creature import Creature


@dataclass
class AttackResult:
    """
    Result of an attack roll.

    Contains all information about an attack: the roll, bonuses, hit/miss status,
    damage dealt, and special conditions (critical hit, advantage, etc.).
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

    @property
    def total_attack(self) -> int:
        """Calculate total attack (roll + bonus)"""
        return self.attack_roll + self.attack_bonus

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
        apply_damage: bool = False
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
        7. Apply damage if requested

        Args:
            attacker: The attacking creature
            defender: The defending creature
            attack_bonus: Total attack bonus (proficiency + ability mod + magic, etc.)
            damage_dice: Damage dice notation (e.g., "1d8+3")
            advantage: Roll with advantage (take higher of 2d20)
            disadvantage: Roll with disadvantage (take lower of 2d20)
            apply_damage: If True, apply damage to defender's HP

        Returns:
            AttackResult containing full attack details
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
        if hit:
            damage = self._calculate_damage(damage_dice, critical_hit)

            if apply_damage:
                defender.take_damage(damage)

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
            disadvantage=disadvantage
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
