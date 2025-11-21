# TimeManager System - Design Document

**Purpose**: Central system for tracking all time-based resource depletion in the D&D 5E Terminal Game.

**Status**: Design Phase (Pre-Implementation)
**Epic**: #126 (Enable "The Unquiet Dead" Adventure Playthrough)
**Related Issues**: #123 (Time Tracking), #124 (Lighting System)

---

## Table of Contents

1. [Overview](#overview)
2. [Design Principles](#design-principles)
3. [Core Data Structure](#core-data-structure)
4. [Resource Type Catalog](#resource-type-catalog)
5. [TimeManager API](#timemanager-api)
6. [Event Flow](#event-flow)
7. [Extension Guide](#extension-guide)
8. [Testing Strategy](#testing-strategy)
9. [Implementation Phases](#implementation-phases)

---

## Overview

### What is TimeManager?

TimeManager is a **unified system** for tracking any resource or effect that changes over time in the game. Instead of having separate systems for spell durations, light sources, food consumption, and other time-based mechanics, TimeManager provides a single, consistent interface.

### Why a Unified System?

D&D 5E has numerous time-based mechanics:
- Torches burn for 1 hour
- Spells last from 1 minute to 8 hours
- Conditions expire after X rounds or hours
- Food/water deprivation causes exhaustion
- Tools have limited uses
- Environmental hazards trigger periodically

Without a unified system, each mechanic would need its own tracking code, leading to:
- ❌ Code duplication
- ❌ Inconsistent behavior
- ❌ Difficult testing
- ❌ Fragile integration

With TimeManager:
- ✅ Single source of truth for time
- ✅ Consistent expiration behavior
- ✅ Event-driven notification
- ✅ Zero-refactor extensibility

### Scope

**In Scope**:
- Track in-game time (minutes elapsed)
- Register time-based effects
- Advance time automatically during gameplay
- Detect and notify when effects expire
- Query active effects

**Out of Scope**:
- Real-world time tracking
- Calendar/date system (future enhancement)
- Time travel or time manipulation spells
- Initiative/turn order (handled by InitiativeTracker)

---

## Design Principles

### 1. Generic by Design

TimeManager knows nothing about specific resource types. It tracks generic `TimedEffect` objects with metadata. Resource-specific logic lives in subscribers, not in TimeManager.

```python
# ✅ Good: Generic
class TimeManager:
    def register_timed_effect(self, effect: TimedEffect) -> None:
        self.active_effects.append(effect)

# ❌ Bad: Specific
class TimeManager:
    def add_torch(self, torch: Torch) -> None:
        self.torches.append(torch)
    def add_spell(self, spell: Spell) -> None:
        self.spells.append(spell)
```

### 2. Event-Driven

TimeManager emits events when effects expire. Game systems subscribe to these events and handle resource-specific logic.

```python
# TimeManager emits event
event_bus.emit(Event(EventType.EFFECT_EXPIRED, data={"effect": expired_effect}))

# Inventory system handles it
def on_effect_expired(self, event: Event):
    effect = event.data["effect"]
    if effect.effect_type == "light_source":
        self._handle_light_expired(effect)
```

### 3. Metadata-Flexible

Each `TimedEffect` has a `metadata: Dict[str, Any]` field that holds resource-specific data. This allows any resource type without schema changes.

```python
# Light source metadata
metadata={"item_id": "torch", "owner": "Thorin"}

# Spell metadata
metadata={"spell_id": "bless", "caster": "Cleric", "targets": ["Fighter", "Rogue"]}

# Condition metadata
metadata={"condition": "poisoned", "save_dc": 10}
```

### 4. Zero-Refactor Extensions

Adding a new resource type requires:
1. Define new `effect_type` string
2. Create `TimedEffect` with appropriate metadata
3. Subscribe to `EFFECT_EXPIRED` event
4. Handle expiration logic in subscriber

**No changes to TimeManager core needed.**

---

## Core Data Structure

### TimedEffect

The fundamental building block of the TimeManager system:

```python
@dataclass
class TimedEffect:
    """A time-based effect or resource that expires after a duration."""

    effect_id: str
    # Unique identifier (e.g., "torch_thorin", "spell_bless_1")
    # Used to remove effects early or query specific effects

    effect_type: str
    # Category of effect: "spell", "condition", "light_source", "buff", etc.
    # Extensible - add new types without code changes

    start_time: int
    # Game time (in minutes) when effect was registered
    # Used to calculate expiration: start_time + duration_minutes

    duration_minutes: int
    # How long the effect lasts
    # -1 = infinite/manual removal
    # 0 = instant (shouldn't be registered)

    target: Optional[Character]
    # Which character is affected (if applicable)
    # None for room-wide effects (e.g., light sources)

    metadata: Dict[str, Any]
    # Resource-specific data
    # Completely flexible - no schema constraints
    # Examples:
    #   {"item_id": "torch", "owner": "Thorin"}
    #   {"spell_id": "bless", "targets": ["Fighter", "Rogue"]}
    #   {"condition": "poisoned", "save_dc": 10}
```

### TimeManager State

```python
class TimeManager:
    """
    Central system for time tracking and timed effect management.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.current_time: int = 0  # Total minutes elapsed since game start
        self.active_effects: List[TimedEffect] = []
```

---

## Resource Type Catalog

This table shows current and planned resource types that TimeManager can handle:

| Effect Type | Duration | Target | Metadata Example | Phase |
|------------|----------|--------|------------------|-------|
| **light_source** | 60-360 min | None | `{"item_id": "torch", "owner": "Thorin"}` | 1 |
| **spell** | 1-480 min | Character | `{"spell_id": "bless", "caster": "Cleric"}` | 1 |
| **condition** | Varies | Character | `{"condition": "poisoned", "save_dc": 10}` | 1 |
| **buff** | 1-60 min | Character | `{"stat": "strength", "value": 25}` | 2 |
| **hunger** | 1440 min | Character | `{"severity": 1}` | 2 |
| **ammo** | -1 (infinite) | Character | `{"ammo_type": "arrow", "count": 20}` | 2 |
| **tool_durability** | -1 | Character | `{"tool": "healers_kit", "uses": 10}` | 3 |
| **environmental** | 60 min | Character | `{"hazard": "cold", "save_dc": 10}` | 3 |
| **deprivation** | 4320 min | Character | `{"type": "rest", "exhaustion": 1}` | 3 |

**Phase 1**: Epic #126 requirements (light, spells, conditions)
**Phase 2**: Consumables and basic resource tracking
**Phase 3**: Advanced survival and environmental mechanics

---

## TimeManager API

### Core Methods

#### `register_timed_effect(effect: TimedEffect) -> None`

Register a new time-based effect.

```python
effect = TimedEffect(
    effect_id="torch_thorin",
    effect_type="light_source",
    start_time=time_manager.current_time,
    duration_minutes=60,
    target=None,
    metadata={"item_id": "torch", "owner": "Thorin"}
)
time_manager.register_timed_effect(effect)
```

**Behavior**:
- Adds effect to `active_effects` list
- Emits `EFFECT_REGISTERED` event (optional)
- No duplicate checking (caller's responsibility)

---

#### `advance_time(minutes: int) -> List[TimedEffect]`

Advance game time and return expired effects.

```python
expired = time_manager.advance_time(10)  # 10 minutes pass
# Returns: [effect1, effect2, ...] that expired during this advance
```

**Behavior**:
1. Increment `self.current_time` by `minutes`
2. Check all `active_effects` for expiration
3. Remove expired effects from `active_effects`
4. Emit `TIME_ADVANCED` event with data: `{"minutes": minutes, "current_time": current_time}`
5. For each expired effect, emit `EFFECT_EXPIRED` event with data: `{"effect": effect}`
6. If `current_time % 60 == 0` (hour boundary), emit `HOUR_PASSED` event
7. Return list of expired effects

---

#### `remove_effect(effect_id: str) -> bool`

Manually remove an effect before expiration (e.g., extinguishing a torch).

```python
removed = time_manager.remove_effect("torch_thorin")
# Returns: True if found and removed, False if not found
```

**Behavior**:
- Find effect by `effect_id`
- Remove from `active_effects`
- Emit `EFFECT_REMOVED` event (not `EFFECT_EXPIRED`)
- Return `True` if found, `False` otherwise

---

#### `get_active_effects(effect_type: Optional[str] = None, target: Optional[Character] = None) -> List[TimedEffect]`

Query active effects, optionally filtered by type or target.

```python
# Get all light sources
lights = time_manager.get_active_effects(effect_type="light_source")

# Get all effects on Thorin
thorin_effects = time_manager.get_active_effects(target=thorin)

# Get all effects
all_effects = time_manager.get_active_effects()
```

---

#### `get_time_remaining(effect_id: str) -> int`

Get remaining duration for a specific effect.

```python
remaining = time_manager.get_time_remaining("torch_thorin")
# Returns: minutes remaining, or -1 if effect not found
```

**Calculation**:
```python
effect = find_effect(effect_id)
elapsed = self.current_time - effect.start_time
remaining = effect.duration_minutes - elapsed
return max(0, remaining)
```

---

#### `get_current_time() -> int`

Get current game time in minutes.

```python
minutes = time_manager.get_current_time()
# Returns: 150 (2 hours 30 minutes elapsed)
```

---

#### `format_time(minutes: int) -> str`

Format minutes into human-readable string.

```python
time_manager.format_time(150)  # "2h 30m"
time_manager.format_time(45)   # "45m"
time_manager.format_time(1440) # "1 day"
```

---

## Event Flow

### Event Types

```python
class EventType(Enum):
    # Time events
    TIME_ADVANCED = "time_advanced"       # Time moved forward
    HOUR_PASSED = "hour_passed"           # Hour boundary crossed

    # Effect lifecycle
    EFFECT_REGISTERED = "effect_registered"  # New effect added
    EFFECT_EXPIRED = "effect_expired"        # Effect duration ended
    EFFECT_REMOVED = "effect_removed"        # Effect manually removed
```

### Typical Event Flow

```
1. Player lights torch
   ↓
2. Inventory.activate_light_source() creates TimedEffect
   ↓
3. TimeManager.register_timed_effect() adds it to active_effects
   ↓
4. EventBus emits EFFECT_REGISTERED
   → LLMEnhancer describes torch lighting
   → UI displays "🔦 Torch lit (60m remaining)"
   ↓
5. Player explores rooms (10 minutes each)
   ↓
6. GameState.move() calls TimeManager.advance_time(10)
   ↓
7. TimeManager checks for expirations
   - 50 minutes remaining → still active
   ↓
8. After 60 minutes total...
   ↓
9. TimeManager.advance_time(10)
   - Detects torch expired
   - Removes from active_effects
   - Emits EFFECT_EXPIRED event
   ↓
10. Inventory listens to EFFECT_EXPIRED
    - Marks torch as "burned out"
    - Removes from active light sources
    ↓
11. LightingManager recalculates room light level
    - Room returns to "dark"
    ↓
12. UI displays "🔦 Your torch has burned out!"
    ↓
13. Next search attempt fails (too dark)
```

---

## Extension Guide

### Adding a New Resource Type

Let's walk through adding **Potion of Speed** (1 minute buff) as an example.

#### Step 1: Define Effect Type Constant

```python
# In dnd_engine/systems/time_manager.py or constants.py
EFFECT_TYPE_BUFF = "buff"
```

#### Step 2: Create the Effect When Resource is Used

```python
# In dnd_engine/systems/inventory.py or item_effects.py

def use_potion_of_speed(character: Character, game_state: GameState) -> Dict:
    """Use Potion of Speed - grants extra action, +2 AC, advantage on DEX for 1 minute."""

    # Apply immediate buff to character
    character.temp_effects["potion_of_speed"] = {
        "extra_action": True,
        "ac_bonus": 2,
        "dex_advantage": True
    }

    # Register with TimeManager
    effect = TimedEffect(
        effect_id=f"potion_speed_{character.name}",
        effect_type=EFFECT_TYPE_BUFF,
        start_time=game_state.time_manager.current_time,
        duration_minutes=1,
        target=character,
        metadata={
            "potion_name": "Potion of Speed",
            "effect_key": "potion_of_speed"  # Key to remove from temp_effects
        }
    )
    game_state.time_manager.register_timed_effect(effect)

    # Emit event for LLM/UI
    game_state.event_bus.emit(Event(
        type=EventType.ITEM_USED,
        data={"item": "potion_of_speed", "character": character.name}
    ))

    return {"success": True, "message": f"{character.name} drinks the Potion of Speed!"}
```

#### Step 3: Subscribe to EFFECT_EXPIRED Event

```python
# In dnd_engine/systems/item_effects.py or character.py

class BuffManager:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.event_bus.subscribe(EventType.EFFECT_EXPIRED, self._on_effect_expired)

    def _on_effect_expired(self, event: Event) -> None:
        """Handle buff expiration."""
        effect = event.data["effect"]

        if effect.effect_type != EFFECT_TYPE_BUFF:
            return  # Not our concern

        character = effect.target
        effect_key = effect.metadata["effect_key"]

        # Remove buff from character
        if effect_key in character.temp_effects:
            del character.temp_effects[effect_key]

        # Notify player
        self.event_bus.emit(Event(
            type=EventType.BUFF_EXPIRED,
            data={
                "character": character.name,
                "buff_name": effect.metadata["potion_name"]
            }
        ))
```

#### Step 4: Display in UI

```python
# In dnd_engine/ui/cli.py or rich_ui.py

def display_active_buffs(character: Character, time_manager: TimeManager):
    """Show active buffs with remaining duration."""
    buffs = time_manager.get_active_effects(
        effect_type=EFFECT_TYPE_BUFF,
        target=character
    )

    if not buffs:
        return

    print("\n✨ Active Buffs:")
    for buff in buffs:
        remaining = time_manager.get_time_remaining(buff.effect_id)
        name = buff.metadata["potion_name"]
        print(f"  - {name}: {remaining}m remaining")
```

#### Step 5: Write Tests

```python
# In tests/test_buff_expiration.py

def test_potion_of_speed_expires():
    event_bus = EventBus()
    time_manager = TimeManager(event_bus)
    character = create_test_character("Fighter")

    # Use potion
    effect = TimedEffect(
        effect_id=f"potion_speed_{character.name}",
        effect_type="buff",
        start_time=0,
        duration_minutes=1,
        target=character,
        metadata={"effect_key": "potion_of_speed"}
    )
    time_manager.register_timed_effect(effect)
    character.temp_effects["potion_of_speed"] = {"extra_action": True}

    # Advance time past expiration
    expired = time_manager.advance_time(2)

    # Verify expired
    assert len(expired) == 1
    assert expired[0].effect_id == f"potion_speed_{character.name}"
    assert "potion_of_speed" not in character.temp_effects
```

---

## Testing Strategy

### Unit Tests

**File**: `tests/test_time_manager.py`

**Coverage**:
- ✅ Time initialization (starts at 0)
- ✅ Time advancement (10 min, 1 hour, etc.)
- ✅ Effect registration
- ✅ Effect expiration detection
- ✅ Manual effect removal
- ✅ Query methods (get_active_effects, get_time_remaining)
- ✅ Event emission (TIME_ADVANCED, HOUR_PASSED, EFFECT_EXPIRED)
- ✅ Edge cases (negative time, zero duration, infinite duration)

**Example**:
```python
def test_effect_expires_at_correct_time():
    event_bus = EventBus()
    time_manager = TimeManager(event_bus)

    effect = TimedEffect(
        effect_id="test_torch",
        effect_type="light_source",
        start_time=0,
        duration_minutes=60,
        target=None,
        metadata={}
    )
    time_manager.register_timed_effect(effect)

    # 59 minutes - should NOT expire
    expired = time_manager.advance_time(59)
    assert len(expired) == 0
    assert len(time_manager.active_effects) == 1

    # 1 more minute (60 total) - should expire
    expired = time_manager.advance_time(1)
    assert len(expired) == 1
    assert expired[0].effect_id == "test_torch"
    assert len(time_manager.active_effects) == 0
```

---

### Integration Tests

**File**: `tests/test_time_integration.py`

**Scenarios**:
- ✅ Movement advances time (10 minutes per room)
- ✅ Searching advances time (10 minutes)
- ✅ Combat advances time (6 seconds per round)
- ✅ Rests advance time (60 min short, 480 min long)
- ✅ Torches expire and room goes dark
- ✅ Spell durations tracked correctly
- ✅ Multiple effects expire in order
- ✅ Events trigger UI updates

**Example**:
```python
def test_torch_expires_during_exploration():
    game_state = create_test_game_state()
    character = game_state.party.members[0]

    # Light torch (60 minute duration)
    character.inventory.activate_light_source("torch", game_state)

    # Verify room is bright
    assert game_state.lighting_manager.get_room_light_level() == LightLevel.BRIGHT

    # Explore 6 rooms (60 minutes)
    for _ in range(6):
        game_state.move("north")  # 10 minutes each

    # Torch should have expired
    active_lights = character.inventory.get_active_light_sources()
    assert len(active_lights) == 0

    # Room should be dark
    assert game_state.lighting_manager.get_room_light_level() == LightLevel.DARK
```

---

### Testing New Resource Types

When adding a new resource type, follow this pattern:

**Unit Test**:
```python
def test_new_resource_type_lifecycle():
    # 1. Register effect
    # 2. Verify active
    # 3. Advance time partway
    # 4. Verify still active
    # 5. Advance past expiration
    # 6. Verify expired
    # 7. Verify event emitted
```

**Integration Test**:
```python
def test_new_resource_affects_gameplay():
    # 1. Create game state with resource
    # 2. Verify resource provides benefit
    # 3. Advance time past expiration
    # 4. Verify benefit removed
    # 5. Verify player notified
```

---

## Implementation Phases

### Phase 1: Core Time System (Epic #126)

**Goal**: Support light sources, spell durations, and conditions for "The Unquiet Dead" adventure.

**Tasks**:
1. Create `time_manager.py` with TimeManager class
2. Add `current_time` to GameState
3. Implement `advance_time()` on movement, searching, rests
4. Add time display to UI
5. Create unit tests (>90% coverage)
6. Create integration tests

**Effect Types Supported**:
- `light_source` (torches, lanterns)
- `spell` (*Bless*, *Light*, *Mage Armor*)
- `condition` (Poisoned, Paralyzed)

**Success Criteria**:
- ✅ Time advances automatically during gameplay
- ✅ Light sources burn out after duration
- ✅ Spell effects expire correctly
- ✅ UI shows current time and active effects

---

### Phase 2: Consumables & Buffs (Post-Epic)

**Goal**: Support potion buffs, food/water tracking, and ammunition.

**Tasks**:
1. Add `buff` effect type for potion buffs
2. Add `hunger`/`thirst` effect types
3. Add `ammo` effect type (count-based, not time-based)
4. Update UI to show buffs and resource status
5. Create tests

**Effect Types Supported**:
- `buff` (Potion of Giant Strength, Potion of Speed)
- `hunger` (Days without food)
- `ammo` (Arrows per quiver)

---

### Phase 3: Advanced Systems (Future)

**Goal**: Environmental hazards, tool durability, exhaustion.

**Tasks**:
1. Add `tool_durability` effect type
2. Add `environmental` effect type
3. Add `deprivation` effect type
4. Implement exhaustion mechanics
5. Create tests

**Effect Types Supported**:
- `tool_durability` (Healer's Kit, Thieves' Tools)
- `environmental` (Extreme cold, suffocation)
- `deprivation` (Rest, food, water)

---

## Summary

The TimeManager system provides:

✅ **Unified time tracking** - one source of truth
✅ **Generic effect system** - handles any resource type
✅ **Event-driven** - loose coupling via event bus
✅ **Zero-refactor extensibility** - add types without core changes
✅ **Consistent behavior** - all resources expire the same way

**Current Support** (Phase 1):
- Light sources (torches, lanterns)
- Spell durations (*Bless*, *Light*, *Mage Armor*)
- Conditions (Poisoned, Paralyzed)

**Future Support** (Phases 2-3):
- Potion buffs
- Food/water tracking
- Ammunition
- Tool durability
- Environmental hazards
- Exhaustion from deprivation

**Key Architectural Principle**:
> "One system handles all time-based resource depletion consistently and efficiently."

See `docs/ARCHITECTURE.md` - Key Design Decision #8 for architectural context.

---

*Last Updated: 2025-11-21*
*Status: Design Document (Pre-Implementation)*
