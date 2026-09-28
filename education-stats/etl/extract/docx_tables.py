"""Fast .docx reader: yields paragraphs and tables (as dense grids) in body order.

python-docx's `table.cells` is quadratic on large merged tables, so we walk the XML
directly with lxml. Horizontal merges (gridSpan) and vertical merges (vMerge) are
expanded so every grid cell carries the text of its merged origin.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Para:
    text: str


@dataclass
class Table:
    index: int
    rows: list[list[str]] = field(default_factory=list)


def _text(el) -> str:
    parts = []
    for node in el.iter(f"{W}t", f"{W}tab", f"{W}br"):
        if node.tag == f"{W}t":
            parts.append(node.text or "")
        else:
            parts.append(" ")
    return "".join(parts).strip()


_SNAP = 80  # twips; grid columns narrower than this are layout slivers, not data columns


def _int(el, attr: str, default: int) -> int:
    try:
        return int(el.get(f"{W}{attr}", default))
    except (TypeError, ValueError):
        return default


def _table_grid(tbl) -> list[list[str]]:
    """Dense grid of a Word table, aligned by *horizontal position*.

    Header and body rows often disagree on gridSpan (Word inserts 9-22 twip sliver
    columns), so counting grid columns misaligns values and headers (seen in 1395).
    We place every cell at its x-extent from <w:tblGrid>, snap boundaries that are
    closer than _SNAP twips, and build the grid on the snapped boundaries.
    """
    gridcols = [_int(g, "w", 0) for g in tbl.findall(f"{W}tblGrid/{W}gridCol")]
    xs = [0]
    for w in gridcols:
        xs.append(xs[-1] + max(w, 0))

    def xpos(col: int) -> int:
        return xs[min(col, len(xs) - 1)] if gridcols else col * 1000

    rows: list[list[tuple[int, int, str, str | None]]] = []
    for tr in tbl.iterchildren(f"{W}tr"):
        gb = tr.find(f"{W}trPr/{W}gridBefore")
        col = _int(gb, "val", 0) if gb is not None else 0
        cells = []
        for tc in tr.iterchildren(f"{W}tc"):
            tcpr = tc.find(f"{W}tcPr")
            span, vmerge = 1, None
            if tcpr is not None:
                gs = tcpr.find(f"{W}gridSpan")
                if gs is not None:
                    span = _int(gs, "val", 1)
                vm = tcpr.find(f"{W}vMerge")
                if vm is not None:
                    vmerge = vm.get(f"{W}val", "continue")
            txt = " ".join(_text(p) for p in tc.iterchildren(f"{W}p")).strip()
            cells.append((xpos(col), xpos(col + span), txt, vmerge))
            col += span
        rows.append(cells)
    # snapped column boundaries
    bounds = sorted({x for r in rows for c in r for x in (c[0], c[1])})
    snapped: list[int] = []
    for b in bounds:
        if not snapped or b - snapped[-1] >= _SNAP:
            snapped.append(b)
    if len(snapped) < 2:
        return []

    def idx(x: int) -> int:
        return min(range(len(snapped)), key=lambda i: abs(snapped[i] - x))

    ncol = len(snapped) - 1
    grid: list[list[str]] = []
    vorigin: dict[int, str] = {}
    for cells in rows:
        row = [""] * ncol
        for x0, x1, txt, vmerge in cells:
            a, b = idx(x0), idx(x1)
            if b <= a:
                continue
            if vmerge == "continue":
                txt = vorigin.get(a, "")
            for k in range(a, b):
                if vmerge == "restart":
                    vorigin[k] = txt
                elif vmerge is None:
                    vorigin.pop(k, None)
                row[k] = txt
        grid.append(row)
    # collapse columns that are the same cell in every row (a body cell spanning two header columns)
    keep = [0]
    for c in range(1, ncol):
        if any(r[c] != r[keep[-1]] for r in grid):
            keep.append(c)
        else:
            continue
    return [[r[c] for c in keep] for r in grid]


def read_blocks(path: str | Path) -> list[Para | Table]:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = etree.fromstring(xml, parser=etree.XMLParser(huge_tree=True))
    body = root.find(f"{W}body")
    out: list[Para | Table] = []
    ti = 0

    def walk(parent):
        nonlocal ti
        for el in parent.iterchildren():
            if el.tag == f"{W}p":
                t = _text(el)
                if t:
                    out.append(Para(t))
            elif el.tag == f"{W}tbl":
                if el.find(f".//{W}tc/{W}tbl") is not None:
                    # layout table wrapping real tables (1387 .doc conversion): descend into cells
                    for tc in el.iter(f"{W}tc"):
                        if tc.getparent().getparent() is el:
                            walk(tc)
                    continue
                out.append(Table(ti, _table_grid(el)))
                ti += 1
            elif el.tag in (f"{W}sdt", f"{W}sdtContent", f"{W}customXml"):
                walk(el)

    walk(body)
    return out
