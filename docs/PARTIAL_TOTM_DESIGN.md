# Partial Theater of the Mind — Play-Surface Design

**Version:** 0.1.0
**Last Updated:** 2026-05-31
**Status:** Design / Vision
**Supersedes (where in conflict):** `docs/CLIENT_2D_ARCHITECTURE.md` (Jan 2025 planning doc)

---

## Table of Contents

1. [Purpose](#purpose)
2. [The Core Idea: Surfaces, Not Scales](#the-core-idea-surfaces-not-scales)
3. [The Scale Ladder](#the-scale-ladder)
4. [The Three Surfaces](#the-three-surfaces)
5. [The Combat Funnel (the one reused seam)](#the-combat-funnel-the-one-reused-seam)
6. [Surface Specifications](#surface-specifications)
7. [How This Maps to the Engine Roadmap](#how-this-maps-to-the-engine-roadmap)
8. [Reconciliation with the 2025 Architecture Doc](#reconciliation-with-the-2025-architecture-doc)
9. [Scope and Non-Goals](#scope-and-non-goals)
10. [Suggested Phasing](#suggested-phasing)
11. [Open Questions](#open-questions)

---

## Purpose

This document defines the **player-facing play model** for the D&D 5E game:
**partial theater of the mind (TotM)**. Narrative prose carries everything that
the tabletop carries in prose — towns, travel, social interaction, discovery —
while the **tactical tile grid** carries combat, where positioning, opportunity
attacks, cover, line of sight, and creature footprints actually matter and where
players need to *see* the board.

It is a **vision/design doc**, not an implementation plan. Its job is to fix the
spine the implementation hangs from, reconcile it with the engine work that has
landed since early 2025, and point each piece at the plan/issue that owns it.

### Why partial TotM

- D&D is mostly *not* played on a grid. The 5-foot battle grid is a **combat**
  tool; towns, exploration, and travel are run in prose, at coarser time scales.
  Forcing the player to walk an `@` through a town past every NPC emulates a
  video game, not the tabletop.
- The last several months of engine work have been overwhelmingly **spatial**:
  the spatial index, creature footprints (Large/Huge/Gargantuan), opportunity
  attacks, the visibility/obscured-area model, and cover. That investment pays
  off *in combat*. Pure TotM would bury it; tile-everything would misapply it.
  Partial TotM spends it exactly where it earns its keep.
- The original 2D client architecture (Jan 2025) already sketched this — a
  tactical viewport with an LLM narrative band beneath it. That intent was never
  built out and then drifted. This doc resurrects and finishes it.

---

## The Core Idea: Surfaces, Not Scales

A naïve design builds a "town system," a "wilderness system," and a "travel
system" as separate features. That triples the work and multiplies the
prose→combat transition logic.

The insight: across every scale of play, there are only **three distinct
presentation surfaces**, and **combat is always the leaf** that any scale drops
*into*.

```
                  ┌──────────────────────────────────────────────┐
   ZOOM OUT  ▲    │  REGION MAP / MONTAGE   (travel, hex/point)   │  ← plan-09
             │    ├──────────────────────────────────────────────┤
             │    │  NODE SURFACE + PROSE   (town, social)        │  ← plan-07
             │    ├──────────────────────────────────────────────┤
             │    │  TILE-WALK + PROSE      (dungeon, wild-site)   │
             ▼    ├──────────────────────────────────────────────┤
   ZOOM IN        │  TILE GRID — COMBAT     (ANY scale spawns it)  │  ← the leaf
                  └──────────────────────────────────────────────┘
                         every scale above can drop INTO combat,
                         and combat is ALWAYS the same tile grid
```

Build **three surfaces + one router + one transition seam**. Every scale of play
is then just a question of *which surface is active*, decided by the active
**pillar** (explore / social / combat — plan-07) and the **location type**.

---

## The Scale Ladder

Micro → macro, with how D&D actually runs each and the surface we assign it:

| Scale | How D&D runs it | Our surface |
|---|---|---|
| **Combat** | 5-ft squares, 6-sec rounds | **Tile grid** |
| **Dungeon** | gridded room-by-room crawl | **Tile-walk + prose band** |
| **Town** | nodes ("go to the tavern"), prose | **Node surface (list) + prose** |
| **Wilderness — as a site** | an outdoor "dungeon"; clearings = rooms | **Tile-walk + prose band** (same as dungeon) |
| **Wilderness — as connector** | hex/point crawl, travel pace, encounter checks | **Region map / montage** |
| **Travel (town → town)** | montage + random-encounter checks | **Region map / montage** |

Two ladder decisions worth stating explicitly:

- **Wilderness-as-site is just a dungeon with a different tileset.** It reuses
  the tile-walk surface wholesale. We do **not** build a separate
  wilderness-exploration mode for adventure locations set outdoors.
- **Wilderness-as-connector and town-to-town travel are the same surface** — the
  travel montage — differing only in zoom.

---

## The Three Surfaces

### 1. Tile Grid (combat + tile-walk exploration)

The existing 2D client. Top-down tiles, fog of war, lighting, sprites. It runs
in two modes:

- **Tile-walk (exploration):** the party moves square-by-square (WASD/arrows);
  the prose band narrates what is found. Used for **dungeons** and
  **wilderness-as-site**.
- **Combat:** initiative, turns, the full spatial ruleset (OAs, cover,
  footprints, visibility). Used **anywhere combat erupts**, at any scale.

The combat mode is the **funnel** every other surface drops into.

### 2. Node Surface + Prose (town, social)

A **list-style** menu of locations within a settlement (tavern, smithy, temple,
market, gate, …), each with a prose description. The player **picks a
destination** rather than walking to it; time compresses (an afternoon of
errands resolves in a few exchanges). Social encounters (dialogue, haggling,
gathering rumors) play here as **prose + choices**.

> v1 is **list-style** (labeled locations + prose). A visual clickable town map
> is a later enhancement, not a v1 requirement.

### 3. Region Map / Montage (travel)

Choosing to travel between places resolves as an **abstract prose montage** with
**random-encounter checks** along the way (see below). No token is walked across
a map in v1; the journey is narrated, interrupted by encounter cards, and ends
at the destination's node surface.

---

## The Combat Funnel (the one reused seam)

The hardest single piece of this design is the **prose/map → grid transition**:
when an encounter fires from *any* surface, creatures must be instantiated onto a
tile grid coherently (where does the party stand, where do the enemies start,
what is the room/clearing geometry).

The leverage: **this is one seam, not five.** A bandit ambush on the road, a
brawl that breaks out in the tavern, and a guardian at the end of a dungeon
corridor all funnel through the *same* "begin combat on a tile grid" path. Build
it once; every scale gets combat for free.

```
  Dungeon tile-walk ─┐
  Town node/social  ─┤
  Travel montage    ─┼──►  [ TRANSITION SEAM ]  ──►  TILE GRID (combat)
  Wilderness site   ─┘     instantiate creatures      run initiative,
                            onto a grid + geometry      resolve, then return
                                                        to the originating surface
```

Inputs the seam needs from each surface:

- **From tile-walk:** trivial — the party is *already* on the grid; just enter
  combat mode in place (this already works today).
- **From a node/prose scene:** a grid + spawn geometry for the encounter. Source
  options: a hand-authored encounter layout, the room's `layout` field (see
  `client-2d/docs/OPTION5_PLAN.md`), or a procedurally generated arena.
- **From the travel montage:** an encounter-appropriate arena keyed by terrain
  (forest road, riverbank, mountain pass), selected from the encounter table
  entry that fired.

On combat end, control returns to the **originating surface** (back to the town
node list, back to the montage to finish the journey, etc.).

---

## Surface Specifications

### Town node surface (v1, list-style)

- Entering a town presents a **list of locations** with short prose blurbs.
- Selecting a location enters it: prose description, available **social
  interactions** (talk, shop, rest, gather rumors), and any **actions** the
  location affords.
- Social interaction is **prose + choices**, not a walked space.
- Combat that breaks out funnels through the transition seam onto a grid, then
  returns to the location/town on resolution.

### Travel montage (v1, abstract)

Player picks a **destination** and a **pace**; the engine computes journey length
from pace × distance and resolves the trip as narrated intervals with
encounter checks.

**Travel pace (SRD-accurate) — makes pace a real decision:**

| Pace | Miles/day | Effect (SRD) | Encounter consequence |
|---|---|---|---|
| **Fast** | 30 | −5 passive Wisdom (Perception) | More likely to be *surprised* / ambushed |
| **Normal** | 24 | — | Baseline |
| **Slow** | 18 | Able to use stealth | Can avoid/pre-empt; search carefully |

Plus **Forced March** (SRD): pushing past 8 hours/day → CON saves (DC 10 +1 per
hour past 8) or a level of exhaustion — for "we *must* reach town before the
ritual completes" tension.

> **SRD provenance note:** the travel-pace table and the montage framing are in
> the open SRD. Encounter *tables* and the "roll a check per interval" cadence
> are DMG convention, **not** in the open SRD — so we design the encounter system
> ourselves (data-driven JSON tables), without contradicting the SRD.

**Montage loop:**

```
   Pick destination + PACE (fast/normal/slow)
            │
            ▼
   Engine computes journey length (days, from pace × distance)
            │
            ▼
   ┌──► For each travel INTERVAL (per day / per watch):
   │        roll encounter check  (data-driven table, by region/terrain)
   │            │
   │       ┌────┴─────┐
   │      miss        hit ──► surface ENCOUNTER CARD/PROMPT
   │       │                      │
   │       │                ┌─────┼───────────────┐
   │       │             combat  social        discovery/
   │       │           (→ TILE   (→ prose +     environment
   │       │             GRID)    choices)      (→ prose, skill check)
   │       │                └─────┴───────────────┘
   │       │                      │ resolve, then resume montage
   │       └◄─────────────────────┘
   ▼
   Arrive at destination (→ Town node surface)
```

- Encounter **tables are JSON**, keyed by region/terrain (data-driven design).
- Pace feeds the encounter math (fast → worse passive Perception → surprise more
  likely; slow → stealth available).
- Combat cards funnel through the transition seam; social/discovery cards stay in
  prose.

### Tile-walk exploration (dungeon + wilderness-site)

Unchanged in spirit from today's 2D client: square-by-square movement, fog of
war, lighting, the prose band narrating discoveries. Combat enters in place.

---

## How This Maps to the Engine Roadmap

This design is the **client/presentation expression** of work the engine is
already doing:

| Surface / behavior | Owning plan / issue |
|---|---|
| Pillar/location-type router (which surface is active) | **plan-07** (#536) — replace `in_combat: bool` with explore/social/combat pillars |
| Travel montage, pace, mounts, cross-area continuity | **plan-09** (#538) — Travel, Mounts & World Navigation |
| Engine owns rules, MCP drives client (surface-agnostic) | **plan-10** (#539) — 2D Client / MCP Convergence |
| Tile-walk movement / terrain / positioning | **plan-03** — Movement, Terrain, Positioning |
| Encounter arena geometry from room data | `client-2d/docs/OPTION5_PLAN.md` — room `layout` field |
| Environment-keyed encounter content | **plan-06** (#535) — Environment, Hazards & Object Model |

The router is the keystone. Once plan-07 gives the engine an explicit **pillar +
location type**, the client's job collapses to: *render the surface this pillar /
location type calls for, and funnel combat through the one seam.*

---

## Reconciliation with the 2025 Architecture Doc

`docs/CLIENT_2D_ARCHITECTURE.md` (Jan 2025) already specified a three-zone screen
— a 70% tactical viewport, a 30% context panel, and a 25% **narrative band** for
LLM prose, plus a `DIALOGUE` game mode and a combat action menu. That intent is
**correct and adopted here.**

However, that doc has drifted and must not be trusted as-is:

- Its `ui/` layer (narrative band, context panel, action menu, dialogue mode) was
  **never built** — `ui/` is effectively empty today.
- It **predates** the spatial index, opportunity attacks, creature footprints,
  the visibility model, plan-07's pillars, and the headless/MCP convergence.
- Its structural sketch (`game_view.py`, `EventBridge`) does not match today's
  `session.py` + `game.py` reality.

**Resolution:** where the two conflict, *this* document wins. The 2025 doc
remains useful for its UI-zone layout, color palette, and asset/fog/lighting
detail, which this doc does not restate.

---

## Scope and Non-Goals

**In scope (this design):**

- The play model and the three surfaces.
- The combat funnel / transition seam as a single reused mechanism.
- The town node surface (list-style, v1) and the travel montage (abstract, v1).
- Mapping each surface to its owning engine plan.

**Out of scope (here):**

- **DM/narration intelligence.** The engine already has an LLM narrative layer;
  this doc designs the *surface* that exposes prose, not the prompt design.
- Full per-surface implementation plans (those spawn from this doc as plan docs /
  issues).
- Visual town maps, region-map token movement, hex-crawl rendering — explicitly
  **later** enhancements; v1 is list/montage.
- Multiplayer, audio, 3D/first-person views.

---

## Suggested Phasing

Each phase is independently playable and builds toward the full ladder.

1. **Combat surface completeness.** Finish the player-facing combat surface on
   the tile grid (action menu, target selection, the spatial rules already in the
   engine) so combat is fully playable by a human, not only via MCP.
2. **Tile-walk + prose band.** Wire the LLM narrative band beneath the dungeon
   tile-walk view (the 2025 doc's narrative zone).
3. **Transition seam.** Build the single prose/scene → grid combat instantiation
   path, validated first from tile-walk (trivial) then from a scripted scene.
4. **Town node surface (list-style).** Location list + prose + social
   interaction; combat funnels through the seam and returns.
5. **Travel montage.** Destination + pace, interval encounter checks against JSON
   tables, encounter cards funneling combat through the seam.
6. **Polish / later.** Visual town map, region-map token travel, richer encounter
   variety.

(Phases 4–5 depend on plan-07's pillar/location-type router; phase 5 depends on
plan-09.)

---

## Open Questions

- **Encounter-check cadence:** per in-game day, or per watch (4–6 hr)? Affects
  encounter frequency tuning and rest interaction.
- **Arena sourcing priority** for the transition seam from non-grid surfaces:
  hand-authored layout → room `layout` field → procedural arena. Which is the v1
  default when no hand-authored layout exists?
- **Time/clock model:** does the engine track an explicit calendar/clock that
  travel and downtime advance? (Relevant to plan-09 and to quest deadlines.)
- **Surface persistence:** when combat funnels off a node/montage and back, what
  state must persist (party position-in-narrative, montage progress, partial
  journey)?
