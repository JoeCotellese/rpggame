# World System Implementation Roadmap

## Overview

Incremental build-out from single dungeon to full open world. Each phase ends with a **playable game** - just with more features unlocked.

```
Phase 1: Room GUIDs + Campaign Progression     ← Issue #102
Phase 2: Town Hub
Phase 3: Multi-Region World
Phase 4: Living NPCs
Phase 5: Factions & Reputation
Phase 6: Advanced Quests
Phase 7: Multi-Campaign Arcs
```

---

## Current State

- Single dungeon works (The Unquiet Dead: Crypt)
- Rooms exist but no GUID system
- No campaign progression
- No towns/settlements
- NPCs are encounter-based only

---

## Phase 1: Room GUIDs + Campaign Progression

**Goal:** Multiple dungeons in a campaign, unlocking sequentially via quest items.

**Playable Outcome:** Complete "The Unquiet Dead" as a 3-dungeon campaign with progression.

### Deliverables

| Item | Description |
|------|-------------|
| Room GUID schema | Every room has a unique ID (e.g., `crypt.entrance`) |
| Room registry | Central lookup for all rooms |
| Conditional exits | Exits with `requires` conditions |
| Campaign definition | JSON defining dungeon sequence and unlock criteria |
| Quest items | Items marked as `quest_item: true`, not sellable/droppable |
| Campaign progress in save | Track completed dungeons, unlocked dungeons, quest items |
| Dungeon completion detection | Boss defeated + quest items = complete |
| Adventure selection UI | Show locked/unlocked/completed states |

### Schema Preview

```json
{
  "id": "crypt.entrance",
  "name": "Crypt Entrance",
  "location_type": "dungeon",
  "parent": "the_unquiet_dead_crypt",
  "description": "Stone steps descend into darkness...",
  "exits": {
    "north": "crypt.hallway_1",
    "south": {
      "destination": "world.graveyard",
      "label": "Exit to Graveyard"
    }
  }
}
```

### Save Structure

```json
{
  "room_id": "crypt.entrance",
  "campaign": {
    "id": "the_unquiet_dead",
    "completed_dungeons": ["the_unquiet_dead_crypt"],
    "unlocked_dungeons": ["the_unquiet_dead_crypt", "cult_hideout"],
    "quest_items": ["gorgus_journal"]
  }
}
```

### Related Issue
- #102 (Quest item system and campaign progression)

---

## Phase 2: Town Hub

**Goal:** A settlement players return to between dungeons.

**Playable Outcome:** Visit Millbrook between dungeons. Shop, rest, talk to quest-givers.

### Deliverables

| Item | Description |
|------|-------------|
| Settlement as mini-dungeon | Town is rooms with `location_type: "settlement"` |
| Inn room | Rest to restore HP/spells, advances time |
| Shop room | Buy/sell items with static inventory |
| Quest-giver NPC | Static NPC that gives campaign context |
| Town ↔ Dungeon connections | Exits link town to dungeon entrances |
| Safe zone flag | `safe_zone: true` - no random encounters |

### Schema Preview

```json
{
  "id": "millbrook.town_square",
  "name": "Millbrook Town Square",
  "location_type": "settlement",
  "safe_zone": true,
  "exits": {
    "north": "millbrook.golden_goose_inn.common_room",
    "east": "millbrook.general_store",
    "south_gate": {
      "destination": "graveyard.entrance",
      "label": "Road to Graveyard"
    }
  },
  "npcs": ["millbrook.mayor_harwick"]
}
```

### New Mechanics

- **Resting:** Restore party, advance time period
- **Shopping:** Static shop inventories, gold economy
- **Time periods:**

| Period | Hours | World State |
|--------|-------|-------------|
| Dawn | 5am-8am | Shops opening, NPCs waking |
| Morning | 8am-12pm | Full activity |
| Midday | 12pm-2pm | Peak activity |
| Afternoon | 2pm-6pm | Full activity |
| Evening | 6pm-10pm | Taverns busy, shops closing |
| Night | 10pm-5am | Most asleep, guards patrol |

---

## Phase 3: Multi-Region World

**Goal:** Multiple settlements and dungeons across a larger world.

**Playable Outcome:** Travel between Millbrook and other towns. Discover new locations.

### Deliverables

