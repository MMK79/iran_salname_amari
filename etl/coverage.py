"""Footnotes -> coverage flags.

Yearbook tables carry numbered footnotes ("(1)" on the title, a row label or a column
header; "1) ..." below the table). Coverage caveats that matter for ratios live there,
e.g. "1) به استثنای دانشگاه آزاد اسلامی" (excludes Islamic Azad University) or
"آمار دانشگاه آزاد را به استثنای سال تحصیلی 86-1385 شامل می‌شود" (includes Azad except
in 1385-86). We resolve every marker to its note text and derive flags per fact.
"""

from __future__ import annotations

import re

from etl.normalize import digits, norm

_NOTE_NO = re.compile(r"^\s*[(\[]?\s*(\d{1,2})\s*[)\]]\s*|^\s*\)\s*(\d{1,2})\s*")
_MARK = re.compile(r"\(\s*(\d{1,2})(?:\s*[و,،]\s*(\d{1,2}))?\s*\)")


def parse_notes(notes: list[str]) -> tuple[dict[int, str], list[str]]:
    numbered: dict[int, str] = {}
    unnumbered: list[str] = []
    for n in notes:
        t = digits(n)
        m = _NOTE_NO.match(t)
        if m:
            numbered[int(m.group(1) or m.group(2))] = t[m.end():]
        elif not norm(t).startswith(("ماخذ", "مأخذ", "مبنا", "-", "[etl]")):
            unnumbered.append(t)
    return numbered, unnumbered


def markers(text: str) -> set[int]:
    out: set[int] = set()
    for m in _MARK.finditer(digits(text or "")):
        out.add(int(m.group(1)))
        if m.group(2):
            out.add(int(m.group(2)))
    return out


def _azad_state(t: str, year_sh: int) -> str | None:
    if "آزاد" not in t:
        return None
    exc_year = re.search(r"به استثنای سال تحصیلی\s*(\d{2})?\s*-?\s*(1[34]\d\d)", t)
    if exc_year and ("شامل می شود" in t or "شامل میشود" in t or "نیز شامل" in t):
        return "excl_azad" if int(exc_year.group(2)) == year_sh else "incl_azad"
    if any(k in t for k in ("به استثنای دانشگاه آزاد", "به استثنا دانشگاه آزاد", "بجز دانشگاه آزاد", "به جز دانشگاه آزاد")):
        return "excl_azad"
    if "شامل نمی" in t or "شامل نمي" in t:
        return "excl_azad"
    if "شامل می" in t or "نیز شامل" in t or "را شامل" in t:
        return "incl_azad"
    return None


def flags(note_texts: list[str], year_sh: int) -> set[str]:
    out: set[str] = set()
    for raw in note_texts:
        t = norm(raw)
        a = _azad_state(t, year_sh)
        if a:
            out.add(a)
        excl = "شامل نمی" in t or "به استثنای" in t or "بجز" in t
        if "علمی کاربردی" in t and excl and "به تفکیک" not in t:
            out.add("excl_uast")
        if "علمی کاربردی" in t and ("به تفکیک جنس" in t or "به تفکیک جنسیت" in t):
            out.add("uast_in_total_only")
        if "پیام نور" in t and excl:
            out.add("excl_pnu")
        if "پیام نور" in t and "به تفکیک استان" in t:
            out.add("pnu_not_by_province")
        if "نیمه وقت" in t or "پاره وقت" in t:
            out.add("incl_parttime")
    if {"excl_azad", "incl_azad"} <= out:
        out.discard("incl_azad")  # conservative
    return out
