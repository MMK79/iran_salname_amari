"""Word-exported .html/.htm reader (1353-1381 yearbooks, windows-1256 or utf-8).

Returns the same Para/Table blocks as the docx reader, in document order, with
colspan/rowspan expanded into a dense grid.
"""

from __future__ import annotations

import re
from pathlib import Path

from lxml import html as lhtml

from etl.extract.docx_tables import Para, Table

_CHARSET = re.compile(rb"charset=([\w-]+)", re.I)


def _decode(raw: bytes) -> str:
    m = _CHARSET.search(raw[:4000])
    enc = m.group(1).decode().lower() if m else "windows-1256"
    if enc in ("unicode", "utf-16"):
        enc = "utf-16"
    try:
        return raw.decode(enc)
    except (LookupError, UnicodeDecodeError):
        for alt in ("utf-8", "windows-1256", "utf-16"):
            try:
                return raw.decode(alt)
            except UnicodeDecodeError:
                continue
    return raw.decode("windows-1256", "replace")


def _cell_text(el) -> str:
    return re.sub(r"\s+", " ", el.text_content()).strip()


def _grid(tbl) -> list[list[str]]:
    grid: dict[tuple[int, int], str] = {}
    r = 0
    rows = [tr for tr in tbl.iter("tr") if tr.getparent() is not None and _owner(tr) is tbl]
    for tr in rows:
        c = 0
        for td in tr:
            if td.tag not in ("td", "th"):
                continue
            while (r, c) in grid:
                c += 1
            cs = int(td.get("colspan", "1") or 1)
            rs = int(td.get("rowspan", "1") or 1)
            txt = _cell_text(td)
            for i in range(rs):
                for j in range(cs):
                    grid[(r + i, c + j)] = txt
            c += cs
        r += 1
    if not grid:
        return []
    nr = max(k[0] for k in grid) + 1
    nc = max(k[1] for k in grid) + 1
    return [[grid.get((i, j), "") for j in range(nc)] for i in range(nr)]


def _owner(tr):
    p = tr.getparent()
    while p is not None and p.tag != "table":
        p = p.getparent()
    return p


def read_blocks(path: str | Path) -> list[Para | Table]:
    doc = lhtml.fromstring(_decode(Path(path).read_bytes()))
    out: list[Para | Table] = []
    ti = 0
    body = doc.find("body") if doc.find("body") is not None else doc
    for el in body.iter():
        if el.tag == "table" and _owner_table(el) is None:
            out.append(Table(ti, _grid(el)))
            ti += 1
        elif el.tag in ("p", "h1", "h2", "h3", "h4") and _owner_table(el) is None:
            t = _cell_text(el)
            if t:
                out.append(Para(t))
    return out


def _owner_table(el):
    p = el.getparent()
    while p is not None:
        if p.tag == "table":
            return p
        p = p.getparent()
    return None
