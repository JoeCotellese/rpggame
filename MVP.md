D&D 5E SRD Game Engine Architecture
Overview
A Python-based terminal game for running D&D 5E SRD adventures with LLM-enhanced narrative. This MVP delivers a command-line interface (CLI) gaming experience while using an extensible engine architecture that separates deterministic game mechanics from creative narrative generation. The plugin-based design enables future expansion to web or native UIs.
Core Design Principles

Separation of Concerns: Game rules, content, narrative enhancement, and UI are completely separated
Data-Driven: All content (monsters, items, spells, dungeons) stored in JSON, not hardcoded
Event-Driven: Components communicate via event bus, enabling loose coupling
Extensible: Plugin architecture allows adding new rule systems, content, or LLM providers
Testable: Each component can be unit tested independently

Architecture Layers
┌─────────────────────────────────────┐
│           UI Layer                  │
│   (CLI, Web, Native - Future)       │
└─────────────────────────────────────┘
                 ↓↑
┌─────────────────────────────────────┐
│      LLM Enhancement Layer          │
│  (Narrative, Dialogue, Descriptions)│
└─────────────────────────────────────┘
                 ↓↑
┌─────────────────────────────────────┐
│         Event Bus                   │
│  (Pub/Sub for game events)          │
└─────────────────────────────────────┘
                 ↓↑
┌─────────────────────────────────────┐
│       Game Engine Core              │
│  (Rules, Combat, State Management)  │
└─────────────────────────────────────┘
                 ↓↑
┌─────────────────────────────────────┐
│         Data Layer                  │
│  (JSON: Monsters, Spells, Dungeons) │
└─────────────────────────────────────┘
Directory Structure
/dnd_engine
  /core                    # Core game mechanics
    dice.py               # Dice rolling (d20, 2d6+3, advantage, etc)
    creature.py           # Base class for all creatures (PC/NPC/Monster)
    character.py          # Player character (extends Creature)
    combat.py             # Combat resolution engine
    game_state.py         # Overall game state manager
    action_resolver.py    # Processes and validates player actions
    
  /systems                # Game subsystems
    initiative.py         # Turn order tracking
    inventory.py          # Item management
    conditions.py         # Status effects (stunned, prone, etc)
    
  /rules                  # Rule loading and validation
    loader.py             # JSON rule file loader
    validator.py          # Schema validation for data files
    
  /data                   # Game content (all JSON)
    /srd
      classes.json        # Character classes
      monsters.json       # Monster stat blocks
      spells.json         # Spell definitions
      items.json          # Equipment and loot
    /content
      /dungeons           # Dungeon definitions
      /encounters         # Pre-built encounters
      
  /llm                    # LLM integration layer
    base.py               # Abstract LLM provider interface
    claude.py             # Anthropic Claude implementation
    enhancer.py           # Narrative enhancement coordinator
    prompts.py            # Prompt templates
    
  /ui                     # User interfaces
    cli.py                # Command-line interface (MVP)
    
  /utils                  # Utilities
    events.py             # Event bus system
    logger.py             # Logging utilities
    
  tests/                  # Unit tests
  main.py                 # Entry point
  requirements.txt
  README.md
Core Components
1. Game Engine Core
Purpose: Deterministic rule execution, no randomness beyond dice rolls
Key Classes:

DiceRoller: Handle all dice mechanics (d20+5, 2d6, advantage/disadvantage)
Creature: Base for characters/monsters (HP, AC, abilities, conditions)
Character: Player character (extends Creature, adds inventory, XP, class)
CombatEngine: Attack resolution, damage calculation, critical hits
GameState: Complete game state (player, location, combat status, history)

Responsibilities:

Roll dice according to 5E rules
Calculate attack bonuses, damage, AC
Manage HP, conditions, death
Validate actions against game rules
Track initiative order
Manage inventory and equipment

2. Event System
Purpose: Decouple components via pub/sub messaging
Event Types:
pythonCOMBAT_START      # Combat begins
COMBAT_END        # Combat concludes
TURN_START        # Creature's turn begins
TURN_END          # Creature's turn ends
ATTACK_ROLL       # Attack attempted
DAMAGE_DEALT      # Damage applied
HEALING_DONE      # HP restored
CHARACTER_DEATH   # Character reaches 0 HP
ROOM_ENTER        # Player enters new room
ITEM_ACQUIRED     # Item added to inventory
LEVEL_UP          # Character gains level
SKILL_CHECK       # Ability/skill check made
Usage Pattern:
python# Component A emits event
event_bus.emit(Event(
    type=EventType.DAMAGE_DEALT,
    data={'attacker': 'Warrior', 'defender': 'Goblin', 'damage': 7}
))

