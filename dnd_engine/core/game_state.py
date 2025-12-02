# ABOUTME: Central game state manager coordinating all game systems
# ABOUTME: Manages dungeon exploration, combat state, player actions, and game flow

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dnd_engine.core.campaign_progress import CampaignProgress, CampaignProgressTracker
from dnd_engine.core.character import Character
from dnd_engine.core.combat import AttackResult, CombatEngine
from dnd_engine.core.creature import Creature
from dnd_engine.core.dice import DiceRoller, format_dice_with_modifier
from dnd_engine.core.party import Party
from dnd_engine.core.npc_manager import NPCManager
from dnd_engine.core.quest import QuestManager
from dnd_engine.core.room_registry import RoomRegistry
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.action_economy import ActionType
from dnd_engine.systems.ai import EnemyAI
from dnd_engine.systems.condition_manager import ConditionManager
from dnd_engine.systems.initiative import InitiativeTracker
from dnd_engine.systems.inventory import EquipmentSlot
from dnd_engine.systems.time_manager import ActiveEffect, EffectType, TimeManager
from dnd_engine.utils.events import Event, EventBus, EventType

logger = logging.getLogger(__name__)

# Direction reversal mapping for fleeing combat
REVERSE_DIRECTIONS = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "up": "down",
    "down": "up"
}


@dataclass
class CombatEvent:
    """
    Structured combat event for history tracking.

    Records a single combat action with all relevant details for
    narrative context, analytics, and replay functionality.
    """
    timestamp: float
    event_type: str  # "attack", "spell", "miss", "death", "damage", "heal"
    attacker: str
    defender: str | None = None
    damage: int = 0
    critical: bool = False
    description: str = ""  # Human-readable summary
    details: dict[str, Any] = field(default_factory=dict)  # Additional event-specific data


@dataclass
class CombatantStatus:
    """
    Status snapshot of a single combatant in combat.

    Used for battlefield state queries and LLM context.
    """
    name: str
    display_name: str  # Includes combat number if applicable (e.g., "Goblin 2")
    current_hp: int
    max_hp: int
    is_alive: bool
    conditions: list[str]
    is_player: bool
    ac: int = 0  # Armor class


@dataclass
class BattlefieldState:
    """
    Complete snapshot of the battlefield state.

    Provides a clean, structured view of combat state for
    UI display, LLM context, analytics, etc.
    """
    party_combatants: list[CombatantStatus]
    enemy_combatants: list[CombatantStatus]
    round_number: int
    current_turn: str  # Name of creature whose turn it is
    in_combat: bool


class CombatItemResult:
    """Result of using a combat attack item (thrown weapon)."""
    def __init__(
        self,
        success: bool,
        attack_result: AttackResult | None,
        item_name: str,
        action_type: ActionType,
        special_effects: list[str] | None = None,
        error_message: str | None = None
    ):
        self.success = success
        self.attack_result = attack_result
        self.item_name = item_name
        self.action_type = action_type
        self.special_effects = special_effects or []
        self.error_message = error_message


@dataclass
class CombatItemUseResult:
    """
    Result of using a consumable item during combat (non-attack items).

    Contains all information needed for UI display without requiring
    the CLI to perform any game logic calculations.
    """
    success: bool
    item_name: str
    action_type: ActionType
    user_name: str
    target_name: str

    # Effect details (from ItemEffectResult)
    effect_type: str | None = None
    effect_message: str | None = None
    effect_amount: int = 0

    # HP tracking for healing display
    hp_before: int | None = None
    hp_after: int | None = None

    # Error handling
    error_message: str | None = None


@dataclass
class CombatSpellResult:
    """
    Result of casting a spell in combat.

    Contains all information needed for UI display without requiring
    the CLI to perform any game logic calculations.
    """
    success: bool
    spell_name: str
    caster_name: str
    targets: list[str]
    is_area_effect: bool
    spell_type: str  # "attack", "save", "auto_hit", "buff"

    # Attack results (spell_type == "attack")
    attack_result: AttackResult | None = None

    # Save results (spell_type == "save")
    save_results: list[dict[str, Any]] | None = None
    save_dc: int | None = None
    save_ability: str | None = None

    # Damage (all damaging spell types)
    total_damage: int = 0
    damage_type: str | None = None

    # Concentration tracking
    broke_concentration: str | None = None  # Previous spell name if broken
    now_concentrating: bool = False

    # Target concentration breaks (from damage dealt)
    target_concentration_breaks: list[dict[str, Any]] = field(default_factory=list)

    # Deaths
    killed_targets: list[str] = field(default_factory=list)

    # HP Pool results (spell_type == "hp_pool", e.g., Sleep)
    hp_pool_rolled: int | None = None
    hp_pool_remaining: int | None = None
    affected_targets: list[dict[str, Any]] | None = None
    unaffected_targets: list[dict[str, Any]] | None = None

    # Error handling
    error: str | None = None

    # Resources consumed (for middleware auto-refund tracking)
    resources_consumed: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class PlayerAttackResult:
    """
    Result of a player executing an attack with their equipped weapon.

    Contains all information needed for UI display without requiring
    the CLI to perform any game logic calculations.
    """
    success: bool
    attack_result: AttackResult
    attacker_name: str
    target_name: str
    weapon_name: str  # "unarmed strike" if no weapon equipped

    # Concentration break info (if target was concentrating)
    concentration_broken: dict[str, Any] | None = None

    # Target death
    target_killed: bool = False

    # Context for LLM narrative enhancement
    narrative_context: dict[str, Any] = field(default_factory=dict)

    # Error handling
    error: str | None = None


@dataclass
class StabilizeResult:
    """
    Result of attempting to stabilize a dying character.

    Contains all information needed for UI display without requiring
    the CLI to perform any game logic calculations.
    """
    success: bool
    helper_name: str
    target_name: str

    # Skill check details
    roll: int
    modifier: int
    total: int
    dc: int


class EnemyTurnAction(Enum):
    """Actions an enemy can take during their turn."""
    ATTACK = "attack"
    CONDITION_REMOVAL = "condition_removal"
    INCAPACITATED = "incapacitated"
    DIED_START_OF_TURN = "died_start_of_turn"
    NO_TARGETS = "no_targets"
    NO_VALID_ATTACK = "no_valid_attack"


@dataclass
class ConditionRemovalOption:
    """
    Option for a creature to attempt removing a condition.

    Contains all information needed for UI to display the removal prompt
    without requiring the CLI to query the game engine multiple times.
    """
    condition_id: str
    condition_name: str
    ability: str
    dc: int
    action_cost: ActionType
    description: str


@dataclass
class ConditionRemovalResult:
    """Result of attempting to remove a condition."""
    condition_id: str
    attempted: bool
    success: bool
    message: str
    action_consumed: ActionType | None = None


@dataclass
class TurnEffectResult:
    """Result of a turn-start or turn-end effect."""
    effect_type: str  # "damage", "condition_expired", etc.
    condition_id: str
    message: str
    damage: int = 0
    creature_died: bool = False


@dataclass
class EnemyTurnResult:
    """
    Result of processing an enemy's turn.

    Contains all information needed for UI display without requiring
    the CLI to perform any game logic calculations.
    """
    enemy_name: str
    enemy_display_name: str
    action_taken: EnemyTurnAction

    # Attack details (when action_taken == ATTACK)
    attack_result: AttackResult | None = None
    target_name: str | None = None
    target_killed: bool = False
    action_data: dict[str, Any] | None = None  # Monster action used

    # Saving throw results from attack (e.g., poison effects)
    saving_throw_triggered: bool = False
    save_ability: str | None = None
    save_dc: int | None = None
    save_succeeded: bool | None = None
    conditions_applied: list[str] = field(default_factory=list)

    # Condition removal (when action_taken == CONDITION_REMOVAL)
    condition_removal: ConditionRemovalResult | None = None

    # Concentration break on target
    concentration_broken: dict[str, Any] | None = None

    # Turn effects
    turn_start_effects: list[TurnEffectResult] = field(default_factory=list)
    turn_end_effects: list[TurnEffectResult] = field(default_factory=list)

    # Incapacitation details
    incapacitating_conditions: list[str] = field(default_factory=list)

    # Narrative context for LLM enhancement
    narrative_context: dict[str, Any] = field(default_factory=dict)

    # Turn management
    turn_advanced: bool = True  # Whether initiative moved to next turn
    combat_ended: bool = False  # Whether combat ended this turn

    # Error handling
    error: str | None = None


@dataclass
class CharacterRestResult:
    """Result of a single character's rest."""
    character_name: str
    hp_recovered: int
    hp_before: int
    hp_after: int
    max_hp: int
    resources_recovered: dict[str, Any]
    can_prepare_spells: bool = False


@dataclass
class PartyRestResult:
    """
    Result of the party taking a rest.

    Contains all information needed for UI display without requiring
    the CLI to perform any game logic calculations.
    """
    rest_type: str  # "short" or "long"
    rest_duration_minutes: int  # 60 for short, 480 for long
    character_results: list[CharacterRestResult]

    @property
    def rest_duration_display(self) -> str:
        """Human-readable rest duration."""
        if self.rest_duration_minutes == 60:
            return "1 hour"
        elif self.rest_duration_minutes == 480:
            return "8 hours"
        else:
            hours = self.rest_duration_minutes // 60
            minutes = self.rest_duration_minutes % 60
            if minutes == 0:
                return f"{hours} hours"
            return f"{hours}h {minutes}m"


@dataclass
class PartyMemberLighting:
    """Lighting information for a single party member."""
    character_name: str
    effective_lighting: str  # "bright", "dim", or "dark"
    has_darkvision: bool


@dataclass
class VisibleItem:
    """Item visible in a room."""
    item_type: str  # "gold", "currency", "item"
    item_id: str | None = None
    item_name: str | None = None
    amount: int | None = None  # For gold type
    gold: int = 0  # For currency type
    silver: int = 0
    copper: int = 0
    platinum: int = 0


@dataclass
class RoomDisplayContext:
    """
    Complete context needed to display a room.

    Encapsulates all game state queries for room display, allowing
    the CLI to focus purely on presentation logic.
    """
    room_id: str
    room_name: str
    description: str
    exits: dict[str, Any]
    monster_names: list[str]
    combat_starting: bool
    base_lighting: str
    party_lighting: list[PartyMemberLighting]
    light_casters: list[str]
    previous_room_id: str | None
    visible_items: list[VisibleItem]
    npc_display_names: list[str]
    room_searched: bool

    # Data for LLM enhancement
    monsters_data: dict[str, Any]
    party_size: int

    def to_llm_dict(self) -> dict[str, Any]:
        """Convert context to dict format for LLM enhancement."""
        return {
            "id": self.room_id,
            "name": self.room_name,
            "description": self.description,
            "monsters": self.monster_names,
            "combat_starting": self.combat_starting,
            "monsters_data": self.monsters_data,
            "party_size": self.party_size,
            "base_lighting": self.base_lighting,
            "party_lighting": [
                {
                    "character": pl.character_name,
                    "lighting": pl.effective_lighting,
                    "has_darkvision": pl.has_darkvision
                }
                for pl in self.party_lighting
            ],
            "light_casters": self.light_casters,
            "previous_room_id": self.previous_room_id
        }


