# ABOUTME: Splits docs/SRD_CC_v5.2.1.txt into per-subsection Markdown files
# ABOUTME: under docs/srd/ for citation during development. Idempotent; safe to re-run.

"""Split the official WotC SRD 5.2.1 plain-text dump into per-subsection Markdown.

The SRD is distributed as a single 1.3 MB plain-text file extracted from the
official PDF. For development reference we want stable, citable paths like
``docs/srd/combat/ranged-attacks.md``.

Strategy
--------
1. Parse the Table of Contents to extract a hierarchical list of (title, page)
   pairs. The TOC uses leader dots and is sometimes laid out in two columns,
   producing lines with two ``title ... page`` pairs glued together.
2. Walk the body, tracking the running page number from the page-footer
   pattern ``<page>\\n\\nSystem Reference Document 5.2.1``. For each TOC entry,
   find the first bare-line occurrence of its title on the expected page (the
   page number from the TOC) -- this disambiguates titles that appear in
   multiple contexts.
3. Slice the body between consecutive heading line numbers. Each slice
   becomes one Markdown file.
4. Three sections are catalogs (Spell Descriptions, Monsters A-Z + Animals,
   Magic Items A-Z) and get a second-pass split using format-specific
   detectors so each spell / monster / magic item lands in its own file.

The script is idempotent: the output tree is wiped and rebuilt on every run.
"""

from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

SRD_VERSION = "5.2.1"
SRD_LICENSE = "CC-BY-4.0"
ATTRIBUTION = (
    "This work includes material from the System Reference Document 5.2.1 "
    "(\"SRD 5.2.1\") by Wizards of the Coast LLC, available at "
    "https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the "
    "Creative Commons Attribution 4.0 International License, available at "
    "https://creativecommons.org/licenses/by/4.0/legalcode."
)

TOC_START = 24
# The TOC contains a main listing followed by an "Index of Stat Blocks"
# (alphabetical monster index). We only want the main listing here -- monster
# entries are emitted by the catalog detector against the body. The end is
# detected dynamically by locating the "Index of Stat" line.
TOC_END_FALLBACK = 510

# Top-level chapters in order, with the printed page each starts on. The page
# is used to disambiguate chapter titles that also appear as subsection titles
# elsewhere in the TOC (e.g. "Magic Items" is both an Equipment subsection on
# page 102 and a major chapter on page 204).
CHAPTERS: list[tuple[str, str, int]] = [
    ("Playing the Game", "playing-the-game", 5),
    ("Character Creation", "character-creation", 19),
    ("Classes", "classes", 28),
    ("Character Origins", "character-origins", 83),
    ("Feats", "feats", 87),
    ("Equipment", "equipment", 89),
    ("Spells", "spells", 104),
    ("Rules Glossary", "rules-glossary", 176),
    ("Gameplay Toolbox", "gameplay-toolbox", 192),
    ("Magic Items", "magic-items", 204),
    ("Monsters", "monsters", 254),
    ("Animals", "animals", 344),
]

CATALOG_SECTIONS = {
    "Spell Descriptions": "spells",
    "Monsters A–Z": "monsters",  # unicode en-dash, as in SRD source
    "Animals": "animals",
    "Magic Items A–Z": "magic-items",
}

# Schools of magic for the Spell Descriptions detector.
SCHOOLS = {
    "Abjuration",
    "Conjuration",
    "Divination",
    "Enchantment",
    "Evocation",
    "Illusion",
    "Necromancy",
    "Transmutation",
}

# Magic item categories (the first word of the category line in an item entry).
ITEM_CATEGORIES = {
    "Armor",
    "Weapon",
    "Wondrous",
    "Potion",
    "Ring",
    "Rod",
    "Scroll",
    "Staff",
    "Wand",
    "Ammunition",
}


# ---------------------------------------------------------------------------
# Data classes


@dataclass
class TocEntry:
    title: str
    page: int
    chapter: str  # chapter slug
    is_chapter: bool = False
    # Filled in during body matching.
    body_line: int | None = None  # 1-indexed


@dataclass
class Section:
    """A resolved section: a slice of body lines belonging to one TOC entry."""

    entry: TocEntry
    start_line: int  # 1-indexed, inclusive (heading line)
    end_line: int  # 1-indexed, exclusive
    body_lines: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# TOC parsing