# Component B subscribes
def on_damage(event):
    # React to damage (log, enhance with LLM, update UI)
    pass

event_bus.subscribe(EventType.DAMAGE_DEALT, on_damage)
3. Data-Driven Content System
Purpose: All content in JSON for easy modification/extension
Monster Format (/data/srd/monsters.json):
json{
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
        "reach": 5,
        "damage": "1d6+2",
        "damage_type": "slashing"
      }
    ]
  }
}
Dungeon Format (/data/content/dungeons/goblin_warren.json):
json{
  "name": "Goblin Warren",
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
      "exits": ["entrance", "throne_room"],
      "enemies": ["goblin", "goblin"],
      "items": [{"type": "gold", "amount": 15}],
      "searchable": true
    }
  },
  "start_room": "entrance"
}
4. Combat System
Purpose: Resolve attacks and manage tactical combat
Combat Flow:

Initiative: Roll 1d20 + DEX modifier for all combatants
Turn Loop:

Start of turn effects (ongoing damage, etc)
Creature takes action (attack, spell, dodge, etc)
Resolve action through CombatEngine
Check for reactions (opportunity attacks)
End of turn effects


Action Resolution:

Attack: Roll 1d20 + attack bonus vs target AC
If hit: Roll weapon damage dice + modifiers
Apply damage to target HP
Check for death


Emit Events: Notify subscribers of combat events
Next Turn: Advance initiative tracker

Key Methods:

resolve_attack(attacker, defender, weapon): Returns hit/miss, damage, crit status
apply_damage(creature, amount): Handles temp HP, death
check_death(creature): Determines if creature dies at 0 HP

5. Initiative System
Purpose: Manage turn order in combat
Features:

Roll initiative (1d20 + DEX) for all combatants
Sort by initiative value (ties broken by DEX modifier)
Track current turn
Track round number
Remove defeated creatures
Cycle through turns

6. LLM Enhancement Layer
Purpose: Add narrative flair without affecting game mechanics
Integration Points (via event subscriptions):

Combat Actions: Enhance "hit for 7 damage" with vivid description
Room Descriptions: Turn "torch-lit hall" into atmospheric scene
NPC Dialogue: Generate personality-driven responses
Quest Updates: Add narrative context to story beats

Provider Interface:
pythonclass LLMProvider(ABC):
    @abstractmethod
    async def enhance_description(context: Dict) -> str:
        """Take game event, return enhanced narrative"""
        pass
    
    @abstractmethod
    async def generate_dialogue(npc_context: Dict, player_input: str) -> str:
        """Generate NPC response"""
        pass
Context Format:
python{
    'type': 'combat',           # combat, room, dialogue
    'action': 'attack',
    'attacker': 'Warrior',
    'defender': 'Goblin',
    'result': 'hit',
    'damage': 7,
    'is_crit': False,
    'weapon': 'longsword'
}
Response: "Your blade slashes across the goblin's chest, spraying green blood. It staggers backward with a shriek of pain."
Key Principle: LLM receives game state/results, returns narrative. It never determines mechanical outcomes.
7. Game State Manager
Purpose: Single source of truth for entire game state
State Components:
python{
  'player': Character,              # PC data
  'current_room': Room,             # Current location
  'dungeon': Dict[str, Room],       # All rooms
  'in_combat': bool,                # Combat flag
  'combat_tracker': InitiativeTracker,  # Turn order
  'action_history': List[str],      # Event log
  'quest_state': Dict               # Quest progress
}
```

**Responsibilities**:
- Maintain complete game state
- Handle room transitions
- Start/end combat
- Save/load game (future)
- Provide state snapshots for LLM context

## Core Game Loop

### Exploration Mode
```
1. Display current room state
   - Room name and description (LLM enhanced)
   - Visible exits
   - Visible creatures/objects
   - Player HP/status

2. Get player input
   - Movement commands: "go north", "enter door"
   - Interaction: "talk to bartender", "search room"
   - Combat initiation: "attack goblin"
   - Inventory: "use potion", "equip sword"

3. Validate action
   - Check if action is legal in current state
   - Check player has required items/abilities

4. Execute action via engine
   - Update game state deterministically
   - Roll dice if needed
   - Emit events

5. Trigger consequences
   - Check for combat start
   - Check for quest updates
   - Check for traps/hazards

6. Enhance with LLM
   - Get narrative description of result
   - Generate NPC responses if applicable

7. Display results to player