| Item | Description |
|------|-------------|
| Region system | Regions contain settlements and dungeons |
| World map | Text-based map showing regions and connections |
| Fast travel | Travel to discovered locations, costs time |
| Location discovery | Track `discovered_locations` in save |
| Travel encounters | Random encounters during travel between locations |
| Region-based content loading | Lazy load regions on entry |

### World Structure

```
World: Faerun
├── Region: Western Reach
│   ├── Settlement: Millbrook
│   │   ├── Town Square
│   │   ├── Golden Goose Inn
│   │   └── General Store
│   ├── Dungeon: Davos Family Crypt
│   └── Dungeon: Abandoned Mill
├── Region: Eastern Valley
│   ├── Settlement: Eastgate
│   └── Dungeon: Temple of Durgon
```

### Travel System

```python
def travel_to(destination_id):
    distance = calculate_distance(current_region, destination_region)

    # Time cost
    advance_time(periods=distance)

    # Random encounter chance per distance unit
    for _ in range(distance):
        if random() < ENCOUNTER_CHANCE:
            return trigger_travel_encounter()

    # Arrive at destination
    enter_room(destination_id)
```

---

## Phase 4: Living NPCs

**Goal:** NPCs as independent entities with schedules and persistent state.

**Playable Outcome:** NPCs move between locations. Killing an NPC is permanent.

### Deliverables

| Item | Description |
|------|-------------|
| NPC GUID system | NPCs have unique IDs separate from rooms |
| NPC registry | Central lookup, computed location |
| Basic schedules | Day/night location changes |
| NPC state persistence | Alive/dead, relationship flags |
| Dynamic room population | NPCs computed on room enter |
| Essential NPCs | Some NPCs cannot be killed |
| NPC dialogue state | Track what's been said |

### Schema Preview

```json
{
  "id": "millbrook.innkeeper_greta",
  "name": "Greta",
  "title": "Innkeeper",
  "essential": false,
  "schedule": {
    "day": "millbrook.golden_goose_inn.common_room",
    "night": "millbrook.golden_goose_inn.upstairs"
  },
  "dialogue_tree": "greta_dialogue",
  "shop_inventory": "inn_services"
}
```

### NPC State in Save

```json
{
  "npc_state": {
    "millbrook.innkeeper_greta": {
      "alive": true,
      "disposition": 50,
      "dialogue_flags": ["introduced", "mentioned_cult"]
    },
    "millbrook.blacksmith_tom": {
      "alive": false,
      "death_cause": "player",
      "death_day": 15
    }
  }
}
```

---

## Phase 5: Factions & Reputation

**Goal:** Player reputation affects world interactions.

**Playable Outcome:** Join the Militia. Become a criminal. Factions react to your choices.

### Deliverables

| Item | Description |
|------|-------------|
| Faction definitions | Factions with ranks and relationships |
| Player reputation per faction | -100 to +100 scale |
| Faction ranks | Unlock through quests/reputation |
| Faction-gated content | Doors, dialogue, quests require faction standing |
| Crime system | Stealing/assault generates bounty |
| Regional bounties | Guards react per-region |
| Faction relationships | Allied/neutral/hostile between factions |

### Schema Preview

```json
{
  "id": "millbrook_militia",
  "name": "Millbrook Militia",
  "ranks": [
    {"id": "recruit", "reputation_required": 0},
    {"id": "soldier", "reputation_required": 25},
    {"id": "captain", "reputation_required": 75}
  ],
  "hostile_factions": ["cult_of_durgon"],
  "allied_factions": ["merchant_guild"]
}
```

### Conditional Content

```json
{
  "id": "millbrook.barracks.armory",
  "exits": {
    "door": {
      "destination": "millbrook.barracks.main",
      "requires": {"faction.millbrook_militia.rank": "soldier"}
    }
  }
}
```

---

## Phase 6: Advanced Quests

**Goal:** Dynamic and branching quest content.

**Playable Outcome:** Radiant quests. Choices that matter. Quest chains.

### Deliverables

| Item | Description |
|------|-------------|
| Quest templates | Parameterized quests filled at runtime |
| Radiant quest generation | "Kill bandit leader at [random dungeon]" |
| Quest chains | Multi-part quests with dependencies |
| Branching outcomes | Player choices affect quest resolution |
| Quest log | Track active, completed, failed quests |
| World state from quests | Quests can modify world permanently |

### Quest Template