# Match one ``<title>...<page>`` pair. Title runs up to a sequence that looks
# like leader dots / spaces, then digits. Allow embedded periods (e.g. "U.").
_TOC_PAIR = re.compile(
    r"""
    (?P<title>[A-Za-z][^.]*?(?:\.[A-Za-z'][^.]*?)*[A-Za-z\'\)])  # title
    [\s.]{2,}                                                    # leader dots
    (?P<page>\d{1,3})                                            # page
    """,
    re.VERBOSE,
)


def parse_toc(lines: list[str]) -> list[TocEntry]:
    """Return ordered TOC entries with chapter assignment.

    The TOC region contains both the main contents listing and the
    "Index of Stat Blocks" alphabetical monster index. We slice at the
    "Index of Stat" line so only main-listing entries are returned;
    individual monsters are emitted by the catalog detector instead.
    """
    # Locate the end of the main TOC: the line that says "Index of Stat".
    toc_end = TOC_END_FALLBACK
    for i, raw in enumerate(lines[TOC_START - 1 : TOC_END_FALLBACK], start=TOC_START):
        if raw.strip() == "Index of Stat":
            toc_end = i - 1
            break

    # TOC entries with long titles wrap across two physical lines. In the
    # early single-column part of the TOC this is safe to undo by joining
    # consecutive lines (title fragment + dotted-page tail). In the later
    # two-column part, the "continuation" line is actually the other
    # column's entry, so joining there corrupts both rows. Switch to
    # no-join mode as soon as a line containing TWO leader-dot/page pairs
    # appears (the unambiguous two-column signal).
    toc_block = lines[TOC_START - 1 : toc_end]
    joined: list[str] = []
    two_column = False
    i = 0
    while i < len(toc_block):
        cur = toc_block[i].rstrip()
        nxt = toc_block[i + 1].rstrip() if i + 1 < len(toc_block) else ""
        if not two_column and len(_TOC_PAIR.findall(cur)) >= 2:
            two_column = True
        if (
            not two_column
            and cur
            and not _TOC_PAIR.search(cur)
            and cur[0].isupper()
            and nxt
            and _TOC_PAIR.match(nxt)
        ):
            joined.append(cur + " " + nxt.lstrip())
            i += 2
            continue
        joined.append(cur)
        i += 1

    raw_pairs: list[tuple[str, int]] = []
    for raw_line in joined:
        for match in _TOC_PAIR.finditer(raw_line):
            title = _clean_toc_title(match.group("title"))
            page = int(match.group("page"))
            if not title:
                continue
            raw_pairs.append((title, page))

    # Hand-fixup for two-column TOC artifacts. The Monk subclass row has
    # "Monk Subclass: Warrior of the Open" wrapping into column 1 of a later
    # row where the leftover "Hand 52" appears, separated by an unrelated
    # column-2 entry. This is the only such case in the published TOC; rather
    # than build a column tokenizer, we patch it explicitly.
    fixed_pairs: list[tuple[str, int]] = []
    for title, page in raw_pairs:
        if title == "Hand" and page == 52:
            fixed_pairs.append(("Monk Subclass: Warrior of the Open Hand", 52))
            continue
        fixed_pairs.append((title, page))
    raw_pairs = fixed_pairs

    # PDF-to-text rendered the TOC as two columns, producing lines with two
    # ``title ... page`` pairs glued together. Within a column entries are
    # in page order, but across columns we see e.g. "Fighter 47" followed by
    # "Spells 104" on the same line, then "Fighter Subclass 49" on the next
    # line -- which produces a non-monotonic page sequence. Sort by page
    # (stable) to restore document order; ties keep the original order so
    # entries on the same page stay in the order they appear in the source.
    raw_pairs.sort(key=lambda p: p[1])

    # Build a chapter lookup keyed by (title, expected_page) so that a title
    # that also appears as a subsection on a different page isn't confused
    # with the chapter itself. Allow ±1 page slack on the chapter page.
    chapter_by_key = {
        (title, page): slug for title, slug, page in CHAPTERS
    }

    def _chapter_slug_for(title: str, page: int) -> str | None:
        for (chap_title, chap_page), slug in chapter_by_key.items():
            if title == chap_title and abs(page - chap_page) <= 1:
                return slug
        return None

    entries: list[TocEntry] = []
    current_chapter_slug = "front-matter"
    for title, page in raw_pairs:
        chap_slug = _chapter_slug_for(title, page)
        if chap_slug is not None:
            current_chapter_slug = chap_slug
            entries.append(
                TocEntry(
                    title=title,
                    page=page,
                    chapter=current_chapter_slug,
                    is_chapter=True,
                )
            )
        else:
            entries.append(
                TocEntry(title=title, page=page, chapter=current_chapter_slug)
            )

    return entries


