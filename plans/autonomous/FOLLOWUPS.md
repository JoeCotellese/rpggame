# Follow-ups

Non-critical findings from adversarial review, deliberately **not** fixed.
See `README.md` → Definition of Critical.

Format: `- [<issue id>] <finding> — <file:line>`

---

## Pre-existing, found during setup

- [setup] Two incompatible character vault implementations coexist:
  `core/character_vault.py` (`~/.dnd_terminal/...`) and
  `core/character_vault_v2.py` (`~/.dnd_game/character_vault.json`). `client-2d`
  uses V2. Seeding the wrong one fails silently.
  — `dnd-engine/dnd_engine/core/character_vault.py`, `character_vault_v2.py`
- [setup] README advertises a Cleric class; `data/srd/classes.json` contains only
  fighter, rogue, wizard. `create_character(class_name="cleric")` raises.
  — `README.md:36`
- [setup] Running pytest from the repo root produces 57 collection errors because
  each package sets its own `pythonpath`. Tests must be run per package.
  — `pyproject.toml`

## P1-01

- [P1-01] `test_party_defeats_enemy` is flaky at ~17% (10 pass / 2 fail over 12
  isolated runs) because it asserts a kill against an unseeded 1d8+10 roll.
  Pre-existing and out of scope, but it makes any failure-count gate unreliable.
  Worth seeding the roll or asserting on damage rather than death.
  — `dnd-engine/tests/test_party_combat.py:160`
- [P1-01] `GameEvent.data` is an untyped `dict[str, Any]`. Typing the ~60 event
  payloads would give clients real guarantees instead of a serialisability
  check. Deliberate scope call, noted in the P1-01 design.
  — `dnd-engine/dnd_engine/session/protocol.py`
- [P1-01] `EventType` has no opportunity-attack or reaction members. P1-03 will
  need to add one; adding an enum member is additive and safe, but worth knowing
  before that issue starts.
  — `dnd-engine/dnd_engine/utils/events.py`
- [P1-01] Weapon attacks emit no bus events. `ATTACK_ROLL` fires only from the
  spell path and only when an `event_bus` argument is passed; `CombatEngine` is
  built without a bus. A real playthrough resolving 16 weapon attacks produced
  zero `ATTACK_ROLL`/`DAMAGE_DEALT` events, so a bus subscriber cannot observe
  combat at all. Existing clients paper over this by reading the returned
  `PlayerAttackResult`. Folded into the P1-02 design rather than fixed, since
  adding emissions would change behaviour for existing subscribers.
  — `dnd-engine/dnd_engine/core/combat.py:720`, `core/game_state.py:754`
- [P1-01] Enemy AI targeting uses global `random` rather than the injected
  `DiceRoller`, so playthroughs cannot be made reproducible. See QUESTIONS.md
  Q-002.
  — `dnd-engine/dnd_engine/systems/ai/targeting.py:80`
- [P1-01] `ActionResult` cannot distinguish "the rules said no" (occupied tile,
  not your turn) from "something broke internally" — both are `ok=False` +
  `error`. A UI wants to treat those differently, and it matters more once
  freeform DM adjudication lands. Worth a `rejected` vs `failed` split in P1-02.
  — `dnd-engine/dnd_engine/session/protocol.py`
- [P1-01] `Intent.from_dict` raises a raw `TypeError` on unknown keys rather than
  a protocol-level error naming the offending field. Unknown/missing `kind`
  already give good `ValueError`s; extra keys should match.
  — `dnd-engine/dnd_engine/session/protocol.py`
- [P1-01] `GameEvent` is unhashable because `data` is a dict, despite
  `frozen=True` generating `__hash__`. Fine today (nothing sets-of-events), but
  it will surprise someone eventually.
  — `dnd-engine/dnd_engine/session/protocol.py`
- [P1-01] The engine suite is flaky in at least two independent places
  (`test_party_defeats_enemy`, `test_attack_on_unconscious_character`), both
  RNG-dependent. Same root cause as Q-002: no determinism seam.
  — `dnd-engine/tests/`

## P1-02

- [P1-02] The terminal client constructs its own `ConditionManager`
  (`cli.py:104`) even though `GameState` already owns one
  (`game_state.py:767`). Two managers over the same creatures invites drift.
  — `client-terminal/terminal_client/ui/cli.py:104`
- [P1-02] Integration fixtures build `Character` objects directly, so nobody is
  equipped and every attack resolves as "unarmed strike". The synthesis path is
  identical, so the ACs still hold, but tests would be more faithful using
  `CharacterFactory`, which grants starting equipment.
  — `dnd-engine/tests/session/test_session_combat.py`
- [P1-02] `TURN_END` is synthesized but no engine path emits it. Harmless today;
  worth confirming the engine should not own it before more clients depend on it.
  — `dnd-engine/dnd_engine/session/session.py`
- [P1-02] `assign_combat_numbers()` is called by `client-terminal` (`cli.py:6243`)
  and now also by the session facade. Once the terminal client migrates to the
  facade its own call becomes redundant. The engine arguably ought to do this at
  combat start so no caller has to — that would be a non-additive change.
  — `client-terminal/terminal_client/ui/cli.py:6243`
- [P1-02] `TIME_ADVANCED` accumulates float drift — `elapsed_minutes` reaches
  `0.30000000000000004` after three combat rounds. Cosmetic, pre-existing, but a
  client rendering elapsed time will show it. Integer seconds would avoid it.
  — `dnd-engine/dnd_engine/systems/time_manager.py`

## P1-03

- [P1-03] Opportunity attacks resolve *after* the mover's step completes — the
  engine moves, then publishes `OPPORTUNITY_PROVOKED`. At a table the attack
  interrupts the movement. Same outcome in the common case, but it differs when
  the attack would have stopped the move (dropping the mover to 0 mid-step).
  Known limitation, not an accident.
  — `dnd-engine/dnd_engine/core/game_state.py:1268`
- [P1-03] `ReactionDispatcher` subscriptions accumulate — registering a handler
  for the same creature four times leaves four subscriptions. Behaviour is
  correct (last-wins picks one) but the list grows across fights. An
  `unregister` before re-registering, or a per-(creature, trigger) replace,
  would bound it.
  — `dnd-engine/dnd_engine/systems/reactions.py:120`

## P1-04

- [P1-04] One matrix configuration yields a run with zero actions, which verifies
  nothing. The pytest test asserts `actions > 0`, but the matrix script only
  checks in aggregate. Assert non-vacuity per run.
  — `plans/autonomous` playtest tooling
