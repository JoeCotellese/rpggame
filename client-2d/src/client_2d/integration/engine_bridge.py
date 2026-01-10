# ABOUTME: Bridge between dnd-engine and client-2d for game state synchronization.
# ABOUTME: Subscribes to engine events and translates them to client-2d updates.

"""Engine bridge for integrating dnd-engine with client-2d."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dnd_engine.core.game_state import GameState as EngineGameState
    from dnd_engine.core.party import Party
    from dnd_engine.utils.events import Event, EventBus


@dataclass
class PlayerState:
    """Player state synchronized from engine."""

    hp: int = 30
    max_hp: int = 30
    name: str = "Player"
    light_source: str = "torch"
    conditions: list[str] = field(default_factory=list)


@dataclass
class EntityState:
    """Entity state synchronized from engine."""

    entity_id: str
    name: str
    entity_type: str  # "monster", "item", "npc"
    hp: int = 0
    max_hp: int = 0
    is_alive: bool = True


@dataclass
class CombatState:
    """Combat state synchronized from engine."""

    in_combat: bool = False
    round_number: int = 0
    current_turn: str = ""
    enemies: list[EntityState] = field(default_factory=list)


# Event callback type for client notifications
ClientEventCallback = Callable[[str, dict[str, Any]], None]


class EngineBridge:
    """Bridge between dnd-engine and client-2d.

    Subscribes to engine EventBus and maintains a synchronized view
    of game state for the client. Notifies client of state changes
    via callbacks.

    Usage:
        from dnd_engine.utils.events import EventBus
        from dnd_engine.core.game_state import GameState

        event_bus = EventBus()
        game_state = GameState(...)

        bridge = EngineBridge()
        bridge.connect(event_bus, game_state)

        # Register client callbacks
        bridge.on_event("player_damaged", lambda data: update_hp_bar(data))
        bridge.on_event("combat_started", lambda data: switch_to_combat_mode(data))

        # Get current state
        player = bridge.get_player_state()
        combat = bridge.get_combat_state()
    """

    def __init__(self) -> None:
        """Initialize the engine bridge."""
        self._event_bus: EventBus | None = None
        self._engine_state: EngineGameState | None = None

        # Synchronized state
        self._player_state = PlayerState()
        self._combat_state = CombatState()
        self._entities: dict[str, EntityState] = {}
        self._turn: int = 0

        # Client callbacks
        self._callbacks: dict[str, list[ClientEventCallback]] = {}

        # Track if connected
        self._connected = False

    def connect(
        self, event_bus: EventBus, engine_state: EngineGameState | None = None
    ) -> None:
        """Connect to the engine event bus.

        Args:
            event_bus: The engine's EventBus instance
            engine_state: Optional GameState for initial sync
        """
        if self._connected:
            self.disconnect()

        self._event_bus = event_bus
        self._engine_state = engine_state
        self._connected = True

        # Subscribe to relevant events
        self._subscribe_to_events()

        # Initial sync if we have state
        if engine_state:
            self._sync_from_engine()

    def disconnect(self) -> None:
        """Disconnect from the engine event bus."""
        if self._event_bus:
            self._unsubscribe_from_events()

        self._event_bus = None
        self._engine_state = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if bridge is connected to engine."""
        return self._connected

    def on_event(self, event_name: str, callback: ClientEventCallback) -> None:
        """Register a callback for client events.

        Args:
            event_name: Event type to listen for
            callback: Function called with event data
        """
        if event_name not in self._callbacks:
            self._callbacks[event_name] = []
        self._callbacks[event_name].append(callback)

    def off_event(self, event_name: str, callback: ClientEventCallback) -> None:
        """Unregister a callback for client events.

        Args:
            event_name: Event type to stop listening for
            callback: Function to remove
        """
        if event_name in self._callbacks:
            try:
                self._callbacks[event_name].remove(callback)
            except ValueError:
                pass

    def _emit_client_event(self, event_name: str, data: dict[str, Any]) -> None:
        """Emit an event to registered client callbacks."""
        if event_name in self._callbacks:
            for callback in self._callbacks[event_name]:
                try:
                    callback(data)
                except Exception:
                    # Don't let callback errors break the bridge
                    pass

    # State getters
    def get_player_state(self) -> PlayerState:
        """Get current player state."""
        return self._player_state

    def get_combat_state(self) -> CombatState:
        """Get current combat state."""
        return self._combat_state

    def get_entities(self) -> dict[str, EntityState]:
        """Get all tracked entities."""
        return self._entities.copy()

    def get_turn(self) -> int:
        """Get current turn number."""
        return self._turn

    # Engine event handlers
    def _subscribe_to_events(self) -> None:
        """Subscribe to engine events."""
        if not self._event_bus:
            return

        # Import here to avoid circular imports
        from dnd_engine.utils.events import EventType

        self._event_bus.subscribe(EventType.DAMAGE_DEALT, self._on_damage_dealt)
        self._event_bus.subscribe(EventType.DAMAGE_TAKEN, self._on_damage_taken)
        self._event_bus.subscribe(EventType.HEALING_DONE, self._on_healing_done)
        self._event_bus.subscribe(EventType.COMBAT_START, self._on_combat_start)
        self._event_bus.subscribe(EventType.COMBAT_END, self._on_combat_end)
        self._event_bus.subscribe(EventType.TURN_START, self._on_turn_start)
        self._event_bus.subscribe(EventType.CHARACTER_DEATH, self._on_character_death)
        self._event_bus.subscribe(EventType.ROOM_ENTER, self._on_room_enter)
        self._event_bus.subscribe(EventType.ITEM_ACQUIRED, self._on_item_acquired)

    def _unsubscribe_from_events(self) -> None:
        """Unsubscribe from engine events."""
        if not self._event_bus:
            return

        from dnd_engine.utils.events import EventType

        self._event_bus.unsubscribe(EventType.DAMAGE_DEALT, self._on_damage_dealt)
        self._event_bus.unsubscribe(EventType.DAMAGE_TAKEN, self._on_damage_taken)
        self._event_bus.unsubscribe(EventType.HEALING_DONE, self._on_healing_done)
        self._event_bus.unsubscribe(EventType.COMBAT_START, self._on_combat_start)
        self._event_bus.unsubscribe(EventType.COMBAT_END, self._on_combat_end)
        self._event_bus.unsubscribe(EventType.TURN_START, self._on_turn_start)
        self._event_bus.unsubscribe(EventType.CHARACTER_DEATH, self._on_character_death)
        self._event_bus.unsubscribe(EventType.ROOM_ENTER, self._on_room_enter)
        self._event_bus.unsubscribe(EventType.ITEM_ACQUIRED, self._on_item_acquired)

    def _on_damage_dealt(self, event: Event) -> None:
        """Handle damage dealt event."""
        data = event.data
        attacker = data.get("attacker", "")
        defender = data.get("defender", "")
        damage = data.get("damage", 0)

        self._emit_client_event(
            "damage_dealt",
            {"attacker": attacker, "defender": defender, "damage": damage},
        )

    def _on_damage_taken(self, event: Event) -> None:
        """Handle damage taken event."""
        data = event.data
        defender = data.get("defender", "")
        damage = data.get("damage", 0)

        # Check if player took damage
        if self._is_player(defender):
            self._player_state.hp = max(0, self._player_state.hp - damage)
            self._emit_client_event(
                "player_damaged",
                {"hp": self._player_state.hp, "damage": damage},
            )

    def _on_healing_done(self, event: Event) -> None:
        """Handle healing event."""
        data = event.data
        target = data.get("target", "")
        healing = data.get("healing", 0)

        if self._is_player(target):
            self._player_state.hp = min(
                self._player_state.max_hp, self._player_state.hp + healing
            )
            self._emit_client_event(
                "player_healed",
                {"hp": self._player_state.hp, "healing": healing},
            )

    def _on_combat_start(self, event: Event) -> None:
        """Handle combat start event."""
        data = event.data
        enemies = data.get("enemies", [])

        self._combat_state.in_combat = True
        self._combat_state.round_number = 1
        self._combat_state.enemies = [
            EntityState(
                entity_id=f"enemy_{i}",
                name=name,
                entity_type="monster",
                is_alive=True,
            )
            for i, name in enumerate(enemies)
        ]

        self._emit_client_event(
            "combat_started",
            {"enemies": enemies, "round": 1},
        )

    def _on_combat_end(self, event: Event) -> None:
        """Handle combat end event."""
        data = event.data
        victory = data.get("victory", False)
        xp = data.get("xp_gained", 0)

        self._combat_state.in_combat = False
        self._combat_state.enemies = []

        self._emit_client_event(
            "combat_ended",
            {"victory": victory, "xp_gained": xp},
        )

    def _on_turn_start(self, event: Event) -> None:
        """Handle turn start event."""
        data = event.data
        combatant = data.get("combatant", "")
        round_num = data.get("round", 0)

        self._combat_state.current_turn = combatant
        self._combat_state.round_number = round_num
        self._turn += 1

        self._emit_client_event(
            "turn_started",
            {"combatant": combatant, "round": round_num},
        )

    def _on_character_death(self, event: Event) -> None:
        """Handle character death event."""
        data = event.data
        name = data.get("name", "")

        # Update entity state
        for _entity_id, entity in self._entities.items():
            if entity.name == name:
                entity.is_alive = False
                break

        self._emit_client_event("entity_died", {"name": name})

    def _on_room_enter(self, event: Event) -> None:
        """Handle room enter event."""
        data = event.data
        room_id = data.get("room_id", "")
        room_name = data.get("room_name", "")

        self._emit_client_event(
            "room_entered",
            {"room_id": room_id, "room_name": room_name},
        )

    def _on_item_acquired(self, event: Event) -> None:
        """Handle item acquired event."""
        data = event.data
        item_id = data.get("item_id", "")
        character = data.get("character", "")

        # Remove from tracked entities if present
        if item_id in self._entities:
            del self._entities[item_id]

        self._emit_client_event(
            "item_acquired",
            {"item_id": item_id, "character": character},
        )

    # Helper methods
    def _is_player(self, name: str) -> bool:
        """Check if a name refers to the player character."""
        return name == self._player_state.name

    def _sync_from_engine(self) -> None:
        """Sync state from engine GameState."""
        if not self._engine_state:
            return

        # Sync party/player state
        party = getattr(self._engine_state, "party", None)
        if party:
            self._sync_player_from_party(party)

        # Sync combat state
        in_combat = getattr(self._engine_state, "in_combat", False)
        self._combat_state.in_combat = in_combat

    def _sync_player_from_party(self, party: Party) -> None:
        """Sync player state from party."""
        # Get first living party member as "the player" for 2D client
        members = getattr(party, "members", [])
        for member in members:
            if getattr(member, "is_alive", True):
                self._player_state.name = getattr(member, "name", "Player")
                self._player_state.hp = getattr(member, "current_hp", 30)
                self._player_state.max_hp = getattr(member, "max_hp", 30)
                break

    def sync_player_hp(self, hp: int, max_hp: int) -> None:
        """Manually sync player HP (for testing or manual updates).

        Args:
            hp: Current HP
            max_hp: Maximum HP
        """
        self._player_state.hp = hp
        self._player_state.max_hp = max_hp

    def sync_entities(self, entities: list[EntityState]) -> None:
        """Manually sync entities (for testing or manual updates).

        Args:
            entities: List of entity states
        """
        self._entities = {e.entity_id: e for e in entities}