8. Loop back to step 1
```

### Combat Mode
```
1. Roll initiative for all combatants
   - 1d20 + DEX modifier per creature
   - Sort descending (highest first)
   - Emit COMBAT_START event

2. Begin round loop:
   
   For each creature in initiative order:
   
   a. Emit TURN_START event
   
   b. Check creature status
      - If dead/unconscious: skip turn
      - Apply start-of-turn effects
   
   c. Get action (player or AI)
      - Player: prompt for action (attack, spell, dodge, etc)
      - Monster: AI selects action based on simple rules
   
   d. Validate action
      - Check action is legal
      - Check resources available (spell slots, etc)
   
   e. Resolve action through CombatEngine
      - Roll attack (1d20 + bonus vs AC)
      - Roll damage if hit
      - Apply damage to target
      - Emit ATTACK_ROLL and DAMAGE_DEALT events
   
   f. Check for reactions
      - Opportunity attacks
      - Shield spell
      - Counterspell
   
   g. Enhance with LLM
      - Get vivid combat description
      - Describe battlefield changes
   
   h. Display results to player
   
   i. Check for death
      - Remove dead creatures from initiative
      - Emit CHARACTER_DEATH if applicable
   
   j. Emit TURN_END event
   
   k. Check combat end conditions
      - All enemies defeated/fled → victory
      - Party defeated → game over
      - If combat continues, next turn

3. Combat ends
   - Emit COMBAT_END event
   - Award XP
   - Return to exploration mode
```

### Turn Action Flow
```
Player Input: "attack goblin with sword"
    ↓
Action Resolver: Parse and validate
    ↓
Combat Engine: resolve_attack(player, goblin, sword)
    ↓
Dice Roller: roll(1d20+5) → 18
    ↓
Combat Engine: 18 vs AC 15 → HIT
    ↓
Dice Roller: roll(1d8+3) → 7 damage
    ↓
Combat Engine: goblin.take_damage(7)
    ↓
Event Bus: emit(DAMAGE_DEALT, {...})
    ↓
LLM Enhancer: enhance_description({...})
    ↓
LLM: "Your longsword cleaves deep into the goblin's shoulder..."
    ↓
UI: Display enhanced narrative + game state
    ↓
Combat Engine: Check if goblin dead (HP: 7→0)
    ↓
Initiative Tracker: Remove goblin
    ↓
Combat Engine: Check if combat over
```

## Key Features for MVP

### Must Have (Playable Game)

1. **Single Character Class**: Fighter only
   - HP, AC, attack bonus, damage
   - No subclass complexity
   - Levels 1-3

2. **Basic Combat**:
   - Initiative system
   - Attack rolls (1d20 + mod vs AC)
   - Damage rolls (weapon dice + mod)
   - Critical hits (nat 20 = double dice)
   - HP tracking and death at 0

3. **Simple Dungeon**:
   - 5-7 rooms with connections
   - Room descriptions
   - Loot and enemies per room
   - Linear or simple branching paths

4. **3-4 Enemy Types**:
   - Goblin (melee, low HP)
   - Bandit (melee, medium HP)
   - Wolf (fast, pack tactics - future)
   - Boss variant (higher stats)

5. **Basic Inventory**:
   - Gold tracking
   - Weapon (affects damage)
   - Armor (affects AC)
   - Potions (restore HP)
   - Simple equipment system

6. **LLM Integration**:
   - Room descriptions when entering
   - Combat action descriptions
   - Simple NPC dialogue (1-2 NPCs)
   - Victory/defeat narration

7. **Core Actions**:
   - Move between rooms
   - Attack enemy
   - Search room (find loot)
   - Use item (drink potion)

### Nice to Have (Enhanced Experience)

8. **Advantage/Disadvantage**: Roll 2d20, take best/worst
9. **Conditions**: Prone, stunned (1-2 only)
10. **Short Rest**: Recover some HP between combats
11. **Simple Skill Checks**: Perception to find hidden items
12. **Equipment Comparison**: Show stat changes when equipping
13. **Combat Log**: Scrollable history of actions
14. **Multiple Save Slots**

### Future Enhancements

15. **Additional Classes**: Rogue (sneak attack), Cleric (healing)
16. **Spellcasting System**: Spell slots, spell list, targeting
17. **Character Creation**: Choose class, roll stats, pick equipment
18. **Leveling System**: Gain XP, level up, choose features
19. **Multiple Dungeons**: Campaign with connected adventures
20. **Quest System**: Track objectives, branching outcomes
21. **Merchant NPCs**: Buy/sell items
22. **Party Members**: Control multiple characters
23. **Death Saves**: 5E death mechanics (3 failures = death)
24. **Reactions**: Opportunity attacks, shield spell
25. **Web UI**: Browser-based interface
26. **Persistent Campaigns**: Save/load complex state

## Data Flow Examples

### Example 1: Player Attacks Goblin
```
1. UI receives: "attack goblin"
2. ActionResolver validates: player in combat, goblin is valid target
3. CombatEngine.resolve_attack(player, goblin)
4. DiceRoller.roll("1d20+5") → 18
5. Compare: 18 >= goblin.ac (15) → HIT
6. DiceRoller.roll("1d8+3") → 7
7. goblin.take_damage(7) → goblin.hp: 7→0
8. EventBus.emit(DAMAGE_DEALT, {attacker, defender, damage: 7})
9. LLMEnhancer receives event via subscription
10. LLMEnhancer calls Claude API with context
11. Claude returns: "Your blade bites deep..."
12. UI displays enhanced narrative
13. CombatEngine checks: goblin.is_alive() → False
14. InitiativeTracker.remove_creature(goblin)
15. CombatEngine checks: any_enemies_alive() → False
16. EventBus.emit(COMBAT_END, {victory: true})
17. GameState.end_combat()
18. Return to exploration mode
```

### Example 2: Player Enters Room
```
1. UI receives: "go north"
2. ActionResolver validates: "north" is valid exit
3. GameState.current_room = dungeon["hall"]
4. EventBus.emit(ROOM_ENTER, {room: "hall", ...})
5. Check for enemies in room
6. If enemies: GameState.start_combat(enemies)
7. LLMEnhancer receives ROOM_ENTER event
8. LLMEnhancer calls Claude with room data
9. Claude returns atmospheric description
10. UI displays enhanced room description
11. If combat: Enter combat mode
12. Else: Show available actions
Technical Specifications
Language & Dependencies

