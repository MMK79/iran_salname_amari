"""Format-independent table model.

Every extractor (docx, converted doc, html grid, html plain-text, pdf) produces
`RawTable`s: a title, the per-column header path, and body rows of
(label, values). Nothing semantic happens here; see `etl.terms` / `etl.facts`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from etl.extract.docx_tables import Para, Table
from etl.normalize import digits, norm, parse_academic_year, to_number

TITLE_RE = re.compile(r"^\s*[-–]?\s*\d{1,3}\s*[-–]\s*\d{1,3}\s*[-–]")
OLD_TITLE_RE = re.compile(r"^\s*\d{1,3}\s*[-–]\s+\S")  # 1353/1355 style "45- ..."


@dataclass
class RawTable:
    yearbook_sh: int
    source_file: str
    source_format: str
    title: str
    table_no: str
    part: int  # 0 for the first physical table under a title, 1.. for continuations
    col_headers: list[str]
    rows: list[tuple[str, list[float | None]]]
    notes: list[str] = field(default_factory=list)
    label_side: str = "first"
    header_source: str = "document"  # or "template:<name>" when headers were inferred

    @property
    def source_table(self) -> str:
        return f"{self.table_no or '?'}#{self.part}"


def table_number(title: str) -> str:
    t = digits(title)
    m = re.match(r"^\s*[-–]?\s*(\d{1,3})\s*[-–]\s*(\d{1,3})", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"^\s*(\d{1,3})\s*[-–]", t)
    return m.group(1) if m else ""


def is_title(text: str) -> bool:
    t = digits(text)
    return bool(TITLE_RE.match(t)) or (bool(OLD_TITLE_RE.match(t)) and len(t) > 12)


def _numeric_ratio(cells: list[str]) -> float:
    ne = [c for c in cells if c.strip()]
    if not ne:
        return 0.0
    return sum(1 for c in ne if to_number(c) is not None or norm(c) in {"-", "…", "×", "××"}) / len(ne)


def grid_to_rawtable(
    grid: list[list[str]],
    *,
    title: str,
    yearbook_sh: int,
    source_file: str,
    source_format: str,
    part: int,
    slash_swapped: bool = True,
) -> RawTable | None:
    grid = [r for r in grid if any(c.strip() for c in r)]
    if len(grid) < 2 or len(grid[0]) < 2:
        return None
    ncol = len(grid[0])
    # which side holds the row labels?
    def textiness(ci: int) -> int:
        return sum(1 for r in grid if r[ci].strip() and to_number(r[ci]) is None)

    label_ci = 0 if textiness(0) >= textiness(ncol - 1) else ncol - 1
    data_cis = [c for c in range(ncol) if c != label_ci]
    # header rows = leading rows that are not mostly numeric (year-like headers count as text)
    h = 0
    while h < len(grid):
        cells = [grid[h][c] for c in data_cis]
        if _numeric_ratio(cells) >= 0.5:
            break
        h += 1
    if h == len(grid):
        return None
    headers = []
    for c in data_cis:
        parts: list[str] = []
        for r in range(h):
            t = grid[r][c].strip()
            if t and (not parts or norm(parts[-1]) != norm(t)):
                parts.append(t)
        headers.append(" > ".join(parts))
    rows = []
    for r in grid[h:]:
        label = r[label_ci].strip()
        vals = [to_number(r[c], slash_swapped=slash_swapped) for c in data_cis]
        if not label and all(v is None for v in vals):
            continue
        rows.append((label, vals))
    return RawTable(
        yearbook_sh=yearbook_sh,
        source_file=source_file,
        source_format=source_format,
        title=title,
        table_no=table_number(title),
        part=part,
        col_headers=headers,
        rows=rows,
        label_side="first" if label_ci == 0 else "last",
    )


def blocks_to_rawtables(
    blocks: list[Para | Table],
    *,
    yearbook_sh: int,
    source_file: str,
    source_format: str,
    default_title: str = "",
    slash_swapped: bool = True,
) -> list[RawTable]:
    """Walk paragraphs+tables in order, attach each table to the most recent title."""
    out: list[RawTable] = []
    title = default_title
    part = 0
    pending_notes: list[str] = []
    last: RawTable | None = None
    for b in blocks:
        if isinstance(b, Para):
            txt = b.text.strip()
            if is_title(txt):
                if last is not None and pending_notes:
                    last.notes.extend(pending_notes)
                pending_notes = []
                base = re.sub(r"\(\s*دنباله\s*\)", "", txt).strip()
                if norm(base) != norm(re.sub(r"\(\s*دنباله\s*\)", "", title)).strip():
                    part = 0
                title = txt
            elif "دنباله" in txt and len(txt) < 40:
                continue
            else:
                pending_notes.append(txt)
        else:
            if not b.rows:
                continue
            # a table whose first cell *is* the title (plain-text html era) is handled elsewhere
            rt = grid_to_rawtable(
                b.rows,
                title=title,
                yearbook_sh=yearbook_sh,
                source_file=source_file,
                source_format=source_format,
                part=part,
                slash_swapped=slash_swapped,
            )
            if last is not None and pending_notes:
                last.notes.extend(pending_notes)
            pending_notes = []
            if rt is not None:
                out.append(rt)
                last = rt
                part += 1
    if last is not None and pending_notes:
        last.notes.extend(pending_notes)
    return out


def table_year(rt: RawTable) -> int:
    """Academic year the non-year rows (provinces, categories) refer to."""
    ys = [y for y in (parse_academic_year(lbl) for lbl, _ in rt.rows) if y]
    if ys:
        return max(ys)
    tys = [int(y) for y in re.findall(r"1[34]\d\d", digits(rt.title))]
    if tys:
        # "سال تحصیلی 99-1398" or "1398-1399" -> start year
        return min(tys) if len(tys) > 1 and max(tys) - min(tys) == 1 else max(tys)
    return rt.yearbook_sh
