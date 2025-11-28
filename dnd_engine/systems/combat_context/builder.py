# ABOUTME: Main CombatContextBuilder class for assembling combat action context
# ABOUTME: Coordinates data gathering and builds complete LLM context dictionaries

from typing import Any

from dnd_engine.core.character import Character
from dnd_engine.core.combat import AttackResult
from dnd_engine.core.creature import Creature
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.combat_context.assemblers import (
    get_attacker_race,
    get_defender_armor,
    get_weapon_context,
)

# Number of recent combat actions to include for LLM context
COMBAT_HISTORY_CONTEXT_SIZE = 12


class CombatContextBuilder:
    """
    Service for assembling combat action context for narrative generation.

    This class encapsulates all the logic for gathering data from various sources
    (items, monsters, races, game state) and building complete context dictionaries
    for LLM narrative generation.
    """

    def __init__(self, data_loader: DataLoader, game_state):
        """
        Initialize the context builder.

        Args:
            data_loader: DataLoader for accessing game content data
            game_state: GameState for accessing current game state
        """
        self.data_loader = data_loader
        self.game_state = game_state
        # Cache for monster name -> monster data lookups (performance optimization)
        self._monster_cache: dict[str, dict[str, Any]] | None = None

    def get_monster_by_name(self, name: str) -> dict[str, Any]:
        """
        Get monster data by name with caching for performance.

        Args:
            name: Monster name to look up

        Returns:
            Monster data dictionary, or empty dict if not found
        """
        if self._monster_cache is None:
            # Build cache on first access
            monsters = self.data_loader.load_monsters()
            self._monster_cache = {
                monster_data["name"]: monster_data
                for monster_data in monsters.values()
            }
        return self._monster_cache.get(name, {})

    def build_attack_context(
        self,
        attacker: Character | Creature,
        defender: Character | Creature,
        result: AttackResult,
        action_data: dict[str, Any] | None = None,
        is_spell: bool = False,
    ) -> dict[str, Any]:
        """
        Build complete context dictionary for an attack action.

        This method gathers all necessary context from various sources:
        - Weapon/spell information
        - Attacker race/type
        - Defender armor
        - Location and combat history
        - Battlefield state

        Args:
            attacker: The attacking Character or Creature
            defender: The defending Character or Creature
            result: AttackResult from combat engine
            action_data: Optional action/spell data dict (for enemies/spells)
            is_spell: Whether this is a spell attack

        Returns:
            Complete context dictionary for LLM narrative generation
        """
        # Ensure monster cache is initialized (lazy loading)
        if self._monster_cache is None:
            monsters = self.data_loader.load_monsters()
            self._monster_cache = {
                monster_data["name"]: monster_data
                for monster_data in monsters.values()
            }

        # Get weapon/spell context
        weapon_name, damage_type = get_weapon_context(
            attacker, self.data_loader, action_data
        )

        # Get attacker race/type (with monster cache for performance)
        attacker_race = get_attacker_race(
            attacker, self.data_loader, self._monster_cache
        )

        # Get defender armor (with monster cache for performance)
        defender_armor = get_defender_armor(
            defender, self.data_loader, self._monster_cache
        )

        # Get location
        current_room = self.game_state.get_current_room()
        location = current_room.get("name", "")

        # Get combat history
        combat_history = self.game_state.get_recent_combat_history(
            count=COMBAT_HISTORY_CONTEXT_SIZE
        )

        # Get battlefield state
        battlefield_state = self.game_state.get_battlefield_state()

        # Detect killing blow - damage will kill the defender
        is_killing_blow = False
        if result.hit and result.damage > 0:
            defender_hp = getattr(defender, "current_hp", getattr(defender, "hp", 0))
            is_killing_blow = result.damage >= defender_hp

        # Build complete context dictionary
        context = {
            "attacker": result.attacker_name,
            "defender": result.defender_name,
            "damage": result.damage,
            "is_critical": result.critical_hit,
            "is_killing_blow": is_killing_blow,
            "hit": result.hit,
            "location": location,
            "weapon": weapon_name,
            "damage_type": damage_type,
            "attacker_race": attacker_race,
            "defender_armor": defender_armor,
            "combat_history": combat_history,
            "battlefield_state": battlefield_state,
        }

        # Add spell flag if applicable
        if is_spell:
            context["is_spell"] = True

        return context
