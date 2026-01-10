# D&D 5E 2D Graphical Client - Architecture Documentation

**Version:** 0.1.0
**Last Updated:** 2025-01-10
**Status:** Planning & Initial Development
**Issue:** #313

---

## Table of Contents

1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [High-Level Architecture](#high-level-architecture)
4. [Core Systems](#core-systems)
5. [Sprite & Asset Management](#sprite--asset-management)
6. [Fog of War & Lighting System](#fog-of-war--lighting-system)
7. [Input & Navigation](#input--navigation)
8. [UI Overlays](#ui-overlays)
9. [Engine Integration](#engine-integration)
10. [Directory Structure](#directory-structure)
11. [Implementation Phases](#implementation-phases)
12. [Success Metrics](#success-metrics)

---

## Overview

The 2D graphical client provides a sprite-based, top-down dungeon crawler interface for the D&D 5E game engine. It renders tile-based maps with fog of war, entity sprites with category-based fallbacks, and D&D-compliant lighting mechanics.

### Core Goals

- **Sprite-Based Rendering**: Categorized entity types (undead, beast, humanoid) with visual fallback hierarchies
- **Classic Dungeon Crawler View**: Top-down perspective with tile-based maps
- **D&D-Compliant Lighting**: Tile-based vision states (bright/dim/dark/unexplored)
- **Keyboard Navigation**: Arrow keys or WASD for movement
- **Direct Engine Integration**: Python imports from dnd-engine, no serialization bridge
- **Extensible Lighting**: Abstraction layer for future raycast shadow-casting upgrades

### Non-Goals (Deferred)

- Real-time multiplayer synchronization
- 3D rendering or isometric views
- Mouse-based pathfinding (Phase 5+ consideration)
- Audio system (Phase 5 optional)

---

## Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Graphics Engine** | Arcade | 2.6+ | Python game library with sprite batching, TileMap support |
| **Map Editor** | Tiled | 1.10+ | .tmx format map editing |
| **Sprites** | PNG | - | 32x32 pixel sprites |
| **Data Format** | JSON | - | Asset manifests, configuration |
| **Game Engine** | dnd-engine | Local | Direct Python import |

### Why Arcade?

- **Pure Python**: No C extensions, easy installation
- **Sprite Batching**: Efficient rendering for many entities
- **TileMap Support**: Native `.tmx` loading via `arcade.tilemap`
- **Modern OpenGL**: Hardware-accelerated rendering
- **Active Development**: Well-maintained with good documentation
- **Pythonic API**: Clean integration with existing codebase

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        2D Client Layer                               │
│  ┌───────────────┬────────────────┬────────────────┬──────────────┐ │
│  │  Input System │  Render System │  UI Overlays   │ Asset Manager│ │
│  │  (keyboard)   │  (sprites,fog) │  (HP,menus)    │ (sprites,tmx)│ │
│  └───────┬───────┴────────┬───────┴────────┬───────┴──────┬───────┘ │
│          │                │                │              │          │
│          └────────────────┼────────────────┼──────────────┘          │
│                           │                │                          │
│                    ┌──────┴────────────────┴──────┐                  │
│                    │      Game View Controller     │                  │
│                    │   (coordinates all systems)   │                  │
│                    └──────────────┬───────────────┘                  │
└───────────────────────────────────┼─────────────────────────────────┘
                                    │
                          ┌─────────┴─────────┐
                          │   Event Bridge    │
                          │  (EventBus sub)   │
                          └─────────┬─────────┘
                                    │
┌───────────────────────────────────┼─────────────────────────────────┐
│                        dnd-engine Layer                              │
│                                   │                                  │
│  ┌────────────────────────────────┼────────────────────────────────┐│
│  │                          EventBus                                ││
│  │  (ROOM_ENTER, COMBAT_START, DAMAGE_DEALT, TURN_START, etc.)     ││
│  └────────────────────────────────┬────────────────────────────────┘│
│                                   │                                  │
│  ┌───────────────┬────────────────┼────────────────┬──────────────┐ │
│  │   GameState   │  CombatEngine  │ InitiativeTrack│  RoomRegistry│ │
│  │               │                │                │              │ │
│  └───────────────┴────────────────┴────────────────┴──────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Responsibility |
|-------|----------------|
| **Input System** | Keyboard capture, command mapping, input buffering |
| **Render System** | Sprite rendering, fog of war, lighting overlays |
| **UI Overlays** | HP bars, combat log, action menus, inventory |
| **Asset Manager** | Sprite loading, tilemap parsing, fallback resolution |
| **Game View Controller** | Coordinates systems, manages game modes (exploration/combat) |
| **Event Bridge** | Subscribes to dnd-engine events, triggers UI updates |

---

## Core Systems

### 1. Game View Controller (`game_view.py`)

The central coordinator that extends `arcade.View`:

```python
class DungeonGameView(arcade.View):
    """Main game view coordinating all 2D client systems."""

    def __init__(self, game_state: GameState, event_bus: EventBus):
        self.game_state = game_state
        self.event_bus = event_bus

        # Core systems
        self.asset_manager = AssetManager()
        self.map_renderer = MapRenderer()
        self.entity_renderer = EntityRenderer()
        self.fog_system = FogOfWarSystem()
        self.lighting_system = LightingSystem()
        self.ui_manager = UIManager()
        self.input_handler = InputHandler()

        # Subscribe to engine events
        self._setup_event_subscriptions()

    def on_draw(self):
        """Render frame: map -> entities -> fog -> UI"""

    def on_update(self, delta_time: float):
        """Update animations, tweens, effects"""

    def on_key_press(self, key: int, modifiers: int):
        """Handle player input"""
```

### 2. Map Renderer (`rendering/map_renderer.py`)

Handles tilemap loading and rendering:

```python
class MapRenderer:
    """Renders tile-based dungeon maps from .tmx files."""

    def load_room(self, room_id: str) -> TileMap:
        """Load tilemap for a room, with fallback to procedural generation."""

    def render(self, camera_position: Vec2):
        """Render visible tiles within camera bounds."""
```

**Tilemap Layers** (standard order):
1. `floor` - Base floor tiles
2. `walls` - Wall and obstacle tiles
3. `decorations` - Props, furniture, environmental details
4. `collision` - Invisible collision layer (for pathfinding)

### 3. Entity Renderer (`rendering/entity_renderer.py`)

Manages sprite rendering for all game entities:

```python
class EntityRenderer:
    """Renders character and creature sprites with animations."""

    def __init__(self, asset_manager: AssetManager):
        self.sprite_lists = {
            'party': arcade.SpriteList(),
            'enemies': arcade.SpriteList(),
            'npcs': arcade.SpriteList(),
            'effects': arcade.SpriteList()
        }

    def sync_entities(self, game_state: GameState):
        """Sync sprite positions with game state."""

    def animate_movement(self, entity_id: str, from_pos: Vec2, to_pos: Vec2):
        """Tween sprite between positions."""
```

### 4. State Manager (`state/game_mode.py`)

Tracks current game mode and transitions:

```python
class GameMode(Enum):
    EXPLORATION = "exploration"
    COMBAT = "combat"
    DIALOGUE = "dialogue"
    INVENTORY = "inventory"
    MENU = "menu"

class GameModeManager:
    """Manages game mode transitions and mode-specific behavior."""

    def transition_to(self, new_mode: GameMode):
        """Handle mode transition effects and UI changes."""
```

---

## Sprite & Asset Management

### Asset Directory Structure

```
client-2d/
└── assets/
    ├── sprites/
    │   ├── characters/
    │   │   ├── fighter.png
    │   │   ├── rogue.png
    │   │   ├── wizard.png
    │   │   ├── cleric.png
    │   │   └── _fallback_humanoid.png
    │   ├── monsters/
    │   │   ├── undead/
    │   │   │   ├── skeleton.png
    │   │   │   ├── zombie.png
    │   │   │   └── _fallback.png
    │   │   ├── beast/
    │   │   │   ├── wolf.png
    │   │   │   ├── giant_rat.png
    │   │   │   └── _fallback.png
    │   │   ├── humanoid/
    │   │   │   ├── goblin.png
    │   │   │   ├── bandit.png
    │   │   │   └── _fallback.png
    │   │   └── _fallback_generic.png
    │   ├── items/
    │   │   ├── weapons/
    │   │   ├── armor/
    │   │   └── consumables/
    │   └── effects/
    │       ├── damage/
    │       ├── healing/
    │       └── status/
    ├── tilesets/
    │   ├── dungeon_basic.png
    │   ├── dungeon_crypt.png
    │   └── dungeon_cave.png
    ├── maps/
    │   ├── crypt/
    │   │   ├── graveyard_entrance.tmx
    │   │   ├── hall_of_the_dead.tmx
    │   │   └── ...
    │   └── _procedural/
    │       └── templates/
    └── ui/
        ├── frames/
        ├── icons/
        └── fonts/
```

### Sprite Fallback Hierarchy

The asset manager resolves sprites using a hierarchical fallback system:

```python
class AssetManager:
    """Manages game assets with intelligent fallback resolution."""

    def get_creature_sprite(self, creature_id: str, creature_type: str) -> arcade.Texture:
        """
        Resolve sprite with fallback hierarchy:
        1. Exact match: monsters/{type}/{creature_id}.png
        2. Category fallback: monsters/{type}/_fallback.png
        3. Generic fallback: monsters/_fallback_generic.png
        """

    def get_character_sprite(self, class_name: str, race: str = None) -> arcade.Texture:
        """
        Resolve character sprite:
        1. Class + race: characters/{class}_{race}.png
        2. Class only: characters/{class}.png
        3. Fallback: characters/_fallback_humanoid.png
        """
```

**Fallback Resolution Order for Monsters:**

| Priority | Path Pattern | Example |
|----------|--------------|---------|
| 1 | `monsters/{type}/{id}.png` | `monsters/undead/skeleton.png` |
| 2 | `monsters/{type}/_fallback.png` | `monsters/undead/_fallback.png` |
| 3 | `monsters/_fallback_generic.png` | Generic monster silhouette |

### Sprite Manifest (`assets/manifest.json`)

```json
{
  "version": "1.0.0",
  "tile_size": 32,
  "sprite_categories": {
    "undead": {
      "fallback": "_fallback.png",
      "sprites": ["skeleton", "zombie", "ghoul", "wight"]
    },
    "beast": {
      "fallback": "_fallback.png",
      "sprites": ["wolf", "giant_rat", "dire_wolf"]
    },
    "humanoid": {
      "fallback": "_fallback.png",
      "sprites": ["goblin", "bandit", "cultist", "guard"]
    }
  },
  "character_classes": ["fighter", "rogue", "wizard", "cleric"]
}
```

---

## Fog of War & Lighting System

### Vision States

The lighting system implements D&D 5E-compliant vision with four tile states:

| State | Description | Rendering |
|-------|-------------|-----------|
| **Unexplored** | Never seen by party | Solid black overlay |
| **Dark** | Previously seen, currently unlit | Grayscale, 70% dimmed |
| **Dim** | Partially illuminated | 40% dimmed, desaturated |
| **Bright** | Fully illuminated | Full color, no overlay |

### Lighting Model

```python
class LightingState(Enum):
    UNEXPLORED = 0  # Black, not visible
    DARK = 1        # Grayscale, previously seen
    DIM = 2         # Partial light (10-20 ft from source)
    BRIGHT = 3      # Full light (0-10 ft from source)

@dataclass
class LightSource:
    """A light source with D&D-compliant radii."""
    position: Tuple[int, int]  # Tile coordinates
    bright_radius: int         # Tiles of bright light
    dim_radius: int            # Additional tiles of dim light
    source_type: str           # "torch", "lantern", "spell", etc.

    # Standard D&D light sources:
    # Torch: bright 20ft (4 tiles), dim +20ft (4 tiles)
    # Lantern: bright 30ft (6 tiles), dim +30ft (6 tiles)
    # Light cantrip: bright 20ft, dim +20ft
```

### Fog of War System (`systems/fog_of_war.py`)

```python
class FogOfWarSystem:
    """Manages tile visibility states based on party position and light."""

    def __init__(self, map_width: int, map_height: int):
        # Visibility grid: 0=unexplored, 1=dark, 2=dim, 3=bright
        self.visibility_grid = np.zeros((map_width, map_height), dtype=np.uint8)
        self.light_sources: List[LightSource] = []

    def update(self, party_positions: List[Tuple[int, int]],
               light_sources: List[LightSource]):
        """
        Recalculate visibility for all tiles.

        Algorithm:
        1. Start with all visible tiles set to DARK (memory)
        2. For each light source:
           - Mark tiles within bright_radius as BRIGHT
           - Mark tiles within dim_radius as DIM (if not already BRIGHT)
        3. Mark tiles outside all light as DARK (if previously seen)
        4. Unexplored tiles remain UNEXPLORED
        """

    def reveal_tile(self, x: int, y: int):
        """Mark a tile as explored (minimum state becomes DARK)."""

    def get_visibility(self, x: int, y: int) -> LightingState:
        """Get current visibility state for a tile."""
```

### Lighting Abstraction (Future Raycast Support)

The lighting system uses a pluggable algorithm interface:

```python
class LightingAlgorithm(ABC):
    """Abstract base for lighting calculation algorithms."""

    @abstractmethod
    def calculate_lit_tiles(self, source: LightSource,
                           obstacles: Set[Tuple[int, int]]) -> Dict[Tuple[int, int], LightingState]:
        """Return dict of tile positions to their lighting state."""

class SimpleLighting(LightingAlgorithm):
    """Phase 1: Simple radius-based lighting (no shadows)."""

    def calculate_lit_tiles(self, source, obstacles):
        # Circular radius, ignores walls
        pass

class RaycastLighting(LightingAlgorithm):
    """Phase 5: Shadow-casting with wall occlusion."""

    def calculate_lit_tiles(self, source, obstacles):
        # Recursive shadowcasting algorithm
        pass
```

### Rendering the Fog

```python
class FogRenderer:
    """Renders fog of war overlay using sprite batching."""

    def __init__(self, tile_size: int = 32):
        self.overlay_sprites = arcade.SpriteList()
        self.fog_textures = {
            LightingState.UNEXPLORED: self._create_black_tile(),
            LightingState.DARK: self._create_dark_overlay(),
            LightingState.DIM: self._create_dim_overlay(),
            LightingState.BRIGHT: None  # No overlay
        }

    def update_from_visibility(self, fog_system: FogOfWarSystem):
        """Sync overlay sprites with visibility grid."""
```

---

## Input & Navigation

### Input Handler (`input/input_handler.py`)

```python
class InputHandler:
    """Handles keyboard input and maps to game actions."""

    # Movement keys (configurable)
    MOVE_KEYS = {
        arcade.key.UP: Direction.NORTH,
        arcade.key.DOWN: Direction.SOUTH,
        arcade.key.LEFT: Direction.WEST,
        arcade.key.RIGHT: Direction.EAST,
        arcade.key.W: Direction.NORTH,
        arcade.key.S: Direction.SOUTH,
        arcade.key.A: Direction.WEST,
        arcade.key.D: Direction.EAST,
    }

    # Action keys
    ACTION_KEYS = {
        arcade.key.SPACE: Action.INTERACT,
        arcade.key.ENTER: Action.CONFIRM,
        arcade.key.ESCAPE: Action.CANCEL,
        arcade.key.I: Action.INVENTORY,
        arcade.key.C: Action.CHARACTER,
        arcade.key.TAB: Action.NEXT_TARGET,
    }

    def handle_key_press(self, key: int, modifiers: int, game_mode: GameMode) -> Optional[GameAction]:
        """Convert key press to game action based on current mode."""
```

### Movement Flow

```
┌──────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Key Press    │────▶│ Input Handler   │────▶│ Game Controller │
│ (Arrow/WASD) │     │ (map to action) │     │ (validate move) │
└──────────────┘     └─────────────────┘     └────────┬────────┘
                                                       │
                                                       ▼
┌──────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Update Fog   │◀────│ EventBus        │◀────│ GameState.move()│
│ & Sprites    │     │ (ROOM_ENTER)    │     │ (engine method) │
└──────────────┘     └─────────────────┘     └─────────────────┘
```

### Combat Input Mode

During combat, input handling changes:

```python
class CombatInputHandler:
    """Handles input during combat mode."""

    def __init__(self, game_state: GameState):
        self.selected_target_index = 0
        self.available_actions = []

    def handle_key(self, key: int) -> Optional[CombatAction]:
        """
        Combat key mappings:
        - TAB: Cycle through targets
        - 1-9: Select action from menu
        - ENTER: Confirm action
        - ESCAPE: Cancel/back
        - Arrow keys: Navigate menus
        """
```

---

## UI Overlays

### UI Manager (`ui/ui_manager.py`)

```python
class UIManager:
    """Manages all UI overlay elements."""

    def __init__(self):
        self.hp_bars = HPBarOverlay()
        self.combat_log = CombatLogOverlay()
        self.action_menu = ActionMenuOverlay()
        self.inventory_panel = InventoryPanel()
        self.minimap = MinimapOverlay()

    def update(self, game_state: GameState):
        """Update all UI elements from game state."""

    def draw(self):
        """Render all visible UI elements."""
```

### HP Bar Overlay (`ui/hp_bars.py`)

```python
@dataclass
class HPBarConfig:
    width: int = 32
    height: int = 4
    offset_y: int = -20  # Below sprite
    bg_color: arcade.Color = arcade.color.DARK_RED
    fg_color: arcade.Color = arcade.color.GREEN
    border_color: arcade.Color = arcade.color.WHITE

class HPBarOverlay:
    """Renders HP bars above/below entity sprites."""

    def draw_for_entity(self, entity: Creature, screen_pos: Vec2):
        """Draw HP bar at entity's screen position."""
```

### Combat Log (`ui/combat_log.py`)

```python
class CombatLogOverlay:
    """Scrolling combat log panel."""

    def __init__(self, max_lines: int = 8, position: str = "bottom-left"):
        self.messages: deque[CombatLogEntry] = deque(maxlen=max_lines)
        self.position = position

    def add_message(self, text: str, message_type: MessageType):
        """Add message with timestamp and type-based styling."""

    def draw(self):
        """Render semi-transparent panel with scrolling text."""
```

### Action Menu (`ui/action_menu.py`)

```python
class ActionMenuOverlay:
    """Combat action selection menu."""

    def __init__(self):
        self.visible = False
        self.selected_index = 0
        self.actions: List[ActionOption] = []

    def show_for_turn(self, character: Character, game_state: GameState):
        """Populate menu with available actions for current turn."""

    def draw(self):
        """Render action menu with selection highlight."""
```

### UI Layout

```
┌────────────────────────────────────────────────────────────┐
│  [Minimap]                                   [Party HP]    │
│  ┌─────┐                                     ┌──────────┐  │
│  │░░░░░│                                     │ Fighter  │  │
│  │░▓░░░│                                     │ ████░░   │  │
│  │░░░░░│                                     │ Wizard   │  │
│  └─────┘                                     │ ██░░░░   │  │
│                                              └──────────┘  │
│                                                            │
│                    [Game View]                             │
│                                                            │
│                                                            │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  [Combat Log]                           [Action Menu]      │
│  > Fighter attacks Skeleton             ┌──────────────┐   │
│  > Hit! 8 damage                        │ 1. Attack    │   │
│  > Skeleton defeated                    │ 2. Spell     │   │
│                                         │ 3. Item      │   │
│                                         │ 4. Dash      │   │
│                                         └──────────────┘   │
└────────────────────────────────────────────────────────────┘
```

---

## Engine Integration

### Event Bridge (`integration/event_bridge.py`)

The event bridge subscribes to dnd-engine events and triggers UI updates:

```python
class EventBridge:
    """Bridges dnd-engine EventBus to 2D client systems."""

    def __init__(self, event_bus: EventBus, game_view: DungeonGameView):
        self.event_bus = event_bus
        self.game_view = game_view
        self._setup_subscriptions()

    def _setup_subscriptions(self):
        """Subscribe to all relevant engine events."""
        subscriptions = {
            EventType.ROOM_ENTER: self._on_room_enter,
            EventType.COMBAT_START: self._on_combat_start,
            EventType.COMBAT_END: self._on_combat_end,
            EventType.TURN_START: self._on_turn_start,
            EventType.DAMAGE_DEALT: self._on_damage_dealt,
            EventType.HEALING_DONE: self._on_healing,
            EventType.CHARACTER_DEATH: self._on_death,
            EventType.ITEM_ACQUIRED: self._on_item_acquired,
            EventType.DESCRIPTION_ENHANCED: self._on_narrative,
        }
        for event_type, handler in subscriptions.items():
            self.event_bus.subscribe(event_type, handler)

    def _on_room_enter(self, event: Event):
        """Handle room transition - load new map, update fog."""
        room_data = event.data
        self.game_view.load_room(room_data['room_id'])
        self.game_view.fog_system.reveal_room_tiles(room_data)

    def _on_damage_dealt(self, event: Event):
        """Handle damage - show damage number, flash sprite."""
        self.game_view.effects.show_damage_number(
            event.data['defender'],
            event.data['damage']
        )
        self.game_view.entity_renderer.flash_sprite(
            event.data['defender'],
            color=arcade.color.RED
        )
```

### GameState Integration

```python
class Client2DGame:
    """Main entry point for 2D client."""

    def __init__(self, campaign_id: str, party: Party):
        # Initialize dnd-engine components
        self.event_bus = EventBus()
        self.game_state = GameState(
            campaign_id=campaign_id,
            party=party,
            event_bus=self.event_bus
        )

        # Initialize 2D client
        self.window = arcade.Window(
            width=1280,
            height=720,
            title="D&D 5E Dungeon Crawler"
        )
        self.game_view = DungeonGameView(self.game_state, self.event_bus)

        # Connect bridge
        self.event_bridge = EventBridge(self.event_bus, self.game_view)

    def run(self):
        """Start the game loop."""
        self.window.show_view(self.game_view)
        arcade.run()
```

### State Synchronization Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    State Sync Flow                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User Input ──▶ GameState.method() ──▶ EventBus.emit()     │
│                                              │               │
│                                              ▼               │
│                                       EventBridge           │
│                                              │               │
│                                              ▼               │
│                                     UI Systems Update       │
│                                              │               │
│                                              ▼               │
│                                       Render Frame          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Principle**: The 2D client never modifies game state directly. All mutations go through `GameState` methods, which emit events that the client reacts to.

---

## Directory Structure

```
client-2d/
├── pyproject.toml              # Package configuration
├── README.md                   # Client-specific documentation
│
├── src/
│   └── client_2d/
│       ├── __init__.py
│       ├── main.py             # Entry point
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── game.py         # Main game class
│       │   ├── game_view.py    # Arcade View implementation
│       │   └── constants.py    # Configuration constants
│       │
│       ├── rendering/
│       │   ├── __init__.py
│       │   ├── map_renderer.py     # Tilemap rendering
│       │   ├── entity_renderer.py  # Sprite rendering
│       │   ├── fog_renderer.py     # Fog overlay rendering
│       │   └── effects.py          # Visual effects (damage numbers, etc.)
│       │
│       ├── systems/
│       │   ├── __init__.py
│       │   ├── fog_of_war.py       # Visibility calculation
│       │   ├── lighting.py         # Light source management
│       │   ├── camera.py           # Camera/viewport control
│       │   └── animation.py        # Sprite animation/tweening
│       │
│       ├── input/
│       │   ├── __init__.py
│       │   ├── input_handler.py    # Keyboard input processing
│       │   └── combat_input.py     # Combat-specific input
│       │
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── ui_manager.py       # UI coordination
│       │   ├── hp_bars.py          # HP bar overlay
│       │   ├── combat_log.py       # Combat log panel
│       │   ├── action_menu.py      # Action selection menu
│       │   ├── inventory_panel.py  # Inventory display
│       │   └── minimap.py          # Minimap overlay
│       │
│       ├── assets/
│       │   ├── __init__.py
│       │   ├── asset_manager.py    # Asset loading and caching
│       │   └── sprite_resolver.py  # Fallback hierarchy resolution
│       │
│       └── integration/
│           ├── __init__.py
│           └── event_bridge.py     # dnd-engine event handling
│
├── assets/
│   ├── manifest.json           # Asset manifest
│   ├── sprites/               # Entity sprites
│   ├── tilesets/              # Tilemap tilesets
│   ├── maps/                  # .tmx map files
│   └── ui/                    # UI elements
│
└── tests/
    ├── test_asset_manager.py
    ├── test_fog_of_war.py
    ├── test_lighting.py
    ├── test_input_handler.py
    └── test_event_bridge.py
```

---

## Implementation Phases

### Phase 1: Foundation (Current)

**Goal**: Single-room navigation with fog of war and torch mechanics.

**Deliverables**:
- [ ] Basic Arcade window and game loop
- [ ] Single room tilemap rendering
- [ ] Party sprite on map (single position)
- [ ] Keyboard navigation (WASD/arrows)
- [ ] Basic fog of war (unexplored → revealed)
- [ ] Torch light source (radius-based)
- [ ] Room transition on exit

**Success Criteria**:
- Player can navigate a room with keyboard
- Fog reveals as player moves
- Torch illuminates surrounding tiles
- Exiting room loads adjacent room

### Phase 2: Entity Integration

**Goal**: GameState integration, entity rendering, movement animations.

**Deliverables**:
- [ ] Enemy sprite rendering from GameState
- [ ] Party member sprites (multiple characters)
- [ ] Movement tweening (smooth transitions)
- [ ] Entity sync on game events
- [ ] Basic creature type sprites with fallbacks

**Success Criteria**:
- Enemies appear in rooms
- All party members visible
- Smooth movement animations
- Sprites update on game state changes

### Phase 3: Combat UI

**Goal**: Playable combat through the 2D interface.

**Deliverables**:
- [ ] Turn indicator (active combatant highlight)
- [ ] Target selection (Tab to cycle, highlight)
- [ ] Action menu overlay
- [ ] Attack animations and effects
- [ ] Damage numbers floating text
- [ ] HP bars above entities
- [ ] Combat log panel
- [ ] Initiative order display

**Success Criteria**:
- Full combat playable via 2D client
- Clear turn indication
- Target selection works
- Visual feedback for all actions

### Phase 4: Essential Overlays

**Goal**: Complete UI for full gameplay.

**Deliverables**:
- [ ] Inventory panel
- [ ] Character status panel
- [ ] Room description display
- [ ] LLM narrative integration
- [ ] Save/load game menu
- [ ] Pause menu

**Success Criteria**:
- All gameplay accessible through UI
- Inventory management works
- Narrative text displays
- Save/load functional

### Phase 5: Polish (Optional)

**Goal**: Enhanced visuals and quality-of-life features.

**Deliverables**:
- [ ] Raycast shadow-casting lighting
- [ ] Darkvision support (different races)
- [ ] Camera smoothing/lerping
- [ ] Particle effects (magic, fire, etc.)
- [ ] Audio system (SFX, ambient)
- [ ] Mouse support (click to move/target)
- [ ] Full-screen mode

---

## Success Metrics

### Phase 1 Completion Criteria

| Metric | Target |
|--------|--------|
| Keyboard navigation | Arrow keys and WASD functional |
| Fog of war | Tiles reveal on approach |
| Torch illumination | Correct 4-tile bright, 4-tile dim radius |
| Room transitions | Load adjacent rooms on exit |
| Frame rate | Stable 60 FPS |

### Overall Success Criteria

| Metric | Target |
|--------|--------|
| Full gameplay | Complete dungeon playable via 2D client |
| Engine integration | Zero serialization, direct Python imports |
| Sprite fallbacks | All creatures render (specific or fallback) |
| Combat | All combat actions accessible |
| Lighting extensibility | Can swap SimpleLighting for RaycastLighting |

---

## Appendix: Technical Notes

### Coordinate Systems

- **Tile Coordinates**: Integer grid positions (0,0 is top-left)
- **World Coordinates**: Pixel positions (tile_x * 32, tile_y * 32)
- **Screen Coordinates**: Pixel positions relative to viewport

### Performance Considerations

- Use SpriteList batching for all entity rendering
- Fog overlay uses single sprite per visible tile (not per frame)
- Tilemap caching prevents re-loading on room return
- Limit fog recalculation to movement events only

### Accessibility Notes

- High contrast mode option for fog states
- Colorblind-friendly HP bar options
- Keyboard-only navigation (no mouse required)
- Configurable key bindings (future)
