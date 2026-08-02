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