def _clean_toc_title(raw: str) -> str:
    """Strip trailing punctuation/whitespace artifacts from TOC titles."""
    title = raw.strip().rstrip(".").rstrip()
    # Some titles end with a stray period like "Bard." -- but "D20" and
    # "A-Z" are legitimate. The rstrip above already handles a single
    # trailing period.
    # Collapse internal whitespace runs (PDF can introduce double spaces).
    title = re.sub(r"\s+", " ", title)
    # Drop titles that are obvious TOC artifacts.
    if title in {"Contents", "Source", "Score", "Modifier", "Ability", "Meaning"}:
        return ""
    return title


# ---------------------------------------------------------------------------
# Page anchoring


def build_page_index(lines: list[str]) -> dict[int, int]:
    """Map page-number -> first body line on that page.

    The standard page footer is ``<page>\\n\\nSystem Reference Document 5.2.1``
    at the bottom of each page, where the integer is the page just ended.
    Some pages (chapter-start, tables that extend to the page edge) omit the
    integer footer, leaving gaps in the anchor set.

    We collect every anchor we can find from explicit footers, then fill in
    missing pages by linear interpolation between adjacent known anchors.
    This gives an APPROXIMATE line number for every page in the document,
    which is good enough for windowed heading lookup.
    """
    anchors: dict[int, int] = {1: 1}
    n = len(lines)
    i = 0
    while i < n:
        stripped = lines[i].strip()
        if stripped.isdigit() and 0 < int(stripped) < 500:
            if i + 2 < n and lines[i + 2].strip() == "System Reference Document 5.2.1":
                page_just_ended = int(stripped)
                next_page = page_just_ended + 1
                j = i + 3
                while j < n and not lines[j].strip():
                    j += 1
                if j < n:
                    anchors.setdefault(next_page, j + 1)
                i = j
                continue
        i += 1

    # Interpolate missing pages from neighboring anchors.
    if not anchors:
        return {}
    max_page = max(anchors)
    sorted_pages = sorted(anchors)
    filled: dict[int, int] = dict(anchors)
    for p in range(1, max_page + 1):
        if p in filled:
            continue
        # Find nearest anchor before and after.
        before = max((q for q in sorted_pages if q < p), default=None)
        after = min((q for q in sorted_pages if q > p), default=None)
        if before is None and after is None:
            continue
        if before is None:
            filled[p] = filled[after]
            continue
        if after is None:
            filled[p] = filled[before]
            continue
        # Linear interpolation.
        span_pages = after - before
        span_lines = filled[after] - filled[before]
        offset = (p - before) * span_lines // span_pages
        filled[p] = filled[before] + offset
    return filled


# ---------------------------------------------------------------------------
# Heading matching


