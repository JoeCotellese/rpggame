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
