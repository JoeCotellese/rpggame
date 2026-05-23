#!/usr/bin/env python3
# ABOUTME: Report SRD conformance audit coverage by scanning @pytest.mark.srd markers.
# ABOUTME: Walks docs/srd/ and tests/srd/ and prints audited vs. unaudited rule files.

"""SRD conformance audit coverage report.

Walks `docs/srd/` to enumerate the rules-text files, and `tests/srd/` to
find every `@pytest.mark.srd(path, ...)` marker. Prints the diff so we
know which docs are audited, which aren't, and what to queue next.

The `@pytest.mark.srd` marker (registered in
`dnd-engine/tests/conftest.py`) is the source of truth — anything tagged
is audited, anything not tagged isn't.

Catalog chapters (spells, monsters, magic items, animals) are excluded
from this report because they're audited by JSON data parity against
`dnd-engine/dnd_engine/data/srd/`, not by behavioral conformance tests.

Files whose YAML frontmatter `source_lines` range is `STUB_LINE_THRESHOLD`
lines or fewer are surfaced separately as "likely SRD-splitter stubs"
and excluded from the suggested queue and progress denominator. These
are chapter intros and framing text that the PDF splitter pulls into
their own files but which contain no auditable rule. Spot-checking the
SRD tree found these range up to 5 lines reliably; rules definitions
of 6+ lines (e.g. critical-hits, immunity) are real rules even if
terse.

Run:
    uv run python scripts/srd_audit_coverage.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRD_DOCS = ROOT / "docs" / "srd"
SRD_TESTS = ROOT / "dnd-engine" / "tests" / "srd"

# Catalog chapters are reconciled by JSON data parity, not by this audit.
CATALOG_CHAPTERS = {"spells", "monsters", "magic-items", "animals"}

# Index and readme files are scaffolding, not rules.
SKIP_NAMES = {"_index.md", "README.md"}

# Files with this many source lines or fewer are treated as SRD-splitter
# stubs (chapter intros, single-paragraph framing) and held out of the
# audit queue. Verified against the full prose tree: range <= 5 catches
# only true stubs; the shortest real rules (e.g., critical-hits.md at 8
# lines) sit comfortably above this threshold.
STUB_LINE_THRESHOLD = 5

MARKER_PATTERN = re.compile(r'pytest\.mark\.srd\(\s*"([^"]+)"')
SOURCE_LINES_PATTERN = re.compile(r"^source_lines:\s*(\d+)\s*-\s*(\d+)\s*$", re.MULTILINE)


def audited_paths() -> dict[str, list[Path]]:
    """Return mapping of SRD relative path -> list of test files that mark it."""
    out: dict[str, list[Path]] = {}
    if not SRD_TESTS.exists():
        return out
    for test_file in SRD_TESTS.rglob("test_*.py"):
        text = test_file.read_text()
        for match in MARKER_PATTERN.finditer(text):
            out.setdefault(match.group(1), []).append(test_file)
    return out


def source_lines_range(path: Path) -> int | None:
    """Return the `source_lines: N-M` span size from frontmatter, or None.

    The SRD splitter writes a `source_lines: <start>-<end>` field in the
    YAML frontmatter recording which lines of `SRD_CC_v5.2.1.txt` the
    file was sliced from. The size of that range is a robust proxy for
    how much rule content the file actually carries.
    """
    text = path.read_text()
    match = SOURCE_LINES_PATTERN.search(text)
    if not match:
        return None
    start, end = int(match.group(1)), int(match.group(2))
    return end - start + 1


def is_stub(path: Path) -> bool:
    """True if the file is a likely SRD-splitter stub (chapter intro / framing)."""
    rng = source_lines_range(path)
    return rng is not None and rng <= STUB_LINE_THRESHOLD


def classify_rule_files() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Walk docs/srd/ and partition into substantive vs stub files by chapter.

    Returns (substantive_by_chapter, stubs_by_chapter).
    """
    substantive: dict[str, list[str]] = {}
    stubs: dict[str, list[str]] = {}
    for md in sorted(SRD_DOCS.rglob("*.md")):
        if md.name in SKIP_NAMES:
            continue
        rel = md.relative_to(SRD_DOCS).as_posix()
        chapter = rel.split("/", 1)[0]
        target = stubs if is_stub(md) else substantive
        target.setdefault(chapter, []).append(rel)
    return substantive, stubs


def main() -> None:
    audited = audited_paths()
    substantive, stubs = classify_rule_files()

    print("SRD conformance audit coverage")
    print("=" * 60)

    # Stale-marker check: tests pointing at SRD files that don't exist.
    all_rule_paths = {p for paths in substantive.values() for p in paths} | {
        p for paths in stubs.values() for p in paths
    }
    stale = sorted(set(audited) - all_rule_paths)
    if stale:
        print()
        print("WARNING: markers pointing at missing SRD files:")
        for path in stale:
            for test_file in audited[path]:
                rel_test = test_file.relative_to(ROOT).as_posix()
                print(f"  {path}  (in {rel_test})")

    print()
    print("Audited rule files:")
    if not audited:
        print("  (none yet)")
    else:
        for path in sorted(audited):
            if path not in all_rule_paths:
                continue  # already reported as stale
            test_paths = ", ".join(t.relative_to(ROOT).as_posix() for t in audited[path])
            print(f"  [x] {path}")
            print(f"       -> {test_paths}")

    print()
    print("Prose chapters (conformance audit targets):")
    prose_total = 0
    prose_done = 0
    for chapter in sorted(substantive):
        if chapter in CATALOG_CHAPTERS:
            continue
        files = substantive[chapter]
        done_in_chapter = [f for f in files if f in audited]
        prose_total += len(files)
        prose_done += len(done_in_chapter)
        bar = "#" * len(done_in_chapter) + "-" * (len(files) - len(done_in_chapter))
        print(f"  {chapter:25s}  {len(done_in_chapter):3d} / {len(files):3d}  [{bar}]")

    stub_total = sum(
        len(paths) for chapter, paths in stubs.items() if chapter not in CATALOG_CHAPTERS
    )

    print()
    print(
        f"Prose progress: {prose_done} / {prose_total} files audited (+ {stub_total} stubs held out)"
    )

    print()
    print(f"Likely SRD-splitter stubs (source_lines range <= {STUB_LINE_THRESHOLD}):")
    if not stub_total:
        print("  (none)")
    else:
        for chapter in sorted(stubs):
            if chapter in CATALOG_CHAPTERS:
                continue
            for path in stubs[chapter]:
                print(f"  {path}")

    print()
    print("Catalog chapters (audited via JSON data parity, not this tool):")
    for chapter in sorted(substantive):
        if chapter not in CATALOG_CHAPTERS:
            continue
        files = substantive[chapter]
        print(f"  {chapter:25s}  {len(files):4d} entries")

    print()
    print("Suggested queue (next unaudited prose files):")
    shown = 0
    for chapter in sorted(substantive):
        if chapter in CATALOG_CHAPTERS:
            continue
        for path in substantive[chapter]:
            if path not in audited:
                print(f"  {path}")
                shown += 1
                if shown >= 20:
                    remaining = prose_total - prose_done - shown
                    if remaining > 0:
                        print(f"  ... (and {remaining} more)")
                    return


if __name__ == "__main__":
    main()
