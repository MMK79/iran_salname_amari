"""Provinces of Iran: today's 31, their historic predecessors, and label aliases.

`code` is this project's stable key. `iso` is ISO 3166-2:IR as of the 2020 revision
(IR-00 .. IR-30) -- recorded from memory and cross-checked against the GeoJSON's own
codes in `dashboard/` (see docs/provinces.md); treat as (unverified) until then.

`group` is a *harmonised* unit that is stable across the splits since 1365 SH, so a
time series can be compared on constant borders:
  G_KHORASAN = Razavi + North + South Khorasan   (split 1383 SH / 2004)
  G_TEHRAN   = Tehran + Alborz + Qom             (Qom 1374/1995, Alborz 1389/2010)
  G_AZSHARGH = East Azerbaijan + Ardabil         (Ardabil 1372/1993)
  G_ZANJAN   = Zanjan + Qazvin                   (Qazvin 1375/1996)  (unverified: parts of
                                                  Qazvin were administered from Tehran before)
  G_MAZ      = Mazandaran + Golestan             (Golestan 1376/1997)
Before 1365 SH, "مرکزی" included Tehran; that entity is kept as a historic unit and is
not mapped to a single current province.
"""

from __future__ import annotations

from dataclasses import dataclass

from etl.normalize import norm


@dataclass(frozen=True)
class Province:
    code: str
    name_fa: str
    name_en: str
    iso: str | None
    group: str
    established_sh: int | None = None  # first academic year it appears as its own unit
    parent: str | None = None  # predecessor it split from
    historic: bool = False
    successors: tuple[str, ...] = ()


CURRENT = [
    Province("AZS", "آذربایجان شرقی", "East Azerbaijan", "IR-03", "G_AZSHARGH"),
    Province("AZG", "آذربایجان غربی", "West Azerbaijan", "IR-04", "AZG"),
    Province("ARD", "اردبیل", "Ardabil", "IR-24", "G_AZSHARGH", 1372, "AZS"),
    Province("ISF", "اصفهان", "Isfahan", "IR-10", "ISF"),
    Province("ALB", "البرز", "Alborz", "IR-30", "G_TEHRAN", 1389, "THR"),
    Province("ILM", "ایلام", "Ilam", "IR-16", "ILM"),
    Province("BSH", "بوشهر", "Bushehr", "IR-18", "BSH"),
    Province("THR", "تهران", "Tehran", "IR-23", "G_TEHRAN"),
    Province("CHB", "چهارمحال و بختیاری", "Chaharmahal and Bakhtiari", "IR-14", "CHB"),
    Province("KHJ", "خراسان جنوبی", "South Khorasan", "IR-29", "G_KHORASAN", 1383, "KHO"),
    Province("KHR", "خراسان رضوی", "Razavi Khorasan", "IR-09", "G_KHORASAN", 1383, "KHO"),
    Province("KHS", "خراسان شمالی", "North Khorasan", "IR-28", "G_KHORASAN", 1383, "KHO"),
    Province("KHZ", "خوزستان", "Khuzestan", "IR-06", "KHZ"),
    Province("ZNJ", "زنجان", "Zanjan", "IR-19", "G_ZANJAN"),
    Province("SMN", "سمنان", "Semnan", "IR-20", "SMN"),
    Province("SBL", "سیستان و بلوچستان", "Sistan and Baluchestan", "IR-11", "SBL"),
    Province("FRS", "فارس", "Fars", "IR-07", "FRS"),
    Province("QZV", "قزوین", "Qazvin", "IR-26", "G_ZANJAN", 1375, "ZNJ"),
    Province("QOM", "قم", "Qom", "IR-25", "G_TEHRAN", 1374, "THR"),
    Province("KRD", "کردستان", "Kurdistan", "IR-12", "KRD"),
    Province("KRM", "کرمان", "Kerman", "IR-08", "KRM"),
    Province("KSH", "کرمانشاه", "Kermanshah", "IR-05", "KSH"),
    Province("KBA", "کهگیلویه و بویراحمد", "Kohgiluyeh and Boyer-Ahmad", "IR-17", "KBA"),
    Province("GLS", "گلستان", "Golestan", "IR-27", "G_MAZ", 1376, "MZN"),
    Province("GIL", "گیلان", "Gilan", "IR-01", "GIL"),
    Province("LRS", "لرستان", "Lorestan", "IR-15", "LRS"),
    Province("MZN", "مازندران", "Mazandaran", "IR-02", "G_MAZ"),
    Province("MRK", "مرکزی", "Markazi", "IR-00", "MRK"),
    Province("HRM", "هرمزگان", "Hormozgan", "IR-22", "HRM"),
    Province("HMD", "همدان", "Hamadan", "IR-13", "HMD"),
    Province("YZD", "یزد", "Yazd", "IR-21", "YZD"),
]

