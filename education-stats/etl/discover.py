"""Locate the education chapter of every yearbook and decide how to read it.

The source tree is read-only. Legacy `.doc` files are read from their LibreOffice
conversions in `.cache/doc2docx/<year>/` (made by scripts/convert_docs.sh). `.rar`
and `.zip` archives are *not* extracted: every archive was checked to contain the
same files that already sit unpacked next to it (see docs/inventory.md).
"""

from __future__ import annotations

import os
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from etl.normalize import norm

SOURCE_DIR = Path(os.environ.get("SOURCE_DIR", "/Volumes/MigMig/Programming/Datasets/Statistical Yearbook/Keshvari"))
CACHE_DIR = Path(os.environ.get("CACHE_DIR", Path(__file__).resolve().parent.parent / ".cache"))


@dataclass
class Unit:
    year: int
    kind: str  # docx_chapter | doc_converted_chapter | doc_converted_book | html_grid | html_text | pdf_chapter | pdf_book
    paths: list[Path]
    source_paths: list[Path]  # original file(s) in the read-only source tree

    def rel(self, p: Path) -> str:
        try:
            return str(p.relative_to(SOURCE_DIR))
        except ValueError:
            return str(p)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _files(d: Path, exts: tuple[str, ...]) -> list[Path]:
    out = []
    for root, _dirs, files in os.walk(d):
        for f in files:
            if f.startswith("~$") or f.startswith("."):
                continue
            if f.lower().endswith(exts):
                out.append(Path(root) / f)
    return sorted(out)


def _is_edu_name(p: Path) -> bool:
    n = norm(_nfc(p.stem))
    return "آموزش" in n or "اموزش" in n


def units_for_year(year: int) -> list[Unit]:
    ydir = SOURCE_DIR / str(year)
    conv = CACHE_DIR / "doc2docx" / str(year)
    docx = [p for p in _files(ydir, (".docx",))]
    pdfs = _files(ydir, (".pdf",))
    htmls = _files(ydir, (".html", ".htm"))
    if docx:
        named = [p for p in docx if _is_edu_name(p)]
        if named:
            return [Unit(year, "docx_chapter", named[:1], named[:1])]
        best = _best_docx(docx)
        return [Unit(year, "docx_chapter", [best], [best])] if best else []
    if year == 1387:
        cands = sorted(conv.glob("TEST*.docx"))
        best = _best_docx(cands)
        src = [p for p in _files(ydir, (".doc",)) if best and p.stem.lower() == best.stem.lower()]
        return [Unit(year, "doc_converted_chapter", [best], src)] if best else []
    if (conv / f"{year}.docx").exists():
        return [Unit(year, "doc_converted_book", [conv / f"{year}.docx"], [ydir / f"{year}.doc"])]
    def in_edu_folder(p: Path) -> bool:
        return any(_is_edu_name(Path(part)) for part in p.relative_to(ydir).parts[:-1])

    edu_html = [p for p in htmls if in_edu_folder(p)]
    if year == 1381:
        edu_html = [p for p in htmls if p.parent.name == "F15"]
    if edu_html:
        kind = "html_text" if 1370 <= year <= 1379 else "html_grid"
        return [Unit(year, kind, edu_html, edu_html)]
    edu_pdf = [p for p in pdfs if in_edu_folder(p)]
    if edu_pdf:  # 1376-1379: one small PDF per table
        return [Unit(year, "pdf_tables", edu_pdf, edu_pdf)]
    if pdfs:
        ch = [p for p in pdfs if _is_edu_name(p)]
        if ch:
            return [Unit(year, "pdf_chapter", ch[:1], ch[:1])]
        return [Unit(year, "pdf_book", pdfs[:1], pdfs[:1])]
    return []


def _best_docx(cands: list[Path]) -> Path | None:
    from etl.extract.docx_tables import Para, read_blocks
    from etl.tables import is_title
    from etl.terms import classify_domain

    best, score = None, 0
    for p in cands:
        try:
            titles = [b.text for b in read_blocks(p) if isinstance(b, Para) and is_title(b.text)]
        except Exception:
            continue
        s = sum(1 for t in titles if classify_domain(t) in ("k12", "he"))
        if s > score:
            best, score = p, s
    return best


def education_chapter(titles: list[str]) -> str | None:
    """Most common chapter number among K-12/HE table titles ('10-15' -> '15')."""
    from etl.tables import table_number
    from etl.terms import classify_domain

    c = Counter()
    for t in titles:
        no = table_number(t)
        if "-" in no and classify_domain(t) in ("k12", "he"):
            c[no.split("-")[1]] += 1
    return c.most_common(1)[0][0] if c else None


def all_years() -> list[int]:
    return sorted(int(p.name) for p in SOURCE_DIR.iterdir() if p.name.isdigit())
