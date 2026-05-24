# Plan: MCP Combat Observability (issue #570)

## Defect

From the MCP perspective, combat is unobservable. The engine resolves enemy turns correctly (HP drops, plan-04 unconsciousness fires, plan-03 P5 combat step records movement), but the `GameSession` layer between the engine and MCP never surfaces the per-turn details to the response payload. Three intertwined symptoms:

1. **`Current Turn` is the PC who just acted.** After enemies run between PC actions, the state response snapshots only the *final* state and never enumerates the intervening combatants.
2. **Enemy actions are absent from the response.** `GameSession.combat_log` is built up correctly inside `_process_enemy_turn` but is *never read* by `get_state` or `_format_state_response` — only by `GameWindow`'s renderer.
3. **`Combat Round` appears to increment per PC action.** The counter itself (`InitiativeTracker.round_number`) is correct (it increments on initiative wrap in `next_turn`), but because the response only ever shows post-drain snapshots and never the intervening turns, every PC reply lands one full cycle later than the previous one, so it *looks* like Round ticks per PC action. This is a presentation defect, not a counter bug.

All three reduce to the same underlying flaw: **the MCP path drains the combat state machine forward to the next PC turn but throws away everything that happened during the drain.** The fix is to capture the per-turn event sequence inside the drain and append it to the response string.

## Diagnosis (file:line citations)

### Bug 1: `Current Turn` stuck on player

- `client-2d/src/client_2d/session.py:1170` — `attack()` runs `while self.processing_enemy_turn: self._process_enemy_turn()` then calls `self.get_state()`. By the time `get_state` runs, the initiative tracker is back on a PC, so `get_current_combatant()` returns that PC's name.
- `client-2d/src/client_2d/session.py:1239` — `wait()` does the identical drain.
- `client-2d/src/client_2d/session.py:785-787` — `_format_state_response` reads `self.engine.get_current_combatant()` synchronously, with no per-turn history.

**Root cause:** Synchronous-drain model with no per-turn capture; the only artifact of the drained turns is in `self.combat_log`, and `_format_state_response` never reads `combat_log`.

### Bug 2: Enemy actions absent from response

- `client-2d/src/client_2d/session.py:471-502` — `_process_enemy_turn()` appends descriptive lines to `self.combat_log` via `_add_combat_log(...)`.
- `client-2d/src/client_2d/session.py:769-857` — `_format_state_response` builds map / party / actions blocks but contains **zero references to `self.combat_log`**.
- The combat log is consumed only by the windowed renderer (which lives in `client-2d/src/client_2d/game.py` and is not relevant to MCP).

**Root cause:** `combat_log` is a windowed-mode artifact. The MCP path never surfaces it. Also, the existing log lines are coarse (no attack rolls, no AC, no movement delta), so even if surfaced they would be less informative than PC attack lines from `_format_attack_report`. Plan-03 P5 wired `MoveResult` and unconsciousness events from the engine but no consumer subscribes for MCP-side accumulation.

### Bug 3: `Combat Round` appears to increment per PC action

- `dnd-engine/dnd_engine/systems/initiative.py:184-190` — `next_turn()` increments `round_number` only on initiative wrap. **Counter is correct.**
- `client-2d/src/client_2d/session.py:707-711` — `get_state()` builds the top-of-output `Turn: N` line from `tracker.round_number` (mis-labeling round as "Turn", a separate cosmetic bug).
- `client-2d/src/client_2d/session.py:784` — `_format_state_response` prints `Combat Round: {combat_data['round']}` which traces back to `tracker.round_number` via `EngineAdapter.get_combat_data()` at `engine_adapter.py:380`.

**Root cause:** Counter is correct. The perceived increment-per-PC-action is the same drain artifact as Bug 1: between two consecutive PC replies, the system silently advances through a full initiative cycle (Goblin → Abe → Bob). The reporter notices only Bob's turns, sees the round climb, and infers wrongly that the counter is broken. *No engine change needed.* Adding the per-turn event log (Bug 2's fix) makes this self-explanatory. There is a separate cosmetic fix: rename the misleading top-line `Turn:` field to `Round:` (or remove it, since `Combat Round:` already appears below in combat mode).

### Architecture call-out: sync vs async drain

