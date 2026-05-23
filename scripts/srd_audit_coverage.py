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

MARKER_PATTERN = re.compile(r'pytest\.mark\.srd\(\s*"([^"]+)"')


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


def rule_files_by_chapter() -> dict[str, list[str]]:
    """Return chapter -> sorted list of SRD-relative paths."""
    out: dict[str, list[str]] = {}
    for md in sorted(SRD_DOCS.rglob("*.md")):
        if md.name in SKIP_NAMES:
            continue
        rel = md.relative_to(SRD_DOCS).as_posix()
        chapter = rel.split("/", 1)[0]
        out.setdefault(chapter, []).append(rel)
    return out


def main() -> None:
    audited = audited_paths()
    by_chapter = rule_files_by_chapter()

    print("SRD conformance audit coverage")
    print("=" * 60)

    # Stale-marker check: tests pointing at SRD files that don't exist.
    all_rule_paths = {p for paths in by_chapter.values() for p in paths}
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
    for chapter in sorted(by_chapter):
        if chapter in CATALOG_CHAPTERS:
            continue
        files = by_chapter[chapter]
        done_in_chapter = [f for f in files if f in audited]
        prose_total += len(files)
        prose_done += len(done_in_chapter)
        bar = "#" * len(done_in_chapter) + "-" * (len(files) - len(done_in_chapter))
        print(f"  {chapter:25s}  {len(done_in_chapter):3d} / {len(files):3d}  [{bar}]")

    print()
    print(f"Prose progress: {prose_done} / {prose_total} files audited")

    print()
    print("Catalog chapters (audited via JSON data parity, not this tool):")
    for chapter in sorted(by_chapter):
        if chapter not in CATALOG_CHAPTERS:
            continue
        files = by_chapter[chapter]
        print(f"  {chapter:25s}  {len(files):4d} entries")

    print()
    print("Suggested queue (next unaudited prose files):")
    shown = 0
    for chapter in sorted(by_chapter):
        if chapter in CATALOG_CHAPTERS:
            continue
        for path in by_chapter[chapter]:
            if path not in audited:
                print(f"  {path}")
                shown += 1
                if shown >= 20:
                    print(f"  ... (and {prose_total - prose_done - 20} more)")
                    return
                continue


if __name__ == "__main__":
    main()