class GameState:
    """
    Central game state manager.

    Coordinates all game systems and maintains the complete game state:
    - Party of player characters
    - Current dungeon and room
    - Combat state and active enemies
    - Game events

    Serves as the single source of truth for the entire game.
    """

    def __init__(
        self,
        party: Party,
        dungeon_name: str,
        event_bus: EventBus | None = None,
        data_loader: DataLoader | None = None,
        dice_roller: DiceRoller | None = None,
        campaign_id: str | None = None,
        campaign_progress: CampaignProgress | None = None
    ):
        """
        Initialize the game state.

        Args:
            party: The party of player characters
            dungeon_name: Name of the dungeon to load
            event_bus: Event bus for game events (creates new if not provided)
            data_loader: Data loader for loading content (creates new if not provided)
            dice_roller: Dice roller (creates new if not provided)
            campaign_id: Optional campaign ID for quest tracking (e.g., "the_unquiet_dead")
            campaign_progress: Optional campaign progress for multi-dungeon campaigns
        """
        self.party = party
        self.event_bus = event_bus or EventBus()
        self.data_loader = data_loader or DataLoader()
        self.dice_roller = dice_roller or DiceRoller()
        # Time tracking system
        self.time_manager = TimeManager(event_bus=self.event_bus)

        # Load dungeon using data_loader (supports mocking in tests)
        self.dungeon_name = dungeon_name  # Store filename for saving
        self.campaign_id = campaign_id

        # Load dungeon - with campaign_id if provided, otherwise try standalone
        self.dungeon = self.data_loader.load_dungeon(dungeon_name, campaign_id)

        # Auto-detect campaign_id from dungeon if not explicitly provided
        if self.campaign_id is None:
            self.campaign_id = self.dungeon.get("campaign_id")

        # Campaign progress for multi-dungeon campaigns
        self.campaign_progress = campaign_progress

        # Campaign tracker for checking completion criteria
        self.campaign_tracker: CampaignProgressTracker | None = None
        if campaign_progress:
            try:
                campaigns_dir = self.data_loader.data_path / "content" / "campaigns"
                if campaigns_dir.exists():
                    self.campaign_tracker = CampaignProgressTracker(campaigns_dir)
            except (AttributeError, TypeError):
                pass

        # Room registry for cross-dungeon navigation
        # May be None if data_path is unavailable (e.g., in tests with mocked loaders)
        self.room_registry: RoomRegistry | None = None
        try:
            content_path = self.data_loader.data_path / "content"
            if self.campaign_id and content_path.exists():
                self.room_registry = RoomRegistry(
                    campaign_id=self.campaign_id,
                    content_path=content_path,
                )
            else:
                # Fallback for test dungeons without campaign
                dungeons_path = content_path / "dungeons"
                if dungeons_path.exists():
                    self.room_registry = RoomRegistry(dungeons_path=dungeons_path)
            # Pre-populate registry cache with current dungeon data
            # so modifications are shared when we return to this dungeon
            if self.room_registry:
                self.room_registry._loaded_dungeons[dungeon_name] = self.dungeon
        except (AttributeError, TypeError):
            # data_path may not exist on mocked loaders
            pass
        self.current_room_id = self.dungeon["start_room"]
        self.previous_room_id: str | None = None  # Track room transitions for narrative

        # Quest tracking system (optional, only if campaign_id is provided)
        self.quest_manager: QuestManager | None = None
        if self.campaign_id:
            try:
                quest_data = self.data_loader.load_quests(self.campaign_id)
                self.quest_manager = QuestManager()
                self.quest_manager.load_quests_from_dict(quest_data)
                # Wire QuestManager to EventBus for event-driven objective tracking
                self.quest_manager.set_event_bus(self.event_bus)

                # Emit initial room enter event to trigger quest auto-activation
                self.event_bus.emit(Event(
                    type=EventType.ROOM_ENTER,
                    data={
                        "room_id": self.current_room_id,
                        "room_name": self.get_current_room()["name"],
                        "dungeon_id": self.dungeon_name,
                    }
                ))
            except FileNotFoundError:
                logger.warning(f"No quest data found for campaign '{self.campaign_id}'")

        # NPC system (optional, only if campaign_id is provided)
        self.npc_manager: NPCManager | None = None
        if self.campaign_id:
            try:
                self.npc_manager = NPCManager(self.campaign_id, self.data_loader)
            except FileNotFoundError:
                logger.warning(f"No NPC data found for campaign '{self.campaign_id}'")

        # Subscribe to quest completion for dungeon unlocking
        self.event_bus.subscribe(EventType.QUEST_COMPLETED, self._on_quest_completed)

        # Combat state
        self.in_combat = False
        self.initiative_tracker: InitiativeTracker | None = None
        self.active_enemies: list[Creature] = []
        self.combat_engine = CombatEngine(self.dice_roller)
        self.combat_history: list[CombatEvent] = []
        self.max_combat_history_size = 50  # Configurable limit

        # Enemy AI and condition management for enemy turn processing
        self.enemy_ai = EnemyAI()
        self.condition_manager = ConditionManager(
            dice_roller=self.dice_roller,
            event_bus=self.event_bus
        )

        # Navigation tracking for flee mechanic
        self.last_entry_direction: str | None = None

        # Action history for narrative context
        self.action_history: list[str] = []

    def start(self) -> None:
        """
        Begin the game.

        Called once after initialization to check the starting room
        for enemies and perform any other game start logic.
        """
        # Check for passive perception features
        self._check_passive_perception()

        # Check for enemies
        self._check_for_enemies()

    def get_current_room(self) -> dict[str, Any]:
        """
        Get the current room data.

        Returns:
            Dictionary containing room information
        """
        return self.dungeon["rooms"][self.current_room_id]

    def mark_room_displayed(self) -> None:
        """
        Mark current room as displayed for narrative transition tracking.

        After displaying a room description, call this to update previous_room_id
        so subsequent "look" commands show "already in room" narrative instead of
        "entering room" narrative.
        """
        self.previous_room_id = self.current_room_id

    def get_effective_lighting(self, character: "Character") -> str:
        """
        Calculate the effective lighting level for a character in the current room.

        Takes into account:
        - Base room lighting
        - Temporary lighting effects (Light spell, torches)
        - Character's darkvision

        Args:
            character: Character to calculate lighting for

        Returns:
            "bright", "dim", or "dark" - the effective lighting level
        """
        room = self.get_current_room()
        base_lighting = room.get("lighting", "bright")

        # Check for temporary lighting effects (Light spell, torches, etc.)
        # Look for active lighting effects in the time manager
        from dnd_engine.systems.time_manager import EffectType
        for effect in self.time_manager.active_effects:
            # Check for Light spell
            if effect.effect_type == EffectType.SPELL and effect.source.lower() == "light":
                return "bright"
            # Check for light-providing items (torches, lanterns, etc.)
            if effect.effect_data.get("light_level"):
                return effect.effect_data["light_level"]

        # If room is dark and character has darkvision, treat as dim
        if base_lighting == "dark" and character.darkvision_range > 0:
            return "dim"

        # Otherwise, return base room lighting
        return base_lighting

    def _apply_lighting_penalties(
        self,
        character: "Character",
        skill: str,
        dc: int,
        action: str
    ) -> tuple[bool, bool, dict[str, Any] | None]:
        """
        Apply lighting penalties to a skill check.

        For sight-based checks (Perception) in poor lighting:
        - Dim light: Apply disadvantage
        - Darkness: Auto-fail

        Args:
            character: Character making the check
            skill: Skill being checked
            dc: DC of the check (for event emission in auto-fail case)
            action: Description of the action (for event emission)

        Returns:
            Tuple of (should_continue, has_disadvantage, check_result_if_autofail)
            - should_continue: False if check auto-failed in darkness
            - has_disadvantage: True if check should be made with disadvantage
            - check_result_if_autofail: The failed check result dict if auto-failed, None otherwise
        """
        if skill != "perception":
            return True, False, None

        lighting = self.get_effective_lighting(character)
        if lighting == "dark":
            # In complete darkness, sight-based Perception checks auto-fail
            check_result = {
                "skill": skill,
                "dc": dc,
                "roll": 0,
                "modifier": 0,
                "total": 0,
                "success": False
            }
            # Emit skill check event
            self.event_bus.emit(Event(
                type=EventType.SKILL_CHECK,
                data={
                    "character": character.name,
                    "skill": skill,
                    "dc": dc,
                    "roll": 0,
                    "modifier": 0,
                    "total": 0,
                    "success": False,
                    "action": action,
                    "success_text": None,
                    "failure_text": "You can't see anything in the complete darkness"
                }
            ))
            return False, False, check_result
        elif lighting == "dim":
            return True, True, None

        return True, False, None

    def get_available_actions(self) -> list[str]:
        """
        Get list of available actions in the current state.

        Returns:
            List of action names (e.g., ["move", "attack", "search"])
        """
        if self.in_combat:
            return ["attack", "use_item"]
        else:
            actions = ["move"]
            room = self.get_current_room()
            if room.get("searchable") and not room.get("searched"):
                actions.append("search")
            return actions

    def move(self, direction: str, check_for_enemies: bool = True) -> bool:
        """
        Move the player in a direction.

        Args:
            direction: Direction to move (must match an exit in current room)
            check_for_enemies: Whether to check for enemies after moving (default True)

        Returns:
            True if move was successful, False otherwise
        """
        if self.in_combat:
            return False  # Cannot move during combat

        current_room = self.get_current_room()
        exits = current_room.get("exits", {})

        if direction not in exits:
            return False  # Invalid direction

        # Check if exit is locked
        if self.is_exit_locked(direction):
            return False  # Door is locked

        # Check if exit requirements are met (quest items, etc.)
        req_check = self.check_exit_requirements(direction)
        if not req_check["met"]:
            return False  # Requirements not met

        # Track direction for flee mechanic (before moving)
        self.last_entry_direction = direction

        # Get destination (handle both string and dict formats)
        exit_info = exits[direction]
        if isinstance(exit_info, str):
            new_room_id = exit_info
        else:
            new_room_id = exit_info["destination"]

        # Check if this is a cross-dungeon move
        if new_room_id not in self.dungeon.get("rooms", {}):
            # Room not in current dungeon - use registry to find and load it
            if not self.room_registry:
                logger.warning(f"Room {new_room_id} not in current dungeon and no registry available")
                return False

            new_dungeon_name = self.room_registry.get_dungeon_for_room(new_room_id)
            if new_dungeon_name:
                new_dungeon = self.room_registry.load_dungeon(new_dungeon_name)
                if new_dungeon and new_room_id in new_dungeon.get("rooms", {}):
                    # Switch to new dungeon
                    self.dungeon = new_dungeon
                    self.dungeon_name = new_dungeon_name
                    logger.info(
                        f"Cross-dungeon move: {self.current_room_id} -> {new_room_id} "
                        f"(switched to {new_dungeon_name})"
                    )
                else:
                    logger.warning(f"Room {new_room_id} not found in dungeon {new_dungeon_name}")
                    return False
            else:
                logger.warning(f"No dungeon found for room {new_room_id}")
                return False

        # Track previous room for narrative transitions
        self.previous_room_id = self.current_room_id

        # Move to new room
        self.current_room_id = new_room_id

        # Emit room enter event
        self.event_bus.emit(Event(
            type=EventType.ROOM_ENTER,
            data={
                "room_id": new_room_id,
                "room_name": self.get_current_room()["name"],
                "dungeon_id": self.dungeon_name,
            }
        ))

        # Check for passive perception features on room entry
        self._check_passive_perception()

        # Advance time for movement (10 minutes per room)
        self.time_manager.advance_time(10, reason="room_movement")

        # Check for enemies and start combat if needed (unless explicitly disabled)
        if check_for_enemies:
            self._check_for_enemies()

        return True

    def get_exit_info(self, direction: str) -> dict[str, Any] | None:
        """
        Get exit information for a direction.

        Args:
            direction: Direction to check

        Returns:
            Exit info dict or None if exit doesn't exist
        """
        current_room = self.get_current_room()
        exits = current_room.get("exits", {})

        if direction not in exits:
            return None

        exit_data = exits[direction]

        # Handle backwards compatibility (string exits)
        if isinstance(exit_data, str):
            return {
                "destination": exit_data,
                "locked": False,
                "unlock_methods": []
            }

        # Return dict exit as-is
        return exit_data

    def is_exit_locked(self, direction: str) -> bool:
        """
        Check if an exit is locked.

        Args:
            direction: Direction to check

        Returns:
            True if exit is locked, False otherwise
        """
        exit_info = self.get_exit_info(direction)
        if not exit_info:
            return False

        return exit_info.get("locked", False)

    def party_has_quest_item(self, item_id: str) -> bool:
        """
        Check if any party member has a specific quest item.

        Args:
            item_id: The item ID to check for

        Returns:
            True if any party member has the item
        """
        for character in self.party.characters:
            if character.inventory.has_item(item_id):
                return True
        return False

    def check_exit_requirements(self, direction: str) -> dict[str, Any]:
        """
        Check if exit requirements are met for a direction.

        Args:
            direction: Direction to check

        Returns:
            Dict with:
            - met: bool - Whether all requirements are met
            - missing: list - List of unmet requirement descriptions
        """
        exit_info = self.get_exit_info(direction)
        if not exit_info:
            return {"met": True, "missing": []}

        requires = exit_info.get("requires")
        if not requires:
            return {"met": True, "missing": []}

        missing = []

        # Check quest_item requirement
        if "quest_item" in requires:
            item_id = requires["quest_item"]
            if not self.party_has_quest_item(item_id):
                # Get item name from data loader if available
                item_name = item_id
                if self.data_loader:
                    items_data = self.data_loader.load_items(self.campaign_id)
                    for category in items_data.values():
                        if item_id in category:
                            item_name = category[item_id].get("name", item_id)
                            break
                missing.append(f"Requires: {item_name}")

        return {"met": len(missing) == 0, "missing": missing}

    def is_exit_hidden(self, direction: str) -> bool:
        """
        Check if an exit should be hidden (requirements not met + hidden_until_unlocked).

        Args:
            direction: Direction to check

        Returns:
            True if exit should be hidden from player
        """
        exit_info = self.get_exit_info(direction)
        if not exit_info:
            return False

        # If not marked as hidden_until_unlocked, always show
        if not exit_info.get("hidden_until_unlocked", False):
            return False

        # Check if requirements are met
        req_check = self.check_exit_requirements(direction)
        return not req_check["met"]

    def get_available_exits(self) -> dict[str, Any]:
        """
        Get exits that should be shown to the player.

        Filters out exits that are hidden due to unmet requirements.

        Returns:
            Dict of direction -> exit info for visible exits
        """
        current_room = self.get_current_room()
        all_exits = current_room.get("exits", {})

        visible_exits = {}
        for direction, exit_info in all_exits.items():
            if not self.is_exit_hidden(direction):
                visible_exits[direction] = exit_info

        return visible_exits

    def get_unlock_methods(self, direction: str) -> list[dict[str, Any]]:
        """
        Get available unlock methods for a locked exit.

        Args:
            direction: Direction to check

        Returns:
            List of unlock method dicts, empty list if not locked or no methods
        """
        exit_info = self.get_exit_info(direction)
        if not exit_info:
            return []

        return exit_info.get("unlock_methods", [])

    def attempt_unlock(
        self,
        direction: str,
        method_index: int,
        character: Character
    ) -> dict[str, Any]:
        """
        Attempt to unlock a door using a specific method.

        Args:
            direction: Direction of the locked door
            method_index: Index of the unlock method to use
            character: Character attempting the unlock

        Returns:
            Dict with unlock result:
            - success: bool - Whether unlock succeeded
            - method: dict - The unlock method used
            - skill_check_result: dict - Skill check details (if applicable)
            - reason: str - Failure reason (if failed)
        """
        # Validate exit exists and is locked
        exit_info = self.get_exit_info(direction)
        if not exit_info:
            return {
                "success": False,
                "reason": f"No exit in direction '{direction}'"
            }

        if not exit_info.get("locked", False):
            return {
                "success": False,
                "reason": "Door is not locked"
            }

        # Get unlock methods
        unlock_methods = exit_info.get("unlock_methods", [])
        if method_index < 0 or method_index >= len(unlock_methods):
            return {
                "success": False,
                "reason": "Invalid unlock method"
            }

        method = unlock_methods[method_index]

        # Handle item-based unlocking
        if "requires_item" in method:
            item_id = method["requires_item"]
            # Check if any party member has the item
            for char in self.party.characters:
                if char.inventory.has_item(item_id):
                    # Unlock the door
                    exit_info["locked"] = False

                    # Check if unlock method is loud - alert destination room
                    if not method.get("silent", True):  # Default to silent if not specified
                        destination_room = exit_info.get("destination")
                        if destination_room:
                            self.set_room_alerted(destination_room, f"loud unlock from {self.current_room_id}")

                    # Emit event
                    self.event_bus.emit(Event(
                        type=EventType.SKILL_CHECK,
                        data={
                            "character": character.name,
                            "action": f"unlock door with {item_id}",
                            "success": True,
                            "automatic": True
                        }
                    ))
                    return {
                        "success": True,
                        "method": method,
                        "automatic": True
                    }

            return {
                "success": False,
                "method": method,
                "reason": f"Party does not have {item_id}"
            }

        # Handle skill-based unlocking
        if "skill" in method:
            skill = method["skill"]
            dc = method["dc"]

            # Check tool proficiency requirement
            tool_proficiency = method.get("tool_proficiency")
            if tool_proficiency:
                # Load proficiencies data to check if character has the tool
                if not hasattr(character, 'tool_proficiencies') or tool_proficiency not in character.tool_proficiencies:
                    # Character lacks required tool proficiency - they can still attempt but without proficiency bonus
                    pass

            # Load skills data
            skills_data = self.data_loader.load_skills()

            # Make skill check
            check_result = character.make_skill_check(skill, dc, skills_data)

            # Emit skill check event
            self.event_bus.emit(Event(
                type=EventType.SKILL_CHECK,
                data={
                    "character": character.name,
                    "skill": skill,
                    "dc": dc,
                    "roll": check_result["roll"],
                    "modifier": check_result["modifier"],
                    "total": check_result["total"],
                    "success": check_result["success"],
                    "action": method["description"]
                }
            ))

            if check_result["success"]:
                # Unlock the door
                exit_info["locked"] = False

                # Check if unlock method is loud - alert destination room
                if not method.get("silent", True):  # Default to silent if not specified
                    destination_room = exit_info.get("destination")
                    if destination_room:
                        self.set_room_alerted(destination_room, f"loud unlock from {self.current_room_id}")

            return {
                "success": check_result["success"],
                "method": method,
                "skill_check_result": check_result
            }

        return {
            "success": False,
            "reason": "Invalid unlock method configuration"
        }

    def get_examinable_objects(self) -> list[dict[str, Any]]:
        """
        Get list of examinable objects in the current room.

        Returns:
            List of examinable object dicts with id, name, description
        """
        room = self.get_current_room()
        return room.get("examinable_objects", [])

    def get_examinable_exits(self) -> list[str]:
        """
        Get list of exits that can be examined in the current room.

        Returns:
            List of direction names that have examine_checks or are locked
        """
        room = self.get_current_room()
        exits = room.get("exits", {})
        examinable = []

        for direction, exit_data in exits.items():
            # Include exits with examine_checks or locked doors
            if isinstance(exit_data, dict):
                has_examine_checks = exit_data.get("examine_checks")
                is_locked = exit_data.get("locked", False)
                if has_examine_checks or is_locked:
                    examinable.append(direction)

        return examinable

    def examine_exit(
        self,
        direction: str,
        character: Character
    ) -> dict[str, Any]:
        """
        Examine an exit (e.g., listen at a door) with a skill check.

        Args:
            direction: Direction of the exit to examine
            character: Character attempting the examination

        Returns:
            Dict with examination result:
            - success: bool - Whether any check succeeded
            - direction: str - Direction examined
            - results: List[Dict] - Results from each examine check
        """
        # Get exit info
        exit_info = self.get_exit_info(direction)
        if not exit_info:
            return {
                "success": False,
                "error": f"No exit in direction '{direction}'"
            }

        # Check if exit has examine_checks
        examine_checks = exit_info.get("examine_checks", [])

        # If no examine_checks but door is locked, provide locked door info
        if not examine_checks:
            is_locked = exit_info.get("locked", False)
            if is_locked:
                unlock_methods = exit_info.get("unlock_methods", [])
                return {
                    "success": True,
                    "direction": direction,
                    "is_locked": True,
                    "unlock_methods": unlock_methods,
                    "description": f"The door to the {direction} is locked. You notice a sturdy lock mechanism."
                }
            else:
                return {
                    "success": False,
                    "error": f"Exit '{direction}' cannot be examined"
                }

        # Load skills data
        skills_data = self.data_loader.load_skills()

        # Perform all examine checks for this exit
        results = []
        any_success = False

        for check in examine_checks:
            skill = check["skill"]
            dc = check["dc"]
            action = check.get("action", f"examine {direction} exit")

            # Apply lighting penalties for sight-based checks
            should_continue, disadvantage, auto_fail_result = self._apply_lighting_penalties(
                character, skill, dc, action
            )

            if not should_continue:
                # Check auto-failed in darkness
                results.append({
                    "skill": skill,
                    "dc": dc,
                    "action": action,
                    "success": False,
                    "check_result": auto_fail_result
                })
                continue

            # Make skill check
            check_result = character.make_skill_check(skill, dc, skills_data, disadvantage=disadvantage)

            # Emit skill check event
            self.event_bus.emit(Event(
                type=EventType.SKILL_CHECK,
                data={
                    "character": character.name,
                    "skill": skill,
                    "dc": dc,
                    "roll": check_result["roll"],
                    "modifier": check_result["modifier"],
                    "total": check_result["total"],
                    "success": check_result["success"],
                    "action": action,
                    "success_text": check.get("on_success") if check_result["success"] else None,
                    "failure_text": check.get("on_failure") if not check_result["success"] else None
                }
            ))

            results.append({
                "skill": skill,
                "dc": dc,
                "action": action,
                "check_result": check_result,
                "success_text": check.get("on_success") if check_result["success"] else None,
                "failure_text": check.get("on_failure") if not check_result["success"] else None
            })

            if check_result["success"]:
                any_success = True

        return {
            "success": any_success,
            "direction": direction,
            "results": results
        }

    def examine_object(
        self,
        object_id: str,
        character: Character
    ) -> dict[str, Any]:
        """
        Examine an object in the current room with a skill check.

        Args:
            object_id: ID of the object to examine
            character: Character attempting the examination

        Returns:
            Dict with examination result:
            - success: bool - Whether any check succeeded
            - object_name: str - Name of the examined object
            - results: List[Dict] - Results from each examine check
            - already_checked: bool - Whether this object was already examined
        """
        room = self.get_current_room()

        # Initialize checked_objects set if not present
        if "checked_objects" not in room:
            room["checked_objects"] = set()

        # Find the object
        examinable_objects = room.get("examinable_objects", [])
        obj = None
        for o in examinable_objects:
            if o["id"] == object_id:
                obj = o
                break

        if not obj:
            return {
                "success": False,
                "error": f"Object '{object_id}' not found in room"
            }

        object_name = obj.get("name", object_id)

        # Check if already examined
        if object_id in room["checked_objects"]:
            return {
                "success": False,
                "object_name": object_name,
                "already_checked": True,
                "results": []
            }

        # Mark as examined
        room["checked_objects"].add(object_id)

        # Load skills data
        skills_data = self.data_loader.load_skills()

        # Perform all examine checks for this object
        results = []
        any_success = False

        for check in obj.get("examine_checks", []):
            skill = check["skill"]
            dc = check["dc"]

            # Apply lighting penalties for sight-based checks
            should_continue, disadvantage, auto_fail_result = self._apply_lighting_penalties(
                character, skill, dc, f"examine {object_name}"
            )

            if not should_continue:
                # Check auto-failed in darkness
                results.append({
                    "skill": skill,
                    "dc": dc,
                    "success": False,
                    "check_result": auto_fail_result
                })
                continue

            # Make skill check
            check_result = character.make_skill_check(skill, dc, skills_data, disadvantage=disadvantage)

            # Emit skill check event
            self.event_bus.emit(Event(
                type=EventType.SKILL_CHECK,
                data={
                    "character": character.name,
                    "skill": skill,
                    "dc": dc,
                    "roll": check_result["roll"],
                    "modifier": check_result["modifier"],
                    "total": check_result["total"],
                    "success": check_result["success"],
                    "action": f"examine {object_name}",
                    "success_text": check.get("on_success") if check_result["success"] else None,
                    "failure_text": check.get("on_failure") if not check_result["success"] else None
                }
            ))

            results.append({
                "skill": skill,
                "dc": dc,
                "check_result": check_result,
                "success_text": check.get("on_success") if check_result["success"] else None,
                "failure_text": check.get("on_failure") if not check_result["success"] else None
            })

            if check_result["success"]:
                any_success = True

        return {
            "success": any_success,
            "object_name": object_name,
            "already_checked": False,
            "results": results
        }

    def search_room(
        self,
        character: Character | None = None
    ) -> dict[str, Any]:
        """
        Search the current room for items, optionally with skill checks.

        If the room has search_checks defined, a skill check is required.
        Otherwise, searching automatically succeeds (backwards compatibility).

        Only reveals items without picking them up.
        Use take_item() to actually pick up items.

        Args:
            character: Character performing the search (required if room has search_checks)

        Returns:
            Dict with search result:
            - success: bool - Whether search succeeded
            - items: List[Dict] - Items found (if successful or already searched)
            - visible_items: List[Dict] - Items that were already visible
            - hidden_items: List[Dict] - Items that were found by searching
            - already_searched: bool - Whether room was already searched
            - check_result: Dict - Skill check result (if applicable)
        """
        room = self.get_current_room()

        # Not searchable rooms return failure
        if not room.get("searchable"):
            return {
                "success": False,
                "items": [],
                "visible_items": [],
                "hidden_items": [],
                "error": "This room cannot be searched"
            }

        # Check if already searched
        already_searched = room.get("searched", False)

        # Separate visible and hidden items
        all_items = room.get("items", [])
        visible_items = [item for item in all_items if item.get("visible", False)]
        hidden_items = [item for item in all_items if not item.get("visible", False)]

        # If already searched, return current items without requiring another check
        if already_searched:
            return {
                "success": True,
                "items": room.get("items", []),
                "visible_items": visible_items,
                "hidden_items": [],
                "already_searched": True
            }

        # Check if room has search_checks
        search_checks = room.get("search_checks", [])

        if search_checks:
            # Skill check required
            if character is None:
                return {
                    "success": False,
                    "items": [],
                    "visible_items": visible_items,
                    "hidden_items": [],
                    "error": "Character required for search with skill check"
                }

            # Load skills data
            skills_data = self.data_loader.load_skills()

            # Perform search check (use first check - typically Investigation or Perception)
            check = search_checks[0]
            skill = check["skill"]
            dc = check["dc"]

            # Make skill check
            check_result = character.make_skill_check(skill, dc, skills_data)

            # Mark room as searched regardless of result
            room["searched"] = True

            # Advance time for searching (10 minutes)
            self.time_manager.advance_time(10, reason="search_room")

            # Emit skill check event
            self.event_bus.emit(Event(
                type=EventType.SKILL_CHECK,
                data={
                    "character": character.name,
                    "skill": skill,
                    "dc": dc,
                    "roll": check_result["roll"],
                    "modifier": check_result["modifier"],
                    "total": check_result["total"],
                    "success": check_result["success"],
                    "action": "search room",
                    "success_text": check.get("on_success") if check_result["success"] else None,
                    "failure_text": check.get("on_failure") if not check_result["success"] else None
                }
            ))

            # Return items only if check succeeded
            if check_result["success"]:
                return {
                    "success": True,
                    "items": room.get("items", []),
                    "visible_items": visible_items,
                    "hidden_items": hidden_items,
                    "already_searched": False,
                    "check_result": check_result,
                    "success_text": check.get("on_success"),
                    "failure_text": None
                }
            else:
                return {
                    "success": False,
                    "items": visible_items,
                    "visible_items": visible_items,
                    "hidden_items": [],
                    "already_searched": False,
                    "check_result": check_result,
                    "success_text": None,
                    "failure_text": check.get("on_failure")
                }
        else:
            # No skill check required - automatic success (backwards compatibility)
            room["searched"] = True

            # Advance time for searching (10 minutes)
            self.time_manager.advance_time(10, reason="search_room")

            return {
                "success": True,
                "items": room.get("items", []),
                "visible_items": visible_items,
                "hidden_items": hidden_items,
                "already_searched": False
            }

    def get_available_items_in_room(self) -> list[dict[str, Any]]:
        """
        Get list of items available to pick up in the current room.

        Returns items if:
        - Item is marked as visible=true, OR
        - Room has been searched and has items, OR
        - Room is not searchable but has items

        Returns:
            List of available items
        """
        room = self.get_current_room()
        items = room.get("items", [])

        # If room is searched or not searchable, all items are available
        if room.get("searched") or not room.get("searchable"):
            return items

        # Otherwise, only return visible items
        return [item for item in items if item.get("visible", False)]

    def take_item(self, item_id: str, character: Character) -> bool:
        """
        Pick up an item from the current room and add it to a character's inventory.

        Args:
            item_id: ID of the item to pick up (or "gold" for currency)
            character: Character who should receive the item

        Returns:
            True if item was successfully taken, False otherwise
        """
        room = self.get_current_room()

        # Check if item is available (visible or room is searched)
        available_items = self.get_available_items_in_room()

        # Find the item in available items
        item_to_take = None
        for item in available_items:
            if item["type"] == "gold" and item_id.lower() == "gold":
                item_to_take = item
                break
            elif item["type"] == "currency" and item_id.lower() in ["gold", "silver", "copper", "currency"]:
                item_to_take = item
                break
            elif item["type"] == "item" and item.get("id") == item_id:
                item_to_take = item
                break

        if not item_to_take:
            return False  # Item not found or not available

        # Handle different item types
        if item_to_take["type"] == "currency":
            # Handle currency with gold, silver, and copper
            from dnd_engine.systems.currency import Currency
            gold = item_to_take.get("gold", 0)
            silver = item_to_take.get("silver", 0)
            copper = item_to_take.get("copper", 0)

            currency = Currency(gold=gold, silver=silver, copper=copper)
            # Split total value evenly among all party members
            total_cp = currency.to_copper()
            split_cp = total_cp // len(self.party.characters)

            for char in self.party.characters:
                split_currency = Currency()
                split_currency._from_copper(split_cp)
                char.inventory.currency.add(split_currency)

            # Emit gold acquired event
            self.event_bus.emit(Event(
                type=EventType.GOLD_ACQUIRED,
                data={"amount": gold, "silver": silver, "copper": copper}
            ))

        elif item_to_take["type"] == "gold":
            amount = item_to_take["amount"]
            # Split gold evenly among all party members
            split_amount = amount // len(self.party.characters)
            for char in self.party.characters:
                char.inventory.add_gold(split_amount)

            # Emit gold acquired event
            self.event_bus.emit(Event(
                type=EventType.GOLD_ACQUIRED,
                data={"amount": amount}
            ))

        elif item_to_take["type"] == "item":
            category = self._get_item_category(item_id)
            if not category:
                return False  # Unknown item category

            # Check if this is a quest item (doesn't transfer between campaigns)
            is_quest_item = item_to_take.get("quest_item", False)

            # Add item to the specified character's inventory
            character.inventory.add_item(item_id, category, quest_item=is_quest_item)

            # Emit item acquired event
            self.event_bus.emit(Event(
                type=EventType.ITEM_ACQUIRED,
                data={"item_id": item_id, "category": category, "character": character.name}
            ))

        # Remove item from room
        room.get("items", []).remove(item_to_take)
        return True

    def prepare_spells(self, character_name: str, spell_ids: list[str]) -> bool:
        """
        Prepare spells for a character (orchestration for player action).

        This method coordinates spell preparation after a long rest. The Character
        class handles validation and state updates.

        Args:
            character_name: Name of character preparing spells
            spell_ids: List of spell IDs to prepare (cantrips will be auto-included by Character)

        Returns:
            True if preparation successful, False if validation failed or character not found
        """
        character = self.party.get_character_by_name(character_name)
        if not character:
            return False

        # Character validates and updates prepared spell list
        success = character.set_prepared_spells(spell_ids)

        if success:
            # Emit event for logging/tracking
            self.event_bus.emit(Event(
                type=EventType.SPELLS_PREPARED,
                data={
                    "character": character_name,
                    "spell_count": len(spell_ids)
                }
            ))

        return success

    def cast_spell_exploration(
        self,
        caster_name: str,
        spell_id: str,
        target_name: str | None = None
    ) -> dict[str, Any]:
        """
        Cast a spell outside of combat during exploration.

        Handles spell slot consumption, healing calculation, and effect application
        for out-of-combat spellcasting. Emits SPELL_CAST event.

        Args:
            caster_name: Name of the character casting the spell
            spell_id: ID of the spell to cast
            target_name: Name of the target character (required for healing/buff spells)

        Returns:
            Dictionary with casting results:
            {
                "success": bool,
                "message": str,
                "healing_amount": int (if healing spell),
                "spell_name": str,
                "error": str (if failed)
            }
        """
        # Find caster
        caster = self.party.get_character_by_name(caster_name)
        if not caster:
            return {
                "success": False,
                "error": f"Character '{caster_name}' not found"
            }

        # Load spell data
        spell_data = self.data_loader.load_spells().get(spell_id)
        if not spell_data:
            return {
                "success": False,
                "error": f"Spell '{spell_id}' not found"
            }

        spell_name = spell_data.get("name", spell_id)
        spell_level = spell_data.get("level", 0)

        # Check if character knows/has prepared this spell
        if spell_id not in caster.prepared_spells and spell_id not in caster.known_spells:
            return {
                "success": False,
                "error": f"{caster_name} doesn't know {spell_name}"
            }

        # Check spell slot availability (cantrips are level 0, always available)
        if spell_level > 0:
            available_slots = caster.get_available_spell_slots(spell_level)
            if available_slots <= 0:
                return {
                    "success": False,
                    "error": f"No level {spell_level} spell slots available"
                }

        # Handle healing spells
        if spell_data.get("healing"):
            if not target_name:
                return {
                    "success": False,
                    "error": "Healing spell requires a target"
                }

            target = self.party.get_character_by_name(target_name)
            if not target:
                return {
                    "success": False,
                    "error": f"Target '{target_name}' not found"
                }

            # Roll healing: dice + spellcasting modifier
            healing_dice = spell_data["healing"].get("dice", "1d8")
            healing_roll = self.dice_roller.roll(healing_dice)

            # Get spellcasting modifier from abilities
            if caster.spellcasting_ability == "int":
                spellcasting_modifier = caster.abilities.int_mod
            elif caster.spellcasting_ability == "wis":
                spellcasting_modifier = caster.abilities.wis_mod
            elif caster.spellcasting_ability == "cha":
                spellcasting_modifier = caster.abilities.cha_mod
            else:
                spellcasting_modifier = 0

            total_healing = healing_roll.total + spellcasting_modifier

            # Apply healing
            old_hp = target.current_hp
            target.heal(total_healing)
            actual_healing = target.current_hp - old_hp

            # Consume spell slot for non-cantrips
            if spell_level > 0:
                caster.use_spell_slot(spell_level)

            # Create active effect if spell has duration
            effect = self._create_spell_effect(spell_data, caster_name, target_name)
            if effect:
                # If this is a concentration spell, break concentration on any previous spell
                if effect.concentration:
                    self.time_manager.remove_concentration_effects(caster_name)
                self.time_manager.add_effect(effect)

            # Emit event
            self.event_bus.emit(Event(
                type=EventType.SPELL_CAST,
                data={
                    "caster": caster_name,
                    "spell": spell_name,
                    "target": target_name,
                    "healing": actual_healing,
                    "spell_level": spell_level
                }
            ))

            return {
                "success": True,
                "message": f"{caster_name} cast {spell_name} on {target_name}",
                "healing_amount": actual_healing,
                "spell_name": spell_name,
                "target": target_name,
                "spell_level": spell_level
            }

        # Handle utility spells (Light, Detect Magic, etc.) with duration tracking
        else:
            # Determine target (default to caster if not specified)
            # This is a simplification: spells like Shield apply to caster,
            # while spells like Light might target an object. For MVP, we assume
            # the caster is a reasonable default target for tracking purposes.
            if not target_name:
                target_name = caster_name

            # Consume spell slot for non-cantrips
            if spell_level > 0:
                caster.use_spell_slot(spell_level)

            # Create active effect if spell has duration
            effect = self._create_spell_effect(spell_data, caster_name, target_name)
            if effect:
                # If this is a concentration spell, break concentration on any previous spell
                if effect.concentration:
                    self.time_manager.remove_concentration_effects(caster_name)
                self.time_manager.add_effect(effect)

            # Emit event
            self.event_bus.emit(Event(
                type=EventType.SPELL_CAST,
                data={
                    "caster": caster_name,
                    "spell": spell_name,
                    "spell_level": spell_level,
                    "target": target_name
                }
            ))

            # Return spell description as flavor text
            description = spell_data.get("description", f"{spell_name} takes effect.")

            return {
                "success": True,
                "message": f"{caster_name} cast {spell_name}",
                "spell_name": spell_name,
                "description": description,
                "spell_level": spell_level,
                "target": target_name,
                "has_duration": effect is not None
            }

    def cast_spell_combat(
        self,
        caster: Character,
        spell_data: dict[str, Any],
        target: Creature | None,
        spellcasting_ability: str
    ) -> "CombatSpellResult":
        """
        Cast a spell during combat.

        Handles spell slot validation/consumption, spell resolution (routing by type,
        damage, effects, concentration).

        Action economy is NOT handled here (caller/middleware responsibility).

        Args:
            caster: Character casting the spell
            spell_data: Complete spell data dictionary
            target: Target creature, or None for area effect spells
            spellcasting_ability: Ability used for spellcasting (int/wis/cha)

        Returns:
            CombatSpellResult with all information needed for UI display.
            Includes resources_consumed for middleware auto-refund tracking.
        """
        spell_name = spell_data.get("name", "Unknown Spell")
        spell_level = spell_data.get("level", 0)
        resources_consumed: list[tuple[str, int]] = []

        # Validate and consume spell slot for leveled spells
        if spell_level > 0:
            if caster.get_available_spell_slots(spell_level) <= 0:
                ordinal = Character._level_to_ordinal(spell_level)
                return CombatSpellResult(
                    success=False,
                    spell_name=spell_name,
                    caster_name=caster.name,
                    targets=[],
                    is_area_effect=False,
                    spell_type="",
                    error=f"No {ordinal}-level spell slots available!"
                )
            # Consume the spell slot
            caster.use_spell_slot(spell_level)
            resources_consumed.append((f"spell_slots_level_{spell_level}", 1))

        has_attack = spell_data.get("attack_type") is not None
        has_save = spell_data.get("saving_throw") is not None
        has_hp_pool = spell_data.get("hp_pool") is not None
        target_type = spell_data.get("target_type")

        # Resolve targets based on target_type
        if target_type == "area" and target is None:
            targets = [e for e in self.active_enemies if e.is_alive]
            if not targets:
                return CombatSpellResult(
                    success=False,
                    spell_name=spell_name,
                    caster_name=caster.name,
                    targets=[],
                    is_area_effect=True,
                    spell_type="save",
                    error="No enemies to target",
                    resources_consumed=resources_consumed
                )
            is_area = True
        else:
            targets = [target] if target else []
            is_area = False

        # Track concentration state BEFORE casting
        broke_concentration = None
        if spell_data.get("concentration", False):
            previous_spell = self.get_concentration_spell(caster.name)
            if previous_spell:
                broke_concentration = previous_spell
                self.time_manager.remove_concentration_effects(caster.name)

        # Route by spell type and attach resources_consumed to result
        if has_attack:
            result = self._resolve_combat_attack_spell(
                caster, targets[0], spell_data, spellcasting_ability,
                spell_name, broke_concentration
            )
        elif has_hp_pool:
            result = self._resolve_combat_hp_pool_spell(
                caster, targets, spell_data, spell_name,
                is_area, broke_concentration
            )
        elif has_save:
            result = self._resolve_combat_save_spell(
                caster, targets, spell_data, spell_name,
                is_area, broke_concentration
            )
        else:
            result = self._resolve_combat_auto_hit_spell(
                caster, targets[0] if targets else None, spell_data,
                spell_name, broke_concentration
            )

        # Attach consumed resources for middleware auto-refund tracking
        result.resources_consumed = resources_consumed
        return result

    def execute_player_attack(
        self,
        attacker: Character,
        target: Creature
    ) -> "PlayerAttackResult":
        """
        Execute a player's attack with their equipped weapon.

        Handles the complete flow of a player attack:
        1. Gets equipped weapon data and properties
        2. Calculates attack and damage bonuses
        3. Resolves the attack via combat engine
        4. Checks target concentration if applicable
        5. Returns comprehensive result for UI display

        Args:
            attacker: Character making the attack
            target: Target creature

        Returns:
            PlayerAttackResult with all information needed for UI display.
        """
        # Get equipped weapon
        equipped_weapon = attacker.inventory.get_equipped_item(EquipmentSlot.WEAPON)

        # Load item data for weapon lookup
        items_data = self.data_loader.load_items(self.campaign_id)

        # Calculate attack/damage bonuses and get weapon info
        ammo_id = None  # Track ammo for consumption after attack
        if equipped_weapon:
            attack_bonus = attacker.get_attack_bonus(equipped_weapon, items_data)
            damage_bonus = attacker.get_damage_bonus(equipped_weapon, items_data)
            weapon_data = items_data.get("weapons", {}).get(equipped_weapon, {})
            damage_dice = weapon_data.get("damage", "1d8")
            damage_dice = format_dice_with_modifier(damage_dice, damage_bonus)
            weapon_name = weapon_data.get("name", equipped_weapon)

            # Check if weapon requires ammunition
            weapon_properties = weapon_data.get("properties", [])
            if "ammunition" in weapon_properties:
                ammo_id = attacker.inventory.get_compatible_ammo(
                    equipped_weapon, items_data
                )
                if not ammo_id:
                    return PlayerAttackResult(
                        success=False,
                        attack_result=AttackResult(
                            attacker_name=attacker.name,
                            defender_name=target.name,
                            attack_roll=0,
                            attack_bonus=attack_bonus,
                            target_ac=target.ac,
                            hit=False,
                            critical_hit=False,
                            damage=0,
                            advantage=False,
                            disadvantage=False
                        ),
                        attacker_name=attacker.name,
                        target_name=target.name,
                        weapon_name=weapon_name,
                        error="No ammunition available for this weapon"
                    )
        else:
            # Fallback to unarmed strike
            attack_bonus = attacker.melee_attack_bonus
            damage_bonus = attacker.melee_damage_bonus
            damage_dice = format_dice_with_modifier("1d8", damage_bonus)
            weapon_name = "unarmed strike"

        # Resolve attack via combat engine
        attack_result = self.combat_engine.resolve_attack(
            attacker=attacker,
            defender=target,
            attack_bonus=attack_bonus,
            damage_dice=damage_dice,
            apply_damage=True,
            game_state=self
        )

        # Consume ammunition after the attack (hit or miss, the ammo is still used)
        if ammo_id:
            attacker.inventory.consume_ammo(ammo_id)

        # Check concentration if target was hit and took damage
        concentration_broken = None
        if attack_result.hit and attack_result.damage > 0 and isinstance(target, Character):
            conc_result = self.check_concentration_from_damage(
                target.name,
                attack_result.damage
            )
            if conc_result["concentration_broken"]:
                concentration_broken = conc_result

        # Build narrative context for LLM enhancement
        narrative_context = {
            "attacker_name": attacker.name,
            "target_name": target.name,
            "weapon_name": weapon_name,
            "hit": attack_result.hit,
            "critical": attack_result.critical_hit,
            "damage": attack_result.damage,
            "target_hp_before": (
                target.current_hp + attack_result.damage if attack_result.hit
                else target.current_hp
            ),
            "target_hp_after": target.current_hp,
            "target_killed": not target.is_alive
        }

        return PlayerAttackResult(
            success=True,
            attack_result=attack_result,
            attacker_name=attacker.name,
            target_name=target.name,
            weapon_name=weapon_name,
            concentration_broken=concentration_broken,
            target_killed=not target.is_alive,
            narrative_context=narrative_context
        )

    def execute_stabilize(
        self,
        helper: Character,
        target: Character
    ) -> "StabilizeResult":
        """
        Execute an attempt to stabilize a dying character.

        Handles the complete flow:
        1. Loads skills data
        2. Makes Medicine skill check (DC 10)
        3. Stabilizes target on success
        4. Emits stabilization event

        Args:
            helper: Character attempting to stabilize
            target: Dying character to stabilize

        Returns:
            StabilizeResult with check details and outcome.
        """
        # Load skills data and make Medicine check (DC 10)
        skills_data = self.data_loader.load_skills()
        check_result = helper.make_skill_check("medicine", 10, skills_data)

        if check_result["success"]:
            # Stabilize the target
            target.stabilize_character()

            # Emit stabilization event
            self.event_bus.emit(Event(
                type=EventType.CHARACTER_STABILIZED,
                data={
                    "helper": helper.name,
                    "target": target.name,
                    "check_total": check_result["total"]
                }
            ))

        return StabilizeResult(
            success=check_result["success"],
            helper_name=helper.name,
            target_name=target.name,
            roll=check_result["roll"],
            modifier=check_result["modifier"],
            total=check_result["total"],
            dc=check_result["dc"]
        )

    def _resolve_combat_attack_spell(
        self,
        caster: Character,
        target: Creature,
        spell_data: dict[str, Any],
        spellcasting_ability: str,
        spell_name: str,
        broke_concentration: str | None
    ) -> "CombatSpellResult":
        """Resolve attack spell via combat_engine.resolve_spell_attack()."""
        # Delegate to existing combat engine method
        result = self.combat_engine.resolve_spell_attack(
            caster=caster,
            target=target,
            spell=spell_data,
            spellcasting_ability=spellcasting_ability,
            apply_damage=True,
            event_bus=self.event_bus
        )

        # Check target concentration if damage was dealt
        target_conc_breaks = []
        if result.hit and result.damage > 0:
            if isinstance(target, Character):
                conc_result = self.check_concentration_from_damage(target.name, result.damage)
                if conc_result["concentration_broken"]:
                    target_conc_breaks.append({
                        "target": target.name,
                        "spell": conc_result["spell_name"],
                        "dc": conc_result["dc"],
                        "save_result": conc_result["save_result"]
                    })

        # Handle concentration for caster
        now_concentrating = False
        if spell_data.get("concentration", False):
            effect = self._create_spell_effect(spell_data, caster.name, target.name)
            if effect:
                self.time_manager.add_effect(effect)
                now_concentrating = True

        killed = [target.name] if not target.is_alive else []

        return CombatSpellResult(
            success=True,
            spell_name=spell_name,
            caster_name=caster.name,
            targets=[target.name],
            is_area_effect=False,
            spell_type="attack",
            attack_result=result,
            total_damage=result.damage,
            damage_type=spell_data.get("damage", {}).get("damage_type"),
            broke_concentration=broke_concentration,
            now_concentrating=now_concentrating,
            target_concentration_breaks=target_conc_breaks,
            killed_targets=killed
        )

    def _resolve_combat_save_spell(
        self,
        caster: Character,
        targets: list[Creature],
        spell_data: dict[str, Any],
        spell_name: str,
        is_area: bool,
        broke_concentration: str | None
    ) -> "CombatSpellResult":
        """Resolve saving throw spell via combat_engine.resolve_spell_save()."""
        # Delegate to existing combat engine method
        save_result = self.combat_engine.resolve_spell_save(
            caster=caster,
            targets=targets,
            spell=spell_data,
            apply_damage=True,
            event_bus=self.event_bus
        )

        # Check concentration breaks for each target that took damage
        target_conc_breaks = []
        killed = []
        total_damage = 0

        for i, target_result in enumerate(save_result["targets"]):
            damage = target_result.get("damage", 0)
            total_damage += damage
            target = targets[i]

            if damage > 0 and isinstance(target, Character):
                conc_result = self.check_concentration_from_damage(target.name, damage)
                if conc_result["concentration_broken"]:
                    target_conc_breaks.append({
                        "target": target.name,
                        "spell": conc_result["spell_name"],
                        "dc": conc_result["dc"],
                        "save_result": conc_result["save_result"]
                    })

            if not target.is_alive:
                killed.append(target.name)

        # Handle concentration for caster
        now_concentrating = False
        if spell_data.get("concentration", False):
            effect_target = targets[0].name if targets else ""
            effect = self._create_spell_effect(spell_data, caster.name, effect_target)
            if effect:
                self.time_manager.add_effect(effect)
                now_concentrating = True

        return CombatSpellResult(
            success=True,
            spell_name=spell_name,
            caster_name=caster.name,
            targets=[t.name for t in targets],
            is_area_effect=is_area,
            spell_type="save",
            save_results=save_result["targets"],
            save_dc=save_result["save_dc"],
            save_ability=save_result["save_ability"],
            total_damage=total_damage,
            damage_type=spell_data.get("damage", {}).get("damage_type"),
            broke_concentration=broke_concentration,
            now_concentrating=now_concentrating,
            target_concentration_breaks=target_conc_breaks,
            killed_targets=killed
        )

    def _resolve_combat_hp_pool_spell(
        self,
        caster: Character,
        targets: list[Creature],
        spell_data: dict[str, Any],
        spell_name: str,
        is_area: bool,
        broke_concentration: str | None
    ) -> "CombatSpellResult":
        """Resolve HP pool spells like Sleep that affect creatures based on HP total."""
        # Delegate to combat engine
        result = self.combat_engine.resolve_spell_hp_pool(
            caster=caster,
            targets=targets,
            spell=spell_data,
            event_bus=self.event_bus
        )

        # Handle concentration for caster (Sleep is not concentration, but others might be)
        now_concentrating = False
        if spell_data.get("concentration", False):
            effect_target = targets[0].name if targets else ""
            effect = self._create_spell_effect(spell_data, caster.name, effect_target)
            if effect:
                self.time_manager.add_effect(effect)
                now_concentrating = True

        return CombatSpellResult(
            success=True,
            spell_name=spell_name,
            caster_name=caster.name,
            targets=[t["name"] for t in result["affected_targets"]],
            is_area_effect=is_area,
            spell_type="hp_pool",
            hp_pool_rolled=result["hp_pool_rolled"],
            hp_pool_remaining=result["hp_pool_remaining"],
            affected_targets=result["affected_targets"],
            unaffected_targets=result["unaffected_targets"],
            broke_concentration=broke_concentration,
            now_concentrating=now_concentrating
        )

    def _resolve_combat_auto_hit_spell(
        self,
        caster: Character,
        target: Creature | None,
        spell_data: dict[str, Any],
        spell_name: str,
        broke_concentration: str | None
    ) -> "CombatSpellResult":
        """Resolve auto-hit damage or buff spells."""
        damage = 0
        damage_data = spell_data.get("damage", {})
        target_conc_breaks = []
        killed = []
        target_name = target.name if target else caster.name

        # Roll and apply damage for auto-hit damage spells (Magic Missile)
        if damage_data and "dice" in damage_data:
            damage_dice = damage_data.get("dice", "1d6")
            damage_roll = self.dice_roller.roll(damage_dice)
            damage = damage_roll.total

            # Apply damage if there's a target
            if target and hasattr(target, 'take_damage'):
                import inspect
                sig = inspect.signature(target.take_damage)
                if 'event_bus' in sig.parameters:
                    target.take_damage(damage, event_bus=self.event_bus)
                else:
                    target.take_damage(damage)

                # Check target concentration
                if isinstance(target, Character):
                    conc_result = self.check_concentration_from_damage(target.name, damage)
                    if conc_result["concentration_broken"]:
                        target_conc_breaks.append({
                            "target": target.name,
                            "spell": conc_result["spell_name"],
                            "dc": conc_result["dc"],
                            "save_result": conc_result["save_result"]
                        })

                if not target.is_alive:
                    killed.append(target.name)

        # Handle effects (concentration or non-concentration buffs)
        now_concentrating = False
        if spell_data.get("concentration", False):
            effect = self._create_spell_effect(spell_data, caster.name, target_name)
            if effect:
                self.time_manager.add_effect(effect)
                now_concentrating = True
        elif spell_data.get("effect"):
            # Non-concentration buff spells (Mage Armor, Shield, etc.)
            effect = self._create_spell_effect(spell_data, caster.name, target_name)
            if effect:
                self.time_manager.add_effect(effect)

        spell_type = "auto_hit" if damage > 0 else "buff"

        return CombatSpellResult(
            success=True,
            spell_name=spell_name,
            caster_name=caster.name,
            targets=[target_name],
            is_area_effect=False,
            spell_type=spell_type,
            total_damage=damage,
            damage_type=damage_data.get("damage_type") if damage > 0 else None,
            broke_concentration=broke_concentration,
            now_concentrating=now_concentrating,
            target_concentration_breaks=target_conc_breaks,
            killed_targets=killed
        )

    def get_concentration_spell(self, character_name: str) -> str | None:
        """
        Get the spell a character is currently concentrating on.

        Args:
            character_name: Name of the character

        Returns:
            Spell name if concentrating, None otherwise
        """
        for effect in self.time_manager.active_effects:
            if effect.concentration and effect.caster_name == character_name:
                return effect.source  # source contains the spell name
        return None

    def check_concentration_from_damage(self, character_name: str, damage: int) -> dict:
        """
        Check if damage breaks a character's concentration on a spell.

        Args:
            character_name: Name of the character who took damage
            damage: Amount of damage taken

        Returns:
            dict with keys:
                - was_concentrating: bool - whether character was concentrating
                - concentration_broken: bool - whether concentration was broken
                - spell_name: str | None - name of spell that was being concentrated on
                - dc: int | None - DC of the concentration check
                - save_result: dict | None - result of the saving throw
        """
        # Check if character is concentrating
        spell_name = self.get_concentration_spell(character_name)
        if not spell_name:
            return {
                "was_concentrating": False,
                "concentration_broken": False,
                "spell_name": None,
                "dc": None,
                "save_result": None
            }

        # Find the character
        character = self.party.get_character_by_name(character_name)
        if not character:
            # Maybe it's an enemy? For now, only handle party members
            return {
                "was_concentrating": True,
                "concentration_broken": False,
                "spell_name": spell_name,
                "dc": None,
                "save_result": None
            }

        # Calculate DC: max(10, damage // 2)
        dc = max(10, damage // 2)

        # Make Constitution saving throw
        save_result = character.make_saving_throw("constitution", dc)

        # If failed, break concentration
        if not save_result["success"]:
            self.time_manager.remove_concentration_effects(character_name)

        return {
            "was_concentrating": True,
            "concentration_broken": not save_result["success"],
            "spell_name": spell_name,
            "dc": dc,
            "save_result": save_result
        }

    def _create_spell_effect(
        self,
        spell_data: dict[str, Any],
        caster_name: str,
        target_name: str
    ) -> ActiveEffect | None:
        """
        Create an ActiveEffect from spell data if the spell has a duration.

        Args:
            spell_data: Spell data dictionary
            caster_name: Name of the caster
            target_name: Name of the target

        Returns:
            ActiveEffect if spell has duration, None otherwise
        """
        from dnd_engine.systems.time_manager import parse_duration

        duration_string = spell_data.get("duration_value")
        if not duration_string:
            return None

        # Parse duration to (type, value)
        parsed = parse_duration(duration_string)
        if not parsed:
            return None

        duration_type, duration_value = parsed

        # Create effect
        spell_name = spell_data.get("name", "Unknown Spell")
        concentration = spell_data.get("concentration", False)
        description = spell_data.get("description", "")

        # Extract effect modifiers if present
        effect_data = {}
        if "effect" in spell_data:
            effect_data = spell_data["effect"].copy()

        effect = ActiveEffect(
            effect_type=EffectType.SPELL,
            source=spell_name,
            duration_type=duration_type,
            duration_value=duration_value,
            remaining_value=duration_value,
            target_name=target_name,
            description=description,
            concentration=concentration,
            caster_name=caster_name if concentration else None,
            effect_data=effect_data
        )

        return effect

    def _get_item_category(self, item_id: str) -> str | None:
        """
        Determine the category of an item by ID.

        Args:
            item_id: ID of the item

        Returns:
            Category name or None if not found
        """
        items_data = self.data_loader.load_items(campaign_id=self.campaign_id)

        # Direct category matches
        for category in [
            "weapons",
            "armor",
            "consumables",
            "magical_items",
            "tools",
            "equipment",
        ]:
            if item_id in items_data.get(category, {}):
                return category

        # Ammunition is stored in inventory as consumables (arrows/bolts are consumed)
        if item_id in items_data.get("ammunition", {}):
            return "consumables"

        return None

    def get_room_description(self) -> str:
        """
        Get a description of the current room.

        Returns:
            Room description string
        """
        room = self.get_current_room()
        desc = f"{room['name']}\n\n{room['description']}\n"

        # Add exits
        exits = room.get("exits", {})
        if exits:
            exit_str = ", ".join(exits.keys())
            desc += f"\nExits: {exit_str}"

        # Add enemy info if in combat
        if self.in_combat and self.active_enemies:
            enemy_names = [e.name for e in self.active_enemies if e.is_alive]
            if enemy_names:
                desc += f"\n\nEnemies: {', '.join(enemy_names)}"

        return desc

    def get_effective_ac(self, creature: "Creature") -> int:
        """
        Calculate effective AC including base AC and active effect modifiers.

        This is the single source of truth for AC calculations. It applies
        modifiers from active effects (spells, items, conditions) in the correct order:
        1. Base AC from armor/natural armor
        2. AC set effects (Mage Armor, Barkskin) - only first applies
        3. AC bonus effects (Shield, Haste) - all stack

        Args:
            creature: Creature to calculate AC for

        Returns:
            Effective AC after applying all modifiers
        """
        from dnd_engine.systems.time_manager import ModifierType

        base_ac = creature._base_ac

        # Query active effects for this creature
        effects = self.time_manager.get_effects_for_character(creature.name)

        # Apply AC modifiers in order
        final_ac = base_ac
        has_set_base = False

        for effect in effects:
            effect_data = effect.effect_data
            if not effect_data:
                continue

            modifier_type = effect_data.get("modifier_type", "")

            if modifier_type == ModifierType.AC_SET_BASE.value and not has_set_base:
                # Only first ac_set_base applies (Mage Armor, Barkskin)
                # These spells set a minimum AC or replace base calculation
                formula = effect_data.get("formula", "")
                if formula:
                    final_ac = self._evaluate_ac_formula(formula, creature)
                    has_set_base = True
            elif modifier_type == ModifierType.AC_BONUS.value:
                # Bonuses stack (Shield: +5, Haste: +2, etc.)
                final_ac += effect_data.get("value", 0)

        return final_ac

    def _evaluate_ac_formula(self, formula: str, creature: "Creature") -> int:
        """
        Evaluate AC formula like '13 + dex_mod'.

        Args:
            formula: Formula string from spell data
            creature: Creature to evaluate formula for

        Returns:
            Calculated AC value
        """
        # Parse formula - supports patterns like "13 + dex_mod", "10 + dex_mod + con_mod"
        result = 0
        formula = formula.lower().replace(" ", "")

        # Split by + and process each part
        parts = formula.split("+")
        for part in parts:
            part = part.strip()
            if part.isdigit():
                # Numeric constant
                result += int(part)
            elif part == "dex_mod":
                result += creature.abilities.dex_mod
            elif part == "con_mod":
                result += creature.abilities.con_mod
            elif part == "str_mod":
                result += creature.abilities.str_mod
            elif part == "int_mod":
                result += creature.abilities.int_mod
            elif part == "wis_mod":
                result += creature.abilities.wis_mod
            elif part == "cha_mod":
                result += creature.abilities.cha_mod
            else:
                logger.warning(f"Unknown formula part: {part}")

        return result

    def get_player_status(self) -> list[dict[str, Any]]:
        """
        Get status for all party members.

        Returns:
            List of dictionaries with character stats for each party member
        """
        return [
            {
                "name": char.name,
                "hp": char.current_hp,
                "max_hp": char.max_hp,
                "ac": char._base_ac,
                "level": char.level,
                "xp": char.xp,
                "alive": char.is_alive
            }
            for char in self.party.characters
        ]

    def is_game_over(self) -> bool:
        """
        Check if the game is over.

        Returns:
            True if game should end (entire party is dead)
        """
        return self.party.is_wiped()

    def _check_for_enemies(self) -> None:
        """Check current room for enemies and start combat if found."""
        room = self.get_current_room()
        enemy_ids = room.get("enemies", [])

        if not enemy_ids:
            return  # No enemies

        # Create enemy creatures
        self.active_enemies = []
        for enemy_id in enemy_ids:
            enemy = self.data_loader.create_monster(enemy_id)
            self.active_enemies.append(enemy)

        # Start combat
        self._start_combat()

    def _check_passive_perception(self) -> None:
        """
        Check party members' passive Perception against hidden features on room entry.

        Passive Perception = 10 + Perception modifier

        Only triggers once per room per party. Results are emitted as events.
        """
        room = self.get_current_room()

        # Skip if no hidden features or already checked
        hidden_features = room.get("hidden_features", [])
        if not hidden_features:
            return

        # Initialize passive_checks_done flag if not present
        if "passive_checks_done" not in room:
            room["passive_checks_done"] = False

        # Only check once per room
        if room["passive_checks_done"]:
            return

        # Mark as checked
        room["passive_checks_done"] = True

        # Load skills data for Perception
        skills_data = self.data_loader.load_skills()

        # Check each hidden feature with trigger "on_enter"
        for feature in hidden_features:
            if feature.get("trigger") != "on_enter":
                continue

            if feature.get("type") != "passive_perception":
                continue

            dc = feature.get("dc", 10)

            # Check each party member's passive Perception
            for character in self.party.characters:
                # Calculate passive Perception: 10 + Perception modifier
                perception_mod = character.get_skill_modifier("perception", skills_data)
                passive_perception = 10 + perception_mod

                # Apply lighting penalties (disadvantage = -5 for passive checks)
                lighting = self.get_effective_lighting(character)
                if lighting == "dim":
                    passive_perception -= 5
                elif lighting == "dark":
                    # In complete darkness, automatic failure for sight-based checks
                    passive_perception = 0

                success = passive_perception >= dc

                # Emit event for this check
                self.event_bus.emit(Event(
                    type=EventType.SKILL_CHECK,
                    data={
                        "character": character.name,
                        "skill": "perception",
                        "dc": dc,
                        "modifier": perception_mod,
                        "total": passive_perception,
                        "success": success,
                        "passive": True,
                        "action": f"passive perception (DC {dc})",
                        "success_text": feature.get("on_success") if success else None,
                        "failure_text": feature.get("on_failure") if not success else None
                    }
                ))

    def is_room_alerted(self, room_id: str | None = None) -> bool:
        """Check if a room's occupants are alerted to the party's presence."""
        if room_id is None:
            room_id = self.current_room_id

        room = self.dungeon["rooms"].get(room_id)
        if not room:
            return False

        # Initialize alert state if not present
        if "alerted" not in room:
            room["alerted"] = False

        return room["alerted"]

    def set_room_alerted(self, room_id: str | None = None, alert_source: str = "unknown") -> None:
        """Set a room's alert state to True."""
        if room_id is None:
            room_id = self.current_room_id

        room = self.dungeon["rooms"].get(room_id)
        if not room:
            return

        room["alerted"] = True
        room["alert_source"] = alert_source

    def _check_for_surprise(self) -> dict:
        """
        Check if either side is surprised in combat.

        Uses group stealth check (all party members must succeed) vs enemy passive Perception.
        Returns dict with party_surprised and enemies_surprised booleans.
        """
        # If room is alerted, no surprise is possible
        if self.is_room_alerted():
            return {"party_surprised": False, "enemies_surprised": False}

        # Load skills data for stealth checks
        skills_data = self.data_loader.load_skills()

        # Get highest enemy passive Perception
        monsters_data = self.data_loader.load_monsters()
        max_enemy_perception = 0  # Start at 0, will take highest from actual enemies

        for enemy in self.active_enemies:
            # Find enemy's passive_perception from monster data
            for monster_id, monster_data in monsters_data.items():
                if monster_data["name"] == enemy.name:
                    enemy_pp = monster_data.get("passive_perception", 10)
                    max_enemy_perception = max(max_enemy_perception, enemy_pp)
                    break

        # Fallback if no passive_perception found
        if max_enemy_perception == 0:
            max_enemy_perception = 10

        # Group stealth check - ALL party members must beat enemy passive Perception
        party_hidden = True
        stealth_results = []

        for character in self.party.get_living_members():
            # Make stealth check for this character
            check_result = character.make_skill_check("stealth", max_enemy_perception, skills_data)
            stealth_results.append(check_result)

            # Emit skill check event (UI will handle display)
            self.event_bus.emit(Event(
                type=EventType.SKILL_CHECK,
                data={
                    "character": character.name,
                    **check_result,
                    "action": f"stealth check (vs passive Perception {max_enemy_perception})"
                }
            ))

            # If ANY party member fails, entire party is detected
            if not check_result["success"]:
                party_hidden = False

        # Determine surprise
        enemies_surprised = party_hidden
        party_surprised = False  # Future: ambush mechanics

        # Display surprise result
        if enemies_surprised:
            print("⚡ SURPRISE ROUND! The enemies are caught off-guard!")
        else:
            print("⚠️  The enemies notice your approach - no surprise!")

        return {
            "party_surprised": party_surprised,
            "enemies_surprised": enemies_surprised,
            "stealth_results": stealth_results
        }

    def _start_combat(self) -> None:
        """Initialize combat with current enemies, checking for surprise."""
        self.in_combat = True
        self.initiative_tracker = InitiativeTracker(self.dice_roller, self.time_manager)

        # Check for surprise
        surprise_result = self._check_for_surprise()

        # Add all living party members to initiative
        for character in self.party.get_living_members():
            self.initiative_tracker.add_combatant(character)
            # Apply surprised condition if party is surprised
            if surprise_result["party_surprised"]:
                character.add_condition("surprised")

        # Add enemies to initiative
        for enemy in self.active_enemies:
            self.initiative_tracker.add_combatant(enemy)
            # Apply surprised condition if enemies are surprised
            if surprise_result["enemies_surprised"]:
                enemy.add_condition("surprised")

        # Emit surprise round event if either side is surprised
        if surprise_result["enemies_surprised"] or surprise_result["party_surprised"]:
            self.event_bus.emit(Event(
                type=EventType.SURPRISE_ROUND,
                data={
                    "party_surprised": surprise_result["party_surprised"],
                    "enemies_surprised": surprise_result["enemies_surprised"],
                    "surprised_creatures": [
                        e.name for e in self.active_enemies if surprise_result["enemies_surprised"]
                    ] + [
                        c.name for c in self.party.get_living_members() if surprise_result["party_surprised"]
                    ]
                }
            ))

        # Emit combat start event
        self.event_bus.emit(Event(
            type=EventType.COMBAT_START,
            data={
                "enemies": [e.name for e in self.active_enemies],
                "party": [c.name for c in self.party.get_living_members()],
                "surprise_round": surprise_result["enemies_surprised"] or surprise_result["party_surprised"]
            }
        ))

    def _check_combat_end(self) -> None:
        """Check if combat should end and handle cleanup."""
        # Remove dead enemies from tracker
        for enemy in self.active_enemies:
            if not enemy.is_alive and self.initiative_tracker:
                self.initiative_tracker.remove_combatant(enemy)

        # Check if combat is over
        if self.initiative_tracker:
            all_enemies_dead = all(not enemy.is_alive for enemy in self.active_enemies)
            party_wiped = self.party.is_wiped()

            # Check if all party members are unconscious (unable to act)
            all_party_unconscious = all(
                char.is_unconscious or char.is_dead
                for char in self.party.characters
            )

            if all_enemies_dead or party_wiped or all_party_unconscious:
                self._end_combat()

    def _end_combat(self) -> None:
        """End combat and perform cleanup."""
        # Determine if party won or lost
        all_enemies_dead = all(not enemy.is_alive for enemy in self.active_enemies)
        victory = all_enemies_dead

        total_xp = 0

        # Only award XP on victory
        if victory:
            # Calculate XP from defeated enemies
            monsters = self.data_loader.load_monsters()

            for enemy in self.active_enemies:
                if not enemy.is_alive:
                    # Find enemy XP value
                    for monster_id, monster_data in monsters.items():
                        if monster_data["name"] == enemy.name:
                            total_xp += monster_data.get("xp", 0)
                            break

            # Award XP to all party members (split evenly)
            if total_xp > 0 and len(self.party.characters) > 0:
                xp_per_character = total_xp // len(self.party.characters)
                for character in self.party.characters:
                    character.gain_xp(xp_per_character)

                    # Check for level-up (can level up multiple times if enough XP)
                    while character.check_for_level_up(self.data_loader, self.event_bus):
                        pass  # Level-up event already emitted by check_for_level_up

        # Clear combat state
        self.in_combat = False
        self.initiative_tracker = None

        # Remove defeated enemies from room only on victory
        room = self.get_current_room()
        # Capture defeated enemy IDs before clearing them (for quest tracking)
        defeated_enemy_ids = list(room.get("enemies", [])) if victory else []
        if victory:
            room["enemies"] = []

        # Clear combat history when combat ends
        self.clear_combat_history()

        # Emit combat end event
        self.event_bus.emit(Event(
            type=EventType.COMBAT_END,
            data={
                "victory": victory,
                "room_id": self.current_room_id,
                "xp_gained": total_xp,
                "xp_per_character": total_xp // len(self.party.characters) if len(self.party.characters) > 0 else 0
            }
        ))

        # Check for boss defeat and dungeon completion (campaign progression)
        if victory and room.get("boss_room"):
            self._handle_boss_defeat(defeated_enemy_ids)

    def _handle_boss_defeat(self, defeated_enemy_ids: list[str]) -> None:
        """
        Handle boss defeat for campaign progression.

        Args:
            defeated_enemy_ids: List of monster IDs that were defeated
        """
        if not self.campaign_progress or not self.campaign_tracker:
            return

        # Record boss defeat for current dungeon
        self.campaign_tracker.record_boss_defeat(
            self.campaign_progress, self.dungeon_name
        )

        # Emit boss defeated event for each defeated enemy
        # This allows quest objectives to track specific monster kills
        for monster_id in defeated_enemy_ids:
            self.event_bus.emit(Event(
                type=EventType.BOSS_DEFEATED,
                data={
                    "dungeon_id": self.dungeon_name,
                    "dungeon_name": self.dungeon.get("name", self.dungeon_name),
                    "monster_id": monster_id,
                }
            ))

        # Check if dungeon completion criteria are now met
        self._check_dungeon_completion()

    def _check_dungeon_completion(self) -> None:
        """Check if current dungeon is complete and unlock next dungeons."""
        if not self.campaign_progress or not self.campaign_tracker:
            return

        # Get quest items in party inventory
        inventory_item_ids = []
        for character in self.party.characters:
            for item in character.inventory.items.values():
                inventory_item_ids.append(item.item_id)

        # Try to complete the dungeon
        newly_unlocked = self.campaign_tracker.complete_dungeon(
            self.campaign_progress,
            self.dungeon_name,
            inventory_item_ids
        )

        if newly_unlocked:
            # Get dungeon names for display
            unlocked_names = []
            for dungeon_id in newly_unlocked:
                definition = self.campaign_tracker.load_campaign_definition(
                    self.campaign_progress.campaign_id
                )
                if definition and dungeon_id in definition.dungeons:
                    unlocked_names.append(definition.dungeons[dungeon_id].name)
                else:
                    unlocked_names.append(dungeon_id)

            # Emit dungeon completed event
            self.event_bus.emit(Event(
                type=EventType.DUNGEON_COMPLETED,
                data={
                    "dungeon_id": self.dungeon_name,
                    "dungeon_name": self.dungeon.get("name", self.dungeon_name),
                    "newly_unlocked": newly_unlocked,
                    "unlocked_names": unlocked_names,
                    "campaign_complete": self.campaign_tracker.is_campaign_complete(
                        self.campaign_progress
                    )
                }
            ))

    def _on_quest_completed(self, event: Event) -> None:
        """
        Handle quest completion to unlock dungeons.

        When a quest completes with unlocks_dungeons, this handler:
        1. Unlocks those dungeons in campaign progress
        2. Emits DUNGEON_COMPLETED event for UI notification

        Args:
            event: Quest completed event with unlocked_dungeons data
        """
        if not self.campaign_progress or not self.campaign_tracker:
            return

        unlocked_dungeons = event.data.get("unlocked_dungeons", [])
        if not unlocked_dungeons:
            return

        # Mark current dungeon as completed and unlock the specified dungeons
        # First record boss defeat if not already done
        if self.dungeon_name not in self.campaign_progress.boss_defeats:
            self.campaign_tracker.record_boss_defeat(
                self.campaign_progress, self.dungeon_name
            )

        # Get current inventory items for completion check
        inventory_item_ids = []
        for character in self.party.characters:
            for item in character.inventory.items.values():
                inventory_item_ids.append(item.item_id)

        # Try to complete the dungeon (this will unlock the dungeons specified
        # in the campaign definition if all criteria are met)
        newly_unlocked = self.campaign_tracker.complete_dungeon(
            self.campaign_progress,
            self.dungeon_name,
            inventory_item_ids
        )

        if newly_unlocked:
            # Get dungeon names for display
            unlocked_names = []
            for dungeon_id in newly_unlocked:
                definition = self.campaign_tracker.load_campaign_definition(
                    self.campaign_progress.campaign_id
                )
                if definition and dungeon_id in definition.dungeons:
                    unlocked_names.append(definition.dungeons[dungeon_id].name)
                else:
                    unlocked_names.append(dungeon_id)

            # Emit dungeon completed event
            self.event_bus.emit(Event(
                type=EventType.DUNGEON_COMPLETED,
                data={
                    "dungeon_id": self.dungeon_name,
                    "dungeon_name": self.dungeon.get("name", self.dungeon_name),
                    "newly_unlocked": newly_unlocked,
                    "unlocked_names": unlocked_names,
                    "campaign_complete": self.campaign_tracker.is_campaign_complete(
                        self.campaign_progress
                    )
                }
            ))

    def record_combat_event(self, event: CombatEvent) -> None:
        """
        Record a combat event in history with automatic trimming.

        Args:
            event: The CombatEvent to record
        """
        self.combat_history.append(event)
        if len(self.combat_history) > self.max_combat_history_size:
            self.combat_history = self.combat_history[-self.max_combat_history_size:]

    def get_recent_combat_history(self, count: int = 12) -> list[CombatEvent]:
        """
        Get recent combat events for narrative context.

        Args:
            count: Number of recent events to return

        Returns:
            List of recent CombatEvent objects
        """
        return self.combat_history[-count:]

    def clear_combat_history(self) -> None:
        """Clear combat history (called when combat ends)."""
        self.combat_history.clear()

    def get_battlefield_state(self) -> BattlefieldState:
        """
        Get complete battlefield state snapshot.

        Returns structured view of all combatants, their status,
        and current combat state. Useful for UI display, LLM context,
        and analytics.

        Returns:
            BattlefieldState with all current combat information
        """
        if not self.in_combat or not self.initiative_tracker:
            # Return empty state if not in combat
            return BattlefieldState(
                party_combatants=[],
                enemy_combatants=[],
                round_number=0,
                current_turn="",
                in_combat=False
            )

        party_combatants = []
        enemy_combatants = []

        # Get current turn info
        current = self.initiative_tracker.get_current_combatant()
        current_turn = current.display_name if current and current.display_name else ""

        # Build combatant status for each entry in initiative
        for entry in self.initiative_tracker.get_all_combatants():
            creature = entry.creature
            status = CombatantStatus(
                name=creature.name,
                display_name=entry.display_name if entry.display_name else creature.name,
                current_hp=creature.current_hp,
                max_hp=creature.max_hp,
                is_alive=creature.is_alive,
                conditions=list(creature.conditions) if hasattr(creature, 'conditions') else [],
                is_player=creature in [c for c in self.party.characters],
                ac=creature.ac
            )

            if status.is_player:
                party_combatants.append(status)
            else:
                enemy_combatants.append(status)

        return BattlefieldState(
            party_combatants=party_combatants,
            enemy_combatants=enemy_combatants,
            round_number=self.initiative_tracker.round_number,
            current_turn=current_turn,
            in_combat=True
        )

    def get_room_display_context(self) -> RoomDisplayContext:
        """
        Get complete context needed to display the current room.

        Encapsulates all game state queries for room display, allowing
        the CLI to focus purely on presentation logic. Follows the same
        pattern as get_battlefield_state().

        Returns:
            RoomDisplayContext with all current room information
        """
        room = self.get_current_room()
        room_id = room.get("id", room.get("name", "unknown").lower().replace(" ", "_"))
        room_name = room.get("name", "Unknown Room")
        description = room.get("description", self.get_room_description())
        exits = self.get_available_exits()

        # Get monster information
        monster_names, monsters_data = self._get_room_monster_info(room)
        combat_starting = self._is_combat_starting(room)

        # Get lighting information
        base_lighting = room.get("lighting", "bright")
        party_lighting = self._calculate_party_lighting()
        light_casters = self._get_active_light_casters()

        # Get visible items
        visible_items = self._get_visible_items(room)

        # Get NPCs
        npc_display_names = self._get_room_npc_names(room)

        return RoomDisplayContext(
            room_id=room_id,
            room_name=room_name,
            description=description,
            exits=exits,
            monster_names=monster_names,
            combat_starting=combat_starting,
            base_lighting=base_lighting,
            party_lighting=party_lighting,
            light_casters=light_casters,
            previous_room_id=self.previous_room_id,
            visible_items=visible_items,
            npc_display_names=npc_display_names,
            room_searched=room.get("searched", False),
            monsters_data=monsters_data,
            party_size=len(self.party.characters)
        )

    def _get_room_monster_info(
        self, room: dict[str, Any]
    ) -> tuple[list[str], dict[str, Any]]:
        """
        Get monster names and data for the current room.

        Args:
            room: Current room data dict

        Returns:
            Tuple of (monster_names list, monsters_data dict)
        """
        enemy_ids = room.get("enemies", [])
        monster_names = []
        monsters_data = {}

        if enemy_ids:
            monsters_data = self.data_loader.load_monsters()
            for enemy_id in enemy_ids:
                if enemy_id in monsters_data:
                    monster_names.append(monsters_data[enemy_id]["name"])

        return monster_names, monsters_data

    def _is_combat_starting(self, room: dict[str, Any]) -> bool:
        """
        Check if combat is about to start in this room.

        Combat starts if there are enemies and we're not already in combat.

        Args:
            room: Current room data dict

        Returns:
            True if combat is about to start
        """
        enemy_ids = room.get("enemies", [])
        return bool(enemy_ids) and not self.in_combat

    def _calculate_party_lighting(self) -> list[PartyMemberLighting]:
        """
        Calculate effective lighting for each party member.

        Returns:
            List of PartyMemberLighting for each character
        """
        party_lighting = []
        for char in self.party.characters:
            lighting = self.get_effective_lighting(char)
            party_lighting.append(PartyMemberLighting(
                character_name=char.name,
                effective_lighting=lighting,
                has_darkvision=char.darkvision_range > 0
            ))
        return party_lighting

    def _get_active_light_casters(self) -> list[str]:
        """
        Get names of characters with active Light spells.

        Returns:
            List of character names who have cast Light
        """
        from dnd_engine.systems.time_manager import EffectType

        light_casters = []
        for effect in self.time_manager.active_effects:
            if effect.effect_type == EffectType.SPELL and effect.source.lower() == "light":
                if effect.caster_name and effect.caster_name not in light_casters:
                    light_casters.append(effect.caster_name)
        return light_casters

    def _get_visible_items(self, room: dict[str, Any]) -> list[VisibleItem]:
        """
        Get visible items in the room.

        Args:
            room: Current room data dict

        Returns:
            List of VisibleItem objects
        """
        visible_items = []
        for item in room.get("items", []):
            if not item.get("visible", False):
                continue

            item_type = item["type"]
            if item_type == "gold":
                visible_items.append(VisibleItem(
                    item_type="gold",
                    amount=item.get("amount", 0)
                ))
            elif item_type == "currency":
                visible_items.append(VisibleItem(
                    item_type="currency",
                    gold=item.get("gold", 0),
                    silver=item.get("silver", 0),
                    copper=item.get("copper", 0),
                    platinum=item.get("platinum", 0)
                ))
            else:
                item_id = item.get("id", "an item")
                visible_items.append(VisibleItem(
                    item_type="item",
                    item_id=item_id,
                    item_name=item_id.replace("_", " ").title()
                ))

        return visible_items

    def _get_room_npc_names(self, room: dict[str, Any]) -> list[str]:
        """
        Get display names of NPCs in the current room.

        Args:
            room: Current room data dict

        Returns:
            List of NPC display names
        """
        if not self.npc_manager:
            return []

        room_id = room.get("id", "")
        npcs = self.npc_manager.get_npcs_in_room(room_id)
        return [npc.display_name for npc in npcs]

    def _get_enemy_display_name(self, enemy: Creature) -> str:
        """
        Get the display name for an enemy from the initiative tracker.

        Args:
            enemy: The enemy creature

        Returns:
            Display name with combat number if applicable (e.g., "Goblin 2")
        """
        if self.initiative_tracker:
            for entry in self.initiative_tracker.get_all_combatants():
                if entry.creature == enemy:
                    return entry.display_name if entry.display_name else enemy.name
        return enemy.name

    def _should_enemy_attempt_condition_removal(
        self,
        enemy: Creature
    ) -> ConditionRemovalResult | None:
        """
        Determine if enemy should attempt condition removal and execute it.

        Args:
            enemy: The enemy creature

        Returns:
            ConditionRemovalResult if attempted, None otherwise
        """
        for condition_id in list(enemy.conditions):
            if not self.condition_manager.can_attempt_early_removal(condition_id):
                continue

            # Use AI to decide if condition should be removed
            if condition_id == "on_fire" and self.enemy_ai.should_attempt_condition_removal(
                enemy
            ):
                # Attempt removal
                result = self.condition_manager.attempt_condition_removal(
                    enemy, condition_id
                )

                if result:
                    return ConditionRemovalResult(
                        condition_id=condition_id,
                        attempted=True,
                        success=result.success,
                        message=result.message
                    )

                return ConditionRemovalResult(
                    condition_id=condition_id,
                    attempted=True,
                    success=False,
                    message=f"{enemy.name} failed to remove {condition_id}"
                )

        return None

    def get_removable_conditions(
        self,
        creature: Character | Creature
    ) -> list[ConditionRemovalOption]:
        """
        Get conditions that can be removed this turn.

        Checks each condition on the creature for early removal options
        and validates that the required action is available.

        Args:
            creature: The creature with conditions to check

        Returns:
            List of ConditionRemovalOption for conditions that can be removed
        """
        options: list[ConditionRemovalOption] = []

        # Get turn state for action availability check
        turn_state = (
            self.initiative_tracker.get_current_turn_state()
            if self.initiative_tracker else None
        )

        for condition_id in list(creature.conditions):
            if not self.condition_manager.can_attempt_early_removal(condition_id):
                continue

            prompt_info = self.condition_manager.get_removal_prompt_info(condition_id)
            if not prompt_info:
                continue

            # Map action_cost string to ActionType
            action_cost_str = prompt_info.get("action_cost", "action")
            action_type_map = {
                "action": ActionType.ACTION,
                "bonus_action": ActionType.BONUS_ACTION,
                "free_object": ActionType.FREE_OBJECT,
                "no_action": ActionType.NO_ACTION
            }
            action_cost = action_type_map.get(action_cost_str, ActionType.ACTION)

            # Check if the required action is available
            if turn_state and not turn_state.is_action_available(action_cost):
                continue

            options.append(ConditionRemovalOption(
                condition_id=condition_id,
                condition_name=prompt_info.get("condition_name", condition_id),
                ability=prompt_info.get("ability", "dexterity"),
                dc=prompt_info.get("dc", 10),
                action_cost=action_cost,
                description=prompt_info.get("description", "")
            ))

        return options

    def attempt_player_condition_removal(
        self,
        creature: Character | Creature,
        condition_id: str
    ) -> ConditionRemovalResult:
        """
        Attempt to remove a condition from a player character.

        Handles the complete flow:
        1. Validates the condition can be removed
        2. Validates and consumes the required action
        3. Executes the ability check via ConditionManager
        4. Returns result with all information for UI display

        Args:
            creature: The creature attempting to remove the condition
            condition_id: The condition to attempt to remove

        Returns:
            ConditionRemovalResult with attempt outcome
        """
        # Check if condition can be removed
        if not self.condition_manager.can_attempt_early_removal(condition_id):
            return ConditionRemovalResult(
                condition_id=condition_id,
                attempted=False,
                success=False,
                message=f"Condition {condition_id} cannot be removed early"
            )

        prompt_info = self.condition_manager.get_removal_prompt_info(condition_id)
        if not prompt_info:
            return ConditionRemovalResult(
                condition_id=condition_id,
                attempted=False,
                success=False,
                message=f"No removal information for {condition_id}"
            )

        # Determine action cost
        action_cost_str = prompt_info.get("action_cost", "action")
        action_type_map = {
            "action": ActionType.ACTION,
            "bonus_action": ActionType.BONUS_ACTION,
            "free_object": ActionType.FREE_OBJECT,
            "no_action": ActionType.NO_ACTION
        }
        action_cost = action_type_map.get(action_cost_str, ActionType.ACTION)

        # Validate and consume action
        turn_state = (
            self.initiative_tracker.get_current_turn_state()
            if self.initiative_tracker else None
        )

        if not turn_state:
            return ConditionRemovalResult(
                condition_id=condition_id,
                attempted=False,
                success=False,
                message="Unable to get current turn state"
            )

        if not turn_state.is_action_available(action_cost):
            action_name = action_cost_str.replace("_", " ").title()
            return ConditionRemovalResult(
                condition_id=condition_id,
                attempted=False,
                success=False,
                message=f"No {action_name} available this turn"
            )

        # Consume the action
        if not turn_state.consume_action(action_cost):
            return ConditionRemovalResult(
                condition_id=condition_id,
                attempted=False,
                success=False,
                message=f"Failed to consume {action_cost_str}"
            )

        # Attempt the removal via ConditionManager
        ability_result = self.condition_manager.attempt_condition_removal(
            creature, condition_id
        )

        if ability_result:
            return ConditionRemovalResult(
                condition_id=condition_id,
                attempted=True,
                success=ability_result.success,
                message=ability_result.message,
                action_consumed=action_cost
            )

        # Fallback if ConditionManager returns None
        return ConditionRemovalResult(
            condition_id=condition_id,
            attempted=True,
            success=False,
            message=f"{creature.name} failed to remove {condition_id}",
            action_consumed=action_cost
        )

    def process_enemy_turn(self) -> EnemyTurnResult | None:
        """
        Process the current enemy's turn and return result for display.

        Handles all game logic for enemy turns:
        - Turn start effects (ongoing damage, etc.)
        - AI decisions (condition removal vs attack)
        - Target selection
        - Attack resolution
        - Concentration checks
        - Turn end effects

        Returns:
            EnemyTurnResult with all information needed for UI display,
            or None if current turn is not an enemy's turn.
        """
        if not self.in_combat or not self.initiative_tracker:
            return None

        current = self.initiative_tracker.get_current_combatant()

        # Check if it's a party member's turn
        for character in self.party.characters:
            if current.creature == character:
                return None  # Not an enemy turn

        enemy = current.creature
        enemy_display_name = self._get_enemy_display_name(enemy)

        # Build base result
        turn_start_effects: list[TurnEffectResult] = []
        turn_end_effects: list[TurnEffectResult] = []

        # Check if enemy is alive
        if not enemy.is_alive:
            self.initiative_tracker.next_turn()
            return EnemyTurnResult(
                enemy_name=enemy.name,
                enemy_display_name=enemy_display_name,
                action_taken=EnemyTurnAction.DIED_START_OF_TURN,
                turn_advanced=True
            )

        # Process turn-start effects (e.g., ongoing fire damage)
        start_results = self.condition_manager.process_turn_start_effects(enemy)
        for result in start_results:
            turn_start_effects.append(TurnEffectResult(
                effect_type=result.effect_type,
                condition_id=result.condition_id,
                message=result.message,
                damage=result.amount,
                creature_died=not enemy.is_alive
            ))

        # Check if enemy died from turn-start effects
        if not enemy.is_alive:
            self.initiative_tracker.next_turn()
            return EnemyTurnResult(
                enemy_name=enemy.name,
                enemy_display_name=enemy_display_name,
                action_taken=EnemyTurnAction.DIED_START_OF_TURN,
                turn_start_effects=turn_start_effects,
                turn_advanced=True
            )

        # Check if enemy can act (not incapacitated or surprised)
        if not enemy.can_take_actions():
            incapacitating = [c.upper() for c in enemy.conditions]
            # Process end-of-turn conditions (will remove surprised, etc.)
            end_results = enemy.process_end_of_turn_conditions(self.event_bus)
            for result in end_results:
                if result["type"] == "condition_expired":
                    turn_end_effects.append(TurnEffectResult(
                        effect_type="condition_expired",
                        condition_id=result["condition"],
                        message=f"{result['condition'].upper()} on {enemy.name} has expired!"
                    ))

            self.initiative_tracker.next_turn()
            return EnemyTurnResult(
                enemy_name=enemy.name,
                enemy_display_name=enemy_display_name,
                action_taken=EnemyTurnAction.INCAPACITATED,
                incapacitating_conditions=incapacitating,
                turn_start_effects=turn_start_effects,
                turn_end_effects=turn_end_effects,
                turn_advanced=True
            )

        # Enemy AI: Check if should attempt to remove conditions
        condition_removal = self._should_enemy_attempt_condition_removal(enemy)
        if condition_removal:
            self.initiative_tracker.next_turn()
            return EnemyTurnResult(
                enemy_name=enemy.name,
                enemy_display_name=enemy_display_name,
                action_taken=EnemyTurnAction.CONDITION_REMOVAL,
                condition_removal=condition_removal,
                turn_start_effects=turn_start_effects,
                turn_advanced=True
            )

        # Choose target from living party members using AI
        living_party = self.party.get_living_members()
        if not living_party:
            # No conscious targets - check if combat should end
            self._check_combat_end()
            if not self.in_combat:
                return EnemyTurnResult(
                    enemy_name=enemy.name,
                    enemy_display_name=enemy_display_name,
                    action_taken=EnemyTurnAction.NO_TARGETS,
                    turn_start_effects=turn_start_effects,
                    combat_ended=True,
                    turn_advanced=False
                )
            # Combat continues (e.g., stabilized characters), advance turn
            self.initiative_tracker.next_turn()
            return EnemyTurnResult(
                enemy_name=enemy.name,
                enemy_display_name=enemy_display_name,
                action_taken=EnemyTurnAction.NO_TARGETS,
                turn_start_effects=turn_start_effects,
                turn_advanced=True
            )

        # Use smart targeting based on enemy intelligence and combat history
        target = self.enemy_ai.select_target_smart(
            available_targets=living_party,
            enemy_intelligence=enemy.abilities.intelligence,
            combat_history=self.combat_history,
            enemy_name=enemy.name,
        )

        # Get monster data for attack
        monsters = self.data_loader.load_monsters()
        monster_data = None
        for mid, mdata in monsters.items():
            if mdata["name"] == enemy.name:
                monster_data = mdata
                break

        if not monster_data or not monster_data.get("actions"):
            self.initiative_tracker.next_turn()
            return EnemyTurnResult(
                enemy_name=enemy.name,
                enemy_display_name=enemy_display_name,
                action_taken=EnemyTurnAction.NO_VALID_ATTACK,
                target_name=target.name,
                turn_start_effects=turn_start_effects,
                error="No monster data or actions found",
                turn_advanced=True
            )

        # Find first weapon attack action (skip Multiattack, etc.)
        action = None
        for act in monster_data["actions"]:
            if "attack_bonus" in act and "damage" in act:
                action = act
                break

        if not action:
            self.initiative_tracker.next_turn()
            return EnemyTurnResult(
                enemy_name=enemy.name,
                enemy_display_name=enemy_display_name,
                action_taken=EnemyTurnAction.NO_VALID_ATTACK,
                target_name=target.name,
                turn_start_effects=turn_start_effects,
                error="No valid attack actions",
                turn_advanced=True
            )

        # Track conditions before attack (for saving throw detection)
        conditions_before = set()
        if hasattr(target, 'active_conditions'):
            conditions_before = set(target.active_conditions.keys())

        # Resolve attack
        attack_result = self.combat_engine.resolve_attack(
            attacker=enemy,
            defender=target,
            attack_bonus=action["attack_bonus"],
            damage_dice=action["damage"],
            apply_damage=True,
            event_bus=self.event_bus,
            action=action,
            game_state=self
        )

        # Check concentration if target was hit and took damage
        concentration_broken = None
        if attack_result.hit and attack_result.damage > 0:
            conc_result = self.check_concentration_from_damage(
                target.name,
                attack_result.damage
            )
            if conc_result["concentration_broken"]:
                concentration_broken = conc_result

        # Detect saving throw results
        saving_throw_triggered = False
        save_ability = None
        save_dc = None
        save_succeeded = None
        conditions_applied: list[str] = []

        if attack_result.hit and "saving_throw" in action:
            save_data = action["saving_throw"]
            save_ability = save_data.get("ability", "constitution").title()
            save_dc = save_data.get("dc")
            saving_throw_triggered = True

            # Check if condition was applied (save failed)
            if hasattr(target, 'active_conditions'):
                conditions_after = set(target.active_conditions.keys())
                new_conditions = conditions_after - conditions_before
                if new_conditions:
                    save_succeeded = False
                    conditions_applied = list(new_conditions)
                else:
                    save_succeeded = True

        # Process end-of-turn conditions
        end_results = enemy.process_end_of_turn_conditions(self.event_bus)
        for result in end_results:
            if result["type"] == "condition_expired":
                turn_end_effects.append(TurnEffectResult(
                    effect_type="condition_expired",
                    condition_id=result["condition"],
                    message=f"{result['condition'].upper()} on {enemy.name} has expired!"
                ))

        # Advance turn
        self.initiative_tracker.next_turn()

        # Check if party wiped
        combat_ended = self.party.is_wiped()
        if combat_ended:
            self._check_combat_end()

        # Build narrative context for LLM enhancement
        narrative_context = {
            "attacker": enemy.name,
            "attacker_display_name": enemy_display_name,
            "target": target.name,
            "action_name": action.get("name", "attack"),
            "hit": attack_result.hit,
            "damage": attack_result.damage if attack_result.hit else 0,
            "critical": attack_result.critical_hit,
            "target_hp_before": target.current_hp + (
                attack_result.damage if attack_result.hit else 0
            ),
            "target_hp_after": target.current_hp,
            "target_killed": not target.is_alive,
        }

        return EnemyTurnResult(
            enemy_name=enemy.name,
            enemy_display_name=enemy_display_name,
            action_taken=EnemyTurnAction.ATTACK,
            attack_result=attack_result,
            target_name=target.name,
            target_killed=not target.is_alive,
            action_data=action,
            saving_throw_triggered=saving_throw_triggered,
            save_ability=save_ability,
            save_dc=save_dc,
            save_succeeded=save_succeeded,
            conditions_applied=conditions_applied,
            concentration_broken=concentration_broken,
            turn_start_effects=turn_start_effects,
            turn_end_effects=turn_end_effects,
            narrative_context=narrative_context,
            turn_advanced=True,
            combat_ended=combat_ended
        )

    def flee_combat(self) -> dict[str, Any]:
        """
        Attempt to flee from combat.

        Party flees together, but each living enemy gets one opportunity attack
        against random living party members. No XP is awarded. Party automatically
        retreats to the previous room (reverse of last_entry_direction).

        Returns:
            Dictionary with flee results including:
            - success: True if fled successfully, False if failed
            - reason: Failure reason (if failed)
            - opportunity_attacks: List of attack results
            - casualties: List of party members who died during flee
            - retreat_direction: Direction party fled (if successful)
            - retreat_room: Room name party fled to (if successful)
        """
        if not self.in_combat:
            return {"success": False, "reason": "Not in combat"}

        # Check if we can retreat (need previous direction)
        if not self.last_entry_direction:
            return {
                "success": False,
                "reason": "Nowhere to retreat! You're trapped in this room."
            }

        # Calculate retreat direction
        retreat_direction = REVERSE_DIRECTIONS.get(self.last_entry_direction)
        if not retreat_direction:
            return {
                "success": False,
                "reason": f"Cannot determine retreat direction from '{self.last_entry_direction}'"
            }

        # Track flee results
        opportunity_attacks = []
        casualties = []

        # Each living enemy gets one opportunity attack
        living_enemies = [e for e in self.active_enemies if e.is_alive]
        living_party = self.party.get_living_members()

        if living_party and living_enemies:
            # Load monster data for attack stats
            monsters = self.data_loader.load_monsters()

            for enemy in living_enemies:
                # Pick a random living party member to attack
                import random
                target = random.choice(living_party)

                # Find enemy's attack data
                monster_data = None
                for monster_id, mdata in monsters.items():
                    if mdata["name"] == enemy.name:
                        monster_data = mdata
                        break

                if monster_data and monster_data.get("actions"):
                    # Find first action with attack_bonus (skip Multiattack, etc.)
                    action = None
                    for act in monster_data["actions"]:
                        if "attack_bonus" in act:
                            action = act
                            break

                    if action:
                        result = self.combat_engine.resolve_attack(
                            attacker=enemy,
                            defender=target,
                            attack_bonus=action["attack_bonus"],
                            damage_dice=action["damage"],
                            apply_damage=True,
                            game_state=self
                        )
                        opportunity_attacks.append(result)

                        # Emit damage event if hit
                        if result.hit:
                            self.event_bus.emit(Event(
                                type=EventType.DAMAGE_DEALT,
                                data={
                                    "attacker": enemy.name,
                                    "defender": target.name,
                                    "damage": result.damage,
                                    "opportunity_attack": True
                                }
                            ))

                            # Check concentration if target took damage
                            if result.damage > 0:
                                concentration_result = self.check_concentration_from_damage(
                                    target.name,
                                    result.damage
                                )
                                if concentration_result["concentration_broken"]:
                                    # Store result for later display
                                    result.concentration_broken = True
                                    result.broken_spell = concentration_result["spell_name"]

                        # Track casualties
                        if not target.is_alive:
                            casualties.append(target.name)
                            self.event_bus.emit(Event(
                                type=EventType.CHARACTER_DEATH,
                                data={"name": target.name}
                            ))

                # Update living party list if someone died
                living_party = self.party.get_living_members()
                if not living_party:
                    break  # No one left to attack

        # Clear combat state (no XP awarded for fleeing)
        self.in_combat = False
        self.initiative_tracker = None
        self.clear_combat_history()

        # Enemies remain in room (can encounter them again)
        # Do NOT clear enemies from room like in _end_combat

        # Retreat to previous room
        move_success = self.move(retreat_direction)

        if not move_success:
            # This shouldn't happen if direction tracking is correct, but handle gracefully
            return {
                "success": False,
                "reason": f"Failed to retreat {retreat_direction} - exit may not exist"
            }

        # Get new room info for return data
        new_room = self.get_current_room()
        retreat_room_name = new_room.get("name", "Unknown")

        # Emit flee event
        self.event_bus.emit(Event(
            type=EventType.COMBAT_FLED,
            data={
                "opportunity_attacks": len(opportunity_attacks),
                "casualties": casualties,
                "surviving_party": [c.name for c in self.party.get_living_members()],
                "retreat_direction": retreat_direction,
                "retreat_room": retreat_room_name
            }
        ))

        return {
            "success": True,
            "opportunity_attacks": opportunity_attacks,
            "casualties": casualties,
            "retreat_direction": retreat_direction,
            "retreat_room": retreat_room_name
        }

    def reset_dungeon(self, new_dungeon_name: str | None = None) -> None:
        """
        Reset the dungeon to its initial state.

        Keeps party data intact while resetting:
        - Current room to dungeon entrance
        - All room states (searched flags, enemies)
        - Combat state
        - Action history

        Args:
            new_dungeon_name: If provided, switch to a different dungeon
        """
        # Emit reset started event
        self.event_bus.emit(Event(
            type=EventType.RESET_STARTED,
            data={
                "old_dungeon": self.dungeon_name,
                "new_dungeon": new_dungeon_name or self.dungeon_name
            }
        ))

        # Load new dungeon if specified, otherwise reload current one
        if new_dungeon_name:
            self.dungeon_name = new_dungeon_name
            self.dungeon = self.data_loader.load_dungeon(
                new_dungeon_name, self.campaign_id
            )
        else:
            # Reload current dungeon from disk to reset state
            self.dungeon = self.data_loader.load_dungeon(
                self.dungeon_name, self.campaign_id
            )

        # Reset to start room
        self.current_room_id = self.dungeon["start_room"]

        # Reset combat state
        self.in_combat = False
        self.initiative_tracker = None
        self.active_enemies = []

        # Reset navigation tracking
        self.last_entry_direction = None
        self.previous_room_id = None

        # Clear action history
        self.action_history = []

        # Emit reset complete event
        self.event_bus.emit(Event(
            type=EventType.RESET_COMPLETE,
            data={
                "dungeon": self.dungeon_name,
                "current_room": self.current_room_id
            }
        ))

    def reset_party_hp(self) -> None:
        """
        Restore all party members to full health.

        Heals all living and dead characters to their maximum HP.
        """
        for character in self.party.characters:
            character.current_hp = character.max_hp

    def reset_party_conditions(self) -> None:
        """
        Clear all conditions from all party members.

        Removes conditions like poisoned, paralyzed, stunned, etc.
        """
        for character in self.party.characters:
            character.active_conditions.clear()

    def use_combat_attack_item(
        self,
        user: Character,
        item_id: str,
        target: Creature
    ) -> CombatItemResult:
        """
        Use a combat attack item (thrown weapon) on a target during combat.

        Handles the complete flow of using attack items like Alchemist's Fire, Acid Vials:
        1. Validates action economy
        2. Consumes item from inventory
        3. Makes ranged attack roll (DEX-based)
        4. Applies damage on hit
        5. Applies special effects (e.g., ongoing fire damage)
        6. Emits appropriate events

        Args:
            user: Character using the item
            item_id: ID of the item to use
            target: Target creature for the attack

        Returns:
            CombatItemResult with attack outcome and display information
        """
        # Load item data (structure: {"weapons": {...}, "armor": {...}, "consumables": {...}})
        items_data = self.data_loader.load_items(self.campaign_id)

        # Find item in categories
        item_data = None
        for category, category_items in items_data.items():
            if item_id in category_items:
                item_data = category_items[item_id]
                break

        if item_data is None:
            return CombatItemResult(
                success=False,
                attack_result=None,
                item_name=item_id,
                action_type=ActionType.ACTION,
                error_message=f"Item '{item_id}' not found"
            )

        item_name = item_data.get("name", item_id)

        # Parse action required
        action_required_str = item_data.get("action_required", "action")
        action_type_map = {
            "action": ActionType.ACTION,
            "bonus_action": ActionType.BONUS_ACTION,
            "free_object": ActionType.FREE_OBJECT,
            "no_action": ActionType.NO_ACTION
        }
        action_required = action_type_map.get(action_required_str, ActionType.ACTION)

        # Validate action economy
        turn_state = self.initiative_tracker.get_current_turn_state() if self.initiative_tracker else None
        if not turn_state:
            return CombatItemResult(
                success=False,
                attack_result=None,
                item_name=item_name,
                action_type=action_required,
                error_message="Unable to get current turn state"
            )

        if not turn_state.is_action_available(action_required):
            action_name = action_required_str.replace("_", " ").title()
            return CombatItemResult(
                success=False,
                attack_result=None,
                item_name=item_name,
                action_type=action_required,
                error_message=f"No {action_name} available this turn"
            )

        # Consume the action
        if not turn_state.consume_action(action_required):
            return CombatItemResult(
                success=False,
                attack_result=None,
                item_name=item_name,
                action_type=action_required,
                error_message=f"Failed to consume {action_required_str}"
            )

        # Use the item from inventory (removes it)
        inventory = user.inventory
        success, used_item_data = inventory.use_item(item_id, items_data)

        if not success:
            # Restore the action since item use failed
            turn_state.reset()
            turn_state.consume_action(action_required)
            return CombatItemResult(
                success=False,
                attack_result=None,
                item_name=item_name,
                action_type=action_required,
                error_message=f"Failed to use {item_name} from inventory"
            )

        # Calculate attack bonus (DEX-based improvised ranged weapon)
        attack_bonus = user.abilities.dex_mod
        if hasattr(user, 'proficiency_bonus'):
            attack_bonus += user.proficiency_bonus

        # Get damage from item
        damage_dice = used_item_data.get("damage", "1d4")
        damage_type = used_item_data.get("damage_type", "damage")

        # Resolve the attack
        attack_result = self.combat_engine.resolve_attack(
            attacker=user,
            defender=target,
            attack_bonus=attack_bonus,
            damage_dice=damage_dice,
            apply_damage=True,
            event_bus=self.event_bus,
            game_state=self
        )

        # Apply special effects on hit
        special_effects = []
        if attack_result.hit:
            # Apply condition if item has applies_condition field (e.g., Alchemist's Fire → on_fire)
            applies_condition = used_item_data.get("applies_condition")
            if applies_condition:
                target.add_condition(applies_condition)
                special_effects.append(applies_condition)

        # Emit item used event
        self.event_bus.emit(Event(
            type=EventType.ITEM_USED,
            data={
                "character": user.name,
                "target": target.name,
                "item_id": item_id,
                "item_name": item_name,
                "effect_type": "attack",
                "action_cost": action_required_str,
                "success": attack_result.hit,
                "damage": attack_result.damage if attack_result.hit else 0
            }
        ))

        return CombatItemResult(
            success=True,
            attack_result=attack_result,
            item_name=item_name,
            action_type=action_required,
            special_effects=special_effects
        )

    def use_item_combat(
        self,
        user: Character,
        item_id: str,
        target: Character | Creature
    ) -> CombatItemUseResult:
        """
        Use a consumable item during combat (non-attack items like potions).

        Handles the complete flow of using consumable items:
        1. Validates action economy
        2. Consumes item from inventory
        3. Applies item effect to target
        4. Emits appropriate events

        Args:
            user: Character using the item
            item_id: ID of the item to use
            target: Target character/creature for the effect

        Returns:
            CombatItemUseResult with effect outcome and display information
        """
        from dnd_engine.systems.item_effects import apply_item_effect

        # Load item data (including campaign-specific items)
        items_data = self.data_loader.load_items(self.campaign_id)

        # Find item in consumables category
        item_data = items_data.get("consumables", {}).get(item_id)

        if item_data is None:
            return CombatItemUseResult(
                success=False,
                item_name=item_id,
                action_type=ActionType.ACTION,
                user_name=user.name,
                target_name=target.name,
                error_message=f"Item '{item_id}' not found in consumables"
            )

        item_name = item_data.get("name", item_id)

        # Parse action required
        action_required_str = item_data.get("action_required", "action")
        action_type_map = {
            "action": ActionType.ACTION,
            "bonus_action": ActionType.BONUS_ACTION,
            "free_object": ActionType.FREE_OBJECT,
            "no_action": ActionType.NO_ACTION
        }
        action_required = action_type_map.get(action_required_str, ActionType.ACTION)

        # Validate action economy
        turn_state = self.initiative_tracker.get_current_turn_state() if self.initiative_tracker else None
        if not turn_state:
            return CombatItemUseResult(
                success=False,
                item_name=item_name,
                action_type=action_required,
                user_name=user.name,
                target_name=target.name,
                error_message="Unable to get current turn state"
            )

        if not turn_state.is_action_available(action_required):
            action_name = action_required_str.replace("_", " ").title()
            return CombatItemUseResult(
                success=False,
                item_name=item_name,
                action_type=action_required,
                user_name=user.name,
                target_name=target.name,
                error_message=f"No {action_name} available this turn"
            )

        # Consume the action
        if not turn_state.consume_action(action_required):
            return CombatItemUseResult(
                success=False,
                item_name=item_name,
                action_type=action_required,
                user_name=user.name,
                target_name=target.name,
                error_message=f"Failed to consume {action_required_str}"
            )

        # Track HP before for healing display
        hp_before = target.current_hp

        # Use the item from inventory (removes it)
        inventory = user.inventory
        success, used_item_data = inventory.use_item(item_id, items_data)

        if not success:
            # Restore the action since item use failed
            turn_state.reset()
            turn_state.consume_action(action_required)
            return CombatItemUseResult(
                success=False,
                item_name=item_name,
                action_type=action_required,
                user_name=user.name,
                target_name=target.name,
                error_message=f"Failed to use {item_name} from inventory"
            )

        # Apply the item's effect
        effect_result = apply_item_effect(
            item_info=used_item_data,
            target=target,
            dice_roller=self.dice_roller,
            event_bus=self.event_bus,
            time_manager=self.time_manager
        )

        # Track HP after for healing display
        hp_after = target.current_hp

        # Emit item used event
        self.event_bus.emit(Event(
            type=EventType.ITEM_USED,
            data={
                "character": user.name,
                "target": target.name,
                "item_id": item_id,
                "item_name": item_name,
                "effect_type": effect_result.effect_type,
                "action_cost": action_required_str,
                "success": effect_result.success
            }
        ))

        return CombatItemUseResult(
            success=True,
            item_name=item_name,
            action_type=action_required,
            user_name=user.name,
            target_name=target.name,
            effect_type=effect_result.effect_type,
            effect_message=effect_result.message,
            effect_amount=effect_result.amount,
            hp_before=hp_before,
            hp_after=hp_after
        )

    def party_rest(self, rest_type: str) -> PartyRestResult:
        """
        Process a rest for the entire party.

        Handles all game logic for resting:
        - Applies rest to all party members
        - Emits appropriate events
        - Advances game time

        Args:
            rest_type: "short" or "long"

        Returns:
            PartyRestResult containing all information needed for display
        """
        if rest_type not in ("short", "long"):
            raise ValueError(f"Invalid rest_type: {rest_type}. Must be 'short' or 'long'")

        # Determine rest duration in minutes
        rest_duration_minutes = 60 if rest_type == "short" else 480

        # Collect results for all party members
        character_results: list[CharacterRestResult] = []
        hp_recovered_total: dict[str, int] = {}
        resources_recovered_total: dict[str, dict[str, Any]] = {}

        for character in self.party.characters:
            hp_before = character.current_hp

            # Apply rest
            if rest_type == "short":
                result = character.take_short_rest()
            else:
                result = character.take_long_rest()

            hp_after = character.current_hp

            # Create character result
            char_result = CharacterRestResult(
                character_name=result["character"],
                hp_recovered=result["hp_recovered"],
                hp_before=hp_before,
                hp_after=hp_after,
                max_hp=character.max_hp,
                resources_recovered=result["resources_recovered"],
                can_prepare_spells=result.get("can_prepare_spells", False)
            )
            character_results.append(char_result)

            # Track for event data
            hp_recovered_total[character.name] = result["hp_recovered"]
            resources_recovered_total[character.name] = result["resources_recovered"]

        # Emit rest event
        event_type = EventType.SHORT_REST if rest_type == "short" else EventType.LONG_REST
        event = Event(
            type=event_type,
            data={
                "party": [char.name for char in self.party.characters],
                "rest_type": rest_type,
                "hp_recovered": hp_recovered_total,
                "resources_recovered": resources_recovered_total
            }
        )
        self.event_bus.emit(event)

        # Advance game time
        reason = "short_rest" if rest_type == "short" else "long_rest"
        self.time_manager.advance_time(rest_duration_minutes, reason=reason)

        return PartyRestResult(
            rest_type=rest_type,
            rest_duration_minutes=rest_duration_minutes,
            character_results=character_results
        )