def match_headings_to_body(
    entries: list[TocEntry], lines: list[str], page_to_line: dict[int, int]
) -> list[TocEntry]:
    """For each TOC entry, find its bare-line heading in the body.

    Two-pass strategy to avoid cascading failures:

    1. Match chapter headings first. Each chapter has a distinct title that
       appears as a bare line at its known page; pick the first occurrence at
       or after the previous chapter's match line, preferring the candidate
       closest to the page anchor.
    2. For each subsection, restrict the search to its containing chapter's
       body range, and pick the candidate closest to the TOC page anchor.

    Subsections that the PDF-to-text conversion dropped (heading not present
    as a bare line in the body) are skipped with a logged warning.
    """
    n = len(lines)

    chapters = [e for e in entries if e.is_chapter]
    non_chapters = [e for e in entries if not e.is_chapter]

    # --- Pass 1: chapters ---
    cursor = 1
    for chapter in chapters:
        anchor = page_to_line.get(chapter.page, cursor)
        candidates = _find_all_headings(chapter.title, lines, cursor, n)
        if not candidates and " " in chapter.title:
            # Some chapter titles render across two physical lines in the
            # PDF (e.g. "Character" then "Creation" on consecutive lines).
            # Try matching the title's words on consecutive bare lines.
            candidates = _find_wrapped_headings(
                chapter.title, lines, cursor, n
            )
        if not candidates:
            print(
                f"  ! could not locate chapter heading: {chapter.title!r} "
                f"(page {chapter.page})"
            )
            continue
        chapter.body_line = min(candidates, key=lambda c: abs(c - anchor))
        cursor = chapter.body_line + 1

    # Build chapter body ranges.
    located_chapters = [c for c in chapters if c.body_line is not None]
    chapter_ranges: dict[str, tuple[int, int]] = {}
    for i, ch in enumerate(located_chapters):
        start = ch.body_line or 1
        end = (
            located_chapters[i + 1].body_line
            if i + 1 < len(located_chapters)
            else n
        ) or n
        chapter_ranges[ch.chapter] = (start, end)

    # --- Pass 2: subsections, scoped to chapter ranges ---
    for entry in non_chapters:
        if entry.chapter not in chapter_ranges:
            continue
        start, end = chapter_ranges[entry.chapter]
        anchor = page_to_line.get(entry.page, start)
        candidates = _find_all_headings(entry.title, lines, start + 1, end)
        if not candidates and " " in entry.title:
            # Subsection headings can also render wrapped in the body --
            # e.g. "Barbarian Subclass:\nPath of the Berserker".
            candidates = _find_wrapped_headings(
                entry.title, lines, start + 1, end
            )
        if not candidates:
            print(
                f"  ! could not locate heading: {entry.title!r} "
                f"(page {entry.page})"
            )
            continue
        entry.body_line = min(candidates, key=lambda c: abs(c - anchor))

    # Return all entries with a body line, sorted by body line so the
    # downstream slicer can pair consecutive headings.
    located = [e for e in entries if e.body_line is not None]
    located.sort(key=lambda e: e.body_line or 0)
    return located


def _find_heading(
    title: str, lines: list[str], start: int, end: int
) -> int | None:
    """Find the first 1-indexed line in [start, end] where the line equals title."""
    target = title
    for idx in range(start - 1, min(end, len(lines))):
        if lines[idx].strip() == target:
            return idx + 1
    return None


def _find_all_headings(
    title: str, lines: list[str], start: int, end: int
) -> list[int]:
    """Return all 1-indexed lines in [start, end] where the stripped line equals title."""
    target = title
    out: list[int] = []
    for idx in range(start - 1, min(end, len(lines))):
        if lines[idx].strip() == target:
            out.append(idx + 1)
    return out


def _find_wrapped_headings(
    title: str, lines: list[str], start: int, end: int
) -> list[int]:
    """Return 1-indexed lines where the title appears split across consecutive bare lines.

    Headings render across multiple physical lines in the PDF text extract
    because the display font wraps. The wrap can split anywhere (word
    boundary or after a colon), so we look for runs of consecutive
    non-empty lines that, joined with single spaces, equal the title. We
    try wraps of 2, 3, or 4 lines.
    """
    title_norm = " ".join(title.split())
    out: list[int] = []
    cap = min(end, len(lines))
    for idx in range(start - 1, cap):
        for run_len in (2, 3, 4):
            if idx + run_len > cap:
                break
            parts = [lines[idx + k].strip() for k in range(run_len)]
            if any(not p for p in parts):
                continue
            joined = " ".join(parts)
            if " ".join(joined.split()) == title_norm:
                out.append(idx + 1)
                break
    return out


# ---------------------------------------------------------------------------
# Section slicing


def build_sections(matched: list[TocEntry], total_lines: int) -> list[Section]:
    sections: list[Section] = []
    for i, entry in enumerate(matched):
        start = entry.body_line or 0
        if i + 1 < len(matched):
            end = matched[i + 1].body_line or total_lines + 1
        else:
            end = total_lines + 1
        sections.append(Section(entry=entry, start_line=start, end_line=end))
    return sections


