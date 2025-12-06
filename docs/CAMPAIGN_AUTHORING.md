# Campaign Authoring Guide

This guide explains how to create campaigns for the D&D 5E Terminal Game. A campaign is a self-contained adventure with locations, characters, quests, and a progression system.

---

## Table of Contents

1. [Campaign Structure](#campaign-structure)
2. [Locations (Dungeons)](#locations-dungeons)
3. [Rooms](#rooms)
4. [Room Interactions](#room-interactions)
5. [NPCs](#npcs)
6. [Quests](#quests)
7. [Objectives](#objectives)
8. [Items](#items)
9. [Progression System](#progression-system)
10. [Testing Your Campaign](#testing-your-campaign)

---

## Campaign Structure

A campaign is a folder containing JSON files:

```
dnd_engine/data/content/campaigns/
└── my_campaign/
    ├── campaign.json      # Campaign metadata and dungeon registry
    ├── quests.json        # Quest definitions
    ├── npcs.json          # Non-player characters
    └── dungeons/          # Location files
        ├── town.json
        └── dungeon.json
```

### campaign.json

The campaign manifest defines metadata and registers all locations:

```json
{
  "id": "my_campaign",
  "name": "My Campaign",
  "description": "A brief description of the adventure.",
  "level_range": "1-3",
  "estimated_playtime": "2-3 hours",
  "starting_room": "town.town_square",
  "dungeons": {
    "town": {
      "name": "Town of Example",
      "order": 1,
      "unlocked_by_default": true,
      "unlocks": []
    },
    "dungeon": {
      "name": "The Dark Caves",
      "order": 2,
      "unlocked_by_default": false,
      "unlocks": []
    }
  }
}
```

| Field | Description |
|-------|-------------|
| `id` | Unique identifier (matches folder name) |
| `name` | Display name shown to players |
| `description` | Brief adventure summary |
| `level_range` | Recommended character levels |
| `estimated_playtime` | How long to complete |
| `starting_room` | Where players begin (format: `dungeon_id.room_id`) |
| `dungeons` | Registry of all locations |

---

## Locations (Dungeons)

Despite the name "dungeon," this refers to any location: a town, forest, cave, castle, etc. Each dungeon is a collection of connected rooms.

### Dungeon Registration

In `campaign.json`, each dungeon entry controls availability:

```json
"dungeons": {
  "town": {
    "name": "Town of Millbrook",
    "order": 1,
    "unlocked_by_default": true,
    "completion_criteria": {
      "boss_defeated": false,
      "required_quest_items": []
    },
    "unlocks": ["forest"]
  },
  "forest": {
    "name": "Darkwood Forest",
    "order": 2,
    "unlocked_by_default": false,
    "unlocks": ["cave"]
  },
  "cave": {
    "name": "Goblin Cave",
    "order": 3,
    "unlocked_by_default": false,
    "final_dungeon": true
  }
}
```

| Field | Description |
|-------|-------------|
| `order` | Display order in location list |
| `unlocked_by_default` | Available at game start? |
| `completion_criteria` | What marks this dungeon "complete" |
| `unlocks` | Dungeons that unlock when this one completes |
| `final_dungeon` | Is this the campaign finale? |

### Dungeon File

Each dungeon has its own JSON file in the `dungeons/` folder:

```json
{
  "id": "town",
  "name": "Town of Millbrook",
  "campaign_id": "my_campaign",
  "description": "A peaceful farming town.",
  "start_room": "town.town_square",
  "level_range": "1-3",
  "focus": "exploration, roleplay",
  "rooms": {
    "town.town_square": { ... },
    "town.inn": { ... }
  }
}
```

---

## Rooms

Rooms are the atomic unit of exploration. Players move between rooms and interact with their contents.

### Room Definition

```json
"town.town_square": {
  "id": "town.town_square",
  "name": "Town Square",
  "description": "A bustling square with a central fountain...",
  "location_type": "settlement",
  "parent": "town",
  "safe_zone": true,
  "lighting": "bright",
  "exits": {
    "north": "town.inn",
    "east": "town.shop",
    "south": {
      "destination": "forest.entrance",
      "label": "Road to Darkwood Forest"
    }
  },
  "enemies": [],
  "items": [],
  "searchable": true,
  "searched": false
}
```

| Field | Description |
|-------|-------------|
| `id` | Unique room ID (format: `dungeon.room_name`) |
| `name` | Display name |
| `description` | Narrative description shown to players |
| `location_type` | `settlement`, `dungeon`, `wilderness` |
| `safe_zone` | If true, no random encounters |
| `lighting` | `bright`, `dim`, or `dark` |
| `exits` | Connections to other rooms |
| `enemies` | Monster IDs to spawn here |
| `items` | Item IDs available in this room |
| `searchable` | Can players search this room? |

### Exit Types

**Simple exit** - just a room ID:
```json
"exits": {
  "north": "town.inn"
}
```

**Labeled exit** - custom description:
```json
"exits": {
  "south": {
    "destination": "forest.entrance",
    "label": "Road to Darkwood Forest"
  }
}
```

**Conditional exit** - requires something to use:
```json
"exits": {
  "down": {
    "destination": "secret.chamber",
    "label": "Trapdoor",
    "requires": {
      "quest_item": "ancient_key"
    },
    "hidden_until_unlocked": true
  }
}
```

### Hidden Rooms

Rooms can be hidden until revealed:

```json
"secret.treasure_room": {
  "id": "secret.treasure_room",
  "name": "Hidden Treasury",
  "hidden": true,
  "reveals_when": "found_secret_lever"
}
```

The room won't appear in exits until the trigger fires (see [Progression System](#progression-system)).

---

## Room Interactions

Room interactions allow players to interact with objects in the environment using their abilities, spells, or items. Interactions can require specific **capabilities** that the party must have active.

### Basic Interaction

```json
"interactions": [
  {
    "id": "open_chest",
    "name": "Open the chest",
    "description": "An unlocked wooden chest sits in the corner.",
    "action": {
      "type": "message",
      "text": "You open the chest and find treasure inside!"
    },
    "rewards": [
      {"type": "item", "id": "potion_of_healing"},
      {"type": "currency", "gold": 25}
    ],
    "one_time": true
  }
]
```

| Field | Description |
|-------|-------------|
| `id` | Unique identifier for this interaction |
| `name` | Display name shown in the interact menu |
| `description` | Flavor text describing what the player sees |
| `action` | What happens when the interaction executes |
| `rewards` | Items or currency granted on success |
| `one_time` | If true, interaction disappears after use |

### Capability-Gated Interactions

Interactions can require the party to have specific capabilities. Capabilities come from:
- **Active spells**: Light grants `light_source`, Mage Hand grants `reach_30ft`
- **Items**: Torches and lanterns grant `light_source`
- **Racial traits**: Elves, dwarves, and other races with darkvision grant `darkvision`

```json
"interactions": [
  {
    "id": "pull_lever",
    "name": "Pull the brass lever",
    "description": "A brass lever on the far wall, across a bubbling acid vat. Too dangerous to reach by hand.",
    "requires_any": ["reach_30ft", "reach_60ft"],
    "action": {
      "type": "message",
      "text": "The spectral hand reaches across the acid vat and pulls the lever. A hidden panel slides open!"
    },
    "rewards": [
      {"type": "item", "id": "potion_of_greater_healing"},
      {"type": "currency", "gold": 15}
    ],
    "one_time": true
  }
]
```

| Field | Description |
|-------|-------------|
| `requires_any` | Party needs at least ONE of these capabilities |
| `requires_all` | Party needs ALL of these capabilities |

### Available Capabilities

| Capability | Granted By | Use Case |
|------------|------------|----------|
| `light_source` | Light spell, torches, lanterns | Reading in dark rooms |
| `darkvision` | Elf, dwarf, half-orc, tiefling, gnome racial traits | Reading in dark rooms |
| `reach_30ft` | Mage Hand spell | Interacting with distant objects |
| `reach_60ft` | Telekinesis spell | Interacting with very distant objects |
| `sense_magic` | Detect Magic spell | Revealing magical items/auras |
| `see_invisible` | See Invisibility spell | Detecting invisible creatures |

### Example: Dark Room with Inscription

This interaction requires either a light source OR darkvision to read text in a dark room:

```json
{
  "id": "read_inscription",
  "name": "Read the wall inscription",
  "description": "Faded writing covers the frost-covered wall. It's too dark to make out the words.",
  "requires_any": ["light_source", "darkvision"],
  "action": {
    "type": "message",
    "text": "With proper illumination, you can read the inscription: 'Specimen 47 - DO NOT THAW. Weakness: fire.'"
  },
  "grants_knowledge": {
    "monster_weakness": {
      "target": "preserved_specimen",
      "weakness": "fire",
      "bonus": "advantage_on_attacks"
    }
  },
  "one_time": true
}
```

Players can:
1. Cast Light spell to gain `light_source` capability
2. Carry a torch (which grants `light_source`)
3. Be an elf or other race with darkvision

### Example: Lever Across a Pit

This interaction requires ranged manipulation to pull a lever that's too far to reach:

```json
{
  "id": "pull_lever",
  "name": "Pull the brass lever",
  "description": "A brass lever on the far wall, across the bubbling acid vat.",
  "requires_any": ["reach_30ft", "reach_60ft"],
  "action": {
    "type": "message",
    "text": "The spectral hand reaches across the acid vat and pulls the lever!"
  },
  "rewards": [
    {"type": "item", "id": "potion_of_greater_healing"}
  ],
  "one_time": true
}
```

Players must:
1. Cast Mage Hand (grants `reach_30ft` for 1 minute)
2. Cast Telekinesis (grants `reach_60ft`)

### How Players Use Interactions

Players use the `interact` command (or `int` for short):

```
> interact
Available interactions:
  1. Pull the brass lever (requires: reach_30ft or reach_60ft)
     A brass lever on the far wall, across the bubbling acid vat.
     [NOT AVAILABLE - need Mage Hand or similar]

  2. Open the chest
     An unlocked wooden chest.
     [AVAILABLE]

> cast mage hand

> interact
Available interactions:
  1. Pull the brass lever
     [AVAILABLE]

> interact 1
The spectral hand reaches across the acid vat and pulls the lever!
You received: Potion of Greater Healing
```

### Interaction Rewards

Rewards can include items, currency, or special knowledge:

```json
"rewards": [
  {"type": "item", "id": "potion_of_healing"},
  {"type": "item", "id": "longsword"},
  {"type": "currency", "gold": 50, "silver": 25}
]
```

### Design Tips

1. **Make requirements thematic**: A lever across a pit should require `reach_30ft`, not just any capability
2. **Provide alternatives**: Use `requires_any` to allow multiple solutions (light OR darkvision)
3. **Consider party composition**: Elves have darkvision naturally, so don't make every dark room require spells
4. **Use one_time wisely**: Most treasure-granting interactions should be one-time
5. **Write descriptive text**: The description should hint at what capability is needed

---

## NPCs

Non-player characters populate your world. They can give quests, sell items, provide hints, and accept quest deliveries.

### NPC Definition

```json
{
  "campaign_id": "my_campaign",
  "npcs": {
    "blacksmith_tom": {
      "id": "blacksmith_tom",
      "name": "Tom",
      "display_name": "Tom, the Blacksmith",
      "home_location": "town.smithy",
      "current_location": "town.smithy",
      "can_move": false,
      "personality": {
        "traits": ["gruff", "honest", "hardworking"],
        "speech_style": "short sentences, working-class accent",
        "attitude_default": "neutral"
      },
      "knowledge": {
        "general": [
          "Has run the smithy for 20 years",
          "Knows about the goblin raids"
        ],
        "quest_hooks": ["clear_the_goblins"],
        "local_lore": [
          "The goblins came from the old mine",
          "They're led by a bugbear named Grak"
        ]
      },
      "shop": {
        "enabled": true,
        "shop_type": "blacksmith",
        "inventory": [
          {"item_id": "longsword", "price": 15, "stock": 2},
          {"item_id": "chain_mail", "price": 75, "stock": 1}
        ],
        "buy_rate": 0.5
      },
      "dialogue": {
        "greeting": "What do you need?",
        "farewell": "Good luck out there."
      }
    }
  }
}
```

### NPC Roles

| Role | How to Configure |
|------|------------------|
| **Quest Giver** | Set as `quest_giver` in quest definition |
| **Quest Turn-in** | Set as `turn_in_npc` in quest definition |
| **Merchant** | Enable `shop` with inventory |
| **Information Source** | Add to `knowledge.quest_hooks` |
| **Delivery Target** | Use DELIVER objective targeting this NPC |

### NPC Schedules

NPCs can move between locations:

```json
"schedule": {
  "morning": "town.smithy",
  "afternoon": "town.market",
  "evening": "town.inn",
  "night": "town.smithy"
}
```

---

## Quests

Quests are the goals players work toward. Each quest has objectives to complete and rewards to claim.

### Quest Definition

```json
{
  "campaign_id": "my_campaign",
  "quests": [
    {
      "id": "clear_the_goblins",
      "name": "Goblin Menace",
      "description": "Goblins have been raiding farms. Find their lair and eliminate the threat.",
      "objectives": [
        {
          "id": "find_lair",
          "type": "discover",
          "target": "cave.goblin_den",
          "description": "Find the goblin lair"
        },
        {
          "id": "kill_chief",
          "type": "kill",
          "target": "goblin_chief",
          "description": "Defeat the goblin chief"
        }
      ],
      "unlocked_by_default": true,
      "quest_giver": "blacksmith_tom",
      "turn_in_npc": "blacksmith_tom",
      "reward_gold": 50,
      "unlocks_quests": ["investigate_mine"],
      "unlocks_dungeons": ["abandoned_mine"],
      "npc_hints": {
        "available": "Those goblins are getting bolder. Someone should do something.",
        "active": "Any luck with those goblins?",
        "completed": "You did it! The town owes you."
      }
    }
  ]
}
```

### Quest Fields

| Field | Description |
|-------|-------------|
| `id` | Unique quest identifier |
| `name` | Display name |
| `description` | Quest log description |
| `objectives` | List of tasks to complete |
| `unlocked_by_default` | Available at game start? |
| `quest_giver` | NPC ID who offers this quest |
| `turn_in_npc` | NPC ID who gives rewards |
| `reward_gold` | Gold reward amount |
| `unlocks_quests` | Quests that become available on completion |
| `unlocks_dungeons` | Locations that unlock on completion |
| `final_quest` | Is this the campaign finale? |
| `npc_hints` | What NPCs say about this quest |

### Quest States

Quests progress through these states:

```
LOCKED → AVAILABLE → ACTIVE → COMPLETED → REWARDED
```

| State | Meaning |
|-------|---------|
| `LOCKED` | Prerequisites not met |
| `AVAILABLE` | Can be accepted from quest giver |
| `ACTIVE` | Player is working on it |
| `COMPLETED` | All objectives done, reward not claimed |
| `REWARDED` | Gold claimed from turn-in NPC |

---

## Objectives

Objectives are the individual tasks within a quest. Each objective has a type that determines how it completes.

### Objective Types

| Type | Completes When | Example |
|------|----------------|---------|
| `kill` | Target enemy dies | Defeat the dragon |
| `fetch` | Item enters inventory | Find the ancient sword |
| `use` | Item is used/read | Read the mysterious scroll |
| `deliver` | Item given to NPC | Bring the letter to the mayor |
| `discover` | Room is entered | Find the hidden shrine |
| `clear` | All enemies in area killed | Clear the bandit camp |

### Objective Definition

```json
{
  "id": "defeat_boss",
  "type": "kill",
  "target": "goblin_chief",
  "description": "Defeat the goblin chief",
  "optional": false
}
```

| Field | Description |
|-------|-------------|
| `id` | Unique within this quest |
| `type` | One of the objective types above |
| `target` | What to kill/fetch/use/discover (ID) |
| `description` | Shown in quest log |
| `optional` | If true, not required for quest completion |

### Objective Triggers (Progression)

Objectives can trigger events when completed. See [Progression System](#progression-system) for details.

```json
{
  "id": "read_map",
  "type": "use",
  "target": "treasure_map",
  "description": "Study the treasure map",
  "triggers": "treasure_location_revealed"
}
```

---

## Items

Items are defined in `data/srd/items.json` for standard equipment, or can be defined as quest items within your campaign.

### Quest Items

Quest items are special items tied to quest objectives:

```json
{
  "id": "ancient_map",
  "name": "Ancient Map",
  "description": "A faded map showing a path through the mountains.",
  "item_type": "quest_item",
  "quest_item": true,
  "value": 0,
  "weight": 0
}
```

Quest items:
- Display with a special marker (★) in inventory
- Cannot be sold
- Are tracked by the quest system
- **Cannot be given away** (see below)

### Quest Item Transfer Protection

The `quest_item: true` flag protects items from being accidentally given to NPCs during conversation. This prevents players from losing critical items needed for quest progression.

| `quest_item` flag | Quest objective | Can give to NPC? |
|-------------------|-----------------|------------------|
| `false` | (any) | ✅ Yes - regular item |
| `true` | DELIVER to *this* NPC | ✅ Yes - intended recipient |
| `true` | Bonus reward for *this* NPC | ✅ Yes - intended recipient |
| `true` | No matching objective | ❌ No - protected |

**The `quest_item` flag is the lock. DELIVER objectives and bonus rewards are the keys that only work for the intended NPC.**

#### Example: Deliverable Quest Item

```json
// Item definition
{
  "id": "skull_of_dragon",
  "name": "Skull of the Dragon",
  "quest_item": true
}

// Quest objective
{
  "id": "return_skull",
  "type": "deliver",
  "target": "father_aldric",
  "deliver_item": "skull_of_dragon",
  "description": "Return the skull to Father Aldric"
}
```

Result:
- Give to Father Aldric → ✅ allowed (DELIVER objective matches)
- Give to random innkeeper → ❌ blocked (no matching objective)

#### Example: Non-Deliverable Quest Item

```json
// Item definition
{
  "id": "ancient_journal",
  "name": "Ancient Journal",
  "quest_item": true
}

// Quest objective - USE, not DELIVER
{
  "id": "read_journal",
  "type": "use",
  "target": "ancient_journal",
  "description": "Read the ancient journal"
}
```

Result:
- Give to any NPC → ❌ blocked (USE objective, not DELIVER)
- Player must read/use the item themselves

#### When to Use Each Pattern

| Scenario | Pattern |
|----------|---------|
| Player must read/examine an item | `type: use` + `quest_item: true` |
| Player must bring item to specific NPC | `type: deliver` + `quest_item: true` |
| Optional bonus for returning item | `bonus_rewards` + `quest_item: true` |
| Player can give item to anyone | `quest_item: false` (or omit flag) |

### Item Placement

Place items in rooms:

```json
"rooms": {
  "cave.treasure_room": {
    "items": ["ancient_map", "gold_coins"],
    "searchable": true
  }
}
```

Or have NPCs give them as rewards:

```json
"bonus_rewards": [
  {
    "condition": "return_item",
    "item_id": "family_heirloom",
    "turn_in_npc": "lord_nobles",
    "reward_item": "magic_ring",
    "description": "Return the heirloom to Lord Nobles"
  }
]
```

---

## Progression System

The progression system controls how the campaign unfolds. There are two mechanisms: **quest-based unlocks** and **trigger-based unlocks**.

### Quest-Based Unlocks

The simplest approach: completing a quest unlocks the next content.

```json
{
  "id": "investigate_crypt",
  "unlocks_quests": ["cult_conspiracy"],
  "unlocks_dungeons": ["cult_hideout"]
}
```

When `investigate_crypt` completes:
- `cult_conspiracy` quest becomes AVAILABLE
- `cult_hideout` dungeon becomes accessible

### Trigger-Based Unlocks

For finer control, objectives can emit triggers that other content listens for.

**Step 1: Objective emits a trigger**

```json
{
  "id": "read_journal",
  "type": "use",
  "target": "cultist_journal",
  "description": "Read the cultist's journal",
  "triggers": "cult_location_revealed"
}
```

**Step 2: Content reacts to the trigger**

```json
// In dungeon definition
{
  "id": "cult_hideout",
  "unlocked_by_default": false,
  "unlocks_when": "cult_location_revealed"
}

// In room definition
{
  "id": "secret_passage",
  "hidden": true,
  "reveals_when": "cult_location_revealed"
}

// In quest definition
{
  "id": "cult_conspiracy",
  "unlocked_by_default": false,
  "available_when": "cult_location_revealed"
}
```

### When to Use Each Approach

| Scenario | Approach |
|----------|----------|
| Linear quest chain | Quest-based (`unlocks_quests`) |
| Dungeon unlocks after quest | Quest-based (`unlocks_dungeons`) |
| Reading item reveals location | Trigger-based |
| Killing boss opens secret door | Trigger-based |
| Finding evidence unlocks new quest mid-dungeon | Trigger-based |
| Multiple things react to one action | Trigger-based |

### Trigger Naming Conventions

Use descriptive, campaign-prefixed trigger names:

```
my_campaign.map_read
my_campaign.boss_defeated
my_campaign.secret_found
```

This prevents conflicts if triggers are shared across campaigns.

### What Can Emit Triggers

| Source | Example |
|--------|---------|
| Objectives | `"triggers": "evidence_found"` |
| Room entry | (future: `"on_enter_triggers": "shrine_discovered"`) |
| Item use | (future: direct item trigger support) |

### What Can React to Triggers

| Target | Field | Effect |
|--------|-------|--------|
| Dungeons | `unlocks_when` | Becomes accessible |
| Rooms | `reveals_when` | Hidden room becomes visible |
| Quests | `available_when` | Quest becomes AVAILABLE |
| Exits | `opens_when` | Locked exit becomes usable |

---

## Testing Your Campaign

### Manual Testing Checklist

1. **Starting state**
   - [ ] Starting room loads correctly
   - [ ] Initial quests are available
   - [ ] Starting NPCs are present

2. **Quest flow**
   - [ ] Quest giver offers quest
   - [ ] Objectives track correctly
   - [ ] Quest completes when objectives done
   - [ ] Turn-in NPC gives rewards
   - [ ] Next quests unlock properly

3. **Progression**
   - [ ] Locked dungeons stay locked
   - [ ] Triggers fire when expected
   - [ ] Hidden content reveals correctly

4. **NPCs**
   - [ ] NPCs appear in correct locations
   - [ ] Shops work correctly
   - [ ] Dialogue makes sense for quest state

### Common Issues

| Problem | Likely Cause |
|---------|--------------|
| Quest won't activate | `quest_giver` NPC not in a room |
| Dungeon won't unlock | `unlocks_dungeons` typo or wrong quest |
| Objective won't complete | `target` doesn't match item/enemy/room ID |
| Hidden room never appears | `reveals_when` trigger never fires |
| NPC not found | `current_location` doesn't match room ID |

### Validation Tips

- Room IDs must be `dungeon_id.room_name` format
- All referenced IDs (NPCs, items, rooms) must exist
- Quest `target_dungeon` should match where objectives are
- Exit destinations must be valid room IDs

---

## Example: Minimal Campaign

Here's a complete minimal campaign with one town, one dungeon, and one quest:

### campaign.json
```json
{
  "id": "example",
  "name": "Example Campaign",
  "description": "A simple example campaign.",
  "level_range": "1",
  "estimated_playtime": "30 minutes",
  "starting_room": "village.square",
  "dungeons": {
    "village": {
      "name": "Village",
      "order": 1,
      "unlocked_by_default": true,
      "unlocks": []
    },
    "cave": {
      "name": "Goblin Cave",
      "order": 2,
      "unlocked_by_default": true,
      "unlocks": []
    }
  }
}
```

### quests.json
```json
{
  "campaign_id": "example",
  "quests": [
    {
      "id": "kill_goblins",
      "name": "Goblin Problem",
      "description": "Clear out the goblins in the cave.",
      "objectives": [
        {
          "id": "kill_chief",
          "type": "kill",
          "target": "goblin",
          "description": "Defeat the goblins"
        }
      ],
      "unlocked_by_default": true,
      "quest_giver": "elder",
      "turn_in_npc": "elder",
      "reward_gold": 25,
      "final_quest": true
    }
  ]
}
```

### npcs.json
```json
{
  "campaign_id": "example",
  "npcs": {
    "elder": {
      "id": "elder",
      "name": "Village Elder",
      "display_name": "The Village Elder",
      "home_location": "village.square",
      "current_location": "village.square",
      "can_move": false,
      "personality": {
        "traits": ["wise", "worried"],
        "speech_style": "formal, elderly"
      },
      "knowledge": {
        "general": ["Goblins have been attacking travelers"],
        "quest_hooks": ["kill_goblins"]
      },
      "shop": {"enabled": false},
      "dialogue": {
        "greeting": "Greetings, traveler. Our village has a problem...",
        "farewell": "Safe travels."
      }
    }
  }
}
```

### dungeons/village.json
```json
{
  "id": "village",
  "name": "Village",
  "campaign_id": "example",
  "start_room": "village.square",
  "rooms": {
    "village.square": {
      "id": "village.square",
      "name": "Village Square",
      "description": "A simple village square. The elder stands near the well.",
      "location_type": "settlement",
      "safe_zone": true,
      "lighting": "bright",
      "exits": {
        "east": {
          "destination": "cave.entrance",
          "label": "Path to Goblin Cave"
        }
      },
      "enemies": [],
      "items": []
    }
  }
}
```

### dungeons/cave.json
```json
{
  "id": "cave",
  "name": "Goblin Cave",
  "campaign_id": "example",
  "start_room": "cave.entrance",
  "rooms": {
    "cave.entrance": {
      "id": "cave.entrance",
      "name": "Cave Entrance",
      "description": "A dark cave mouth. You hear goblin chatter within.",
      "location_type": "dungeon",
      "safe_zone": false,
      "lighting": "dim",
      "exits": {
        "west": {
          "destination": "village.square",
          "label": "Back to Village"
        }
      },
      "enemies": ["goblin", "goblin"],
      "items": []
    }
  }
}
```

---

## Reference

### File Locations

| Content Type | Location |
|--------------|----------|
| Campaigns | `dnd_engine/data/content/campaigns/` |
| Standard items | `dnd_engine/data/srd/items.json` |
| Monsters | `dnd_engine/data/srd/monsters.json` |
| Classes | `dnd_engine/data/srd/classes.json` |

### ID Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Campaign | `snake_case` | `the_unquiet_dead` |
| Dungeon | `snake_case` | `cult_hideout` |
| Room | `dungeon.room_name` | `arden.town_square` |
| Quest | `snake_case` | `investigate_crypt` |
| NPC | `snake_case` | `father_aldric` |
| Item | `snake_case` | `potion_of_healing` |
| Trigger | `campaign.event_name` | `unquiet_dead.journal_read` |

### Quest Objective Quick Reference

| Type | Target Is | Completes On |
|------|-----------|--------------|
| `kill` | Monster ID | Enemy death |
| `fetch` | Item ID | Item acquired |
| `use` | Item ID | Item used |
| `deliver` | Item ID | Item given to `turn_in_npc` |
| `discover` | Room ID | Room entered |
| `clear` | Room ID | All enemies dead |
