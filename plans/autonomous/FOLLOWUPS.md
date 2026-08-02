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
