# ABOUTME: Main enemy AI controller for combat behavior decisions.
# ABOUTME: Handles condition removal decisions and target selection for enemy creatures.


from dnd_engine.systems.ai.targeting import LowestHPStrategy, TargetingStrategy


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
