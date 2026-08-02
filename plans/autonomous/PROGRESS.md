# Progress Log

Append-only. One entry per wake-up. Newest at the bottom.

Format:
```
## <UTC timestamp> — <issue id> — <stage>
Did: <what happened>
Gate: <pass/fail + evidence>
Next: <the single next stage>
```

---

## 2026-08-02 03:1x UTC — setup — bootstrap
Did: Verified environment end to end before planning. Synced deps; confirmed the
headless client boots and `GameSession` is drivable in-process; confirmed MCP
serves; confirmed git push reachable. Found and fixed the empty-vault blocker
(added `scripts/seed_test_vault.py`). Captured the test baseline (3 pre-existing
failures) and five landmines into `BASELINE.md`. Wrote the loop protocol,
roadmap, and this log.
Gate: pass — playtest harness proven runnable, baseline pinned.
Next: P1-01 SPEC.

## 2026-08-02 03:3x UTC — P1-01 — SPEC
Did: Wrote `issues/P1-01.md` — session protocol types. 6 acceptance criteria, each
with a named verification method; exact type signatures; client-facing UI contract
for terminal / 2D / MCP; rollback plan. Read the existing surfaces first so the
design composes rather than guesses: `core/move_result.py` sets the house style
(frozen + slots + per-field edge-case docs), and `GameEvent` reuses the existing
`EventType` enum rather than introducing a parallel taxonomy.
Notable find: `InitiativeTracker` already has `pause_for_reaction()`,
`resume_paused_turn()`, and `is_paused_for_reaction` (`systems/initiative.py:285-338`).
The engine can already pause mid-turn — P1-03 only needs to add the channel that
routes the question to a human, which de-risks it substantially.
Gate: pass — Definition of Ready fully satisfied.
Next: P1-01 BUILD.

## 2026-08-02 03:4x UTC — P1-01 — BUILD
Did: TDD. Wrote `tests/session/test_protocol.py` (31 tests, one class per AC),
confirmed it failed on `ModuleNotFoundError`, then implemented
`dnd_engine/session/protocol.py` and `__init__.py`. Matched the `core/move_result.py`
house style: frozen + slots, per-field docs covering `None` semantics.
Design note worth keeping: intent `from_dict` dispatch uses an explicit registry
built after the class definitions rather than `__init_subclass__`, because
`slots=True` makes the dataclass decorator return a *replacement* class object —
a subclass hook would have registered the pre-slots class and silently broken
deserialisation.
Gate: PASS.
  - new tests: 31 passed
  - engine suite: 3686 passed, 0 failed
  - client-2d: 576 passed, 2 failed (both pre-existing baseline)
  - client-terminal: 506 passed
  - total failures 2, at or under the pinned baseline
  - ruff clean, mypy clean on new code
  - strangler gate: 2D client boots and renders; terminal client imports clean
Finding: the engine's "1 pre-existing failure" is **flaky, not stable**.
`test_party_defeats_enemy` failed 2 of 12 isolated runs (~17%) — it asserts a kill
against an unseeded 1d8+10 roll. `BASELINE.md` updated to treat the engine count as
0–1 and to require an isolated re-run before calling anything a regression.
Next: P1-01 PLAYTEST.

## 2026-08-02 03:5x UTC — P1-01 — PLAYTEST
Did: Forward verification by driving a **real crypt playthrough** (walk, fight
skeletons, 16 resolved weapon attacks) and asserting the protocol carries what the
engine actually emits — added as a permanent test,
`tests/session/test_protocol_integration.py`, with an explicit non-vacuity guard so
it cannot pass on an empty run. Regression verification via `GameSession`: 5/5 moves
accepted, party 44/44, explored 255→270/300.
Gate: PASS — all 6 ACs verified with evidence recorded in `issues/P1-01.md`.
  - session tests: 36 passed (31 unit + 5 integration)
  - engine 3686 / client-2d 576 (2 pre-existing) / client-terminal 506
  - ruff clean