Language: Python 3.10+
Core Dependencies:

anthropic: Claude API integration
pydantic: Data validation
pytest: Unit testing


Future Dependencies:

fastapi: Web API (future)
sqlalchemy: Save/load (future)



Performance Considerations

LLM Calls: Async, non-blocking
Caching: Cache room descriptions, monster descriptions
Batch Processing: Queue multiple LLM requests when possible
Graceful Degradation: Game playable without LLM (basic descriptions)

Testing Strategy

Unit Tests: Each component tested independently

Dice rolling probabilities
Combat calculations
Initiative ordering
Damage application


Integration Tests: Component interactions

Full combat encounter
Room navigation
Inventory management


Data Validation: Schema validation for all JSON files
LLM Mocking: Test without API calls using mock responses

Extension Points
Adding New Content

New Monster: Add entry to /data/srd/monsters.json
New Dungeon: Create JSON in /data/content/dungeons/
New Item: Add to /data/srd/items.json
New Class: Add to /data/srd/classes.json (requires code for features)

Adding New Systems

New Rule System: Implement RuleSystem interface (Pathfinder, etc)
New LLM Provider: Implement LLMProvider interface (GPT, local model)
New UI: Implement UI layer consuming game events
New Subsystem: Create in /systems/, hook into event bus

Modding Support

All game data in JSON (user-editable)
Event system allows plugins to hook game events
Clear interfaces for extending core systems
Documentation for data formats

Success Criteria
A successful MVP will:

✅ Allow player to navigate 5+ rooms
✅ Execute tactical combat following 5E rules
✅ Track character state (HP, inventory, location)
✅ Provide engaging LLM-enhanced narrative
✅ Complete a simple dungeon objective (rescue, defeat boss)
✅ Feel like D&D, not just a calculator
✅ Be extensible for future features
✅ Have clean, testable code architecture

Next Steps for Implementation

Week 1: Core engine

Dice roller
Creature/Character classes
Combat engine
Initiative system


Week 2: Game state & data

GameState manager
JSON data loaders
Sample monsters and dungeon


Week 3: LLM integration

Event bus implementation
Claude API integration
Prompt templates


Week 4: UI & polish

CLI interface
Combat loop
Playtesting and balancing




Notes for Claude Code
This architecture prioritizes:

Modularity: Each component is independent
Extensibility: Easy to add content and features
Clarity: Clear separation of concerns
Testability: Components can be tested in isolation

The event bus is key to keeping components decoupled. The game engine emits events, and other systems (LLM, UI, logging) subscribe to react.
Start with the core engine (dice, combat, character) as it has no dependencies. Add the event system next, then build outward.