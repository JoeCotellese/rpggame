# D&D 5E Terminal Game - Design Patterns Audit

**Version:** 1.0.0
**Date:** 2025-11-30
**Purpose:** Comprehensive documentation of architectural and design patterns discovered in the codebase.

---

## Table of Contents

1. [Overview](#overview)
2. [Creational Patterns](#creational-patterns)
3. [Structural Patterns](#structural-patterns)
4. [Behavioral Patterns](#behavioral-patterns)
5. [Dependency Patterns](#dependency-patterns)
6. [Data Flow Patterns](#data-flow-patterns)
7. [Asynchronous Patterns](#asynchronous-patterns)
8. [System-Specific Patterns](#system-specific-patterns)
9. [Architecture Principles](#architecture-principles)
10. [Pattern Summary Table](#pattern-summary-table)

---

## Overview

This codebase demonstrates a mature, well-architected system using multiple design patterns in concert. The architecture prioritizes:

- **Loose Coupling**: Systems interact via events, not direct calls
- **High Cohesion**: Related functionality grouped logically
- **Extensibility**: New features added without modifying existing code
- **Testability**: Each component can be tested independently
- **Data Independence**: Content separated from game logic

The patterns serve specific architectural goals:

```
┌──────────────────────────────────────────────┐
│         Architectural Goals                  │
├──────────────────────────────────────────────┤
│ • Deterministic game mechanics              │
│ • Optional narrative enhancement (LLM)      │
│ • User-friendly terminal interface          │
│ • Easy content creation (JSON data)         │
│ • Extensible without code changes           │
│ • Multi-provider LLM support               │
└──────────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────────┐
│      Design Patterns Working Together        │
├──────────────────────────────────────────────┤
│ Factory → Create varied objects              │
│ Builder → Assemble complex data              │
│ Strategy → Pluggable behaviors              │
│ Observer → Loose coupling via events        │
│ Middleware → Validation pipeline            │
│ DI → Manage dependencies cleanly            │
│ Registry → Centralized content access       │
│ Data-Driven → JSON content separation       │
└──────────────────────────────────────────────┘
```

---

## Creational Patterns

### 1. Factory Pattern

**Purpose**: Encapsulate object creation logic, especially for complex types.

#### 1.1 CharacterFactory (Abstract Factory)

**Location**: `/dnd_engine/core/character_factory.py`

**Use Case**: Creating player characters with intricate initialization logic (ability rolling, racial bonuses, equipment, spells).

**Key Methods**:

| Method | Purpose | Complexity |
|--------|---------|-----------|
| `roll_ability_score()` | Generate 4d6 drop lowest | Simple |
| `auto_assign_abilities()` | Map scores to class priorities | Medium |
| `apply_racial_bonuses()` | Apply race-specific modifiers | Medium |
| `calculate_hp()` | Roll and apply CON modifier | Simple |
| `calculate_ac()` | Base AC + armor + DEX | Medium |
| `apply_starting_equipment()` | Equip items, ammo, tools | Complex |
| `initialize_spellcasting()` | Set up spell slots, known spells | Complex |
| `initialize_class_resources()` | Ki points, rage, etc. | Medium |
| `create_character_interactive()` | Full interactive flow | Very Complex |

**Example**:

```python
# Before Factory (scattered logic)
ability_scores = [16, 14, 13, 12, 10, 8]  # Manual assignment
strength = ability_scores[0]
dexterity = ability_scores[1]
ac = 10 + (dexterity - 10) // 2
# ... 200 more lines of setup

# After Factory (encapsulated)
character = CharacterFactory.create_character_interactive(
    loader=data_loader,
    rng=random.Random()
)
# All setup handled internally
```

**Benefits**:
- ✅ Complex logic encapsulated
- ✅ Reusable creation process
- ✅ Single source of truth for character creation
- ✅ Testable independently
- ✅ Easy to extend (add new class, race)

**Pattern Variant**: Abstract Factory via multiple static methods rather than subclasses.

---

#### 1.2 LLMProviderFactory

**Location**: `/dnd_engine/llm/factory.py`

**Use Case**: Creating appropriate LLM provider based on configuration.

**Implementation**:

```python
def create_llm_provider(
    provider_name: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> LLMProvider | None:
    """Factory function creating LLM provider based on config."""
```

**Strategy**:

1. Auto-detect from `LLM_PROVIDER` environment variable
2. Validate API keys exist
3. Return typed provider or `None`

**Supported Providers**:

| Provider | Type | Location |
|----------|------|----------|
| `AnthropicProvider` | Production | `/llm/anthropic_provider.py` |
| `OpenAIProvider` | Production | `/llm/openai_provider.py` |
| `DebugProvider` | Testing | `/llm/debug_provider.py` |
| `None` | Fallback | Disables LLM |

**Benefits**:
- ✅ Centralized provider creation
- ✅ Easy to add new providers
- ✅ Configuration-driven (no hardcoding)
- ✅ Graceful fallback to no-LLM mode
- ✅ Testable provider creation logic

---

### 2. Builder Pattern

**Purpose**: Construct complex objects step-by-step, especially when assembling data from multiple sources.

#### 2.1 CombatContextBuilder

**Location**: `/dnd_engine/systems/combat_context/builder.py`

**Use Case**: Assembling complete context for LLM narrative generation from scattered game state.

**Method**: `build_attack_context()`

**Data Gathering Process**:

```
Input: attacker, defender, attack_result
         ↓
    ┌────┴────┬───────────┬──────────┬──────────┐
    ↓         ↓           ↓          ↓          ↓
  Weapon   Armor      Location    Combat      Battlefield
  Data     Data       Data        History     State
    ↓         ↓           ↓          ↓          ↓
    └────┬────┴───────────┴──────────┴──────────┘
         ↓
    Complete Attack Context
         ↓
  LLM Narrative Generation
```

**Key Methods**:

```python
class CombatContextBuilder:
    def build_attack_context(
        self,
        attacker: Creature,
        defender: Creature,
        result: AttackResult
    ) -> AttackContext:
        """Assemble complete attack context."""
        # Returns AttackContext with all needed data
```

**Data Assembled**:

```python
@dataclass
class AttackContext:
    attacker: CombatantContext           # Race, class, armor
    defender: CombatantContext           # Race, class, armor
    attack_params: AttackParameters      # Bonus, damage dice, weapon
    location: str                         # Room/battlefield zone
    result: AttackResult                 # Hit/miss/damage
    combat_history: list[str]            # Last 12 actions
    battlefield_state: dict              # Enemy positions, conditions
```

**Related Module**: `/dnd_engine/systems/combat_context/assemblers.py`

Provides helper functions:
- `extract_weapon_data()`
- `extract_armor_data()`
- `get_combat_history()`
- `build_battlefield_state()`

**Benefits**:
- ✅ Complex assembly logic in one place
- ✅ Lazy-loads monster data (caches after first access)
- ✅ Separates data gathering from narrative generation
- ✅ Easy to add new context fields
- ✅ Performance optimization via caching

---

#### 2.2 TurnState Builder

**Location**: `/dnd_engine/systems/action_economy.py` (Lines 24-133)

**Use Case**: Building action economy state for D&D 5E turns.

**Structure**:

```python
@dataclass
class TurnState:
    """Action economy for one combat turn."""
    action_used: bool = False
    bonus_action_used: bool = False
    reaction_used: bool = False
    free_object_interaction_used: bool = False

    def consume_action(action_type: ActionType) -> bool:
        """Attempt to consume action, return success."""
```

**Action Types**:

- `ACTION`: Attack, Cast Spell, Dodge, Disengage, Help, Hide, Ready, Search, Use Object
- `BONUS_ACTION`: Rogue Cunning Action, Barbarian Rage, etc.
- `FREE_OBJECT`: Draw weapon, drop item, open door
- `NO_ACTION`: Talk, look (always available)

**Benefits**:
- ✅ Encapsulates 5E action economy rules
- ✅ Prevents invalid action combinations
- ✅ Easy to reset per turn
- ✅ Testable validation logic

---

### 3. Registry Pattern (Data Loader)

**Purpose**: Provide single point of access to all game content with lazy loading.

#### 3.1 DataLoader

**Location**: `/dnd_engine/rules/loader.py`

**Responsibility**: Load and cache all game content from JSON files.

**Registry Contents**:

| Content Type | File | Access Method | Returns |
|--------------|------|---------------|---------|
| Monsters | `monsters.json` | `load_monsters()` | `Dict[str, dict]` |
| Items | `items.json` | `load_items()` | `Dict[str, Item]` |
| Classes | `classes.json` | `load_classes()` | `Dict[str, dict]` |
| Races | `races.json` | `load_races()` | `Dict[str, dict]` |
| Skills | `skills.json` | `load_skills()` | `Dict[str, dict]` |
| Conditions | `conditions.json` | `load_conditions()` | `Dict[str, dict]` |
| Spells | `spells.json` | `load_spells()` | `Dict[str, dict]` |

**Caching Strategy**:

```python
class DataLoader:
    def __init__(self):
        self._monsters_cache = None
        self._items_cache = None
        # ... other caches

    def load_monsters(self) -> Dict[str, dict]:
        if self._monsters_cache is None:
            self._monsters_cache = self._load_json('monsters.json')
        return self._monsters_cache
```

**Factory Method**:

```python
def create_monster(self, monster_id: str) -> Creature:
    """Convert JSON to Creature instance."""
    monster_data = self.load_monsters()[monster_id]
    return Creature(
        name=monster_data['name'],
        ac=monster_data['ac'],
        hp_formula=monster_data['hp'],
        # ... map all fields
    )
```

**Benefits**:
- ✅ Centralized content access
- ✅ Lazy loading (only load what's needed)
- ✅ Caching (efficient after first load)
- ✅ Single source of truth
- ✅ Easy to extend (add new JSON files)
- ✅ Separates content from code

---

#### 3.2 SaveSlotManager (Repository Pattern)

**Location**: `/dnd_engine/core/save_slot_manager.py`

**Purpose**: Manage 10-slot save system with metadata.

**Repository Interface**:

```python
class SaveSlotManager:
    def list_slots(self) -> List[SaveSlotMetadata]
    def get_slot(self, slot_number: int) -> SaveSlotMetadata | None
    def save_game(self, game_state: GameState, slot: int) -> None
    def load_game(self, slot: int) -> GameState | None
    def delete_slot(self, slot: int) -> None
```

**Metadata Tracking**:

```python
@dataclass
class SaveSlotMetadata:
    slot_number: int
    campaign_name: str
    character_names: List[str]
    playtime_seconds: int
    last_save_timestamp: str
    dungeon_name: str
    current_room: str
```

**Storage**:

- Slots: `slot_01.json` through `slot_10.json`
- Location: `~/.dnd_game/saves/`
- Format: JSON with version tracking

**Benefits**:
- ✅ Abstraction over filesystem details
- ✅ Consistent save/load interface
- ✅ Metadata tracking (playtime, last save)
- ✅ Multiple slots management
- ✅ Easy to add features (compression, versioning)

---

## Structural Patterns

### 1. Layering Architecture

**Pattern**: Multi-layer separation with clear dependencies.

**Layer Stack** (bottom to top):

```
┌────────────────────────────────────────┐
│  UI Layer (cli.py, rich_ui.py)        │ ← User interaction
├────────────────────────────────────────┤
│  Service Layer (combat_context.py)    │ ← Data assembly
├────────────────────────────────────────┤
│  LLM Enhancement Layer (llm/)         │ ← Narrative
├────────────────────────────────────────┤
│  Middleware Layer (combat_middleware)  │ ← Validation
├────────────────────────────────────────┤
│  Event Bus (utils/events.py)          │ ← Pub/Sub
├────────────────────────────────────────┤
│  Game Engine (core/, systems/)        │ ← Rules & state
├────────────────────────────────────────┤
│  Data Layer (data/srd/, data/content/) │ ← JSON content
└────────────────────────────────────────┘
```

**Dependency Direction**: Only downward (UI depends on Service, Service depends on Engine, etc.)

**Benefits**:
- ✅ Clear responsibility boundaries
- ✅ Each layer can be tested independently
- ✅ Easy to replace or upgrade layers (e.g., new UI)
- ✅ Reduced coupling between components

---

### 2. Adapter Pattern

**Location**: `/dnd_engine/main_v2.py` (Lines 95-149)

**Purpose**: Make CLI compatible with `SaveSlotManager` interface.

**Adapter Class**: `SaveSlotCLIAdapter`

**Adaptation**:

```python
class SaveSlotCLIAdapter:
    """Adapts SaveSlotManager to old CampaignManager interface."""

    def __init__(self, save_slot_manager: SaveSlotManager):
        self.save_slot_manager = save_slot_manager

    def save_campaign_state(
        self,
        campaign_name: str,
        game_state: GameState,
        slot_number: int
    ) -> None:
        """Provides old interface, uses new SaveSlotManager internally."""
        self.save_slot_manager.save_game(game_state, slot_number)
```

**Benefits**:
- ✅ Gradual migration from old to new systems
- ✅ Existing code continues to work
- ✅ No breaking changes
- ✅ Clear conversion point

---

## Behavioral Patterns

### 1. Observer Pattern (Event-Driven Architecture)

**Core Pattern**: Pub/Sub messaging for loose coupling.

**Location**: `/dnd_engine/utils/events.py`

#### 1.1 EventBus - Central Hub

**Architecture**:

```
System A → Event → EventBus → System B (subscriber)
                      ↓
                   System C (subscriber)
                      ↓
                   System D (subscriber)
```

**Interface**:

```python
class EventBus:
    @staticmethod
    def subscribe(
        event_type: EventType,
        handler: EventHandler
    ) -> None:
        """Register interest in event type."""

    @staticmethod
    def emit(event: Event) -> None:
        """Publish event to all subscribers."""

    @staticmethod
    def unsubscribe(
        event_type: EventType,
        handler: EventHandler
    ) -> None:
        """Unregister from event type."""
```

#### 1.2 Event Types

**Complete EventType Enumeration** (44 types):

**Combat Events**:
- `COMBAT_START`, `COMBAT_END`, `COMBAT_FLED`
- `TURN_START`, `TURN_END`
- `ATTACK_ROLL`, `DAMAGE_DEALT`, `HEALING_DONE`
- `CHARACTER_DEATH`, `DEATH_SAVE`
- `SNEAK_ATTACK`

**Exploration Events**:
- `ROOM_ENTER`
- `ITEM_ACQUIRED`

**Inventory Events**:
- `ITEM_EQUIPPED`, `ITEM_UNEQUIPPED`, `ITEM_USED`
- `GOLD_ACQUIRED`

**Character Events**:
- `LEVEL_UP`
- `SKILL_CHECK`

**Effect Events**:
- `SPELL_CAST`
- `CONDITION_APPLIED`, `CONDITION_REMOVED`
- `EFFECT_EXPIRED`

**System Events**:
- `LONG_REST`, `SHORT_REST`
- `DESCRIPTION_ENHANCED`

#### 1.3 Key Subscribers

| Subscriber | Module | Events | Purpose |
|------------|--------|--------|---------|
| CLI | `ui/cli.py` | Most events | Display to player |
| LLMEnhancer | `llm/enhancer.py` | Narrative events | Generate descriptions |
| Logger | `utils/logging_config.py` | All events | Audit trail |
| SaveManager | `core/save_slot_manager.py` | Critical events | Auto-save triggers |

**Subscriber Example**:

```python
# In CLI initialization
def __init__(self, game_state: GameState):
    self.event_bus = event_bus
    self.event_bus.subscribe(EventType.COMBAT_START, self._on_combat_start)
    self.event_bus.subscribe(EventType.DAMAGE_DEALT, self._on_damage)
    self.event_bus.subscribe(EventType.CHARACTER_DEATH, self._on_death)

def _on_damage(self, event: Event):
    """Handle damage event."""
    data = event.data
    print(f"{data['attacker']} dealt {data['damage']} damage to {data['defender']}")
```

**Benefits**:
- ✅ Loose coupling (systems don't know about each other)
- ✅ Easy to add new subscribers (e.g., analytics)
- ✅ Extensible (new event types added easily)
- ✅ Testable (mock event bus)
- ✅ Enables async operations (LLM calls)

---

### 2. Strategy Pattern

**Purpose**: Pluggable algorithms for AI behavior.

**Location**: `/dnd_engine/systems/ai/targeting.py`

#### 2.1 TargetingStrategy

**Base Interface** (ABC):

```python
class TargetingStrategy(ABC):
    """Strategy for selecting attack targets."""

    @abstractmethod
    def select_target(self, available_targets: List[Creature]) -> Creature:
        """Choose target from available options."""
```

**Implementations**:

| Strategy | Logic | Use Case |
|----------|-------|----------|
| `LowestHPStrategy` | Always target lowest HP | Optimal gameplay |
| `RandomStrategy` | Random target selection | Unpredictable enemies |
| `HighestThreatStrategy` | Target highest damage dealer | Boss tactics (future) |

**Example Implementation**:

```python
class LowestHPStrategy(TargetingStrategy):
    def select_target(self, available_targets: List[Creature]) -> Creature:
        """Target creature with lowest current HP."""
        return min(available_targets, key=lambda c: c.current_hp)

class RandomStrategy(TargetingStrategy):
    def __init__(self, rng: random.Random):
        self.rng = rng

    def select_target(self, available_targets: List[Creature]) -> Creature:
        """Randomly select a target."""
        return self.rng.choice(available_targets)
```

#### 2.2 Integration with EnemyAI

**Composition Pattern**:

```python
class EnemyAI:
    def __init__(self, targeting_strategy: TargetingStrategy | None = None):
        self.targeting_strategy = targeting_strategy or LowestHPStrategy()

    def select_target(self, available_targets: List[Creature]) -> Creature:
        """Delegate target selection to strategy."""
        return self.targeting_strategy.select_target(available_targets)

    def decide_action(self, context: CombatContext) -> Action:
        """Decide what enemy should do."""
        # Use strategy to select target
        target = self.select_target(context.available_targets)
        return Action(action_type="attack", target=target)
```

**Usage**:

```python
# Default (lowest HP targeting)
ai = EnemyAI()

# Custom strategy
ai = EnemyAI(targeting_strategy=RandomStrategy(rng))

# Can change strategy at runtime
ai.targeting_strategy = HighestThreatStrategy()
```

**Benefits**:
- ✅ Easy to add new AI behaviors (new Strategy class)
- ✅ Runtime strategy switching
- ✅ Testable strategies independently
- ✅ Avoids complex if/else chains
- ✅ Follows Open/Closed Principle

---

### 3. Middleware Pattern (Chain of Responsibility)

**Purpose**: Execute actions through validation pipeline.

**Location**: `/dnd_engine/systems/combat_middleware.py`

#### 3.1 Architecture

**Middleware Chain**:

```
Input
  ↓
┌──────────────────────────────────────┐
│ TurnValidationMiddleware             │
│ - Check: In combat?                  │
│ - Check: Right turn?                 │
│ - Check: Actor alive?                │
└──────────────────┬───────────────────┘
                   ↓ (if valid)
┌──────────────────────────────────────┐
│ ActionEconomyMiddleware              │
│ - Check: Action available?           │
│ - Consume: ACTION/BONUS_ACTION       │
│ - Track for refund on failure        │
└──────────────────┬───────────────────┘
                   ↓ (if valid)
┌──────────────────────────────────────┐
│ LoggingMiddleware                    │
│ - Log action attempt                 │
│ - Track for audit trail              │
└──────────────────┬───────────────────┘
                   ↓ (if valid)
┌──────────────────────────────────────┐
│ Action Handler (combat logic)        │
│ - Execute attack                     │
│ - Apply damage                       │
│ - Emit events                        │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ ResourceCleanupMiddleware (on error) │
│ - Refund consumed actions            │
│ - Restore resources                  │
└──────────────────────────────────────┘
```

#### 3.2 Base Class

```python
@dataclass
class CombatActionContext:
    """Context passed through middleware chain."""
    game_state: GameState
    actor: Character
    action_type: ActionType
    action_name: str
    details: Dict[str, Any]
    result: ActionResult  # SUCCESS, CANCELLED, FAILED
    resources_consumed: List[Tuple[str, int]]

class CombatMiddleware(ABC):
    """Base class for middleware components."""

    @abstractmethod
    def process(
        self,
        context: CombatActionContext,
        next_middleware: Callable
    ) -> bool:
        """Process action, call next middleware, return success."""
```

#### 3.3 Implementations

**TurnValidationMiddleware**:

```python
class TurnValidationMiddleware(CombatMiddleware):
    """Validate basic combat conditions."""

    def process(self, context: CombatActionContext, next_middleware: Callable) -> bool:
        if not context.game_state.in_combat:
            context.result = ActionResult.CANCELLED
            context.error_message = "Not in combat"
            return False

        if not self._is_actors_turn(context):
            context.error_message = "Not your turn"
            return False

        if not context.actor.is_alive:
            context.error_message = "You are unconscious"
            return False

        return next_middleware(context)  # Proceed to next middleware
```

**ActionEconomyMiddleware**:

```python
class ActionEconomyMiddleware(CombatMiddleware):
    """Validate and consume action economy."""

    def process(self, context: CombatActionContext, next_middleware: Callable) -> bool:
        action_type = context.action_type
        turn_state = context.actor.current_turn_state

        if not turn_state.is_action_available(action_type):
            context.error_message = f"No {action_type.name} available"
            return False

        # Consume action
        turn_state.consume_action(action_type)
        context.resources_consumed.append((action_type.name, 1))

        return next_middleware(context)
```

**LoggingMiddleware**:

```python
class LoggingMiddleware(CombatMiddleware):
    """Log all combat actions."""

    def process(self, context: CombatActionContext, next_middleware: Callable) -> bool:
        logger.info(
            f"{context.actor.name} attempting {context.action_name}",
            extra={
                'action_type': context.action_type,
                'details': context.details
            }
        )
        return next_middleware(context)
```

#### 3.4 Executor

```python
class CombatActionExecutor:
    """Executes actions through middleware chain."""

    def __init__(self):
        self.middleware = [
            TurnValidationMiddleware(),
            ActionEconomyMiddleware(),
            LoggingMiddleware(),
        ]

    def execute(
        self,
        actor: Character,
        action_type: ActionType,
        action_name: str,
        action_handler: Callable,
        **details
    ) -> CombatActionContext:
        """Execute action through middleware chain."""
        context = CombatActionContext(
            game_state=game_state,
            actor=actor,
            action_type=action_type,
            action_name=action_name,
            details=details,
            result=ActionResult.SUCCESS,
            resources_consumed=[]
        )

        # Chain middleware together
        chain = action_handler
        for middleware in reversed(self.middleware):
            chain = lambda ctx, mw=middleware, next_fn=chain: (
                mw.process(ctx, next_fn)
            )

        # Execute
        try:
            success = chain(context)
            context.result = ActionResult.SUCCESS if success else ActionResult.FAILED
        except Exception as e:
            context.result = ActionResult.FAILED
            context.error_message = str(e)
            # Refund all resources
            self._refund_resources(context)

        return context
```

**Benefits**:
- ✅ Eliminates boilerplate (50+ lines per action before)
- ✅ Consistent validation across all actions
- ✅ Automatic resource cleanup on failure
- ✅ Easy to add new middleware
- ✅ Testable components independently
- ✅ Single source of validation logic

**Before & After**:

```python
# Before (50+ lines per action)
def handle_attack(self, target):
    if not self.game_state.in_combat:
        self.display("Not in combat")
        return

    if not self.is_actors_turn():
        self.display("Not your turn")
        return

    if not self.actor.is_alive:
        self.display("You are unconscious")
        return

    if not self.actor.current_turn_state.is_action_available():
        self.display("No action available")
        return

    # Consume action
    self.actor.current_turn_state.consume_action()

    try:
        result = self.combat_engine.resolve_attack(self.actor, target)
        self.display(f"You hit for {result.damage} damage")
        # ... more code
    except Exception as e:
        # Manual refund
        self.actor.current_turn_state.cancel_action()
        raise

# After (10-15 lines focused on logic)
def handle_attack(self, target):
    context = self.executor.execute(
        actor=self.actor,
        action_type=ActionType.ACTION,
        action_name="attack",
        action_handler=lambda ctx: self._execute_attack(ctx, target),
        target=target.name
    )
    # All validation and cleanup handled by middleware
```

---

### 4. State Machine Pattern

**Location**: `/dnd_engine/systems/action_economy.py`

**Purpose**: Track turn action availability with valid state transitions.

**State Model**:

```python
@dataclass
class TurnState:
    action_used: bool = False
    bonus_action_used: bool = False
    reaction_used: bool = False
    free_object_interaction_used: bool = False
```

**Valid Transitions**:

```
Turn Start
    ↓
┌─────────────────────────────────────┐
│ Unused Action/Bonus/Reaction/Free   │
│                                     │
│ Can transition to:                  │
│ - Action_used (via consume_action)  │
│ - BonusAction_used (via consume)    │
│ - Reaction_used                     │
│ - Free_used                         │
└─────────────────────────────────────┘
    ↓ (all consumed)
┌─────────────────────────────────────┐
│ Turn Complete (All Used)            │
└─────────────────────────────────────┘
    ↓
Turn End / Reset
```

**Methods**:

```python
def consume_action(self, action_type: ActionType) -> bool:
    """Consume action, prevent double-consumption."""
    if action_type == ActionType.ACTION and not self.action_used:
        self.action_used = True
        return True
    return False

def reset(self) -> None:
    """Reset for new turn."""
    self.action_used = False
    self.bonus_action_used = False
    self.reaction_used = False
    self.free_object_interaction_used = False
```

**Benefits**:
- ✅ Enforces valid state transitions
- ✅ Impossible to double-consume actions
- ✅ Clear turn lifecycle
- ✅ Easy to debug (track state changes)

---

## Dependency Patterns

### 1. Dependency Injection

**Purpose**: Make dependencies explicit and testable.

**Injection Points**:

| Component | Depends On | Injection | Benefit |
|-----------|-----------|-----------|---------|
| CLI | GameState | Constructor | Can test with mock state |
| CombatContextBuilder | GameState, DataLoader | Constructor | Can test with test data |
| EnemyAI | TargetingStrategy | Constructor | Can swap strategies |
| LLMEnhancer | LLMProvider | Constructor | Can test with mock LLM |
| CharacterFactory | DataLoader | Parameter | Can use test data |

**Example**:

```python
# Constructor injection
class CombatContextBuilder:
    def __init__(
        self,
        game_state: GameState,
        data_loader: DataLoader
    ):
        self.game_state = game_state
        self.data_loader = data_loader

# Usage
builder = CombatContextBuilder(
    game_state=game_state,
    data_loader=DataLoader()  # Can inject test loader
)

# Testing
builder = CombatContextBuilder(
    game_state=mock_game_state,
    data_loader=test_data_loader  # Use test data
)
```

**Benefits**:
- ✅ Explicit dependencies
- ✅ Easy to test (inject mocks)
- ✅ Easy to extend (new implementation)
- ✅ Avoids global state
- ✅ Clear object relationships

---

### 2. Inversion of Control (IoC)

**Purpose**: Systems don't control each other; control flows through events.

**Pattern**: Event Bus as IoC Container

**Traditional Approach** (Tight Coupling):

```
┌─────────────────────┐
│  Combat Engine      │
│                     │
│  Calls:             │
│  ├─ ui.display()    │ ← Knows about UI
│  ├─ llm.enhance()   │ ← Knows about LLM
│  └─ save.save()     │ ← Knows about Save
└─────────────────────┘
```

**IoC Approach** (Loose Coupling):

```
┌─────────────────────────────────────────────┐
│  Combat Engine                              │
│                                             │
│  Emits: Event(DAMAGE_DEALT, {...})         │
└────────────────┬────────────────────────────┘
                 ↓
         ┌───────────────┐
         │   Event Bus   │
         └───────┬───────┘
                 ↓
    ┌────────────┼────────────┐
    ↓            ↓            ↓
┌────────┐  ┌──────┐    ┌─────────┐
│  UI    │  │ LLM  │    │  Save   │
│Display │  │Enhance   │ Manager │
└────────┘  └──────┘    └─────────┘
```

**Implementation**:

```python
# Combat engine doesn't know about UI/LLM/Save
class CombatEngine:
    def apply_damage(self, creature, damage):
        creature.current_hp -= damage

        # Emit event - let others decide what to do
        event_bus.emit(Event(
            type=EventType.DAMAGE_DEALT,
            data={
                'attacker': self.attacker.name,
                'defender': creature.name,
                'damage': damage
            }
        ))

# UI subscribes and reacts
class CLI:
    def __init__(self):
        event_bus.subscribe(EventType.DAMAGE_DEALT, self._on_damage)

    def _on_damage(self, event: Event):
        data = event.data
        self.display(f"{data['attacker']} dealt {data['damage']} damage")

# LLM subscribes and reacts
class LLMEnhancer:
    def __init__(self):
        event_bus.subscribe(EventType.DAMAGE_DEALT, self._enhance_damage)

    def _enhance_damage(self, event: Event):
        # Generate vivid combat narrative
        self.schedule_llm_call(event)
```

**Benefits**:
- ✅ Combat engine is independent module
- ✅ New systems added without changing engine
- ✅ Easy to disable features (unsubscribe)
- ✅ Natural event ordering
- ✅ Testable in isolation

---

### 3. Configuration Management

**Approach**: Environment variables + Factory pattern

**Configuration Sources** (Priority):

1. **Command-line arguments** (highest)
2. **Environment variables** (`.env` file)
3. **Default values** (lowest)

**Key Configuration**:

```bash
# .env file
LLM_PROVIDER=anthropic              # Which LLM to use
ANTHROPIC_API_KEY=sk-ant-...        # Credentials
ANTHROPIC_MODEL=claude-3-5-haiku    # Model selection
LLM_TIMEOUT=10                       # API timeout
LLM_MAX_TOKENS=150                   # Response length
```

**Factory Pattern Leveraging Config**:

```python
def create_llm_provider(
    provider_name: str | None = None
) -> LLMProvider | None:
    """Create LLM provider based on config."""

    # Use passed name, fall back to env, then None
    provider_name = (
        provider_name or
        os.getenv('LLM_PROVIDER') or
        'none'
    )

    if provider_name == 'anthropic':
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set, disabling LLM")
            return None
        return AnthropicProvider(api_key)

    elif provider_name == 'openai':
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, disabling LLM")
            return None
        return OpenAIProvider(api_key)

    elif provider_name == 'debug':
        return DebugProvider()

    return None  # No LLM
```

**Benefits**:
- ✅ No hardcoded secrets
- ✅ Different configs per environment
- ✅ Runtime configuration changes
- ✅ Graceful fallbacks
- ✅ Easy testing (override env vars)

---

## Data Flow Patterns

### 1. Game Loop Flow

**High-Level Game Flow**:

```
┌─────────────────┐
│  Application    │
│    Startup      │
└────────┬────────┘
         ↓
┌─────────────────────────────────┐
│  Initialize Components          │
├─────────────────────────────────┤
│ • Load .env configuration       │
│ • Create LLM provider           │
│ • Create EventBus               │
│ • Create SaveSlotManager        │
│ • Create LLMEnhancer (subscribe)│
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│  Main Menu Loop                 │
├─────────────────────────────────┤
│ • Display save slots            │
│ • Load character vault          │
│ • Get player choice             │
│   - New game                    │
│   - Load game                   │
│   - Continue last               │
│   - Exit                        │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│  Game Session                   │
├─────────────────────────────────┤
│ 1. Load GameState (or create)   │
│ 2. Initialize CLI               │
│    • Subscribe to events        │
│    • Initialize systems         │
│ 3. Main Game Loop (repeats)     │
│ 4. End Session                  │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│  Main Game Loop                 │
└─────────────────────────────────┘
         ↓
      ┌──┴──┐
      ↓     ↓
  Exploration Combat
      ↓     ↓
      └──┬──┘
         ↓
   ┌──────────────────┐
   │ Get Player Input │
   └────────┬─────────┘
            ↓
   ┌──────────────────────────────────┐
   │ Process Action                   │
   ├──────────────────────────────────┤
   │ • Validate command               │
   │ • Execute game logic             │
   │ • Emit events                    │
   │ • Update state                   │
   └────────┬─────────────────────────┘
            ↓
   ┌──────────────────────────────────┐
   │ Event Subscribers React          │
   ├──────────────────────────────────┤
   │ • UI: Display results            │
   │ • LLM: Generate narrative        │
   │ • Systems: Update affected items │
   └────────┬─────────────────────────┘
            ↓
   ┌──────────────────────────────────┐
   │ Auto-Save                        │
   └────────┬─────────────────────────┘
            ↓
      Repeat Main Loop
```

---

### 2. Combat Action Flow

**Detailed Combat Action Processing**:

```
Player Input: "attack goblin"
         ↓
┌────────────────────────────┐
│ CLI.parse_command()        │
│ Result: AttackAction       │
└────────┬───────────────────┘
         ↓
┌────────────────────────────────────────────┐
│ CombatActionExecutor.execute()             │
│ Through middleware chain:                  │
├────────────────────────────────────────────┤
│ 1. TurnValidationMiddleware                │
│    ✓ In combat?                            │
│    ✓ Right turn?                           │
│    ✓ Alive?                                │
│ 2. ActionEconomyMiddleware                 │
│    ✓ Action available?                     │
│    → Consume ACTION                        │
│ 3. LoggingMiddleware                       │
│    → Log attack attempt                    │
│ 4. Execute Action Handler                  │
└────────┬───────────────────────────────────┘
         ↓
┌────────────────────────────────────────────┐
│ Combat Engine.resolve_attack()             │
├────────────────────────────────────────────┤
│ 1. Get weapon data from attacker           │
│ 2. Roll 1d20 + attack bonus                │
│ 3. Compare to defender AC                  │
│ 4. If hit: Roll damage                     │
│ 5. If miss: Return miss result             │
│ 6. Check for critical (natural 20)         │
│ 7. Return AttackResult                     │
└────────┬───────────────────────────────────┘
         ↓
┌────────────────────────────────────────────┐
│ Apply Damage                               │
├────────────────────────────────────────────┤
│ • Reduce defender HP                       │
│ • Check death                              │
│ • Return result                            │
└────────┬───────────────────────────────────┘
         ↓
    ┌────┴────┐
    ↓         ↓
  Dead?    Alive?
    ↓         ↓
┌────────┐ ┌──────────────┐
│ DEATH  │ │ Continue     │
└────┬───┘ └──────────────┘
     ↓
┌────────────────────────────────────────────┐
│ EventBus.emit(EVENT_TYPE, {...})          │
├────────────────────────────────────────────┤
│ Events emitted (in order):                 │
│ 1. ATTACK_ROLL                             │
│ 2. DAMAGE_DEALT (if hit)                   │
│ 3. CHARACTER_DEATH (if fatal)              │
└────────┬───────────────────────────────────┘
         ↓
    ┌────┴────┬────────┬──────────┐
    ↓         ↓        ↓          ↓
   UI        LLM     Logger    SaveMgr
    ↓         ↓        ↓          ↓
┌───────┐ ┌──────┐ ┌────────┐ ┌────────┐
│Display│ │Schedule   │ │Record  │ │Trigger │
│Result │ │ Narrative │ │Event   │ │ Auto   │
│       │ │Generation │ │        │ │ Save   │
└───────┘ └──────┘ └────────┘ └────────┘
         ↓
  ┌──────────────────────────────────────┐
  │ LLMEnhancer (async, background)      │
  ├──────────────────────────────────────┤
  │ 1. Gather context from state         │
  │ 2. Call LLM API with timeout         │
  │ 3. Display enhanced narrative        │
  │ 4. Handle timeout → fallback         │
  └──────────────────────────────────────┘
         ↓
      Next Turn
```

**State After Attack**:

```
Game State Updates:
├─ Party[0].hp: 15 → 15 (no damage)
├─ Enemies[0].hp: 8 → 1 (took 7 damage)
├─ InitiativeTracker.current_turn: 1 → 2
├─ Party[0].action_used: false → true
├─ Combat History: [..., "Thorin attacks goblin for 7 damage"]
└─ EventLog: [ATTACK_ROLL, DAMAGE_DEALT, TURN_END]
```

---

### 3. Character State Persistence

**Save File Structure**:

```json
{
  "metadata": {
    "campaign_name": "The Crypt",
    "character_names": ["Thorin", "Elara"],
    "playtime_seconds": 3600,
    "last_save_timestamp": "2025-11-30T15:30:00Z",
    "dungeon_name": "poisoned_laboratory",
    "current_room": "lab_entrance"
  },
  "game_state": {
    "party": {
      "members": [
        {
          "name": "Thorin",
          "class": "Fighter",
          "level": 1,
          "current_hp": 10,
          "max_hp": 11,
          "temporary_hp": 0,
          "abilities": {
            "str": 16, "dex": 13, "con": 14,
            "int": 10, "wis": 12, "cha": 8
          },
          "ac": 16,
          "speed": 30,
          "proficiency_bonus": 2,
          "skills": {...},
          "proficiencies": {...},
          "inventory": {
            "items": [...],
            "equipped": {...},
            "gold": 50
          },
          "active_effects": [...],
          "conditions": [],
          "resource_pools": {...},
          "spellcasting": {...}
        }
      ]
    },
    "enemies": [],
    "current_location": "lab_entrance",
    "dungeon": {...},
    "in_combat": false,
    "combat_tracker": null,
    "visited_rooms": ["entrance"],
    "quest_state": {}
  }
}
```

**Serialization Flow**:

```
GameState (Python objects)
    ↓
@dataclass.asdict() with custom handlers
    ↓
JSON-serializable dict
    ↓
json.dump() → file
    ↓
slot_01.json through slot_10.json
    ↓
--- Load Flow (reverse) ---
    ↓
Load from file → json.load()
    ↓
Dict → Class constructors
    ↓
GameState (Python objects)
    ↓
Ready for gameplay
```

**Benefits**:
- ✅ Complete state preservation
- ✅ No data loss on save
- ✅ Human-readable format (JSON)
- ✅ Extensible (add new fields)
- ✅ Version-trackable

---

## Asynchronous Patterns

### 1. Background Thread Event Loop

**Location**: `/dnd_engine/llm/enhancer.py`

**Purpose**: Non-blocking LLM calls that don't stall game loop.

**Architecture**:

```
Main Thread (Game Loop)          Background Thread
        ├─ Synchronous            ├─ asyncio event loop
        │  ├─ Player input         │  ├─ Pending coroutines
        │  ├─ Combat calc          │  ├─ LLM API calls
        │  ├─ Event emit           │  └─ Waiting for results
        │  └─ Display              │
        │                          ├─ LLMEnhancer._run_sync()
        ├─ Schedule async          │  ├─ Await coroutine
        │  └─ Schedule in bg loop  │  └─ Return result
        │                          │
        └─ Don't wait              └─ Runs independently
```

**Implementation**:

```python
class LLMEnhancer:
    def __init__(self, llm_provider: LLMProvider | None):
        self.llm_provider = llm_provider
        self._background_loop = None
        self._background_thread = None
        self._start_event_loop()

    def _start_event_loop(self):
        """Create background thread with asyncio loop."""
        def run_loop():
            self._background_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._background_loop)
            self._background_loop.run_forever()

        self._background_thread = threading.Thread(
            target=run_loop,
            daemon=True
        )
        self._background_thread.start()

    def _schedule_async(self, coro):
        """Schedule coroutine in background loop."""
        future = asyncio.run_coroutine_threadsafe(
            coro,
            self._background_loop
        )
        return future

    def _run_sync(self, coro, timeout=20):
        """Run async coroutine synchronously with timeout."""
        future = self._schedule_async(coro)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return None  # Fallback to basic description

    def enhance_attack(self, context: AttackContext) -> str:
        """Generate attack narrative (with timeout)."""
        try:
            prompt = build_prompt(context)
            narrative = self._run_sync(
                self.llm_provider.generate(prompt),
                timeout=LLM_TIMEOUT
            )
            return narrative or get_fallback_narrative(context)
        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")
            return get_fallback_narrative(context)
```

**Call Sequence**:

```
Main Thread                    Background Thread
    │
    ├─ enhance_room_description()
    │  ├─ Create coroutine
    │  └─ Schedule in bg loop ──────────→ asyncio loop receives
    │                                     coroutine
    │                                     ├─ Call API (blocking)
    │                                     ├─ Wait for response
    │                                     └─ Result ready
    │
    ├─ Continue game loop (no wait)
    │  ├─ Get next player input
    │  ├─ Process action
    │  └─ Display to player
    │
    └─ If still waiting
       └─ Display fallback + later
          update with full narrative
```

**Benefits**:
- ✅ Game never blocks on LLM API
- ✅ 3-10 second LLM calls don't pause gameplay
- ✅ Timeout after 20 seconds → fallback
- ✅ Graceful degradation
- ✅ No player notice of LLM failure

**Failure Modes**:

```
LLM Call Sequence
    ↓
┌─────────────────┐
│ API Timeout     │
│ (>20 seconds)   │
└────────┬────────┘
         ↓
┌──────────────────────────────────┐
│ Display fallback (basic text)    │
│ "You damage the goblin."         │
└──────────────────────────────────┘
         ↓
┌──────────────────────────────────┐
│ API response eventually arrives  │
│ Log but discard (player moved on)│
└──────────────────────────────────┘
```

---

## System-Specific Patterns

### 1. Time-Based Effect Management

**Location**: `/dnd_engine/systems/time_manager.py`

**Pattern**: Generic timed effect tracking for any duration-based system.

**Data Structure**:

```python
@dataclass
class ActiveEffect:
    """Time-based effect with generic metadata."""
    effect_id: str
    effect_type: str  # "spell", "condition", "light_source", "buff", etc.
    start_time: int
    duration_minutes: int
    target: Optional[Character] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if effect duration elapsed."""
```

**Effect Types Supported** (Extensible):

| Type | Example | Duration | Metadata |
|------|---------|----------|----------|
| `spell` | *Bless*, *Light*, *Mage Armor* | 1min-8hrs | Spell level, effect description |
| `condition` | Poisoned, Paralyzed | Varies | Save DC, damage type |
| `light_source` | Torch, Lantern | 1-6 hours | Light radius, brightness |
| `buff` | Temporary ability boost | Minutes | Bonus value, ability |
| `debuff` | Curse, exhaustion | Varies | Penalty value |

**TimeManager Methods**:

```python
class TimeManager:
    def add_effect(
        self,
        effect: ActiveEffect
    ) -> None:
        """Register time-based effect."""

    def advance_time(self, minutes: int) -> None:
        """Advance exploration time, check expirations."""
        for effect in self.active_effects:
            if effect.is_expired:
                self._handle_expiration(effect)

    def advance_rounds(self, rounds: int) -> None:
        """Advance combat rounds (1 round = 6 seconds)."""
        # Convert rounds to time
        minutes = rounds * 0.1
        self.advance_time(minutes)
```

**Event Flow**:

```
Effect Created
    ↓
TimeManager.add_effect(effect)
    ├─ Store in active_effects list
    └─ Record start_time
    ↓
Time Passes
    ├─ advance_time(minutes)
    ├─ Check each effect.is_expired
    │
    └─ Effect Expires
       ├─ Remove from list
       ├─ Emit EFFECT_EXPIRED event
       │  └─ Other systems react (remove condition, etc.)
       └─ Emit CONDITION_REMOVED (if condition)
          └─ Subscribers update UI
```

**Benefits**:
- ✅ Single system for all time-based effects
- ✅ Easy to add new effect types (just new metadata)
- ✅ Consistent expiration behavior
- ✅ Event-driven notifications
- ✅ Supports both exploration (minutes) and combat (rounds)

---

### 2. Resource Pool System

**Location**: `/dnd_engine/systems/resources.py`

**Purpose**: Generic ability resource management (spell slots, ki, rage, etc.).

**Data Structure**:

```python
@dataclass
class ResourcePool:
    """Generic resource with recovery mechanic."""
    resource_id: str
    name: str  # "1st Level Spell Slot"
    max_value: int
    current_value: int
    recovery_type: str  # "short_rest", "long_rest", "daily", "permanent"
    recovery_amount: int = None
```

**Resource Types**:

| Character | Resource | Max | Recovery |
|-----------|----------|-----|----------|
| Wizard | 1st Spell Slots | 2 | Long Rest |
| Barbarian | Rage Uses | 2 | Long Rest |
| Rogue | Cunning Action | 1 per turn | Per Turn |
| Fighter | Action Surge | 1 | Short Rest |
| Cleric | Channel Divinity | 1 | Short Rest |

**Usage**:

```python
# Get resource
spell_slots = wizard.get_resource_pool("1st_level_spells")
print(f"Available: {spell_slots.current_value}/{spell_slots.max_value}")

# Consume
if spell_slots.current_value > 0:
    spell_slots.current_value -= 1
    # Cast spell
else:
    print("No spell slots remaining")

# Recovery
def long_rest(character):
    for pool in character.resource_pools:
        if pool.recovery_type == "long_rest":
            pool.current_value = pool.max_value
```

**Benefits**:
- ✅ Single system for all resources
- ✅ Consistent recovery logic
- ✅ Easy to add new class resources (just data)
- ✅ Prevent over-consumption

---

### 3. Condition System (Data-Driven)

**Location**: `/dnd_engine/systems/condition_manager.py`

**Data Location**: `/dnd_engine/data/srd/conditions.json`

**Pattern**: Load conditions from JSON, apply generically.

**Condition Schema**:

```json
{
  "on_fire": {
    "name": "On Fire",
    "description": "Burning in flames",
    "effects": {
      "take_damage": {
        "trigger": "turn_start",
        "damage_dice": "1d4",
        "damage_type": "fire"
      },
      "ac_penalty": -2
    },
    "can_end_early": true,
    "end_early_check": {
      "ability": "dexterity",
      "dc": 10
    },
    "duration_rounds": null  # Ends manually or save
  }
}
```

**Usage**:

```python
class ConditionManager:
    def apply_condition(
        self,
        creature: Creature,
        condition_id: str,
        duration_rounds: int | None = None
    ) -> None:
        """Apply condition with effects."""
        condition_data = self.load_conditions()[condition_id]

        # Apply effects
        if 'ac_penalty' in condition_data['effects']:
            creature.ac -= condition_data['effects']['ac_penalty']

        # Track for later removal
        self.active_conditions[creature.name].append({
            'condition': condition_id,
            'applied_at_round': self.current_round,
            'duration': duration_rounds
        })

    def check_condition_expiration(self) -> None:
        """Check which conditions should end."""
        for creature_name, conditions in self.active_conditions.items():
            for condition in conditions[:]:  # Copy list
                if self._is_expired(condition):
                    self.remove_condition(creature_name, condition)
                    event_bus.emit(Event(
                        EventType.CONDITION_REMOVED,
                        {'creature': creature_name, 'condition': condition}
                    ))
```

**Benefits**:
- ✅ No code changes to add conditions
- ✅ Data-driven effects
- ✅ Consistent application
- ✅ Event-based removal
- ✅ Easy to balance (change JSON)

---

### 4. Inventory System (Composition)

**Location**: `/dnd_engine/systems/inventory.py`

**Pattern**: Composition of items with equipment slots.

**Data Structures**:

```python
@dataclass
class InventoryItem:
    item_id: str           # Reference to items.json
    category: str          # "weapons", "armor", "consumables"
    quantity: int
    quest_item: bool       # Doesn't transfer between saves

@dataclass
class Inventory:
    items: Dict[str, InventoryItem]  # item_id -> InventoryItem
    equipment_slots: Dict[str, str]  # "WEAPON" -> item_id
    gold: int

    def add_item(self, item_id: str, quantity: int = 1) -> None:
        """Add items, stacking quantities."""

    def equip_item(self, item_id: str, slot: str) -> None:
        """Equip item in slot (WEAPON, ARMOR, SHIELD)."""

    def unequip_item(self, slot: str) -> None:
        """Unequip from slot."""
```

**Item Management**:

```
Inventory (Party-wide)
    ├─ Items dict
    │  ├─ "short_sword" → Qty: 2
    │  ├─ "leather_armor" → Qty: 1
    │  ├─ "healing_potion" → Qty: 5
    │  └─ "rope_50ft" → Qty: 1
    │
    ├─ Equipment slots
    │  ├─ WEAPON: "short_sword"
    │  ├─ ARMOR: "leather_armor"
    │  └─ SHIELD: empty
    │
    ├─ Quest items
    │  └─ "crystal_key" (quest-specific, doesn't persist)
    │
    └─ Gold: 250
```

**Benefits**:
- ✅ Quantity tracking (multiple items)
- ✅ Quest items flagged (campaign-specific)
- ✅ Equipment slots (clear equipped state)
- ✅ Party-wide inventory (shared loot)

---

## Architecture Principles

### 1. Separation of Concerns

**Principle**: Each module has one reason to change.

**Application**:

| Module | Responsibility | Change Reason |
|--------|-----------------|--------------|
| `core/` | Game mechanics | D&D rules change |
| `llm/` | Narrative enhancement | LLM provider changes |
| `ui/` | User interaction | UI framework upgrade |
| `data/srd/` | Game content | Balance tuning |
| `systems/` | Game subsystems | New features |

**Benefit**: Changing UI doesn't affect game rules, changing D&D rules doesn't affect LLM behavior.

---

### 2. Loose Coupling

**Principle**: Components work independently, communicate via events.

**Example**:

```
Gaming Engine              Optional LLM
    │                         │
    ├─ Deterministic          │
    ├─ Works standalone       │
    ├─ Rolls dice            │
    ├─ Calculates damage     │
    │                         │
    └─ Emit: DAMAGE_DEALT    ─→ LLMEnhancer
       (event bus)             Receives event
                               Generates narrative
                               (doesn't affect game)
```

**Benefit**: LLM failure doesn't crash game, new features added without modifying core.

---

### 3. High Cohesion

**Principle**: Related functionality grouped together.

**Example**: All action economy in one module

```
action_economy.py
    ├─ ActionType enum
    ├─ TurnState dataclass
    ├─ Action consumption logic
    └─ Validation methods
```

vs. scattered across CLI, combat, etc.

**Benefit**: Easy to find, test, modify action economy without side effects.

---

### 4. Open/Closed Principle

**Principle**: Open for extension, closed for modification.

**Examples**:

✅ **Adding new AI strategy**:
```python
class ThreadingStrategy(TargetingStrategy):
    def select_target(self, targets):
        # New strategy without modifying existing code
```

✅ **Adding new condition**:
```json
{
  "frightened": {
    "name": "Frightened",
    "description": "Afraid of source"
  }
}
```

✅ **Adding new LLM provider**:
```python
class GroqProvider(LLMProvider):
    async def generate(self, prompt):
        # New provider without changing factory
```

❌ **Adding new action type** (violates principle):
```python
# Would require changing 10+ middleware implementations
if action_type == ActionType.NEW_ACTION:
    # Scattered checks everywhere
```

**Benefit**: System grows via extension, not modification.

---

### 5. Dependency Inversion

**Principle**: Depend on abstractions, not concrete implementations.

**Example**:

```python
# Good: Depend on abstraction
class CLI:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider  # Could be any provider

# Bad: Depend on concrete implementation
class CLI:
    def __init__(self):
        self.llm = AnthropicProvider()  # Tight coupling
```

**Benefit**: Easy to test (inject mock), easy to swap implementations.

---

## Pattern Summary Table

| Category | Pattern | Location | Purpose |
|----------|---------|----------|---------|
| **Creational** | Factory (Character) | `core/character_factory.py` | Encapsulate complex character creation |
| **Creational** | Factory (LLM Provider) | `llm/factory.py` | Create provider based on config |
| **Creational** | Builder (Combat Context) | `systems/combat_context/builder.py` | Assemble complex context from scattered data |
| **Creational** | Builder (Turn State) | `systems/action_economy.py` | Build action economy state |
| **Creational** | Registry (Data Loader) | `rules/loader.py` | Single point of content access |
| **Creational** | Repository (Save Manager) | `core/save_slot_manager.py` | Manage save/load with slots |
| **Structural** | Layering | Architecture | Clear separation of concerns |
| **Structural** | Adapter | `main_v2.py` | Make new SaveSlot compatible with old interface |
| **Behavioral** | Observer (Event Bus) | `utils/events.py` | Pub/Sub for loose coupling |
| **Behavioral** | Strategy (Targeting) | `systems/ai/targeting.py` | Pluggable AI targeting behaviors |
| **Behavioral** | Middleware | `systems/combat_middleware.py` | Validation pipeline for actions |
| **Behavioral** | State Machine | `systems/action_economy.py` | Track valid turn state transitions |
| **Dependency** | DI (Constructor) | Multiple modules | Explicit dependencies |
| **Dependency** | IoC (Event Bus) | `utils/events.py` | Control via events, not direct calls |
| **Dependency** | Configuration | `.env` + Factory | External config + factory creation |
| **Data Flow** | Game Loop | `main_v2.py` | Sequential turn-by-turn gameplay |
| **Data Flow** | Combat Flow | `core/combat.py` | Detailed attack resolution |
| **Data Flow** | State Persistence | `core/save_slot_manager.py` | Save/load complete game state |
| **Async** | Background Thread Loop | `llm/enhancer.py` | Non-blocking LLM calls |
| **System** | Time-Based Effects | `systems/time_manager.py` | Generic duration tracking |
| **System** | Resource Pools | `systems/resources.py` | Generic ability resources |
| **System** | Conditions | `systems/condition_manager.py` | Data-driven status effects |
| **System** | Inventory | `systems/inventory.py` | Item and equipment management |

---

## Conclusion

This codebase demonstrates sophisticated architectural patterns applied in concert:

1. **Creational patterns** manage object creation (Factory, Builder, Registry)
2. **Behavioral patterns** structure interactions (Observer, Strategy, Middleware)
3. **Structural patterns** organize components (Layering, Adapter)
4. **Dependency patterns** manage coupling (DI, IoC, Configuration)
5. **Data patterns** separate content from logic (Data-Driven, Registry)

**Result**:

- ✅ Deterministic game engine independent of LLM
- ✅ Extensible without modifying core code
- ✅ Testable in isolation
- ✅ Content-driven (JSON modification without code)
- ✅ Multiple integration points (new UI, new providers, new systems)

The patterns serve the project's goals rather than being applied dogmatically, resulting in a clean, maintainable, and extensible architecture.
