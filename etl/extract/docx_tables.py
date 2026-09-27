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


def _table_grid(tbl) -> list[list[str]]:
    grid: list[list[str]] = []
    vorigin: dict[int, str] = {}
    for tr in tbl.iterchildren(f"{W}tr"):
        row: list[str] = []
        col = 0
        for tc in tr.iterchildren(f"{W}tc"):
            tcpr = tc.find(f"{W}tcPr")
            span = 1
            vmerge = None
            if tcpr is not None:
                gs = tcpr.find(f"{W}gridSpan")
                if gs is not None:
                    span = int(gs.get(f"{W}val", "1"))
                vm = tcpr.find(f"{W}vMerge")
                if vm is not None:
                    vmerge = vm.get(f"{W}val", "continue")
            # nested tables: take only direct paragraphs' text
            txt = " ".join(_text(p) for p in tc.iterchildren(f"{W}p")).strip()
            if vmerge == "continue":
                txt = vorigin.get(col, "")
            elif vmerge == "restart":
                for k in range(span):
                    vorigin[col + k] = txt
            else:
                for k in range(span):
                    vorigin.pop(col + k, None)
            for _ in range(span):
                row.append(txt)
            col += span
        grid.append(row)
    width = max((len(r) for r in grid), default=0)
    return [r + [""] * (width - len(r)) for r in grid]


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
                out.append(Table(ti, _table_grid(el)))
                ti += 1
            elif el.tag in (f"{W}sdt", f"{W}sdtContent", f"{W}customXml"):
                walk(el)

    walk(body)
    return out
