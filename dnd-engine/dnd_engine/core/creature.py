# ABOUTME: Base Creature class representing any living entity in the game
# ABOUTME: Handles HP, abilities, conditions, damage, and healing

from dataclasses import dataclass


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
    ):
        """
        Initialize a creature.

        Args:
            name: Creature's name
            max_hp: Maximum hit points
            ac: Armor class (target number for attacks)
            abilities: Ability scores (STR, DEX, CON, INT, WIS, CHA)
            current_hp: Starting HP (defaults to max_hp if not specified)
            speed: Movement speed in feet per round (default 30 ft)
        """
        self.name = name
        self.max_hp = max_hp
        self.current_hp = current_hp if current_hp is not None else max_hp
        self._base_ac = ac  # Store base AC (before modifiers from spells/effects)
        self.abilities = abilities
        self.speed = speed  # Movement speed in feet (5 ft = 1 grid square)
        # Condition tracking with metadata for duration and repeat saves
        # Maps condition name -> metadata dict
        self.active_conditions: dict[str, dict] = {}

    @property
    def is_alive(self) -> bool:
        """Check if the creature is alive (HP > 0)"""
        return self.current_hp > 0

    @property
    def initiative_modifier(self) -> int:
        """Initiative modifier (uses Dexterity)"""
        return self.abilities.dex_mod

    @property
    def ac(self) -> int:
        """
        Base armor class (without spell modifiers).

        For effective AC including active effects like Mage Armor or Shield,
        use GameState.get_effective_ac(creature) instead.
        """
        return self._base_ac

    @ac.setter
    def ac(self, value: int) -> None:
        """Set base armor class."""
        self._base_ac = value

    def take_damage(self, amount: int) -> None:
        """
        Apply damage to the creature.

        HP cannot go below 0.

        Args:
            amount: Amount of damage to apply
        """
        self.current_hp = max(0, self.current_hp - amount)

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

    def add_condition(self, condition: str) -> None:
        """
        Add a basic condition to the creature (e.g., 'prone', 'stunned').
        For conditions with duration/repeat saves, use apply_condition_with_metadata().

        Args:
            condition: Name of the condition to add
        """
        condition_name = condition.lower()
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
            event_bus: Optional EventBus instance to emit saving throw event

        Returns:
            Dictionary with:
            - "success": bool (total >= dc)
            - "roll": int (the d20 roll before modifier)
            - "modifier": int (ability modifier)
            - "total": int (roll + modifier)
            - "dc": int (the DC that was beaten)
            - "ability": str (the ability that was saved with, in short form)

        Raises:
            ValueError: If ability name is invalid
        """
        from dnd_engine.core.dice import DiceRoller

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

        # Roll the saving throw
        roller = DiceRoller()
        roll_result = roller.roll("d20", advantage=advantage, disadvantage=disadvantage)

        # Calculate total
        total = roll_result.total + modifier

        # Determine success
        success = total >= dc

        # Create result dict
        result = {
            "success": success,
            "roll": roll_result.rolls[0]
            if len(roll_result.rolls) == 1
            else max(roll_result.rolls)
            if advantage
            else min(roll_result.rolls),
            "modifier": modifier,
            "total": total,
            "dc": dc,
            "ability": ability_short,
        }

        return result

    def __str__(self) -> str:
        """String representation of the creature"""
        status = "alive" if self.is_alive else "dead"
        return f"{self.name} (HP: {self.current_hp}/{self.max_hp}, AC: {self._base_ac}, {status})"
