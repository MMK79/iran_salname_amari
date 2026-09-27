"""PDF yearbooks (1399-1402): text layer via `pdftotext -layout`, headers from templates.

The PDFs are Word exports with a proper Unicode text layer, but pdftotext returns the
lines in *visual* order: in each data row the numbers appear left-to-right, i.e. the
reverse of the logical (right-to-left) column order, and multi-level column headers
are scattered over several lines. So:

* body rows are parsed per line: label (Persian text or a "1398-1399" year) plus the
  numeric tokens, reversed back into logical order;
* column headers are *not* reconstructed from the PDF. They are taken from the same
  table (same title, same continuation part, same number of columns) in the most
  recent Word-based yearbook (1393-1398). Such tables carry
  `header_source = "template:<yearbook>/<table>"` so they can be audited. A table with
  no matching template is kept in raw cells only.
* Every templated table is checked arithmetically in `etl.validate` (total = male +
  female, province sums), which catches a wrong template.
"""

from __future__ import annotations

import difflib
import re
import subprocess
import unicodedata
from functools import lru_cache
from pathlib import Path

from etl.discover import CACHE_DIR, Unit
from etl.normalize import digits, norm, to_number
from etl.tables import RawTable

_BIDI = re.compile("[‎‏‪-‮⁦-⁩]")
_TITLE_NO = re.compile(r"^\s*-?\s*(\d{1,2})\s*-\s*(\d{1,2})\s*-?\s*")
_YEAR_LABEL = re.compile(r"1[34]\d\d\s*-\s*1[34]\d\d|\d{2}\s*-\s*1[34]\d\d")
_TOKEN = re.compile(r"1[34]\d\d\s*-\s*1[34]\d\d|\d[\d,]*(?:/\d+)?|(?<!\S)[-–—](?!\S)|[^\s\d]+")


def _pages(pdf: Path) -> list[str]:
    cache = CACHE_DIR / "pdf" / (re.sub(r"[^\w.-]", "_", str(pdf.parent.name)) + "__" + pdf.stem + ".txt")
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, check=True).stdout.decode(
            "utf-8", "replace"
        )
        cache.write_text(f"<!-- converted-from: {pdf} | tool: pdftotext -layout -->\f" + txt)
    return cache.read_text().split("\f")[1:]


# footnote markers as pdftotext renders them: "(1)", ")1(", "( )1", "1( )", "(1و2)"
_FOOT = re.compile(r"\(\s*\d{1,2}\s*\)|\)\s*\d{1,2}\s*\(|\(\s*\)\s*\d{1,2}(?!\d)|\d{1,2}\s*\(\s*\)|\(\s*\d\s*و\s*\d\s*\)")


def _clean(line: str) -> str:
    """Drop bidi controls, unify digits, remove footnote markers."""
    # NFKC folds Arabic presentation forms (the 1401 PDF uses U+FB50-FEFF glyphs) to letters
    s = digits(unicodedata.normalize("NFKC", _BIDI.sub("", line))).replace("٫", "/")
    return _FOOT.sub(" ", s)


def _is_edu_page(page: str) -> bool:
    head = " ".join(_clean(x) for x in page.strip().splitlines()[:3])
    return "آموزش" in head and not any(w in head for w in ("بهداشت", "فرهنگ", "نیروی", "نيروي"))


@lru_cache(maxsize=1)
def _templates() -> list[tuple[str, int, int, list[str], str, str]]:
    """(title_key, part, ncols, headers, source, domain) from the Word-era yearbooks."""
    from etl.discover import units_for_year
    from etl.extract.docx_tables import read_blocks
    from etl.tables import blocks_to_rawtables
    from etl.terms import classify_domain

    out = []
    for y in (1398, 1397, 1396, 1395, 1394, 1393):
        for u in units_for_year(y):
            if u.kind != "docx_chapter":
                continue
            for rt in blocks_to_rawtables(read_blocks(u.paths[0]), yearbook_sh=y, source_file=u.rel(u.paths[0]),
                                          source_format="docx"):
                out.append((title_key(rt.title), rt.part, len(rt.col_headers), rt.col_headers,
                            f"{y}/{rt.source_table}", classify_domain(rt.title)))
    return out


def title_key(title: str) -> str:
    t = norm(title)
    t = re.sub(r"\(\s*دنباله\s*\)|دنباله", "", t)
    t = re.sub(r"[\d()\-–:،,./]+", " ", t)
    t = re.sub(r"سال تحصیلی|برحسب|بر حسب|به تفکیک|تفکیک", " ", t)
    return re.sub(r"\s+", "", t)


def find_template(title: str, part: int, ncols: int) -> tuple[list[str], str] | None:
    key = title_key(title)
    best, score = None, 0.0
    for tk, tp, tn, headers, src, _dom in _templates():
        if tn != ncols:
            continue
        s = difflib.SequenceMatcher(None, key, tk).ratio() + (0.05 if tp == part else 0)
        if s > score:
            best, score = (headers, src), s
    return best if score >= 0.72 else None