def attach_body(sections: list[Section], lines: list[str]) -> None:
    for s in sections:
        # Skip the heading line itself; body is what follows up to (but not
        # including) the next heading.
        s.body_lines = lines[s.start_line : s.end_line - 1]


# ---------------------------------------------------------------------------
# Body cleaning


_PAGE_FOOTER_RE = re.compile(r"^\s*\d{1,3}\s*$")
_RUNNING_HEADER_RE = re.compile(r"^System Reference Document 5\.2\.1$")


def clean_body(raw_lines: list[str]) -> str:
    """Strip page-footer artifacts and collapse blank-line runs.

    Removes:
    - The complete footer triple (blank, page-num, blank, running-header, blank).
    - Stray running-header lines that got separated from their page-num by
      column-bleed in two-column sections.
    - Stray bare integer lines surrounded by blanks that match the page-num
      pattern (also from column-bleed).
    """
    out: list[str] = []
    i = 0
    n = len(raw_lines)
    while i < n:
        line = raw_lines[i].rstrip()
        # Stray running-header line on its own.
        if _RUNNING_HEADER_RE.match(line.strip()):
            while out and not out[-1].strip():
                out.pop()
            i += 1
            while i < n and not raw_lines[i].strip():
                i += 1
            out.append("")
            continue
        # Bare page-number line: only treat as a footer if it's surrounded by
        # blanks AND followed soon (within 6 lines) by a running header.
        if (
            _PAGE_FOOTER_RE.match(line)
            and (i == 0 or not raw_lines[i - 1].strip())
            and any(
                _RUNNING_HEADER_RE.match(raw_lines[k].strip())
                for k in range(i + 1, min(i + 7, n))
            )
        ):
            while out and not out[-1].strip():
                out.pop()
            i += 1
            while i < n and not raw_lines[i].strip():
                i += 1
            out.append("")
            continue
        out.append(line)
        i += 1
    # Collapse 3+ consecutive blanks to a single blank.
    collapsed: list[str] = []
    prev_blank = False
    for line in out:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        collapsed.append(line)
        prev_blank = is_blank
    # Trim leading/trailing blanks.
    while collapsed and not collapsed[0].strip():
        collapsed.pop(0)
    while collapsed and not collapsed[-1].strip():
        collapsed.pop()
    return "\n".join(collapsed) + "\n"


# ---------------------------------------------------------------------------
# Catalog detection (spells, monsters, items)


def detect_spell_entries(body_lines: list[str], offset: int) -> list[tuple[str, int]]:
    """Return (spell_name, line_offset_within_body) pairs.

    A spell entry begins where a line N contains a title-case name and line N+2
    starts with ``Level <n> <School>`` or ``<School> Cantrip``.
    The ``offset`` argument is the absolute body line where these lines start
    (unused for the result -- offsets are local to body_lines).
    """
    entries: list[tuple[str, int]] = []
    n = len(body_lines)
    for i in range(n):
        line = body_lines[i].strip()
        if not line or not _looks_like_proper_name(line):
            continue
        # Find the next non-blank line.
        j = i + 1
        while j < n and not body_lines[j].strip():
            j += 1
        if j >= n:
            continue
        next_line = body_lines[j].strip()
        if _is_spell_meta_line(next_line):
            entries.append((line, i))
    return entries


def _is_spell_meta_line(line: str) -> bool:
    if not line:
        return False
    # "Level 3 Evocation (Sorcerer, Wizard)" or "Conjuration Cantrip (Bard, ...)"
    m_level = re.match(r"^Level\s+\d+\s+([A-Z][a-z]+)", line)
    if m_level and m_level.group(1) in SCHOOLS:
        return True
    m_cantrip = re.match(r"^([A-Z][a-z]+)\s+Cantrip\b", line)
    if m_cantrip and m_cantrip.group(1) in SCHOOLS:
        return True
    return False


