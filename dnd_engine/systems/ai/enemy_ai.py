# ABOUTME: Main enemy AI controller for combat behavior decisions.
# ABOUTME: Handles condition removal decisions and target selection for enemy creatures.


from dnd_engine.systems.ai.targeting import (
    LowestHPStrategy,
    RecentAttacker,
    TargetingStrategy,
    get_strategy_for_intelligence,
)


class EnemyAI:
    """Handles AI decisions for enemy creatures during combat."""

    def __init__(self, targeting_strategy: TargetingStrategy | None = None):
        """
        Initialize the enemy AI.

        Args:
            targeting_strategy: Strategy to use for target selection.
                               Defaults to LowestHPStrategy if not provided.
        """
        self.targeting_strategy = targeting_strategy or LowestHPStrategy()

    def should_attempt_condition_removal(self, enemy) -> bool:
        """
        Determine if an enemy should attempt to remove a condition instead of attacking.

        Current AI logic:
        - If on_fire and current_hp <= 4 (one more 1d4 could kill), attempt to extinguish
        - Otherwise, attack normally

        Args:
            enemy: The enemy creature with conditions

        Returns:
            True if enemy should attempt condition removal (consumes turn)
        """
        # Check if enemy has the on_fire condition
        if "on_fire" in enemy.conditions:
            # If one more 1d4 damage could kill (HP <= 4), try to extinguish
            if enemy.current_hp <= 4:
                return True

        return False

    def select_target(self, available_targets: list) -> object:
        """
        Select a target from available targets using the configured strategy.

        Args:
            available_targets: List of potential targets (Characters)

        Returns:
            The selected target

        Raises:
            ValueError: If available_targets is empty
        """
        return self.targeting_strategy.select_target(available_targets)

    def select_target_smart(
        self,
        available_targets: list,
        enemy_intelligence: int,
        combat_history: list | None = None,
        enemy_name: str = "",
        retaliation_weight: float | None = None,
    ) -> object:
        """
        Select a target using intelligence-based smart targeting.

        This method creates a SmartTargetingStrategy based on the enemy's
        intelligence and recent combat history, providing more realistic
        AI behavior.

        Args:
            available_targets: List of potential targets (Characters)
            enemy_intelligence: The enemy's INT score (determines behavior)
            combat_history: List of CombatEvent objects to find recent attackers
            enemy_name: Name of the enemy (to find who attacked them)
            retaliation_weight: Optional override for retaliation chance (0.0-1.0)

        Returns:
            The selected target

        Raises:
            ValueError: If available_targets is empty
        """
        # Find who recently attacked this enemy
        recent_attacker = None
        if combat_history and enemy_name:
            recent_attacker = self._find_recent_attacker(combat_history, enemy_name)

        # Create smart strategy based on intelligence
        strategy = get_strategy_for_intelligence(
            intelligence=enemy_intelligence,
            recent_attacker=recent_attacker,
            retaliation_weight=retaliation_weight,
        )

        return strategy.select_target(available_targets)

    def _find_recent_attacker(
        self, combat_history: list, enemy_name: str
    ) -> RecentAttacker | None:
        """
        Find who most recently attacked the specified enemy.

        Searches combat history in reverse order (most recent first)
        to find the most recent attack against this enemy.

        Args:
            combat_history: List of CombatEvent objects
            enemy_name: Name of the enemy to find attackers for

        Returns:
            RecentAttacker info if found, None otherwise
        """
        enemy_name_lower = enemy_name.lower()

        # Search history from most recent to oldest
        for event in reversed(combat_history):
            # Skip non-attack events
            if event.event_type not in ("attack", "spell"):
                continue

            # Check if this enemy was the defender/target
            if event.defender and event.defender.lower() == enemy_name_lower:
                # Only count attacks that dealt damage
                if event.damage > 0:
                    return RecentAttacker(
                        attacker_name=event.attacker,
                        damage_dealt=event.damage,
                        rounds_ago=0,  # Could calculate from timestamps if needed
                    )

        return None