```json
{
  "template_id": "bounty_hunt",
  "name": "Bounty: {target_name}",
  "description": "Eliminate {target_name} at {location_name}.",
  "parameters": {
    "target_type": "bandit_leader",
    "location_type": "bandit_dungeon"
  },
  "objectives": [
    {"type": "kill", "target": "{target_id}"}
  ],
  "rewards": {
    "gold": "{player_level} * 50",
    "reputation": {"faction": "millbrook_militia", "amount": 10}
  }
}
```

### Branching Example

```json
{
  "quest_id": "the_informant",
  "decision_point": "informant_fate",
  "options": [
    {
      "choice": "turn_in",
      "outcome": "informant_arrested",
      "reputation": {"militia": 20, "thieves_guild": -30}
    },
    {
      "choice": "let_go",
      "outcome": "informant_escapes",
      "reputation": {"militia": -10, "thieves_guild": 20}
    },
    {
      "choice": "kill",
      "outcome": "informant_dead",
      "reputation": {"militia": 5, "thieves_guild": -50}
    }
  ]
}
```

---

## Phase 7: Multi-Campaign Arcs

**Goal:** Connected campaigns forming an epic story.

**Playable Outcome:** Finish "The Unquiet Dead," start "Rise of the Demon Lord" with consequences carried forward.

### Deliverables

| Item | Description |
|------|-------------|
| Campaign namespacing | Rooms prefixed by campaign or shared |
| Cross-campaign state | World state persists across campaigns |
| Campaign-aware content | NPCs reference past campaign events |
| Party persistence | Same party can play multiple campaigns |
| World evolution | Locations change based on prior campaigns |
| Story arc definition | Meta-structure linking campaigns |

### Story Arc Definition

```json
{
  "arc_id": "the_demon_wars",
  "name": "The Demon Wars",
  "campaigns": [
    {
      "id": "the_unquiet_dead",
      "order": 1,
      "level_range": "1-3",
      "required": true
    },
    {
      "id": "rise_of_demon_lord",
      "order": 2,
      "level_range": "4-7",
      "requires_completion": "the_unquiet_dead"
    },
    {
      "id": "the_final_seal",
      "order": 3,
      "level_range": "8-10",
      "requires_completion": "rise_of_demon_lord"
    }
  ]
}
```

### World Evolution

```json
{
  "id": "millbrook.town_square",
  "description_default": "A quiet market town...",
  "description_overrides": {
    "campaign:rise_of_demon_lord": {
      "condition": {"completed": "the_unquiet_dead"},
      "description": "The town bears scars from the cult attack. Rebuilding is underway..."
    }
  }
}
```

---

## Implementation Timeline Suggestion

| Phase | Estimated Scope | Dependencies |
|-------|-----------------|--------------|
| Phase 1 | Core foundation | None - start here |
| Phase 2 | Medium | Phase 1 |
| Phase 3 | Medium-Large | Phase 2 |
| Phase 4 | Large | Phase 2 |
| Phase 5 | Medium | Phase 4 |
| Phase 6 | Large | Phase 4, 5 |
| Phase 7 | Medium | Phase 6 |

**Note:** Phases 4-5 can potentially be developed in parallel with Phase 3.

---

## Key Architectural Decisions

1. **Everything gets a GUID** - Rooms, NPCs, containers, quests, factions
2. **Hierarchy is metadata, not navigation** - You navigate by GUID connections
3. **Sparse state storage** - Only save deltas from defaults
4. **Lazy evaluation** - Compute world state on-demand, not continuously
5. **Turn-based simplifies simulation** - No real-time NPC movement or interrupts
6. **Data-driven everything** - JSON definitions, not hardcoded logic
7. **Conditions are expressions** - Reusable `requires` syntax everywhere
8. **Death is permanent** - No resurrection, high stakes combat
9. **TPK = Game Over** - Total party kill ends the run, reload or restart
10. **Partial death = Recruit** - New party members join at (party avg level - 1)

---

## Decisions Made

| Decision | Choice | Notes |
|----------|--------|-------|
| GUID format | Human-readable IDs | e.g., `crypt.entrance`, `millbrook.inn.common_room` |
| Time granularity | 6 periods | Dawn, Morning, Midday, Afternoon, Evening, Night |
| Party death (TPK) | Game over | Reload save or start fresh |
| Party death (partial) | Recruit replacements | New recruits at party average level - 1 |
| Resurrection | None | Death is permanent, keeps stakes high |

## Open Questions

- [ ] Should completed dungeons be replayable with scaled enemies? (deferred)
- [ ] Tooling for content authoring at scale? (deferred)