def detect_monster_entries(body_lines: list[str]) -> list[tuple[str, int]]:
    """Detect monster stat block entries.

    Pattern: a bare proper-name line whose next non-blank line starts with a
    creature-size keyword (Tiny/Small/Medium/Large/Huge/Gargantuan). Some
    entries duplicate the name on the next line as a stat-block label; we
    look past that to the size line.
    """
    entries: list[tuple[str, int]] = []
    n = len(body_lines)
    for i in range(n - 1):
        name = body_lines[i].strip()
        if not name or not _looks_like_proper_name(name):
            continue
        # Find the next non-blank line.
        j = i + 1
        while j < n and not body_lines[j].strip():
            j += 1
        if j >= n:
            continue
        # Skip a duplicate-name line (stat-block label) if present.
        if body_lines[j].strip() == name:
            j += 1
            while j < n and not body_lines[j].strip():
                j += 1
            if j >= n:
                continue
        if _looks_like_creature_meta(body_lines[j].strip()):
            entries.append((name, i))
    return entries


_SIZE_PREFIX = re.compile(
    r"^(Tiny|Small|Medium|Large|Huge|Gargantuan)\b", re.IGNORECASE
)


def _looks_like_creature_meta(line: str) -> bool:
    return bool(_SIZE_PREFIX.match(line))


def detect_magic_item_entries(body_lines: list[str]) -> list[tuple[str, int]]:
    """Detect magic item entries.

    Pattern: ``<Name>\\n\\n<Category>...<Rarity>``. The category line's first
    word is one of ITEM_CATEGORIES. The rarity can land on the same line or
    wrap to the next; we check the next 2 lines combined.
    """
    rarities = ("Common", "Uncommon", "Rare", "Legendary", "Artifact")
    entries: list[tuple[str, int]] = []
    n = len(body_lines)
    for i in range(n):
        name = body_lines[i].strip()
        if not name or not _looks_like_proper_name(name):
            continue
        j = i + 1
        while j < n and not body_lines[j].strip():
            j += 1
        if j >= n:
            continue
        meta = body_lines[j].strip()
        first_word = meta.split()[0] if meta else ""
        if first_word not in ITEM_CATEGORIES:
            continue
        # Concatenate up to the next two non-blank lines to find rarity.
        combined = meta
        k = j + 1
        added = 0
        while k < n and added < 2:
            piece = body_lines[k].strip()
            if piece:
                combined += " " + piece
                added += 1
            k += 1
        if any(r in combined for r in rarities):
            entries.append((name, i))
    return entries


_PROPER_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9' \-–—,+/&()]+$")

# Lines that look like proper names but are actually stat-block section
# headers inside an entry (Actions, Traits, etc.) or rules-glossary list
# items. Rejected as catalog entry names.
_STAT_BLOCK_SECTIONS = frozenset(
    {
        "Actions",
        "Bonus Actions",
        "Reactions",
        "Legendary Actions",
        "Legendary Resistance",
        "Spells",
        "Spellcasting",
        "Innate Spellcasting",
        "Traits",
        "Skills",
        "Senses",
        "Languages",
        "Damage Resistances",
        "Damage Immunities",
        "Condition Immunities",
        "Damage Vulnerabilities",
        "Equipment",
        "Description",
        "Creature Type",
        "Habitat",
        "Treasure",
    }
)


def _looks_like_proper_name(line: str) -> bool:
    if len(line) < 2 or len(line) > 80:
        return False
    if line.endswith((".", ":", "?", "!")):
        return False
    if not _PROPER_NAME_RE.match(line):
        return False
    if line in _STAT_BLOCK_SECTIONS:
        return False
    # Reject creature-meta lines that start with a size keyword.
    if _SIZE_PREFIX.match(line):
        return False
    # Reject lines that read as sentence fragments. We look for unambiguous
    # sentence signals -- a lowercase function word at the start of an
    # internal word that doesn't appear in published item/spell names. The
    # list intentionally omits "or" because it appears legitimately in names
    # like "Ammunition, +1, +2, or +3".
    if re.search(r"\b(the|but|when|you|your)\b", line):
        return False
    return True


# ---------------------------------------------------------------------------
# Output


def slugify(text: str) -> str:
    text = text.lower()
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "untitled"


