# D&D 5E SRD Game Engine - Requirements & Architecture

> ⚠️ **HISTORICAL DOCUMENT - ARCHIVED**
>
> This document represents the original design specification from November 2025.
> Many features marked as "future", "out of scope", or "not implemented" are now **fully implemented**.
>
> **For current system architecture and implementation status, see [ARCHITECTURE.md](../ARCHITECTURE.md)**
>
> This document is preserved for historical reference and to understand the original design vision and decision-making process.

**Version:** 0.1
**Last Updated:** 2025-11-16
**Original Status:** Initial Design
**Current Status:** ⚠️ ARCHIVED - See ARCHITECTURE.md for current state

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Core Design Principles](#core-design-principles)
3. [System Architecture](#system-architecture)
4. [Character Creation System](#character-creation-system)
5. [Party System](#party-system)
6. [Game Loop Specifications](#game-loop-specifications)
7. [Combat System](#combat-system)
8. [LLM Integration](#llm-integration)
9. [Data Structures](#data-structures)
10. [MVP Feature Set](#mvp-feature-set)
11. [Future Enhancements](#future-enhancements)
12. [Technical Specifications](#technical-specifications)

---

## Project Overview

### Vision

A Python-based D&D 5E SRD game engine that combines deterministic rule execution with LLM-enhanced narrative. The engine separates game mechanics (combat, inventory, rules) from narrative generation (descriptions, dialogue, atmosphere), creating an extensible foundation for single-player and party-based adventures.

### Goals

- **Accurate 5E Rules**: Combat, abilities, and mechanics follow SRD faithfully
- **Engaging Narrative**: LLM enhances descriptions without affecting mechanics
- **Extensible Design**: Easy to add classes, monsters, dungeons, and rules
- **Party Support**: Architecture supports single character now, party later
- **Data-Driven**: Content in JSON, not hardcoded
- **Testable**: Each component independently testable

### Non-Goals (Out of Scope)

- Multiplayer/networked gameplay
- Real-time combat (turn-based only)
- 3D graphics or complex UI
- Full D&D 5E content (only SRD)
- Character builder website/app (game only)

---

## Core Design Principles

### 1. Separation of Concerns

```
UI Layer          → Presents information, accepts input
LLM Layer         → Enhances narrative, generates dialogue
Event Bus         → Decouples components via pub/sub
Game Engine       → Deterministic rules and state management
Data Layer        → JSON content (monsters, spells, dungeons)
```

### 2. Deterministic Core + Narrative Enhancement

- **Game Engine**: Calculates attack rolls, damage, HP → deterministic outcomes
- **LLM Layer**: Receives outcomes, returns vivid descriptions → no mechanical impact

### 3. Event-Driven Architecture

Components communicate via events:
- Combat engine emits `DAMAGE_DEALT`
- LLM enhancer subscribes, generates description
- UI subscribes, displays to player
- Logger subscribes, records to history

### 4. Data-Driven Content

- Monsters defined in JSON, not code
- Dungeons defined in JSON with rooms, enemies, loot
- Easy to add content without coding

### 5. Party-Aware Design

Even in MVP (single character), design for future party support:
- Combat system handles multiple PCs
- Game state tracks array of characters
- Actions reference character by ID/index
- Initiative includes all party members

---

## System Architecture

### High-Level Layers

```
┌─────────────────────────────────────────────────┐
│              UI Layer                           │
│  CLI (MVP) / Web (Future) / Native (Future)     │
└─────────────────────────────────────────────────┘
                      ↓↑
┌─────────────────────────────────────────────────┐
│         LLM Enhancement Layer                   │
│  Narrative, Dialogue, Atmosphere                │
│  - Subscribes to game events                    │
│  - Calls Claude API                             │
│  - Returns enhanced descriptions                │
└─────────────────────────────────────────────────┘
                      ↓↑
┌─────────────────────────────────────────────────┐
│              Event Bus                          │
│  Pub/Sub for game events                        │
│  - COMBAT_START, DAMAGE_DEALT, ROOM_ENTER, etc  │
└─────────────────────────────────────────────────┘
                      ↓↑
┌─────────────────────────────────────────────────┐
│          Game Engine Core                       │
│  Rules, Combat, State Management                │
│  - Dice rolling                                 │
│  - Combat resolution                            │
│  - Character/Party management                   │
│  - Inventory and equipment                      │
└─────────────────────────────────────────────────┘
                      ↓↑
┌─────────────────────────────────────────────────┐
│            Data Layer (JSON)                    │
│  Classes, Monsters, Spells, Items, Dungeons     │
└─────────────────────────────────────────────────┘
```

### Directory Structure

```
/dnd_engine
  /core                     # Core game mechanics
    __init__.py
    dice.py                 # Dice rolling (4d6, advantage, etc)
    creature.py             # Base for all creatures
    character.py            # Player character class
    party.py                # Party management (future, but design now)
    combat.py               # Combat resolution engine
    game_state.py           # Overall game state
    action_resolver.py      # Parse and validate actions
    character_factory.py    # Character creation system
    
  /systems                  # Game subsystems
    __init__.py
    initiative.py           # Turn order tracking
    inventory.py            # Item management
    conditions.py           # Status effects
    
  /rules                    # Rule loading and validation
    __init__.py
    loader.py               # Load JSON rule files
    validator.py            # Validate against schemas
    
  /data                     # Game content (JSON)
    /srd
      classes.json          # Class definitions with ability priorities
      monsters.json         # Monster stat blocks
      spells.json           # Spell definitions (future)
      items.json            # Equipment and loot
      equipment.json        # Weapons, armor with stats
    /content
      /dungeons
        goblin_warren.json  # Example dungeon
      /encounters
        
  /llm                      # LLM integration
    __init__.py
    base.py                 # Abstract LLM provider interface
    claude.py               # Anthropic Claude implementation
    enhancer.py             # Coordinates narrative enhancement
    prompts.py              # Prompt templates
    
  /ui                       # User interfaces
    __init__.py
    cli.py                  # Command-line interface (MVP)
    
  /utils                    # Utilities
    __init__.py
    events.py               # Event bus system
    logger.py               # Logging
    
  tests/                    # Unit and integration tests
    test_dice.py
    test_combat.py
    test_character_creation.py
    test_initiative.py
    
  main.py                   # Entry point
  requirements.txt
  README.md
```

---

## Character Creation System

### Overview

Character creation uses a **roll → auto-assign → optional swap** flow that balances randomness with player agency while preventing bad builds.

### Creation Flow

```
1. ROLL ABILITIES
   ├─ Roll 4d6, drop lowest, six times
   ├─ Generate six ability scores
   └─ Display results to player

2. AUTO-ASSIGN (Class-Optimized)
   ├─ Read ability priorities from class data
   ├─ Assign highest score to primary ability
   ├─ Assign remaining scores by priority
   ├─ Calculate derived stats (HP, AC, bonuses)
   └─ Display proposed character

3. OPTIONAL RE-ASSIGN
   ├─ Player can swap any two abilities
   ├─ Repeat swaps until satisfied
   ├─ Or accept defaults immediately
   └─ Enter character name

4. CREATE CHARACTER OBJECT
   ├─ Assign starting equipment
   ├─ Set level 1 features
   ├─ Initialize inventory
   └─ Return completed Character
```

### Class Ability Priorities

Stored in `/data/srd/classes.json`:

```json
{
  "fighter": {
    "name": "Fighter",
    "hit_die": "1d10",
    "ability_priorities": [
      "strength",      // Highest score goes here
      "constitution",  // Second highest
      "dexterity",     // Third highest
      "wisdom",
      "intelligence",
      "charisma"       // Lowest score goes here
    ],
    "primary_ability": "strength",
    "saving_throw_proficiencies": ["strength", "constitution"],
    "armor_proficiencies": ["light", "medium", "heavy", "shields"],
    "weapon_proficiencies": ["simple", "martial"],
    "starting_equipment": {
      "weapon": "longsword",
      "armor": "chain_mail",
      "items": ["backpack", "rope", "torch"],
      "gold": 10
    }
  },
  
  "rogue": {
    "name": "Rogue",
    "hit_die": "1d8",
    "ability_priorities": [
      "dexterity",     // Highest
      "intelligence",
      "constitution",
      "charisma",
      "wisdom",
      "strength"       // Lowest
    ],
    "primary_ability": "dexterity",
    "starting_equipment": {
      "weapon": "shortsword",
      "armor": "leather_armor",
      "items": ["thieves_tools", "backpack"],
      "gold": 15
    }
  }
}
```

### Example CLI Interaction

```
=== Character Creation ===

Rolling ability scores (4d6, drop lowest)...
  Roll 1: [6,5,4,2] = 15 (dropped 2)
  Roll 2: [6,4,3,1] = 13 (dropped 1)
  Roll 3: [5,5,4,3] = 14 (dropped 3)
  Roll 4: [4,3,2,2] = 9  (dropped 2)
  Roll 5: [6,5,3,2] = 14 (dropped 2)
  Roll 6: [5,4,4,2] = 13 (dropped 2)

Rolled scores: [15, 14, 14, 13, 13, 9]

Auto-assigning for Fighter (optimizes for Strength/Constitution)...

╔════════════════════════════════════════╗
║        Your Fighter                    ║
╠════════════════════════════════════════╣
║ STR: 15 (+2) ← Primary attack stat    ║
║ DEX: 14 (+2)                           ║
║ CON: 14 (+2) ← Extra hit points       ║
║ INT: 9  (-1)                           ║
║ WIS: 13 (+1)                           ║
║ CHA: 13 (+1)                           ║
╠════════════════════════════════════════╣
║ HP:  12 (1d10 + CON modifier)          ║
║ AC:  16 (Chain mail armor)             ║
║ ATK: +5 (Proficiency + STR)            ║
║ DMG: 1d8+2 (Longsword + STR)           ║
╚════════════════════════════════════════╝

Commands:
  accept    - Start playing with this character
  swap      - Swap two ability scores
  reroll    - Roll new ability scores (once only)

> swap int cha

Swapping INT (9) and CHA (13)...

║ INT: 13 (+1) ← swapped                 ║
║ CHA: 9  (-1) ← swapped                 ║

> accept

What is your character's name? Thorin

Welcome, Thorin the Fighter! Your adventure begins...
```

### Architecture Components

**CharacterFactory** (`/core/character_factory.py`)

```python
class CharacterFactory:
    """Creates characters through guided creation process"""
    
    def create_character_interactive(self, ui) -> Character:
        """Interactive character creation flow"""
        # 1. Roll abilities
        # 2. Choose class (MVP: auto-select Fighter)
        # 3. Auto-assign based on class priorities
        # 4. Allow swaps
        # 5. Prompt for name
        # 6. Apply starting equipment
        # 7. Return Character object
        
    def roll_abilities(self) -> List[int]:
        """Roll 4d6 drop lowest, six times"""
        
    def auto_assign_abilities(self, scores: List[int], 
                             class_name: str) -> Abilities:
        """Assign scores optimally for class"""
        
    def swap_abilities(self, abilities: Abilities, 
                      ability1: str, ability2: str) -> Abilities:
        """Swap two ability scores"""
        
    def calculate_derived_stats(self, character_class: str,
                               abilities: Abilities) -> Dict:
        """Calculate HP, AC, attack bonus, etc."""
```

### Party Integration (Future)

For single character (MVP):
```python
party = Party(characters=[fighter])
```

For multiple characters (future):
```python
# Create multiple characters
fighter = factory.create_character_interactive(ui)
rogue = factory.create_character_interactive(ui)
cleric = factory.create_character_interactive(ui)

# Form party
party = Party(characters=[fighter, rogue, cleric])
```

The system already supports this since:
- Initiative tracker handles multiple PCs
- Combat engine works with any Creature
- Game state tracks party array, not single character

---

## Party System

### Design for Future Party Support

Even though MVP has one character, design decisions accommodate parties:

### Party Class

```python
@dataclass
class Party:
    """Manages a group of characters"""
    characters: List[Character]
    shared_inventory: List[Dict] = field(default_factory=list)  # Party loot
    shared_gold: int = 0  # Split gold or individual?
    
    def get_living_members(self) -> List[Character]:
        """Return characters with HP > 0"""
        
    def is_wiped(self) -> bool:
        """Check if all party members dead"""
        
    def add_character(self, character: Character):
        """Add character to party"""
        
    def remove_character(self, character: Character):
        """Remove character (death, left party)"""
        
    def get_character_by_name(self, name: str) -> Optional[Character]:
        """Find character in party"""
```

### Game State with Party

```python
@dataclass
class GameState:
    party: Party                    # Changed from single 'player'
    current_room: Room
    dungeon: Dict[str, Room]
    in_combat: bool = False
    combat_tracker: Optional[InitiativeTracker] = None
    active_character: Optional[Character] = None  # Whose turn in exploration
```

### Combat with Party

**Initiative includes all party members:**
```
Initiative Order:
  1. Rogue (18)
  2. Goblin 1 (15)
  3. Fighter (14)
  4. Goblin 2 (12)
  5. Cleric (8)
```

**Turn flow:**
```
[Rogue's Turn]
> attack goblin 1
[Roll attack, resolve]

[Goblin 1's Turn]
[AI chooses target: attacks Rogue]

[Fighter's Turn]
> attack goblin 1
[Roll attack, resolve]

...
```

### Party Actions in Exploration

**MVP (Single Character):**
```
> go north
> attack goblin
> search room
```

**Future (Party):**
```
> go north          // Whole party moves
> Thorin attack goblin
> Lyra cast healing word on Thorin
> search room       // Specify who searches? Or party effort?
```

**Design Decision Needed:**
- Do all party members act simultaneously in exploration?
- Or do we track whose "turn" it is even out of combat?
- Recommendation: Simultaneous in exploration, strict turns in combat

### Party Inventory

**Two approaches:**

**Approach 1: Individual Inventories**
- Each character has own inventory
- Must specify who carries what
- More realistic, more micromanagement

**Approach 2: Shared Party Inventory**
- Abstract "party backpack"
- Anyone can use any item
- Simpler, less realistic

**Recommendation for MVP:** Individual inventories, but allow easy transfers
**Future:** Add "party stash" for shared items

### Party Death and Failure

**If one character dies:**
- Remove from initiative
- Party continues fighting
- Potential to revive (future: resurrection spells)

**If all characters die:**
- Game over
- Or: Party wipes, restart from last rest? (roguelike mode)

**Design for MVP:**
- Single character death = game over
- Future: Party wipes only if all dead

---

## Game Loop Specifications

### Main Game Loop

```
┌─────────────────────────────────────┐
│   Character Creation                │
│   (Roll → Assign → Swap → Name)     │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│   Initialize Game State             │
│   - Load dungeon                    │
│   - Place party in start room       │
│   - Set up event subscribers        │
└──────────────┬──────────────────────┘
               ↓
         ┌─────────────┐
         │ Game Active?│
         └─────┬───────┘
               ↓ Yes
    ┌──────────────────────┐
    │  Exploration Mode    │◄─────┐
    └──────────┬───────────┘      │
               │                   │
        ┌──────▼───────┐          │
        │ Combat Start?│          │
        └──────┬───────┘          │
               │ Yes               │
        ┌──────▼───────┐          │
        │ Combat Mode  │          │
        └──────┬───────┘          │
               │                   │
        ┌──────▼───────┐          │
        │ Combat Over? │          │
        └──────┬───────┘          │
               │ Yes               │
               └───────────────────┘
               │ No (party dead)
               ↓
         ┌─────────────┐
         │  Game Over  │
         └─────────────┘
```

### Exploration Mode Loop

```
1. Display Current State
   ├─ Room description (LLM enhanced)
   ├─ Visible exits
   ├─ Visible creatures/NPCs
   ├─ Party status (HP for each member)
   └─ Available actions

2. Get Player Input
   ├─ Movement: "go north", "enter door"
   ├─ Interaction: "talk to merchant", "search room"
   ├─ Combat: "attack goblin"
   ├─ Inventory: "use potion", "equip sword"
   ├─ Party: "check party", "give sword to Lyra"
   └─ Meta: "help", "quit", "save"

3. Validate Action
   ├─ Is action legal in current context?
   ├─ Does character have required items/abilities?
   ├─ Is target valid?
   └─ Check resource availability

4. Execute Action
   ├─ Update game state
   ├─ Roll dice if needed
   ├─ Apply consequences
   └─ Emit events

5. Check Triggers
   ├─ Combat initiation (enemies in room)?
   ├─ Traps triggered?
   ├─ Quest objectives completed?
   ├─ NPCs react?
   └─ Environmental effects?

6. Enhance with LLM
   ├─ Get narrative description
   ├─ Generate NPC responses
   └─ Add atmospheric details

7. Display Results
   └─ Show outcome to player

8. Check Game State
   ├─ Party wiped? → Game Over
   ├─ Quest complete? → Victory
   └─ Otherwise → Loop to step 1
```

### Combat Mode Loop

```
1. Combat Initiation
   ├─ Identify all combatants (party + enemies)
   ├─ Roll initiative for each (1d20 + DEX mod)
   ├─ Sort by initiative (highest first)
   ├─ Emit COMBAT_START event
   └─ Display initiative order

2. Round Loop
   │
   ├─ For each creature in initiative order:
   │  │
   │  ├─ START OF TURN
   │  │  ├─ Emit TURN_START event
   │  │  ├─ Apply start-of-turn effects
   │  │  └─ Check if incapacitated → skip turn
   │  │
   │  ├─ GET ACTION
   │  │  ├─ If PC: prompt player for action
   │  │  ├─ If NPC: run AI to select action
   │  │  └─ Display available actions
   │  │
   │  ├─ VALIDATE ACTION
   │  │  ├─ Is action legal?
   │  │  ├─ In range?
   │  │  └─ Resources available?
   │  │
   │  ├─ RESOLVE ACTION
   │  │  ├─ Roll attack (if attack action)
   │  │  ├─ Roll damage (if hit)
   │  │  ├─ Apply effects
   │  │  ├─ Update creature states
   │  │  └─ Emit action events
   │  │
   │  ├─ CHECK REACTIONS
   │  │  ├─ Opportunity attacks?
   │  │  ├─ Shield spell?
   │  │  └─ Other reactions (future)
   │  │
   │  ├─ ENHANCE WITH LLM
   │  │  ├─ Generate combat description
   │  │  └─ Describe battlefield changes
   │  │
   │  ├─ DISPLAY RESULTS
   │  │  ├─ Show narrative
   │  │  ├─ Show HP changes
   │  │  └─ Show status updates
   │  │
   │  ├─ CHECK DEATH
   │  │  ├─ If creature HP ≤ 0
   │  │  ├─ Remove from initiative
   │  │  └─ Emit CHARACTER_DEATH event
   │  │
   │  └─ END OF TURN
   │     ├─ Apply end-of-turn effects
   │     └─ Emit TURN_END event
   │
   ├─ Check Combat End Conditions
   │  ├─ All enemies defeated? → Victory
   │  ├─ All party members dead? → Defeat
   │  └─ Otherwise → Next turn
   │
   └─ Increment round counter

3. Combat End
   ├─ Emit COMBAT_END event
   ├─ Award XP (future)
   ├─ Distribute loot
   ├─ LLM generates victory/defeat narration
   └─ Return to exploration mode (or game over)
```

---

## Combat System

### Combat Resolution

**Attack Roll:**
```
1. Attacker rolls 1d20
2. Add attack bonus (proficiency + ability modifier)
3. Compare to defender's AC
4. If roll ≥ AC: HIT
5. If natural 20: CRITICAL HIT
6. If natural 1: CRITICAL MISS (future: fumble effects)
```

**Damage Roll:**
```
1. Roll weapon damage dice (e.g., 1d8 for longsword)
2. Add ability modifier (STR for melee, DEX for ranged)
3. If critical hit: roll damage dice twice
4. Apply damage to target HP
5. Check for death (HP ≤ 0)
```

**Advantage/Disadvantage (Future):**
```
Advantage: Roll 2d20, take higher
Disadvantage: Roll 2d20, take lower
```

### Combat Actions (MVP)

**Available Actions:**
- **Attack**: Make a weapon attack
- **Dodge**: Impose disadvantage on attacks against you (future)
- **Dash**: Move extra distance (future)
- **Help**: Give ally advantage (future)
- **Use Item**: Drink potion, etc.

**Future Actions:**
- Cast Spell
- Shove
- Grapple
- Ready Action
- Hide

### Monster AI

**Simple AI for MVP:**

```python
def monster_ai_action(monster: Creature, targets: List[Creature]) -> Action:
    """Simple monster AI"""
    
    # 1. If HP < 25%, flee (future)
    # 2. Otherwise, attack
    
    # Choose target:
    # - Lowest HP target (focus fire)
    # - Or random target
    # - Or closest target (future: positioning)
    
    target = min(targets, key=lambda t: t.current_hp)
    
    return AttackAction(actor=monster, target=target)
```

**Future AI Improvements:**
- Tactical positioning
- Use abilities/spells
- Flee when outmatched
- Focus fire or spread damage
- Protect allies

### Initiative System

**Rolling Initiative:**
```
For each combatant:
  Roll 1d20 + DEX modifier
  
Sort descending by:
  1. Initiative value (higher first)
  2. DEX modifier (ties broken by DEX)
  3. Random (if still tied - future)
```

**Initiative Tracking:**
```python
class InitiativeTracker:
    order: List[InitiativeEntry]  # Sorted list
    current_index: int             # Whose turn
    round_number: int              # Current round
    
    def get_current() -> Creature
    def next_turn() -> Creature
    def remove_creature(creature)  # When creature dies
```

### Death and Defeat

**MVP (Simple Death):**
- HP ≤ 0 → creature dies immediately
- No death saves
- Character death = game over
- Monster death = removed from combat

**Future (5E Death Saves):**
- PC at 0 HP → unconscious, not dead
- Roll death saves (1d20)
  - 10+ = success
  - <10 = failure
  - 3 successes = stabilized
  - 3 failures = dead
- Damage while at 0 HP = automatic failure
- Critical hit while at 0 HP = 2 failures

---

## LLM Integration

### Purpose

The LLM enhances narrative without affecting game mechanics. It receives game events and returns descriptions.

### Integration Points

**1. Room Descriptions**
- Event: `ROOM_ENTER`
- Input: Room data (name, features, enemies, items)
- Output: Atmospheric 2-3 sentence description

**2. Combat Actions**
- Event: `DAMAGE_DEALT`, `ATTACK_ROLL`
- Input: Attacker, defender, action, result, damage
- Output: Vivid combat narration

**3. NPC Dialogue**
- Event: Player talks to NPC
- Input: NPC personality, player input, context
- Output: In-character response

**4. Quest Updates**
- Event: Quest milestone reached
- Input: Quest state, what happened
- Output: Narrative context for story beat

**5. Death/Victory**
- Event: `CHARACTER_DEATH`, `COMBAT_END`
- Input: How combat ended, who died
- Output: Dramatic narration

### Event Subscription Pattern

```python
# LLM enhancer subscribes to events
event_bus.subscribe(EventType.DAMAGE_DEALT, llm_enhancer.on_damage)
event_bus.subscribe(EventType.ROOM_ENTER, llm_enhancer.on_room_enter)

# When event occurs
event_bus.emit(Event(
    type=EventType.DAMAGE_DEALT,
    data={
        'attacker': 'Thorin',
        'defender': 'Goblin',
        'damage': 7,
        'weapon': 'longsword',
        'is_crit': False
    }
))

# LLM enhancer receives and processes
async def on_damage(event: Event):
    context = event.data
    description = await claude.enhance_description(context)
    # Description: "Your longsword cleaves through the goblin's guard..."
    ui.display_narrative(description)
```

### Prompt Templates

**Combat Enhancement:**
```
You are narrating a D&D combat encounter.

Attacker: {attacker}
Defender: {defender}
Action: {action}
Result: {"hit" if hit else "miss"}
Damage: {damage}
Weapon: {weapon}

Provide a vivid, dramatic 2-3 sentence description of this moment.
Do NOT include dice rolls or game mechanics - just describe what happens.
```

**Room Description:**
```
You are describing a D&D dungeon room.

Room: {room_name}
Type: {room_type}
Features: {features}
Enemies: {enemy_list}
Atmosphere: {mood}

Provide an atmospheric 2-3 sentence description.
Set the mood and describe what the party sees, hears, and smells.
```

### LLM Provider Interface

```python
class LLMProvider(ABC):
    @abstractmethod
    async def enhance_description(self, context: Dict[str, Any]) -> str:
        """Enhance game event with narrative"""
        pass
    
    @abstractmethod
    async def generate_dialogue(self, npc: Dict, player_input: str) -> str:
        """Generate NPC response"""
        pass
```

### Caching Strategy

**Cache frequently used descriptions:**
- Monster appearance descriptions
- Common room descriptions
- Standard combat phrases

**Generate fresh for:**
- Combat outcomes (always unique)
- Important story moments
- NPC dialogue (context-dependent)

### Graceful Degradation

Game must work without LLM:
- Fall back to basic descriptions
- "You hit the goblin for 7 damage"
- "You enter a torch-lit hall"

LLM is enhancement, not requirement.

---

## Data Structures

### Character

```python
@dataclass
class Character(Creature):
    # Identity
    name: str
    character_class: str
    level: int
    experience: int
    
    # Abilities (inherited from Creature)
    abilities: Abilities
    
    # Combat stats (inherited from Creature)
    max_hp: int
    current_hp: int
    armor_class: int
    speed: int
    proficiency_bonus: int
    
    # Equipment
    equipped_weapon: Optional[Dict]
    equipped_armor: Optional[Dict]
    inventory: List[Dict]
    gold: int
    
    # Status (inherited from Creature)
    conditions: List[str]
    temp_hp: int
```

### Monster

```python
# Monsters use base Creature class
# Loaded from /data/srd/monsters.json

{
  "goblin": {
    "name": "Goblin",
    "size": "small",
    "type": "humanoid",
    "ac": 15,
    "hp": "2d6",  # Rolled at spawn time
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
        "reach": 5,
        "damage": "1d6+2",
        "damage_type": "slashing"
      }
    ],
    "traits": [
      {
        "name": "Nimble Escape",
        "description": "Can Disengage or Hide as bonus action"
      }
    ]
  }
}
```

### Room

```python
@dataclass
class Room:
    id: str
    name: str
    description: str  # Base description (before LLM enhancement)
    exits: List[str]  # List of room IDs
    enemies: List[str]  # List of monster IDs to spawn
    items: List[Dict]  # Loot in room
    searchable: bool = False
    searched: bool = False
    npcs: List[str] = field(default_factory=list)  # NPCs in room
```

### Dungeon

```json
{
  "name": "Goblin Warren",
  "description": "A network of caves infested with goblins",
  "start_room": "entrance",
  "rooms": {
    "entrance": {
      "name": "Cave Entrance",
      "description": "A dark opening in the hillside",
      "exits": ["hall"],
      "enemies": [],
      "items": []
    },
    "hall": {
      "name": "Main Hall",
      "description": "A torch-lit chamber",
      "exits": ["entrance", "throne_room", "armory"],
      "enemies": ["goblin", "goblin"],
      "items": [{"type": "gold", "amount": 15}],
      "searchable": true
    },
    "throne_room": {
      "name": "Goblin King's Throne",
      "description": "A crude throne room",
      "exits": ["hall"],
      "enemies": ["goblin_boss"],
      "items": [
        {"type": "weapon", "name": "magic_dagger", "damage": "1d4+1"},
        {"type": "gold", "amount": 50}
      ]
    }
  }
}
```

### Game State

```python
@dataclass
class GameState:
    # Party (designed for future multi-character support)
    party: Party  # Contains List[Character]
    
    # World state
    current_room: Room
    dungeon: Dict[str, Room]
    
    # Combat state
    in_combat: bool = False
    combat_tracker: Optional[InitiativeTracker] = None
    
    # History
    action_history: List[str] = field(default_factory=list)
    
    # Quest state (future)
    quest_state: Dict[str, Any] = field(default_factory=dict)
```

---

## MVP Feature Set

### Must Have for Playable Game

#### 1. Character Creation
- ✅ Roll 4d6 drop lowest for abilities
- ✅ Auto-assign based on class priorities
- ✅ Allow ability swaps
- ✅ Single class: Fighter
- ✅ Fixed starting equipment

#### 2. Combat System
- ✅ Initiative system (1d20 + DEX)
- ✅ Attack rolls (1d20 + bonus vs AC)
- ✅ Damage rolls (weapon dice + modifier)
- ✅ Critical hits (nat 20 = double damage dice)
- ✅ HP tracking
- ✅ Death at 0 HP (no death saves)

#### 3. Simple Dungeon
- ✅ 5-7 rooms
- ✅ Room descriptions
- ✅ Connected rooms (exits)
- ✅ Enemies spawned per room
- ✅ Loot in rooms

#### 4. Enemies
- ✅ Goblin (low HP, melee)
- ✅ Bandit (medium HP, melee)
- ✅ Goblin Boss (higher stats)
- ✅ Simple AI (attack lowest HP target)

#### 5. Inventory
- ✅ Gold tracking
- ✅ Weapon (changes damage)
- ✅ Armor (changes AC)
- ✅ Potions (restore HP)
- ✅ Equipment system

#### 6. Core Actions
- ✅ Move between rooms
- ✅ Attack enemy
- ✅ Search room (find loot)
- ✅ Use item (drink potion)
- ✅ Check inventory/stats

#### 7. LLM Integration
- ✅ Room descriptions enhanced
- ✅ Combat action descriptions
- ✅ 1-2 NPCs with dialogue
- ✅ Victory/defeat narration

#### 8. CLI Interface
- ✅ Text-based display
- ✅ Command parsing
- ✅ Combat log
- ✅ Status display (HP, location)

### Nice to Have (MVP+)

- ⭐ Advantage/disadvantage rolls
- ⭐ Short rest (recover HP)
- ⭐ Simple conditions (prone, stunned)
- ⭐ Skill checks (Perception to find hidden items)
- ⭐ Equipment comparison display
- ⭐ Multiple difficulty modes

### Explicitly Out of Scope for MVP

- ❌ Multiple classes
- ❌ Spellcasting
- ❌ Character leveling
- ❌ Death saves
- ❌ Multiple dungeons
- ❌ Quest system
- ❌ Party support (architected for, not implemented)
- ❌ Save/load
- ❌ Web UI

---

## Future Enhancements

### Phase 2: Core Expansion

1. **Additional Classes**
   - Rogue (sneak attack, skills)
   - Cleric (healing, support spells)
   - Each with ability priorities and features

2. **Spellcasting System**
   - Spell slots (per level)
   - Spell preparation
   - Spell targeting
   - Concentration mechanics

3. **Character Leveling**
   - XP tracking
   - Level-up mechanics
   - New abilities/features
   - HP increase

4. **Death Saves**
   - 5E-accurate death mechanics
   - Stabilization
   - Healing unconscious characters

### Phase 3: Party Support

5. **Party Management**
   - Create multiple characters
   - Control party in combat
   - Party inventory sharing
   - Formation/positioning

6. **Party Dynamics**
   - Simultaneous exploration actions
   - Turn order in combat
   - Party death conditions
   - Splitting the party (optional)

### Phase 4: Content Expansion

7. **Multiple Dungeons**
   - Campaign with connected dungeons
   - Overworld map
   - Travel between locations

8. **Quest System**
   - Track objectives
   - Branching outcomes
   - Quest rewards (XP, items, reputation)

9. **More Content**
   - 20+ monsters
   - 10+ dungeons
   - More items/weapons/armor
   - More classes/subclasses

### Phase 5: Advanced Features

10. **Save/Load System**
    - Persistent game state
    - Multiple save slots
    - Auto-save on important events

11. **Reactions**
    - Opportunity attacks
    - Shield spell
    - Counterspell

12. **Advanced Combat**
    - Positioning/grid
    - Cover mechanics
    - Area of effect spells
    - Conditions (all 5E conditions)

13. **NPC Interactions**
    - Merchants (buy/sell)
    - Quest givers
    - Reputation system
    - Persuasion/intimidation checks

### Phase 6: UI/UX

14. **Web UI**
    - Browser-based interface
    - Visual character sheet
    - Map display
    - Better combat visualization

15. **Mobile/Native Apps**
    - iOS/Android ports
    - Touch-optimized UI
    - Offline play

---

## Technical Specifications

### Language & Core Dependencies

**Language:** Python 3.10+

**Required Dependencies:**
```
anthropic>=0.18.0    # Claude API
pydantic>=2.0.0      # Data validation
pytest>=7.0.0        # Testing
```

**Optional Dependencies:**
```
fastapi>=0.100.0     # Web API (future)
sqlalchemy>=2.0.0    # Save/load (future)
rich>=13.0.0         # CLI formatting (nice-to-have)
```

### Development Standards

**Code Style:**
- PEP 8 compliant
- Type hints for all functions
- Docstrings for all classes/methods
- Maximum line length: 100 characters

**Testing:**
- Unit tests for all core components
- Integration tests for game loops
- Minimum 80% code coverage
- Mock LLM calls in tests

**Documentation:**
- README with setup instructions
- Architecture documentation (this file)
- API documentation for key classes
- Example dungeons and content

### Performance Requirements

**LLM Integration:**
- Async/await for all LLM calls
- Non-blocking UI during LLM requests
- Timeout after 10 seconds
- Graceful degradation if LLM unavailable

**Response Times:**
- Dice rolls: < 1ms
- Combat resolution: < 10ms
- Room navigation: < 50ms
- LLM enhancement: < 3 seconds (acceptable wait)

**Memory:**
- Game state < 10MB
- Support dungeons with 50+ rooms
- Support parties with 4+ characters
- Support 20+ concurrent enemies (large battles)

### File Formats

**JSON Schemas:**
- All data validated against JSON schemas
- Schema files in `/data/schemas/`
- Validation on load
- Clear error messages for invalid data

**Save Files (Future):**
- JSON format for save games
- Human-readable
- Include version number
- Backward compatibility considerations

---

## Open Questions & Decisions Needed

### Character Creation

- ✅ **DECIDED:** Roll → Auto-assign → Swap flow
- ❓ **OPEN:** Allow re-roll once? Or unlimited? Or no re-rolls?
  - Recommendation: One re-roll allowed if all scores < 12
- ❓ **OPEN:** What if player wants to manually assign instead of auto-assign?
  - Recommendation: MVP auto-assigns only, manual assign in future

### Party System

- ✅ **DECIDED:** Architecture supports party, MVP implements single character
- ❓ **OPEN:** In exploration, do all party members act simultaneously or take turns?
  - Recommendation: Simultaneous (all move together, any can interact)
- ❓ **OPEN:** Shared gold or individual?
  - Recommendation: Shared party gold (simpler)
- ❓ **OPEN:** Can party split up?
  - Recommendation: No for MVP, maybe future

### Combat

- ✅ **DECIDED:** Simple death (0 HP = dead) for MVP
- ❓ **OPEN:** Monster AI - focus fire or spread damage?
  - Recommendation: Focus lowest HP (more challenging)
- ❓ **OPEN:** Positioning/grid or abstract "in melee/ranged"?
  - Recommendation: Abstract for MVP, grid in future
- ❓ **OPEN:** Do critical misses (nat 1) have special effects?
  - Recommendation: No for MVP, just auto-miss

### LLM Integration

- ✅ **DECIDED:** LLM enhances but doesn't determine mechanics
- ❓ **OPEN:** Cache descriptions or generate fresh every time?
  - Recommendation: Cache monster/room templates, generate combat outcomes fresh
- ❓ **OPEN:** What if LLM call fails or times out?
  - Recommendation: Fall back to basic text, continue game
- ❓ **OPEN:** Allow player to disable LLM for faster play?
  - Recommendation: Yes, add `--no-llm` flag

### Content

- ✅ **DECIDED:** Goblin Warren as first dungeon
- ❓ **OPEN:** How many rooms in MVP dungeon?
  - Recommendation: 5-7 rooms, ~3 combat encounters, simple boss
- ❓ **OPEN:** Include merchant NPC in MVP?
  - Recommendation: No, just combat and exploration
- ❓ **OPEN:** Include any puzzles/traps?
  - Recommendation: No for MVP, adds complexity

---

## Success Criteria

### MVP Success Metrics

A successful MVP delivers:

1. ✅ Character creation that feels fun and balanced
2. ✅ 30-60 minutes of engaging gameplay
3. ✅ 5-7 rooms with varied encounters
4. ✅ Tactical combat following 5E rules accurately
5. ✅ LLM descriptions that enhance immersion
6. ✅ Clear victory condition (defeat boss)
7. ✅ Clean, extensible code architecture
8. ✅ Comprehensive test coverage (>80%)

### Quality Bars

**Gameplay:**
- Combat feels strategic (choices matter)
- Character feels distinct (Fighter abilities clear)
- Dungeon feels coherent (not random rooms)
- Victory feels earned

**Technical:**
- No crashes or game-breaking bugs
- LLM failures handled gracefully
- All dice rolls mathematically correct
- Clean separation of concerns

**User Experience:**
- Clear instructions for new players
- Helpful error messages
- Progress is saved (or game is short enough not to need it)
- Fun to replay with different dice rolls

---

## Implementation Phases

### Week 1: Core Engine
- Dice roller with tests
- Creature/Character classes
- Combat engine
- Initiative system
- Unit tests for all

### Week 2: Game State & Data
- GameState manager
- Room/Dungeon classes
- JSON data loaders
- Sample monsters (3 types)
- Sample dungeon (5 rooms)

### Week 3: LLM Integration
- Event bus implementation
- Claude API integration
- Prompt templates
- Event subscribers
- Graceful degradation

### Week 4: UI & Polish
- CLI interface
- Character creation flow
- Combat loop
- Exploration loop
- Playtesting and bug fixes

### Week 5: Content & Balance
- Complete Goblin Warren dungeon
- Balance combat encounters
- Polish LLM prompts
- Add more loot/items
- Final testing

---

## Appendix: Example Play Session

```
=== DUNGEON MASTER ===
A D&D 5E Adventure

[Character Creation...]
Your Fighter, Thorin, is ready!

=== GOBLIN WARREN ===

You stand before a dark cave entrance in the hillside. The stench of 
unwashed bodies and rotting meat wafts from within. Somewhere in these 
tunnels, the merchant's daughter is held captive.

HP: 12/12 | AC: 16 | Location: Cave Entrance

Exits: north (deeper into cave)

> go north

You enter a torch-lit hall. Crude braziers cast flickering shadows on 
the walls. Two goblins crouch around a small fire, roasting something 
unidentifiable on sticks. They leap up as you enter, grabbing their 
weapons!

[COMBAT BEGINS]

Rolling initiative...
  Thorin: 14
  Goblin 1: 12
  Goblin 2: 8

=== ROUND 1 ===

[THORIN'S TURN]
HP: 12/12 | AC: 16

Enemies: Goblin 1 (healthy), Goblin 2 (healthy)

Actions: attack, dodge, use item

> attack goblin 1

You swing your longsword...
Attack roll: 18 (1d20: 13 + 5) vs AC 15 → HIT!
Damage: 7 (1d8: 5 + 2)

Your blade carves through the goblin's leather armor, biting deep into 
its shoulder. Green blood spurts as it howls in pain and staggers backward!

Goblin 1: 7 HP → 0 HP [DEFEATED]

[GOBLIN 1 DEFEATED]

[GOBLIN 2'S TURN]
The surviving goblin snarls and charges at you!

Attack roll: 8 (1d20: 4 + 4) vs AC 16 → MISS

Its scimitar clangs off your chain mail harmlessly as you sidestep 
the wild swing.

=== ROUND 2 ===

[THORIN'S TURN]
HP: 12/12 | AC: 16

Enemies: Goblin 2 (healthy)

> attack goblin 2

You swing your longsword...
Attack roll: 23 (1d20: 18 + 5) vs AC 15 → HIT!
Damage: 9 (1d8: 7 + 2)

Your follow-up strike is devastating! The blade catches the goblin 
across the chest, dropping it instantly.

Goblin 2: 7 HP → 0 HP [DEFEATED]

[COMBAT VICTORY]

The hall falls silent save for your heavy breathing. The goblins lie 
motionless at your feet.

Searching the bodies, you find:
  - 15 gold pieces
  - Healing Potion

HP: 12/12 | Gold: 25 | Location: Main Hall

The hall has three exits: south (back to entrance), north (deeper), 
east (side passage)

> go north

You approach a heavy wooden door. Beyond it, you hear guttural 
voices... and a girl's frightened whimper. This must be where they're 
holding the captive!

> [continue adventure...]
```

---

**END OF REQUIREMENTS DOCUMENT**

*This is a living document and will be updated as decisions are made and implementation proceeds.*