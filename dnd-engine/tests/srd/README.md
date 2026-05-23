# SRD Conformance Tests

This tree mirrors `docs/srd/` and contains one test file per SRD section,
cross-referencing the rules text against the engine implementation.

## How it works

Each test class corresponds to a subsection of an SRD doc. The class
docstring quotes the rule verbatim with a citation. Each method tests one
discrete sentence of the rule:

- **Real tests** verify the rule is enforced where it should be.
- **Stubs** (`pytest.skip("GAP: ...")`) stake out rules that aren't yet
  enforced. The skip reason cites where the rule lives today (if it lives
  somewhere besides the engine) or marks it as "not implemented
  anywhere."

The `@pytest.mark.srd(path, lines=...)` marker — applied module-wide via
`pytestmark` — links a test file to its SRD source. The marker is
registered in `tests/conftest.py`.

## Reading the report

```bash
# Full collection tree — the conformance "table of contents".
uv run pytest --collect-only -q tests/srd/

# Run only — passes confirm enforcement, skips surface gaps.
uv run pytest tests/srd/ -v
```

A skipped test in this tree is a known gap, not a bug. A failing test is
a regression in rule enforcement and must be fixed.

## Knowing what's been audited

To avoid duplicating effort, run from the repo root:

```bash
uv run python scripts/srd_audit_coverage.py
```

The script scans every `@pytest.mark.srd(path, ...)` marker in this
tree and diffs against `docs/srd/**.md`. It prints per-chapter progress
bars, a list of audited files, and a suggested queue of unaudited prose
files. The marker is the single source of truth — a test file isn't
"audited" until it carries the marker pointing at the SRD doc.

The script also warns about **stale markers** — tests pointing at SRD
files that no longer exist (e.g. after a `scripts/split_srd.py` rerun
that renamed a section).

## Adding a new conformance file

1. Identify the SRD doc you're auditing (e.g.
   `docs/srd/playing-the-game/cover.md`).
2. Mirror the path under `tests/srd/` and create the test file (snake-cased).
3. Add `pytestmark = pytest.mark.srd("playing-the-game/cover.md", lines="...")`
   using the `source_lines` value from the doc's frontmatter.
4. One class per subsection; class docstring quotes the rule.
5. One method per discrete rule sentence — real assertion if implemented,
   `pytest.skip("GAP: ...")` if not.

## Why tests instead of a markdown matrix

A static conformance doc rots; tests can't lie. If a rule is broken, the
real test fails and CI yells. If a gap is closed, the stub starts
passing (and `strict` markers, if used, catch the unexpected pass).
`pytest --collect-only` produces an auto-current table of contents.