def write_section_file(
    out_root: Path,
    chapter_slug: str,
    section_slug: str,
    title: str,
    body: str,
    *,
    source_lines: tuple[int, int],
    source_pages: tuple[int, int | None],
    parent: str | None = None,
) -> Path:
    chapter_dir = out_root / chapter_slug
    chapter_dir.mkdir(parents=True, exist_ok=True)
    path = chapter_dir / f"{section_slug}.md"
    frontmatter = [
        "---",
        f"source: SRD_CC_v{SRD_VERSION}.txt",
        f"source_lines: {source_lines[0]}-{source_lines[1]}",
        f"source_pages: {source_pages[0]}",
        f"srd_chapter: {chapter_slug}",
        f"srd_section: {title}",
    ]
    if parent:
        frontmatter.append(f"parent: {parent}")
    frontmatter.append("license: CC-BY-4.0")
    frontmatter.append("---")
    content = "\n".join(frontmatter) + f"\n\n# {title}\n\n{body}\n"
    path.write_text(content, encoding="utf-8")
    return path


def write_chapter_index(
    out_root: Path,
    chapter_slug: str,
    chapter_title: str,
    section_titles: list[tuple[str, str]],  # (title, slug)
) -> None:
    chapter_dir = out_root / chapter_slug
    chapter_dir.mkdir(parents=True, exist_ok=True)
    path = chapter_dir / "_index.md"
    lines = [
        "---",
        f"srd_chapter: {chapter_slug}",
        f"srd_chapter_title: {chapter_title}",
        f"source: SRD_CC_v{SRD_VERSION}.txt",
        "license: CC-BY-4.0",
        "---",
        "",
        f"# {chapter_title}",
        "",
        f"Sections in this chapter (from SRD {SRD_VERSION}):",
        "",
    ]
    for title, slug in section_titles:
        lines.append(f"- [{title}]({slug}.md)")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("docs/SRD_CC_v5.2.1.txt"),
        help="Path to the SRD plain-text source file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/srd"),
        help="Output directory for the Markdown tree.",
    )
    args = parser.parse_args()

    if not args.source.exists():
        print(f"Source not found: {args.source}")
        return 1

    raw = args.source.read_text(encoding="utf-8")
    lines = raw.splitlines()
    total_lines = len(lines)

    print(f"Loaded {total_lines:,} lines from {args.source}")

    # 1. TOC
    toc_entries = parse_toc(lines)
    print(f"Parsed {len(toc_entries)} TOC entries")

    # 2. Page index
    page_to_line = build_page_index(lines)
    print(f"Indexed {len(page_to_line)} page boundaries")

    # 3. Match TOC headings to body
    matched = match_headings_to_body(toc_entries, lines, page_to_line)
    print(f"Matched {len(matched)} / {len(toc_entries)} headings")

    # 4. Build sections + attach body slices
    sections = build_sections(matched, total_lines)
    attach_body(sections, lines)

    # 5. Wipe and rebuild output tree
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True, exist_ok=True)

    # 6. Write files per-chapter, handling catalog sub-splits.
    chapter_titles_by_slug = {slug: title for title, slug, _ in CHAPTERS}
    chapter_section_index: dict[str, list[tuple[str, str]]] = {
        slug: [] for _, slug, _ in CHAPTERS
    }

    total_files = 0
    for section in sections:
        entry = section.entry
        body_text = clean_body(section.body_lines)
        if not body_text.strip():
            continue
        # Catalog detection.
        if entry.title in CATALOG_SECTIONS:
            written = _emit_catalog(
                args.out,
                CATALOG_SECTIONS[entry.title],
                entry.title,
                section,
                lines,
            )
            for slug, title in written:
                chapter_section_index[CATALOG_SECTIONS[entry.title]].append(
                    (title, slug)
                )
            total_files += len(written)
            continue
        # Regular section.
        section_slug = slugify(entry.title)
        # Avoid collisions: prefix with sequence if duplicate.
        existing = chapter_section_index[entry.chapter]
        if any(s == section_slug for _, s in existing):
            section_slug = f"{section_slug}-{len(existing) + 1}"
        write_section_file(
            args.out,
            entry.chapter,
            section_slug,
            entry.title,
            body_text,
            source_lines=(section.start_line, section.end_line - 1),
            source_pages=(entry.page, None),
        )
        chapter_section_index[entry.chapter].append((entry.title, section_slug))
        total_files += 1

    # 7. Per-chapter indexes.
    for slug, sections_listed in chapter_section_index.items():
        if not sections_listed:
            continue
        title = chapter_titles_by_slug.get(slug, slug.replace("-", " ").title())
        write_chapter_index(args.out, slug, title, sections_listed)

    # 8. Root README.
    _write_root_readme(args.out, len(chapter_section_index), total_files)

    print(f"Wrote {total_files} section files to {args.out}")
    return 0


