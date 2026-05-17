# Scenario YAML Schema (v1)

Scenarios capture a complete game setup — map, party, enemies, seed — so a
single `load_scenario(path)` call reproduces an exact playtest state.
Lives under `dnd-engine/tests/scenarios/yaml/`. Engine consumer:
`dnd_engine.scenarios.ScenarioLoader`.

## Top-level keys

| Key | Required | Type | Description |
| --- | --- | --- | --- |
| `name` | yes | str | Human-readable scenario name. |
| `seed` | yes | int | RNG seed; drives all dice rolls deterministically. |
| `map` | yes | mapping | See **map** below. |
| `party` | yes | list | One or more party members (see **party member**). |
| `enemies` | yes | list | Zero or more enemies (see **enemy**); empty list still required. |
| `script` | no | list | MCP actions to run after load. Parsed but not yet executed (Phase 4 / #363). |
| `assertions` | no | list | Expected state checks. Parsed but not yet executed (Phase 4 / #363). |

## `map`

| Key | Required | Type | Description |
| --- | --- | --- | --- |
| `dungeon` | yes | str | Dungeon file name (without `.json`). |
| `campaign` | yes | str | Campaign ID containing the dungeon. |
| `start_room` | no | str | Override start room ID. Falls back to the dungeon's default. |
| `tiles` | — | — | **Inline tiles are not yet implemented**; the loader rejects this key with a clear message. |

## `party` member

| Key | Required | Type | Description |
| --- | --- | --- | --- |
| `class` | yes | str | Class ID (`fighter`, `rogue`, `wizard`). |
| `race` | yes | str | Race ID (`human`, `mountain_dwarf`, `high_elf`, `halfling`). |
| `weapons` | yes | list[str] | Ordered weapon item IDs. First is equipped to the WEAPON slot; the rest go in the pack. Must be non-empty. |
| `position` | yes | [int, int] | `[x, y]` tile coordinates for visual placement. |
| `name` | no | str | Character name. `CharacterFactory` generates one if omitted. |
| `level` | no | int | Starting level. Default `1`. |

## `enemy`

| Key | Required | Type | Description |
| --- | --- | --- | --- |
| `monster_id` | yes | str | SRD monster ID (e.g. `goblin`, `giant_rat`). Must exist in `dnd_engine/data/srd/monsters.json`. |
| `position` | yes | [int, int] | `[x, y]` tile coordinates. |

## Entity ID convention

Entity IDs match Phase 1's spawn tools so MCP scripts and assertions stay
portable across the two paths:

- Party member → `pc_<name_lowercased_with_spaces_as_underscores>`
- Enemy → `<monster_id>_<index_in_enemies_list>` (zero-indexed)

For example, a party member named `Archy` becomes `pc_archy`; the second
goblin in the enemies list becomes `goblin_1`.

## Validation guarantees

Every error from `ScenarioLoader.load(path)` is a
`ScenarioValidationError` whose message includes:

- The offending top-level key, list index, or nested path (e.g.
  `party[0].position`).
- The bad value when the failure is type-related.
- The file path when the YAML itself is malformed or missing.

Unknown class/race/`monster_id` values surface as
`ScenarioValidationError` (the underlying `ValueError`/`KeyError` from
`CharacterFactory` / `DataLoader` is wrapped) so callers don't need to
special-case engine exception types.

## Example

```yaml
name: ranged_attack_basic
seed: 42
map:
  dungeon: laboratory
  campaign: poisoned_laboratory
  start_room: laboratory.entrance
party:
  - class: fighter
    race: high_elf
    weapons: [shortbow]
    position: [3, 5]
    name: Archy
enemies:
  - monster_id: goblin
    position: [10, 5]
```