Today the drain is **synchronous inside the MCP handler** (`session.py:1170-1171, 1239-1240`), not via the 30 Hz `tick()` loop — `tick()` guards on `processing_enemy_turn` and the MCP handler runs the drain before returning. So we do **not** need to refactor to an async model. The fix is straightforward: capture log lines in a per-call accumulator inside the drain.

There is one subtle bug: `_process_mcp_commands` at `session.py:635` short-circuits when `processing_enemy_turn` is True. If a PC reply *returns* the response while `processing_enemy_turn` is somehow still True (e.g. an unconscious party member's death-save turn loop is in flight), subsequent MCP commands would silently wait. The synchronous drain inside `attack`/`wait` makes this unlikely in practice, but we add an assertion so it can't hide.

## Phased fix

Four small, independently mergeable phases. Each phase is a separate PR. TDD: failing test first.

### Phase 1 — Per-call combat event accumulator (foundation)

**Scope:** Introduce a per-call list on `GameSession` that captures structured combat events drained between MCP request and response. No behavior change to drain order; only adds capture.

**Files touched:**
- `client-2d/src/client_2d/session.py` — Add `self._pending_combat_events: list[str]` initialized to `[]`, a `_drain_enemy_turns()` helper that wraps the existing drain loop and accumulates one descriptive line per processed turn (including the active combatant's name, the action taken, and target/result), and a `_consume_pending_events() -> list[str]` reader. Replace the two raw `while self.processing_enemy_turn: self._process_enemy_turn()` loops in `attack` and `wait` with calls to the new helper.
- `client-2d/tests/test_game_session.py` — New unit test class `TestCombatEventAccumulator`. Verifies that after a `wait()` call with a hostile goblin adjacent, `session._consume_pending_events()` returns lines containing the goblin's name and either `hit`/`miss`/`damage`/`incapacitated`.

**Behavior change:** None observable from MCP yet. Internal plumbing only.

**Tests added:**
- `test_drain_enemy_turns_captures_enemy_attack` — spawns a goblin adjacent to Abe with a deterministic seed, calls `pass_turn()` to hand initiative to the goblin, drives the drain, asserts pending events include the goblin's name and the result.
- `test_drain_enemy_turns_captures_unconscious_death_save` — knocks a PC to 0 HP, drives the drain through that PC's death-save turn, asserts pending events include the death-save outcome.
- `test_pending_events_reset_between_drains` — proves the accumulator clears between MCP calls.

**Risk:** Low. The new helper *wraps* the existing loop; the loop body is unchanged. Windowed mode keeps its own `self.combat_log` (rolling-10 buffer) untouched.

### Phase 2 — Surface the accumulated events in MCP responses

**Scope:** Make `attack()` and `wait()` (and `combat_move()` if it can drain enemies — verify in implementation) include the drained event lines in the response string. Add a `Recent Combat:` block to `_format_state_response` populated from `_consume_pending_events()` so any handler returning state shows the events it caused.

**Files touched:**
- `client-2d/src/client_2d/session.py` —
  - `attack()` (`:1045-1174`): after `_drain_enemy_turns()`, prepend the drained event lines (if any) to the existing `report + state` payload, formatted as a `Between turns:` block.
  - `wait()` (`:1232-1242`): same surfacing.
  - `_format_state_response()` (`:769`): if there are unconsumed pending events at format time, render them under a `Recent Combat:` header. Belt-and-braces in case a caller invokes `get_state()` without first consuming the events.

**Behavior change:** MCP responses to `game_attack` / `game_wait` now include attack rolls, hit/miss/damage, and target-killed/down lines for every enemy turn that ran between the PC's last action and the reply. The format mirrors the existing PC `_format_attack_report` style (`"<actor> attacks <target>: roll N+M = T vs AC X -> HIT/MISS for D damage"`).

**Tests added:**
- `test_wait_response_includes_goblin_attack_line` — **the acceptance test.** Scripted MCP scenario: spawn a goblin adjacent to the party, `set_seed` deterministically, call `session.wait()`, assert the returned string matches a regex like `r"Goblin.*(HIT|MISS).*roll \d+"` and contains `"damage"` when hit.
- `test_attack_response_includes_intervening_enemy_turns` — set up Abe-then-Goblin-then-Bob initiative, call Abe's attack, assert the reply includes a line attributed to the goblin before the final state snapshot.
- `test_response_event_block_format_is_stable` — golden-string check on the `Between turns:` header so MCP consumers can grep for it.

**Risk:** Low/medium. The risk is double-rendering events if a caller invokes `get_state()` after `attack()`. We mitigate by having `_consume_pending_events()` drain (return-and-clear) and only `_format_state_response` showing pending events if the accumulator is non-empty.

### Phase 3 — Make `Current Turn` accurate at reply time + clarify Round line

**Scope:** Two presentation fixes to remove the perception that combat is broken.

**Files touched:**
- `client-2d/src/client_2d/session.py`:
  - `_format_state_response()` (`:781-787`): the line is already correct *after* the drain — the bug from the reporter's perspective is the absence of intervening turn info, which Phase 2 fixes. Add an explicit `Next Turn:` line *after* the `Current Turn:` line, to make it obvious whose turn the player is on for their next action. (`current_turn_idx + 1) % len(combatants)` resolved against the initiative tracker.)
  - `get_state()` (`:707-711`): the top-of-output `Turn: N` line currently reads `tracker.round_number` and labels it `Turn:`, which is misleading. Rename to `Round: N` outside combat (when applicable) and drop it inside combat where `Combat Round:` already appears. This is the field semantic mismatch — the formatter is pulling round-number into a field labeled "turn", which compounds the confusion in the bug report.

**Behavior change:** Reply payload now reads
```
Combat Round: 2
Current Turn: Bob
Next Turn: Goblin 1
```
…and the deceptive top-line `Turn: 2` is removed for the combat case.

**Tests added:**
- `test_current_turn_matches_active_combatant_at_reply_time` — set up initiative [Goblin, Abe, Bob], call `wait()`, assert the response's `Current Turn:` line names whichever combatant the tracker now points to.
- `test_combat_round_increments_only_after_full_initiative_cycle` — three combatants, drive `next_turn()` three times via repeated `wait` calls, assert the round in the response goes `1 → 1 → 1 → 2` (only the wrap bumps it). Pure engine assertion; no event-bus dependency.
- `test_top_line_no_longer_says_turn_in_combat` — guards against the rename regressing.

**Risk:** Low. Windowed mode reads the same fields but renders them in its own HUD widgets; the `Turn:` top-line rename only affects MCP wire output.

### Phase 4 — Engine-event subscription for richer per-turn detail (optional polish)

**Scope:** Replace string-formatting in `_drain_enemy_turns` with an `EventBus`-subscribed collector so the events match the engine's source of truth (attack roll, attack bonus, AC, damage, target HP delta, movement consumed). The engine already emits `ATTACK_ROLL`, `DAMAGE_DEALT`, `DAMAGE_TAKEN`, `CREATURE_MOVED`, `TURN_START`, `TURN_END` (see `dnd-engine/dnd_engine/utils/events.py:22-45`).

**Files touched:**
- `client-2d/src/client_2d/session.py` — `initialize()` and `initialize_mcp_server()` subscribe a `_CombatEventCollector` to the relevant `EventType`s on `self.engine.event_bus`. Collector buffers a list of structured event dicts. `_drain_enemy_turns` returns the buffered events rather than reading from `combat_log`.
- `client-2d/src/client_2d/integration/engine_adapter.py` — expose `event_bus` if not already (it is, at `:257`).
- `client-2d/tests/test_game_session.py` — assert each enemy attack produces an ATTACK_ROLL + DAMAGE_DEALT pair in the response.

**Behavior change:** Enemy attack lines now include the roll/AC detail mirroring PC `_format_attack_report` lines, closing the symmetry gap.

**Tests added:**
- `test_enemy_attack_response_includes_roll_and_ac` — asserts goblin's reply lines match the same regex shape as PC attack lines (`r"roll \d+\+\d+ = \d+ vs AC \d+"`).
- `test_enemy_movement_appears_in_response` — when a goblin moves to close distance before attacking, a movement line appears.

**Risk:** Medium. Two things to watch:
1. `EventBus` re-entrancy contract (`game_state.py:740`): subscribers must not call back into the engine. The collector only appends to a list.
2. The windowed renderer also subscribes to some events; ensure the new subscription is idempotent across multiple `initialize_mcp_server` calls and unsubscribes on `shutdown()`.

## Test plan summary

| # | Test | File | Phase |
|---|---|---|---|
| 1 | `test_drain_enemy_turns_captures_enemy_attack` | `test_game_session.py` | 1 |
| 2 | `test_drain_enemy_turns_captures_unconscious_death_save` | `test_game_session.py` | 1 |
| 3 | `test_pending_events_reset_between_drains` | `test_game_session.py` | 1 |
| 4 | `test_wait_response_includes_goblin_attack_line` (**acceptance**) | `test_game_session.py` | 2 |
| 5 | `test_attack_response_includes_intervening_enemy_turns` | `test_game_session.py` | 2 |
| 6 | `test_response_event_block_format_is_stable` | `test_game_session.py` | 2 |
| 7 | `test_current_turn_matches_active_combatant_at_reply_time` | `test_game_session.py` | 3 |
| 8 | `test_combat_round_increments_only_after_full_initiative_cycle` | `test_game_session.py` | 3 |
| 9 | `test_top_line_no_longer_says_turn_in_combat` | `test_game_session.py` | 3 |
| 10 | `test_enemy_attack_response_includes_roll_and_ac` | `test_game_session.py` | 4 |
| 11 | `test_enemy_movement_appears_in_response` | `test_game_session.py` | 4 |

All tests use the existing scenario fixture pattern (`SCENARIO_DIR / "ranged_attack_basic.yaml"` or a new minimal `mcp_adjacent_goblin.yaml`) plus `session.set_seed(N)` for determinism, mirroring `test_game_session.py:421` and surrounding setup.

## Out of scope

- **#569 (movement-budget display).** Adjacent bug in the same status block; the fix is small but distinct (the `Movement: X ft remaining` line reads the stale TurnState across combatants). Should remain its own issue.
- **Combat-log capacity.** The windowed `combat_log` is capped at 10 lines (`session.py:278`). The MCP per-call accumulator is unbounded by call but resets per call; we should *not* enlarge or shrink the windowed buffer.
- **Plan-10 broader convergence (#539).** This plan slots conceptually under plan-10's umbrella (the MCP-side surfacing of engine truth) but doesn't duplicate any of its existing children (#326, #336, #348-354, #399, #401). Reference plan-10 in the PR description but file as its own issue.
- **Bug 3 engine investigation.** The `round_number` counter is correct as-is. No engine change.
- **LLM narrative enhancement.** Out of scope per plan-10.

## Risk

| Risk | Mitigation |
|---|---|
| Windowed mode regresses on the renamed top-line `Turn:` field | Windowed HUD reads via property/method, not by parsing the MCP string. Verify by running `GameWindow` after Phase 3. |
| Plan-04 dying flow re-entrancy | The new accumulator is purely list-append; no engine calls. Death-save processing already runs inside the same drain loop; Phase 1's helper preserves call order. |
| Plan-03 P5 combat step regresses | No changes to `_combat_move_via_engine` semantics. Phase 4's event subscription is read-only. |
| Double-rendering events when handler returns state | `_consume_pending_events` is a take-and-clear; `_format_state_response` reads `_pending_combat_events` only if non-empty. The `attack`/`wait` happy path consumes before formatting. |
| EventBus subscriber leaks across test sessions (Phase 4) | `GameSession.shutdown()` must unsubscribe; add a fixture-scoped teardown. |
| Headless tick loop tries to drain in parallel with sync MCP handler | `_process_mcp_commands` early-exits when `processing_enemy_turn` is True (`session.py:635`); sync drain finishes before returning. Add an assertion to make this contract loud. |

## Sequencing

- **PR 1:** Phase 1 (accumulator plumbing). Mergeable independently; no MCP-visible change.
- **PR 2:** Phase 2 (surface events). Closes the dominant user pain. Could ship without Phase 3/4.
- **PR 3:** Phase 3 (clarity fixes). Cosmetic but addresses the report's `Current Turn` and `Combat Round` complaints directly.
- **PR 4:** Phase 4 (engine-event subscription). Quality bump; defer if scope creeps.

Recommended cadence: ship PR 1+2 together if reviewer load allows (the accumulator is uninteresting on its own); ship PR 3 same day; defer PR 4 if review budget is tight.

## Critical files

- `/Users/joec/git-dnd/rpggame/client-2d/src/client_2d/session.py`
- `/Users/joec/git-dnd/rpggame/client-2d/src/client_2d/integration/engine_adapter.py`
- `/Users/joec/git-dnd/rpggame/client-2d/src/client_2d/testing/state_renderer.py`
- `/Users/joec/git-dnd/rpggame/dnd-engine/dnd_engine/utils/events.py`
- `/Users/joec/git-dnd/rpggame/client-2d/tests/test_game_session.py`
