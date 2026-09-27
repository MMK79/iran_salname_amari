"""Persian text and number normalisation.

Everything that compares Persian strings goes through `norm()` first, so that the
many spellings the yearbooks use over 60 years (Arabic vs Persian yeh/kaf, ZWNJ,
tatweel, diacritics, dotted leaders, footnote markers) compare equal.
"""

from __future__ import annotations

import re
import unicodedata

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_CHARS = str.maketrans(
    {
        "\u064a": "\u06cc",  # Arabic yeh -> Persian yeh
        "\u0649": "\u06cc",  # alef maksura -> yeh
        "\u0626": "\u06cc",  # yeh with hamza -> yeh
        "\u0643": "\u06a9",  # Arabic kaf -> Persian keheh
        "\u0629": "\u0647",  # teh marbuta -> heh
        "\u06c0": "\u0647",  # heh with yeh above -> heh
        "\u0623": "\u0627",  # alef hamza above -> alef
        "\u0625": "\u0627",  # alef hamza below -> alef
        "\u0671": "\u0627",  # alef wasla -> alef
        "\u200c": " ",  # ZWNJ -> space (so the joined and spaced forms of a word compare equal)
        "\u200b": " ",  # zero-width space (1398+ titles) -> space
        "\u200d": "",
        "\u200e": "",
        "\u200f": "",
        "\u202a": "",
        "\u202b": "",
        "\u202c": "",
        "\u202d": "",
        "\u202e": "",
        "\ufeff": "",
        "\u0640": "",  # tatweel (kashida)
        "\xa0": " ",
    }
)
_DIACRITICS = re.compile("[\u064b-\u065f\u0670]")
_LEADERS = re.compile("[.\u2026\u00b7\u0640]{2,}")
_FOOTNOTE = re.compile(r"\(\s*[0-9]+(\s*[و,،]\s*[0-9]+)*\s*\)|\*+")
_WS = re.compile(r"\s+")


def digits(s: str) -> str:
    return s.translate(_DIGITS)


def norm(s: str | None, *, keep_footnotes: bool = False) -> str:
    """Canonical form of a Persian label for matching (not for display)."""
    if not s:
        return ""
    s = digits(unicodedata.normalize("NFKC", s)).translate(_CHARS)
    s = _DIACRITICS.sub("", s)
    s = _LEADERS.sub(" ", s)
    if not keep_footnotes:
        s = _FOOTNOTE.sub(" ", s)
    s = s.replace("هیأت", "هیات").replace("هییت", "هیات")
    s = s.replace("دوره", "دوره").replace("دورة", "دوره")
    s = _WS.sub(" ", s).strip(" .:-–—|ا") if not keep_footnotes else _WS.sub(" ", s).strip()
    return s


_NUM = re.compile(r"^[+-]?\d+(\.\d+)?$")
MISSING_TOKENS = {"", "-", "–", "—", "_", "…", "...", "..", "×", "××", "*", "**", "000", "ـ", "0-"}


def to_number(cell: str | None, *, slash_swapped: bool = True) -> float | None:
    """Parse a yearbook numeric cell.

    * Persian/Arabic digits -> ASCII; thousands separators (`,` `٬` `'` spaces) dropped.
    * `-`, `…`, `×` (not applicable / not available) -> None.
      `000` is the 1350s convention for "not available" and is treated as missing.
    * Decimals are written with `/`. In the Word-based yearbooks (.docx/.doc) the RTL
      layout stores "28.7" as "7/28" (fraction first), so with `slash_swapped=True`
      "a/b" -> b.a . PDF/plain-text sources store it visually as "28/7"; pass False.
    * Footnote markers like "886(1)" are stripped.
    """
    if cell is None:
        return None
    s = digits(cell).translate(_CHARS)
    s = _FOOTNOTE.sub("", s)
    s = s.replace("٬", "").replace(",", "").replace("،", "").replace("'", "").replace(" ", "")
    s = s.strip(" .|ا")
    if s in MISSING_TOKENS:
        return None
    if "/" in s or "٫" in s:
        parts = re.split(r"[/٫]", s)
        if len(parts) == 2 and all(p.isdigit() for p in parts if p) and parts[0] and parts[1]:
            a, b = parts
            return float(f"{b}.{a}") if slash_swapped else float(f"{a}.{b}")
        return None
    if _NUM.match(s):
        return float(s)
    return None


def is_numeric_cell(cell: str | None) -> bool:
    if cell is None:
        return False
    s = norm(cell)
    return to_number(cell) is not None or s in MISSING_TOKENS


_Y4 = re.compile(r"1[34]\d\d")
_Y2 = re.compile(r"(?<!\d)(\d{2})(?!\d)")


def parse_academic_year(label: str) -> int | None:
    """'99-1398', '1398-1399', '81-1380(2)', '66-1365..', '1370' -> start year (SH).

    Returns None if the label is not a year. Census labels ('آبان 1375') are not
    academic years and return None.
    """
    s = digits(label)
    s = _FOOTNOTE.sub("", s)
    s = re.sub(r"[.\s]+$", "", s).strip()
    if re.search(r"[آ-ی]", s.translate(_CHARS)) and not re.fullmatch(r"(سال|سال تحصیلی)\s*.*", norm(s)):
        return None
    ys = [int(y) for y in _Y4.findall(s)]
    if not ys:
        return None
    rest = _Y4.sub("", s)
    if not re.fullmatch(r"[\s\-–—/()0-9]*", rest):
        return None
    if len(ys) >= 2:
        return min(ys)
    return ys[0]


def sh_to_gregorian_start(year_sh: int) -> int:
    """Solar Hijri academic year start -> Gregorian year in which it starts (Mehr = Sept/Oct)."""
    return year_sh + 621