Two findings the unit tests could never have caught, both folded into the
roadmap sketches of the issues they affect:
  1. **Weapon attacks emit nothing to the event bus.** `ATTACK_ROLL` fires only
     from the spell path, and `CombatEngine` is constructed without a bus at all.
     16 real attacks produced zero attack/damage events. P1-02 therefore cannot
     build its event stream from bus subscriptions — it must synthesize events
     from returned result objects and merge them with bus events.
  2. **The engine has no determinism seam.** Enemy AI targeting calls global
     `random`, bypassing the injected `DiceRoller`. Seeding the dice leaves the
     type set varying 5-6; adding `random.seed()` made it worse (9 to 46 events);
     pinning `PYTHONHASHSEED` stabilised the count but not the types. This makes
     P1-04's "run twice, assert identical" premise unsound, so P1-04 was
     redesigned in `ROADMAP.md` to a same-run comparison that has no RNG
     dependence. Logged as Q-002 for Joe.
Next: P1-01 REVIEW.

## 2026-08-02 04:0x UTC — P1-01 — REVIEW
Did: Adversarial pass framed as "which AC can I prove is NOT met" rather than a
diff read. Found one critical defect and one spec/implementation mismatch.
**CRITICAL (fixed): `GameEvent` could not carry real movement payloads.**
`CREATURE_MOVED` carries `Position` objects, which are not JSON-serialisable, so
`ActionResult.to_json()` raised `TypeError` on any grid movement — and P1-02's
facade will emit exactly those. Tuples were separately lossy (returned as lists,
compared unequal). PLAYTEST missed it because crypt navigation is room-based and
never touches the grid path. Fixed by normalising payloads through a new
`to_jsonable()` at construction, so in-memory form == wire form; `Position(1,2)`
now renders as `{"x":1,"y":2}` and unknown objects degrade to `str()` rather than
breaking a turn. 8 regression tests added.
**Spec corrected: AC-3 claimed four outcome states, the design has three.**
Amended the AC rather than leaving a spec the code doesn't meet; logged the
rejected-vs-error distinction to FOLLOWUPS for P1-02.
Attacked and found sound: no transitive `core` import (AC-1 holds beyond its
static check), malformed wire input rejected cleanly, no strangler violation.
Gate: PASS — zero unresolved critical findings.
  - session tests 44 passed; engine 3699 passed; client-2d 576 (2 pre-existing);
    client-terminal 506; ruff + mypy clean; both clients boot and play
Baseline correction: a new engine failure appeared that was NOT mine. Applied the
isolation procedure — 10/10 passes isolated, and 4 of 5 full runs fully green with
identical code. The engine suite is flaky in at least two independent places, so a
raw failure count is not a usable gate. `BASELINE.md` now carries an explicit
3-step procedure to follow before ever declaring a regression.
Next: P1-01 SHIP.

## 2026-08-02 04:1x UTC — P1-01 — SHIP ✅ ISSUE COMPLETE
Did: Verified the full Definition of Done rather than rubber-stamping it, then
marked P1-01 done and queued P1-02.
Gate: PASS — every DoD item confirmed fresh:
  - session tests 44 passed (31 unit + 5 integration + 8 normalisation regression)
  - engine 3699 passed, 0 failed
  - client-2d 576 passed, 2 failed (both pre-existing baseline)
  - client-terminal 506 passed
  - regression playtest PASS (5/5 moves, party 44/44, explored 255→270/300)
  - terminal client boots: "D&D 5E Terminal Game v0.2.0"
  - zero unresolved critical findings; non-critical logged to FOLLOWUPS.md
  - working tree clean, all 4 commits pushed
Corrected the AC-2 evidence row to record that its first PASS was wrong — the
playtest never carried a `Position` because crypt navigation is room-based, so
the gap only surfaced under adversarial review. The evidence table should show
what actually happened, not a tidied version.
**P1-01 delivered:** `dnd_engine/session/` — `Intent` (+4 subclasses),
`GameEvent`, `PendingDecision`, `ActionResult`, `to_jsonable`. Purely additive;
nothing outside its own tests imports it yet. P1-02 gives it a producer.
Next: P1-02 SPEC — with two design inputs already captured in the roadmap sketch
(weapon attacks emit nothing to the bus; the rejected-vs-error split).