def _parse_line(line: str) -> tuple[str, list[float | None]] | None:
    toks = _TOKEN.findall(_clean(line))
    label_parts, nums = [], []
    for t in toks:
        if _YEAR_LABEL.fullmatch(t.replace(" ", "")):
            label_parts.append(t.replace(" ", ""))
        elif re.fullmatch(r"\d[\d,]*(?:/\d+)?", t) or t in ("-", "–", "—"):
            nums.append(t)
        elif re.fullmatch(r"[.…]+", t) or t in ("(", ")"):
            continue
        else:
            label_parts.append(t)
    label = " ".join(label_parts)
    label = re.sub(r"\.{2,}|…+", " ", label).strip(" .")
    if not nums:
        return None
    # pdftotext keeps visual order: right-most column (the first logical one) comes last
    vals = [to_number(n, slash_swapped=False) for n in reversed(nums)]
    return label, vals


def rawtables(u: Unit) -> list[RawTable]:
    out: list[RawTable] = []
    for pdf in u.paths:
        pages = _pages(pdf)
        if u.kind == "pdf_book":
            pages = [p for p in pages if _is_edu_page(p)]
        out += _parse_pages(pages, u, pdf)
    return out


def _parse_pages(pages: list[str], u: Unit, pdf: Path) -> list[RawTable]:
    tables: list[dict] = []
    cur: dict | None = None
    seen: dict[str, int] = {}
    pending_label: list[str] = []
    for page in pages:
        lines = page.splitlines()
        for i, raw in enumerate(lines):
            line = _clean(raw).strip()
            if not line:
                continue
            m = _TITLE_NO.match(line)
            if m and re.search(r"[آ-ی]{3,}", line) and len(line) > 15:
                a, b = int(m.group(1)), int(m.group(2))
                chapter, no = (a, b) if a >= b or a == 17 else (b, a)
                title = f"{no}-{chapter}- " + line[m.end():].strip()
                base = title_key(title)
                part = seen.get(base, -1) + 1
                seen[base] = part
                cur = {"title": title, "no": f"{no}-{chapter}", "part": part, "rows": [], "notes": []}
                tables.append(cur)
                pending_label = []
                continue
            if cur is None:
                continue
            nline = norm(line)
            if nline.startswith("ماخذ") or nline.startswith("مأخذ") or re.match(r"^\)?\d\)", line.strip()):
                cur["notes"].append(line)
                continue
            if "سالنامه آماری" in line or "سالنامه آماري" in line:
                continue
            parsed = _parse_line(line)
            if parsed is None:
                # a text-only line: may be the first half of a two-line row label
                if re.search(r"[آ-ی]{2,}", line) and len(line) < 120:
                    pending_label = [re.sub(r"\.{2,}", " ", line).strip()]
                continue
            label, vals = parsed
            if not label and pending_label:
                label = pending_label[0]
                # the second half of the label may follow on the next line
                if i + 1 < len(lines):
                    nxt = _clean(lines[i + 1]).strip()
                    if nxt and _parse_line(nxt) is None and re.search(r"\.{3,}", nxt):
                        label = f"{label} {re.sub(r'[.…]{2,}', ' ', nxt).strip()}"
            pending_label = []
            if not label and len(vals) == 1:
                continue  # page number
            if label and any(lbl == label for lbl, _ in cur["rows"]):
                # the same row label again = the next physical part of the table (headers change!)
                cur = {"title": cur["title"], "no": cur["no"], "part": cur["part"] + 1, "rows": [], "notes": []}
                seen[title_key(cur["title"])] = cur["part"]
                tables.append(cur)
            cur["rows"].append((label, vals))
    out = []
    for t in tables:
        if not t["rows"]:
            continue
        counts: dict[int, int] = {}
        for _, v in t["rows"]:
            counts[len(v)] = counts.get(len(v), 0) + 1
        ncols = max(counts, key=counts.get)
        rows = [(lbl, v) for lbl, v in t["rows"] if len(v) == ncols]
        t["dropped_rows"] = [(lbl, len(v)) for lbl, v in t["rows"] if len(v) != ncols]
        dropped = len(t["rows"]) - len(rows)
        tpl = find_template(t["title"], t["part"], ncols)
        headers, src = (tpl if tpl else ([""] * ncols, "none"))
        notes = t["notes"] + ([f"[etl] {dropped} row(s) dropped: token count != {ncols}: {t['dropped_rows'][:6]}"]
                              if dropped else [])
        out.append(RawTable(
            yearbook_sh=u.year, source_file=u.rel(pdf), source_format="pdf", title=t["title"], table_no=t["no"],
            part=t["part"], col_headers=headers, rows=rows, notes=notes,
            header_source=f"template:{src}" if tpl else "none",
        ))
    return out