HISTORIC = [
    Province("KHO", "خراسان", "Khorasan (undivided, until 1382)", None, "G_KHORASAN", None, None, True,
             ("KHR", "KHS", "KHJ")),
]

ALL = {p.code: p for p in CURRENT + HISTORIC}

# Aliases seen in the yearbooks (normalised on load). Order matters only for readability.
_ALIASES: dict[str, str] = {
    "آذربایجان شرقی": "AZS", "آذربایجان شرقي": "AZS", "آذربایجان‌شرقی": "AZS",
    "آذربایجان غربی": "AZG",
    "اردبیل": "ARD",
    "اصفهان": "ISF",
    "البرز": "ALB",
    "ایلام": "ILM", "ايالم": "ILM", "ایالم": "ILM",
    "بوشهر": "BSH",
    "تهران": "THR",
    "چهارمحال و بختیاری": "CHB", "چهار محال و بختیاری": "CHB", "چهارمحال وبختیاری": "CHB", "چهارمحال بختیاری": "CHB",
    "خراسان جنوبی": "KHJ",
    "خراسان رضوی": "KHR",
    "خراسان شمالی": "KHS",
    "خراسان": "KHO",
    "خوزستان": "KHZ",
    "زنجان": "ZNJ",
    "سمنان": "SMN",
    "سیستان و بلوچستان": "SBL", "سیستان وبلوچستان": "SBL", "سيستان و بلوچستان": "SBL",
    "فارس": "FRS",
    "قزوین": "QZV",
    "قم": "QOM",
    "کردستان": "KRD",
    "کرمان": "KRM",
    "کرمانشاه": "KSH", "باختران": "KSH", "کرمانشاهان": "KSH",
    "کهگیلویه و بویراحمد": "KBA", "کهگیلویه وبویراحمد": "KBA", "کهکیلویه و بویراحمد": "KBA",
    "کهگیلویه و بویر احمد": "KBA", "کهگیلویه": "KBA",
    "گلستان": "GLS",
    "گیلان": "GIL", "گیالن": "GIL",
    "لرستان": "LRS",
    "مازندران": "MZN",
    "مرکزی": "MRK",
    "هرمزگان": "HRM",
    "همدان": "HMD",
    "یزد": "YZD",
}
ALIASES = {norm(k).replace(" ", ""): v for k, v in _ALIASES.items()}

NATIONAL_LABELS = {norm(x).replace(" ", "") for x in ["کل کشور", "جمع کل", "کل", "کشور", "جمع کشور", "کل کشور جمع"]}


def match_province(label: str) -> str | None:
    """Return province code for a row label, 'IRN' for the national total, else None."""
    key = norm(label).replace(" ", "")
    if not key:
        return None
    if key in NATIONAL_LABELS:
        return "IRN"
    if key in ALIASES:
        return ALIASES[key]
    return None


def province_for_year(code: str, year_sh: int) -> str:
    """Tehran before 1389 includes Alborz etc.: callers use `group` for constant borders."""
    return code
