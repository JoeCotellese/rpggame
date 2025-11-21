# D&D 5E Terminal Game - Architecture Documentation

**Version:** 0.2.0
**Last Updated:** 2025-11-18
**Status:** Active Development (Beyond MVP)

---

## Table of Contents

1. [System Purpose](#system-purpose)
2. [High-Level Architecture](#high-level-architecture)
3. [Project Structure](#project-structure)
4. [Core Components](#core-components)
5. [Data Flow](#data-flow)
6. [Key Design Decisions](#key-design-decisions)
7. [External Dependencies](#external-dependencies)
8. [Configuration & Environment](#configuration--environment)
9. [Testing Strategy](#testing-strategy)
10. [Extension Points](#extension-points)
11. [Future Considerations](#future-considerations)

---

## System Purpose

A Python-based terminal game for running D&D 5E SRD adventures with LLM-enhanced narrative. This project combines deterministic game mechanics (dice rolls, combat rules, HP tracking) with creative narrative generation (room descriptions, combat flavor, NPC dialogue) to create an immersive tabletop RPG experience in your terminal.

**Current State:** The system has evolved beyond its initial MVP to include party support, save/load functionality, multiple dungeons, and a rich terminal UI.

---

## High-Level Architecture

### Architectural Style

**Event-Driven Layered Architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────┐
│              UI Layer                           │
│   CLI (rich_ui.py, cli.py)                      │
│   - Command parsing                             │
│   - Display formatting (Rich library)           │
│   - Player interaction                          │
└─────────────────┬───────────────────────────────┘
                  ↕
┌─────────────────────────────────────────────────┐
│         LLM Enhancement Layer                   │
│   (llm/enhancer.py, providers)                  │
│   - Narrative generation                        │
│   - Combat descriptions                         │
│   - Room atmosphere                             │
│   - Multi-provider support (OpenAI, Anthropic)  │
└─────────────────┬───────────────────────────────┘
                  ↕
┌─────────────────────────────────────────────────┐
│              Event Bus                          │
│   (utils/events.py)                             │
│   - Pub/Sub messaging                           │
│   - Loose coupling between components           │
│   - Event types: Combat, Exploration, Items     │
└─────────────────┬───────────────────────────────┘
                  ↕
┌─────────────────────────────────────────────────┐
│          Game Engine Core                       │
│   (core/, systems/)                             │
│   - Dice rolling & probability                  │
│   - Combat resolution (5E rules)                │
│   - Character & party management                │
│   - Initiative tracking                         │
│   - Inventory & equipment                       │
│   - Save/load game state                        │
└─────────────────┬───────────────────────────────┘
                  ↕
┌─────────────────────────────────────────────────┐
│            Data Layer                           │
│   (data/srd/, data/content/)                    │
│   - Classes, monsters, items (JSON)             │
│   - Dungeon definitions                         │
│   - Skill & condition data                      │
└─────────────────────────────────────────────────┘
```

### Core Design Principles

1. **Separation of Concerns**: Game rules, content, narrative enhancement, and UI are completely separated
2. **Data-Driven Design**: All content (monsters, items, spells, dungeons) stored in JSON, not hardcoded
3. **Event-Driven Architecture**: Components communicate via event bus for loose coupling
4. **Extensibility**: Plugin architecture allows adding new rule systems, content, or LLM providers
5. **Deterministic Core + Creative Enhancement**: Game engine produces deterministic outcomes; LLM only enhances narrative

---

## Project Structure

### Directory Tree

```
/home/user/rpggame/
├── dnd_engine/              # Main package
│   ├── core/                # Core game mechanics
│   │   ├── __init__.py
│   │   ├── dice.py          # Dice rolling (d20, advantage, etc.)
│   │   ├── creature.py      # Base class for all creatures
│   │   ├── character.py     # Player character (extends Creature)
│   │   ├── party.py         # Party management
│   │   ├── combat.py        # Combat resolution engine
│   │   ├── game_state.py    # Game state manager
│   │   ├── character_factory.py  # Character creation
│   │   └── save_manager.py  # Save/load functionality
│   │
│   ├── systems/             # Game subsystems
│   │   ├── __init__.py
│   │   ├── initiative.py    # Turn order tracking
│   │   ├── inventory.py     # Item management
│   │   ├── currency.py      # Gold & currency tracking
│   │   ├── resources.py     # Resource management (HP, spell slots)
│   │   ├── action_economy.py     # Action/bonus action/reaction
│   │   ├── item_effects.py  # Item usage effects
│   │   └── condition_manager.py  # Status effects (stunned, prone, etc.)
│   │
│   ├── rules/               # Rule loading and content generation
│   │   ├── __init__.py
│   │   ├── loader.py        # JSON data loader
│   │   └── dungeon_generator.py  # Procedural dungeon generation
│   │
│   ├── data/                # Game content (JSON)
│   │   ├── srd/             # D&D 5E SRD content
│   │   │   ├── classes.json     # Character classes
│   │   │   ├── monsters.json    # Monster stat blocks
│   │   │   ├── items.json       # Equipment and consumables
│   │   │   ├── skills.json      # Skill definitions
│   │   │   ├── conditions.json  # Status conditions
│   │   │   ├── races.json       # Character races
│   │   │   └── progression.json # Level progression
│   │   └── content/         # Game content
│   │       └── dungeons/
│   │           ├── goblin_warren.json.backup
│   │           └── poisoned_laboratory.json
│   │
│   ├── llm/                 # LLM integration
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract LLM provider interface
│   │   ├── factory.py       # Provider factory pattern
│   │   ├── anthropic_provider.py   # Claude integration
│   │   ├── openai_provider.py      # GPT integration
│   │   ├── debug_provider.py       # Debug/testing provider
│   │   ├── enhancer.py      # Narrative enhancement coordinator
│   │   └── prompts.py       # Prompt templates
│   │
│   ├── ui/                  # User interfaces
│   │   ├── __init__.py
│   │   ├── cli.py           # Command-line interface
│   │   └── rich_ui.py       # Rich terminal formatting
│   │
│   ├── utils/               # Utilities
│   │   ├── __init__.py
│   │   ├── events.py        # Event bus system
│   │   └── logging_config.py     # Logging configuration
│   │
│   └── main.py              # Entry point
│
├── tests/                   # Test suite (65 test files)
│   ├── test_*.py            # Unit tests
│   ├── test_*_integration.py     # Integration tests
│   └── test_*_e2e.py        # End-to-end tests
│
├── pyproject.toml           # Project configuration
├── requirements.txt         # Python dependencies
├── README.md                # User documentation
├── CLAUDE.md                # Development standards
└── docs/
    ├── ARCHITECTURE.md      # This document
    ├── ROADMAP.md           # Strategic planning and feature roadmap
    ├── DEBUG_LLM.md         # Debug provider docs
    └── SPEC_HISTORICAL_2025-11.md  # Historical reference
```

---

## Core Components

### 1. Game Engine Core (`core/`)

The deterministic heart of the game. No randomness except dice rolls.

#### **Dice System** (`dice.py`)
- **Purpose**: All dice rolling mechanics
- **Key Features**:
  - Standard notation parsing (1d20+5, 2d6, etc.)
  - Advantage/disadvantage (roll twice, take best/worst)
  - Critical hit support
  - Deterministic seeding for testing
- **Example**:
  ```python
  roller = DiceRoller()
  result = roller.roll("1d20+5")  # Returns DiceRoll object
  # result.total = 18, result.rolls = [13], result.modifier = 5
  ```

#### **Creature System** (`creature.py`, `character.py`)
- **Purpose**: Base for all creatures (PCs, NPCs, monsters)
- **Creature (Base Class)**:
  - Abilities (STR, DEX, CON, INT, WIS, CHA)
  - HP (current, max, temporary)
  - AC, speed, proficiency bonus
  - Conditions (stunned, prone, etc.)
- **Character (Player Characters)**:
  - Extends Creature
  - Class, level, XP
  - Inventory, equipped items
  - Death saves (for unconscious characters)
- **Data Flow**: JSON → DataLoader → Creature/Character instances

#### **Combat Engine** (`combat.py`)
- **Purpose**: Resolve attacks and damage per D&D 5E rules
- **Key Methods**:
  - `resolve_attack()`: 1d20 + bonus vs AC → hit/miss
  - `calculate_damage()`: Weapon dice + modifiers
  - `apply_damage()`: Reduce HP, handle temp HP
  - `check_critical()`: Natural 20 = crit (double damage dice)
- **Attack Flow**:
  ```
  1. Roll 1d20 + attack bonus
  2. Compare to target AC
  3. If hit: roll damage dice + modifiers
  4. Apply damage to creature
  5. Emit DAMAGE_DEALT event
  6. Check for death
  ```

#### **Party System** (`party.py`)
- **Purpose**: Manage groups of characters
- **Features**:
  - Multiple character support
  - Shared/individual inventory
  - Party death detection (all members at 0 HP)
  - Character lookup by name
- **Design**: Even single-character games use Party with one member

#### **Game State** (`game_state.py`)
- **Purpose**: Single source of truth for game state
- **State Components**:
  ```python
  {
    'party': Party,                # PCs
    'current_room': Room,          # Location
    'dungeon': Dict[str, Room],    # All rooms
    'in_combat': bool,             # Combat flag
    'combat_tracker': InitiativeTracker,  # Turn order
    'visited_rooms': Set[str],     # Exploration tracking
    'quest_state': Dict            # Quest progress (future)
  }
  ```

#### **Save/Load System** (`save_manager.py`)
- **Purpose**: Persist game state to disk
- **Format**: JSON with version tracking
- **Saved Data**: Party state, dungeon state, combat state, inventory
- **Future**: Multiple save slots, auto-save

### 2. Event System (`utils/events.py`)

Pub/Sub messaging for loose coupling between components.

#### **Event Types**
```python
class EventType(Enum):
    # Combat
    COMBAT_START, COMBAT_END, COMBAT_FLED
    TURN_START, TURN_END
    ATTACK_ROLL, DAMAGE_DEALT, HEALING_DONE
    CHARACTER_DEATH, DEATH_SAVE
    SNEAK_ATTACK  # Rogue mechanic

    # Exploration
    ROOM_ENTER, ITEM_ACQUIRED

    # Inventory
    ITEM_EQUIPPED, ITEM_UNEQUIPPED, ITEM_USED
    GOLD_ACQUIRED

    # Character
    LEVEL_UP, SKILL_CHECK

    # LLM
    DESCRIPTION_ENHANCED
```

#### **Usage Pattern**
```python
# Component A: Emit event
event_bus.emit(Event(
    type=EventType.DAMAGE_DEALT,
    data={
        'attacker': 'Thorin',
        'defender': 'Goblin',
        'damage': 7,
        'weapon': 'longsword'
    }
))

# Component B: Subscribe
def on_damage(event: Event):
    print(f"{event.data['attacker']} dealt {event.data['damage']} damage!")

event_bus.subscribe(EventType.DAMAGE_DEALT, on_damage)
```

#### **Key Subscribers**
- **LLMEnhancer**: Enhances narrative descriptions
- **CLI**: Displays events to player
- **Logger**: Records events for debugging
- **SaveManager**: Triggers auto-save on important events

### 3. Game Subsystems (`systems/`)

Specialized systems for specific mechanics.

#### **Initiative Tracker** (`initiative.py`)
- **Purpose**: Manage turn order in combat
- **Algorithm**:
  1. Roll 1d20 + DEX modifier for each combatant
  2. Sort descending (ties broken by DEX modifier)
  3. Track current turn, round number
  4. Remove defeated creatures
  5. Cycle through turns

#### **Inventory System** (`inventory.py`)
- **Purpose**: Item management
- **Features**:
  - Add/remove items
  - Equipment slots (weapon, armor, shield)
  - Consumables (potions)
  - Weight tracking (future)
- **Integration**: Works with both Character and Party inventories

#### **Currency System** (`currency.py`)
- **Purpose**: Gold and treasure tracking
- **Features**: Add/subtract gold, loot distribution

#### **Condition Manager** (`condition_manager.py`)
- **Purpose**: Track status effects (prone, stunned, poisoned, etc.)
- **Integration**: Affects attack rolls, saves, movement

#### **Action Economy** (`action_economy.py`)
- **Purpose**: Track action, bonus action, reaction per turn
- **5E Rules**: Each creature gets one of each per turn

### 4. LLM Enhancement Layer (`llm/`)

Narrative enhancement without affecting mechanics.

#### **Provider Pattern**
- **Base Interface** (`base.py`): Abstract `LLMProvider` class
- **Implementations**:
  - `anthropic_provider.py`: Claude (Haiku, Sonnet, Opus)
  - `openai_provider.py`: GPT (GPT-4o, GPT-4o-mini)
  - `debug_provider.py`: Shows prompts without API calls
- **Factory** (`factory.py`): Creates provider based on config

#### **Enhancer** (`enhancer.py`)
- **Purpose**: Coordinate LLM calls with game events
- **Pattern**: Async LLM calls on background thread
- **Event Subscriptions**:
  - `ROOM_ENTER` → atmospheric room description
  - `COMBAT_END` → victory/defeat narration
  - `DAMAGE_DEALT` → vivid combat description (on-demand)
  - `CHARACTER_DEATH` → dramatic death narration
- **Caching**: Cache room descriptions, monster appearances
- **Graceful Degradation**: Falls back to basic text if LLM fails

#### **Prompts** (`prompts.py`)
- **Purpose**: Template-based prompt generation
- **Templates**:
  - Combat action: "You hit the goblin for 7 damage" → "Your blade cleaves..."
  - Room description: "Torch-lit hall" → "Flickering torches cast dancing shadows..."
  - NPC dialogue: Context-aware character responses

### 5. UI Layer (`ui/`)

User interaction and display.

#### **CLI** (`cli.py`)
- **Purpose**: Main game loop and command parsing
- **Game Modes**:
  - Exploration: Movement, searching, interaction
  - Combat: Initiative-based turn resolution
  - Inventory: Item management
- **Command Parser**: Natural language commands → game actions
- **Integration**: Subscribes to all event types for display

#### **Rich UI** (`rich_ui.py`)
- **Purpose**: Enhanced terminal formatting using Rich library
- **Features**:
  - Color-coded messages (combat = red, success = green)
  - Formatted tables (character stats, inventory)
  - Progress bars (HP bars)
  - Panels and borders
  - Banner display

### 6. Data Layer (`data/`)

All content in JSON for easy modification.

#### **SRD Data** (`data/srd/`)
- `classes.json`: Fighter, Rogue, Cleric (ability priorities, features)
- `monsters.json`: Goblins, bandits, bosses (stat blocks)
- `items.json`: Weapons, armor, potions (properties, effects)
- `skills.json`: Perception, Stealth, etc. (ability modifiers)
- `conditions.json`: Stunned, prone, etc. (effects)
- `races.json`: Human, Elf, Dwarf (ability bonuses, features)
- `progression.json`: Level-up tables (HP, proficiency, features)

#### **Content Data** (`data/content/`)
- `dungeons/`: Room definitions, enemy placement, loot
  - Example: `poisoned_laboratory.json`
  - Procedurally generated via `dungeon_generator.py`

#### **Data Format Example** (Monster)
```json
{
  "goblin": {
    "name": "Goblin",
    "size": "small",
    "type": "humanoid",
    "ac": 15,
    "hp": "2d6",
    "speed": 30,
    "abilities": {
      "str": 8, "dex": 14, "con": 10,
      "int": 10, "wis": 8, "cha": 8
    },
    "actions": [
      {
        "name": "Scimitar",
        "type": "melee-weapon-attack",
        "to_hit": 4,
        "damage": "1d6+2",
        "damage_type": "slashing"
      }
    ]
  }
}
```

---

## Data Flow

### Example: Player Attacks Goblin

```
┌─────────────────────────────────────────────────┐
│  1. Player Input: "attack goblin"              │
└───────────────┬─────────────────────────────────┘
                ↓
┌─────────────────────────────────────────────────┐
│  2. CLI.parse_command() → AttackAction          │
└───────────────┬─────────────────────────────────┘
                ↓
┌─────────────────────────────────────────────────┐
│  3. CombatEngine.resolve_attack(player, goblin) │
└───────────────┬─────────────────────────────────┘
                ↓
┌─────────────────────────────────────────────────┐
│  4. DiceRoller.roll("1d20+5") → 18              │
│     Compare: 18 ≥ goblin.ac (15) → HIT          │
└───────────────┬─────────────────────────────────┘
                ↓
┌─────────────────────────────────────────────────┐
│  5. DiceRoller.roll("1d8+3") → 7 damage         │
│     goblin.current_hp: 7 → 0                    │
└───────────────┬─────────────────────────────────┘
                ↓
┌─────────────────────────────────────────────────┐
│  6. EventBus.emit(DAMAGE_DEALT, {...})          │
└───────────────┬─────────────────────────────────┘
                ↓
        ┌───────┴────────┐
        ↓                ↓
┌──────────────┐   ┌─────────────────┐
│ LLMEnhancer  │   │ CLI Display     │
│ (async)      │   │ (sync)          │
└──────┬───────┘   └─────┬───────────┘
       ↓                  ↓
┌──────────────┐   ┌─────────────────┐
│ Claude API   │   │ Show: "You hit  │
│ Call         │   │ for 7 damage"   │
└──────┬───────┘   └─────────────────┘
       ↓
┌──────────────────────────────────────┐
│ Enhanced: "Your longsword cleaves    │
│ through the goblin's leather armor..." │
└──────┬───────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│ Display enhanced narrative           │
└──────────────────────────────────────┘
```

### Combat Flow

```
┌─────────────────────┐
│  Combat Initiated   │
│  (player enters     │
│   room with enemies)│
└──────────┬──────────┘
           ↓
┌─────────────────────────────────┐
│  1. Roll Initiative             │
│     - 1d20 + DEX for each       │
│     - Sort descending           │
│     - Emit COMBAT_START         │
└──────────┬──────────────────────┘
           ↓
┌─────────────────────────────────┐
│  2. Turn Loop                   │
│     For each combatant:         │
│     ┌─────────────────────────┐ │
│     │ a. Emit TURN_START      │ │
│     │ b. Get action (PC/AI)   │ │
│     │ c. Resolve action       │ │
│     │ d. Emit events          │ │
│     │ e. Check death          │ │
│     │ f. Emit TURN_END        │ │
│     └─────────────────────────┘ │
└──────────┬──────────────────────┘
           ↓
      ┌────┴────┐
      │ Enemies │
      │  alive? │
      └────┬────┘
      Yes  │  No
      ↑────┘  ↓
┌─────────────────────────────────┐
│  3. Combat End                  │
│     - Emit COMBAT_END           │
│     - Award loot                │
│     - Return to exploration     │
└─────────────────────────────────┘
```

---

## Key Design Decisions

### 1. Event-Driven Architecture

**Decision**: Use pub/sub event bus for component communication.

**Rationale**:
- **Decoupling**: Game engine doesn't know about LLM or UI
- **Extensibility**: Add new systems by subscribing to events
- **Testing**: Mock event bus to test components in isolation

**Trade-offs**:
- More complex than direct calls
- Debugging can be harder (event flow less obvious)
- Worth it for flexibility and modularity

### 2. Deterministic Core + Creative Enhancement

**Decision**: Game engine produces outcomes; LLM only enhances narrative.

**Rationale**:
- **Reliability**: Game always works, even if LLM fails
- **Fairness**: LLM can't change dice rolls or damage
- **Performance**: LLM is optional enhancement, not requirement
- **Testing**: Test game logic without API calls

**Implementation**:
- Combat engine emits events with deterministic results
- LLM receives events, returns descriptions
- UI displays both mechanical and narrative info

### 3. Data-Driven Content

**Decision**: All content in JSON, not hardcoded.

**Rationale**:
- **Moddability**: Players can create content without coding
- **Balance**: Adjust monster stats without recompiling
- **Extensibility**: Add new dungeons, items, monsters easily
- **Separation**: Content creators ≠ developers

**Trade-offs**:
- Schema validation needed
- Loading overhead (mitigated by caching)

### 4. Party-First Design

**Decision**: Always use Party abstraction, even for single characters.

**Rationale**:
- **Future-proofing**: Easier to add multi-character support later
- **Consistency**: Same code paths for 1 or 4 characters
- **Initiative**: Already handles multiple PCs in turn order

**Current State**: Party support implemented, works with 1+ characters.

### 5. Rich Terminal UI

**Decision**: Use Rich library for terminal formatting.

**Rationale**:
- **UX**: Color, tables, progress bars improve readability
- **Immersion**: Better visual experience than plain text
- **Accessibility**: Color-blind modes, screen reader support

**Trade-offs**:
- Dependency on Rich library
- Slightly slower rendering (negligible)

### 6. Multiple LLM Providers

**Decision**: Factory pattern for LLM providers.

**Rationale**:
- **Flexibility**: Switch between OpenAI, Anthropic, local models
- **Cost**: Use cheaper models for prototyping
- **Reliability**: Fallback if one provider is down
- **Testing**: Debug provider shows prompts without API calls

### 7. Narrative-First Spatial Design

**Decision**: Use abstract room-based exploration with zone-level positioning, not grid-based coordinates.

**Rationale**:
- **Terminal UI Focus**: Text-based interface prioritizes narrative flow over tactical precision
- **Immersion**: Players read descriptions and make choices, not track coordinates
- **Accessibility**: Simpler mental model, easier to visualize without a map
- **Development Velocity**: Significantly simpler to implement and maintain
- **Story Over Tactics**: Game emphasizes investigation, atmosphere, and storytelling

**Implementation Philosophy**:
- **Exploration**: Room-to-room navigation (graph-based)
- **Combat**: Abstract positioning (Near/Mid/Far zones) for range calculations
- **Light & Vision**: Zone-based visibility (bright/dim/dark areas within rooms)
- **Time**: Automatic passage during actions (movement, searching, resting)

**What This Means**:
- ✅ D&D mechanics respected (attack ranges, light radii, movement)
- ✅ Tactical choices preserved (positioning, resources, timing)
- ❌ No precise grid coordinates (no "move to X,Y")
- ❌ No flanking bonuses or exact AOE placement
- ❌ No diagonals or opportunity attack paths

**Trade-offs**:
- **Lose**: Full tactical combat simulation (like tabletop with miniatures)
- **Gain**: Faster gameplay, clearer presentation, narrative immersion
- **Worth It**: For a terminal-based narrative RPG, abstraction enhances experience

**Impact on Systems**:
- **Lighting (#124)**: Light sources affect room zones, not exact radii
- **Time (#123)**: Automatic advancement during actions, not manual tracking
- **Combat**: Range matters (30ft spell, 60ft darkvision) but via zones
- **Dungeons**: Rooms with connections, not coordinate grids

This constraint guides all spatial system design. When in doubt, choose the approach that preserves narrative flow over tactical precision.

### 8. Extensible Time-Based Resource Management

**Decision**: TimeManager uses a generic TimedEffect system that can track any resource that depletes over time.

**Rationale**:
- **Unified System**: One manager for all time-based depletion (light sources, spell durations, conditions, consumables)
- **Future-Proof**: Can add new resource types without refactoring core system
- **Consistent Behavior**: All time-based resources follow same expiration/notification patterns
- **Event-Driven**: Expiration events work the same for all resource types

**Extensible Design**:
```python
class TimedEffect:
    effect_id: str
    effect_type: str  # "spell", "condition", "light_source", "buff", "food", "ammo", etc.
    start_time: int
    duration_minutes: int
    target: Optional[Character]
    metadata: Dict[str, Any]  # Type-specific data
```

**Current Support** (Phase 1 - Epic #126):
- ✅ Light sources (torches, lanterns) - 60-360 minute durations
- ✅ Spell durations (*Bless*, *Light*, *Mage Armor*) - 1 minute to 8 hours
- ✅ Conditions (Poisoned, Paralyzed) - Varies by source

**Planned Extensions** (Post-Epic):
- 🔮 Consumable buffs (potions with duration)
- 🔮 Food/water tracking (days since last meal)
- 🔮 Ammunition tracking (arrows per quiver)
- 🔮 Tool durability (thieves' tools, healer's kit uses)
- 🔮 Environmental effects (cold exposure, suffocation timer)

**Implementation Philosophy**:
- Start with MVP (light + spells + conditions)
- Extend by adding new `effect_type` values
- Metadata dict holds type-specific data
- No refactoring needed to add new types

**Why This Matters**:
D&D has many time-based resources: torches burn out, spells expire, conditions fade, food spoils, tools break. A single system handles all of these consistently and efficiently.

---

## External Dependencies

### Production Dependencies

```toml
anthropic >= 0.18.0      # Claude API
openai >= 1.0.0          # GPT API
pydantic >= 2.5.0        # Data validation
python-dotenv >= 1.0.0   # Environment config
rich >= 14.2.0           # Terminal UI
prompt-toolkit >= 3.0.52 # Interactive prompts
questionary >= 2.0.0     # User input widgets
```

### Development Dependencies

```toml
pytest >= 7.4.0          # Testing framework
pytest-asyncio >= 0.21.0 # Async test support
pytest-cov >= 4.1.0      # Coverage reporting
mypy >= 1.7.0            # Type checking
ruff >= 0.1.0            # Linting and formatting
```

### Dependency Justification

- **anthropic/openai**: LLM narrative enhancement
- **pydantic**: Validate JSON data against schemas
- **rich**: Color, formatting, progress bars in terminal
- **prompt-toolkit/questionary**: Interactive character creation
- **pytest**: Industry standard testing
- **mypy**: Static type checking (project uses type hints)
- **ruff**: Fast Python linter (replaces flake8, black, isort)

---

## Configuration & Environment

### Environment Variables

Configured via `.env` file:

```bash
# LLM Provider (openai, anthropic, debug, or none)
LLM_PROVIDER=anthropic

# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Anthropic Configuration
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-haiku-20241022

# LLM Settings
LLM_TIMEOUT=10           # Seconds
LLM_MAX_TOKENS=150       # Response length
```

### Command-Line Arguments

```bash
dnd-game [options]

Options:
  --no-llm                 Disable LLM enhancement
  --llm-provider PROVIDER  Override LLM provider (openai, anthropic, debug)
  --dungeon NAME           Choose dungeon (default: goblin_warren)
  --generate-dungeon       Generate random dungeon
  --debug                  Enable debug logging to file
  --version                Show version
```

### Configuration Precedence

1. Command-line arguments (highest priority)
2. Environment variables (`.env` file)
3. Default values (lowest priority)

---

## Testing Strategy

### Test Structure

**Total Tests**: 65 test files

**Test Types**:
1. **Unit Tests** (`test_*.py`): Test individual components in isolation
2. **Integration Tests** (`test_*_integration.py`): Test component interactions
3. **End-to-End Tests** (`test_*_e2e.py`): Test complete workflows

### Key Test Coverage

**Core Systems**:
- `test_dice.py`: Dice rolling, advantage, critical hits
- `test_combat.py`: Attack resolution, damage calculation
- `test_character_factory.py`: Character creation flow
- `test_party.py`: Party management
- `test_inventory.py`: Item management

**Integration Tests**:
- `test_attack_combat_integration.py`: Full attack sequence
- `test_character_creation_integration.py`: Complete character creation
- `test_skills_integration.py`: Skill checks with character abilities
- `test_logging_integration.py`: Event logging across systems

**E2E Tests**:
- `test_inventory_e2e.py`: Item acquisition, equipment, usage

### Testing Practices

- **Mocking**: Mock LLM providers (no API calls in tests)
- **Fixtures**: Reusable character, party, dungeon fixtures
- **Coverage**: Target >80% code coverage (current via pytest-cov)
- **Async**: Use pytest-asyncio for async LLM tests
- **Deterministic**: Seed DiceRoller for reproducible tests

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=dnd_engine tests/

# Specific test file
pytest tests/test_combat.py

# Verbose
pytest -v
```

---

## Extension Points

### Adding New Content

**New Monster**:
1. Add entry to `data/srd/monsters.json`
2. Define stats, actions, traits
3. Use in dungeon via monster ID

**New Dungeon**:
1. Create JSON in `data/content/dungeons/`
2. Define rooms, exits, enemies, loot
3. Reference in `--dungeon` CLI argument

**New Item**:
1. Add to `data/srd/items.json`
2. Define type (weapon, armor, consumable)
3. Optionally add effect in `item_effects.py`

**New Character Class**:
1. Add to `data/srd/classes.json`
2. Define ability priorities, features, proficiencies
3. Implement class features in `character.py` (if complex)

### Adding New Systems

**New LLM Provider**:
1. Implement `LLMProvider` interface in `llm/`
2. Add to factory in `llm/factory.py`
3. Update CLI arguments

**New UI**:
1. Create new module in `ui/`
2. Subscribe to relevant events
3. Implement display logic
4. Example: Web UI with FastAPI + WebSockets

**New Subsystem**:
1. Create module in `systems/`
2. Subscribe to relevant events
3. Emit new events for other systems
4. Example: Crafting system, reputation system

### Plugin Architecture

**Current State**: Designed for plugins but not formalized.

**Future**:
- Plugin directory (`plugins/`)
- Plugin manifest (JSON)
- Auto-discovery and loading
- Sandboxed execution

---

## Future Considerations

### Technical Debt

1. **Save/Load**: Currently basic JSON; could use versioning, compression
2. **Procedural Generation**: Dungeon generator is simple; could be more sophisticated
3. **AI Behavior**: Monster AI is basic (attack lowest HP); could use tactics
4. **Multiplayer**: Architecture supports it, but not implemented

### Planned Enhancements

#### Phase 1: Core Expansion (Near-Term)
- **Spellcasting System**: Spell slots, targeting, concentration
- **Character Leveling**: XP, level-up, new abilities
- **Death Saves**: 5E-accurate death mechanics
- **More Classes**: Wizard, Ranger, Paladin

#### Phase 2: Content Expansion (Mid-Term)
- **Campaign System**: Multi-dungeon storylines
- **Quest Tracking**: Objectives, branching outcomes
- **Merchant NPCs**: Buy/sell items, reputation
- **More Dungeons**: 10+ dungeons with varied themes

#### Phase 3: Advanced Features (Long-Term)
- **Web UI**: Browser-based interface (FastAPI + React)
- **Multiplayer**: Co-op parties (WebSocket server)
- **Mobile App**: iOS/Android native apps
- **Modding Tools**: Visual dungeon editor, monster creator

### Performance Optimizations

**Current Bottlenecks**:
- LLM API calls (3-10 seconds)
  - *Mitigation*: Async calls, caching, fallback to basic text
- JSON loading (negligible, but could cache)
  - *Future*: Pre-load common data, lazy load dungeons

**Scalability**:
- Current: Single-player, local state
- Future: Server-side state for multiplayer, database for persistence

### Open Questions

1. **Balancing**: How to balance procedurally generated encounters?
2. **Narrative Continuity**: How to maintain story coherence across LLM calls?
3. **Modding Security**: How to safely load user-created content?
4. **Accessibility**: Screen reader support, alternative input methods?

---

## Summary

This architecture prioritizes:

✅ **Modularity**: Each component is independent and testable
✅ **Extensibility**: Easy to add content, features, and systems
✅ **Clarity**: Clear separation of concerns, well-documented
✅ **Testability**: 65 test files, >80% coverage target
✅ **Flexibility**: Multiple LLM providers, data-driven content
✅ **Reliability**: Game works without LLM, graceful degradation

The system has evolved from MVP to a robust, feature-rich terminal game while maintaining architectural integrity. The event-driven design and data-driven content make it easy to extend without modifying core systems.

**For New Contributors**: Start with `../README.md` for setup, then read this document for architecture. The codebase follows the structure documented here. See `../CLAUDE.md` for development standards.

---

*Last Updated: 2025-11-18 by Claude Code (Architecture Documentation Task)*