def _emit_catalog(
    out_root: Path,
    chapter_slug: str,
    catalog_title: str,
    section: Section,
    all_lines: list[str],
) -> list[tuple[str, str]]:
    """Write per-entry files for a catalog section.

    Returns a list of (slug, title) for index building.
    """
    body_lines = section.body_lines
    if chapter_slug == "spells":
        entries = detect_spell_entries(body_lines, section.start_line)
    elif chapter_slug in {"monsters", "animals"}:
        entries = detect_monster_entries(body_lines)
    elif chapter_slug == "magic-items":
        entries = detect_magic_item_entries(body_lines)
    else:
        entries = []

    if not entries:
        # Fall back: write the whole section as one file.
        body_text = clean_body(body_lines)
        slug = slugify(catalog_title)
        write_section_file(
            out_root,
            chapter_slug,
            slug,
            catalog_title,
            body_text,
            source_lines=(section.start_line, section.end_line - 1),
            source_pages=(section.entry.page, None),
        )
        return [(slug, catalog_title)]

    written: list[tuple[str, str]] = []
    for i, (name, local_offset) in enumerate(entries):
        next_offset = entries[i + 1][1] if i + 1 < len(entries) else len(body_lines)
        entry_body_lines = body_lines[local_offset + 1 : next_offset]
        body_text = clean_body(entry_body_lines)
        if not body_text.strip():
            continue
        slug = slugify(name)
        if any(s == slug for s, _ in written):
            slug = f"{slug}-{i}"
        abs_start = section.start_line + local_offset
        abs_end = section.start_line + next_offset - 1
        write_section_file(
            out_root,
            chapter_slug,
            slug,
            name,
            body_text,
            source_lines=(abs_start, abs_end),
            source_pages=(section.entry.page, None),
            parent=catalog_title,
        )
        written.append((slug, name))
    return written


def _write_root_readme(out_root: Path, chapter_count: int, file_count: int) -> None:
    readme = out_root / "README.md"
    content = f"""# D&D 5E SRD — Development Reference

Per-subsection Markdown split of the official **Wizards of the Coast System
Reference Document {SRD_VERSION}** ({SRD_LICENSE}). The split is generated by
`scripts/split_srd.py` from `docs/SRD_CC_v{SRD_VERSION}.txt`; do not edit
files in this tree by hand — re-run the splitter instead.

## Attribution

{ATTRIBUTION}

## Why this exists

When building game features we need to cite the canonical rules text. The
plain-text source is 1.3 MB / 60k lines, too large for an LLM context window
and impractical to grep. This tree gives each subsection a stable file path
suitable for inline citation in code comments and PR descriptions.

## Citation conventions

Cite by relative path with a heading anchor when narrowing matters:

> Per `docs/srd/playing-the-game/ranged-attacks.md`, a ranged attack roll
> has Disadvantage when the target is beyond normal range.

For verbatim quotes in a commit body, reference the `source_lines` range in
the file's YAML frontmatter so the original passage can be re-found in the
SRD source if the split changes.

## Regenerating

```bash
uv run python scripts/split_srd.py
```

The output tree is wiped and rebuilt on every run; it is checked into git so
contributors don't need to run the script to read the rules.

## Known limitations (catalog files)

The SRD source is a plain-text dump of a two-column PDF. For the prose
chapters (Playing the Game, Combat, Exploration, etc.) the columns flow
predictably and the split is clean. For the **catalog** chapters where each
entry is a stat block — Monsters A–Z, Animals, Magic Items A–Z — the text
extraction interleaves content from adjacent columns. As a result some
catalog files contain bleed from neighboring entries (e.g. an unrelated
creature name or stat-block fragment embedded mid-paragraph). Treat catalog
files as a **convenience reference** for prose; for authoritative monster
stats, use the structured JSON under `dnd-engine/dnd_engine/data/srd/`.

Spell description files (`spells/*.md`) are clean — the Spell Descriptions
section is single-column in the source PDF.

## Contents

{chapter_count} chapters, {file_count} section files. See each
`<chapter>/_index.md` for the section list.
"""
    readme.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
