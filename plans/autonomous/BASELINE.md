# Pinned Baseline

Captured 2026-08-02 before any autonomous work began. The loop gates against
these numbers. **Do not "fix" the pre-existing failures** — they are outside
scope and chasing them burns the night.

## Test baseline

Run per package, from that package's directory.

| Package | Command | Result |
|---|---|---|
| `dnd-engine` | `uv run pytest -q --no-cov` | **1 failed**, 3654 passed, 142 skipped |
| `client-2d` | `uv run pytest -q --no-cov` | **2 failed**, 576 passed, 2 skipped |
| `client-terminal` | `uv run pytest -q --no-cov` | 0 failed, 506 passed |

**Total pre-existing failures: 3.** Any run showing more than 3 means the loop
broke something.

Known-failing tests:

- `dnd-engine/tests/test_party_combat.py::TestPartyCombat::test_party_defeats_enemy`
  — **FLAKY, not stably red.** Measured 2026-08-02 during P1-01 BUILD: 12
  consecutive isolated runs produced **10 passes, 2 failures (~17% failure
  rate)**. The test asserts `not goblin_enemy.is_alive` after a 1d8+10 hit
  against an unseeded dice roll. A full-suite run may therefore report either
  0 or 1 engine failure with no code change.
  **Gate implication:** treat the engine's failure count as `0–1`, and never
  conclude a regression from this test alone — re-run it in isolation before
  believing it. Do not "fix" it; it is out of scope (see `ROADMAP.md`).
- `client-2d/tests/test_game_session.py::TestSessionTick::test_tick_does_not_auto_drain_enemy_turns_when_mcp_active`
- `client-2d/tests/test_game_session.py::TestSessionTick::test_tick_auto_drains_enemy_turns_in_windowed_mcp_mode`

Running all three packages from the repo root fails with 57 collection errors.
That is a harness quirk, not a code failure — each package sets its own
`pythonpath`.

## Environment facts

| Fact | Value |
|---|---|
| `uv` | 0.8.17 at `/root/.local/bin/uv` |
| `uv sync --all-extras` | works |
| `ANTHROPIC_API_KEY` | **not set** |
| `OPENAI_API_KEY` | **not set** |
| `.env` | absent |
| git remote | reachable, push works |

### LLM consequence

No API key is available. Any LLM-dependent work must be built against the
`LLMProvider` interface and verified with `dnd_engine/llm/debug_provider.py`.
The real provider path cannot be verified here and must be flagged for Joe's
manual validation.

## Headless playtest harness

Verified working. The 2D client runs without a window and `GameSession` can be
driven in-process:

```python
from client_2d.session import GameSession
s = GameSession(enable_mcp=False, dev_mode=True)
s.initialize()
s.get_state()      # ASCII map + party HP + light source
s.move("east")
s.wait()
```

`uv run dnd-2d --headless --dev --mcp --mcp-port <port>` also boots and serves
MCP over SSE at `/sse`. In-process `GameSession` is preferred for acceptance
tests: no port, no subprocess, no transport flakiness.

Dev tools useful for deterministic playtests: `set_seed()`, `load_scenario()`,
`spawn_monster()`, `spawn_character()`, `set_position()`, `clear_enemies()`,
`reset_game()`.

### Vault prerequisite

The headless client **refuses to start with an empty vault**. A fresh container
must run:

```bash
uv run python scripts/seed_test_vault.py
```

## Landmines found during setup

Recorded so the loop does not rediscover them at 3am.

1. **Two incompatible character vaults.** `core/character_vault.py`
   (`CharacterVault`, stores under `~/.dnd_terminal/characters/vault/`) and
   `core/character_vault_v2.py` (`CharacterVaultV2`, single JSON at
   `~/.dnd_game/character_vault.json`). `client-2d` uses **V2** via
   `engine_adapter.py:128`. Seeding the wrong one silently produces "vault has
   no characters".
2. **The rules loader class is `DataLoader`, not `RuleLoader`.**
3. **`CharacterFactory()` takes no data loader.** The loader is passed per call:
   `create_character(class_name=..., race_name=..., data_loader=..., name=...)`.
4. **Only three classes and four races exist** in `data/srd/`: fighter, rogue,
   wizard; human, mountain_dwarf, high_elf, halfling. The README's claim of a
   Cleric is wrong — `"cleric"` raises `ValueError`.
5. **`client_2d.testing.TestHarness` is not the engine.** It defines its own stub
   `GameState` dataclass. Do not use it as an acceptance gate. Use
   `GameSession`.
