#!/usr/bin/env python
"""Export the education statistics as static JSON for a website's interactive Iran map.

    uv run python scripts/export_site.py [--db data/out/edu.duckdb] [--out exports/site]

Writes provinces.json, k12.json, he.json, provenance.json, meta.json.
Everything is read from the SQL views (v_k12_best, v_k12_students_per_teacher,
v_k12_core_students_per_teacher, v_he_best, v_he_students_per_staff); no cleaning is redone here.

Conventions
* A missing value is absent or JSON null; a zero is never used for "not available".
* Province codes are the project codes (etl/provinces.py). IRN = national total. KHO = undivided
  Khorasan (<= 1382), only in the data, and listed under provinces.json "historic_units".
* Ratios are rounded to 2 decimals; students/teachers are integers as printed in the yearbooks.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
GEOJSON = ROOT / "dashboard" / "data" / "provinces.geojson"

VIEWBOX = (1000, 860)
LAT0 = 32.0  # standard parallel for the equirectangular x-scaling
MAX_PROVINCES_BYTES = 400_000

K12_LEVELS = ["primary", "lower_secondary", "upper_secondary"]
K12_ALL = ["all_levels", "core_three"]
GENDERS = ["total", "male", "female"]
# Years whose province-level HE tables are quarantined (docs/validation.md, dashboard-spec.md).
HE_QUARANTINE_YEARS = {1399, 1400, 1402}
HE_STAFF_PREFERENCE = {"fulltime": 0, "fulltime_and_hourly": 1, "unspecified": 2}


# ------------------------------------------------------------------ geometry
def _project(lon: float, lat: float) -> tuple[float, float]:
    return (lon * math.cos(math.radians(LAT0)), -lat)


def _dp(points: list[tuple[float, float]], eps: float) -> list[tuple[float, float]]:
    """Douglas-Peucker on an open polyline (iterative)."""
    n = len(points)
    if n < 3:
        return points
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = points[a], points[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        dmax, idx = -1.0, -1
        for i in range(a + 1, b):
            px, py = points[i]
            d = math.hypot(px - ax, py - ay) if norm == 0 else abs(dy * (px - ax) - dx * (py - ay)) / norm
            if d > dmax:
                dmax, idx = d, i
        if dmax > eps:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(points, keep, strict=True) if k]


def _area(ring: list[tuple[float, float]]) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
        s += x1 * y2 - x2 * y1
    return s / 2


def _centroid(ring: list[tuple[float, float]]) -> tuple[float, float]:
    a = _area(ring)
    if abs(a) < 1e-12:
        xs, ys = zip(*ring, strict=True)
        return sum(xs) / len(xs), sum(ys) / len(ys)
    cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
        cr = x1 * y2 - x2 * y1
        cx += (x1 + x2) * cr
        cy += (y1 + y2) * cr
    return cx / (6 * a), cy / (6 * a)


def build_provinces(eps_px: float) -> dict:
    gj = json.loads(GEOJSON.read_text())
    # 1) project every ring (geojson order), group by province code
    feats: dict[str, dict] = {}
    for f in gj["features"]:
        p = f["properties"]
        geom = f["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        rec = feats.setdefault(p["code"], {"name_en": p["shapeName"], "name_fa": p["name_fa"], "polys": []})
        for poly in polys:
            rec["polys"].append([[_project(x, y) for x, y in ring[:-1]] for ring in poly])
    # 2) fit to the viewBox
    xs = [x for r in feats.values() for poly in r["polys"] for ring in poly for x, _ in ring]
    ys = [y for r in feats.values() for poly in r["polys"] for ring in poly for _, y in ring]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = VIEWBOX
    s = min(w / (x1 - x0), h / (y1 - y0))
    ox = (w - (x1 - x0) * s) / 2
    oy = (h - (y1 - y0) * s) / 2

    def fit(pt):
        return ((pt[0] - x0) * s + ox, (pt[1] - y0) * s + oy)

    out = {}
    for code, rec in feats.items():
        d: list[str] = []
        best_area, label = -1.0, (0.0, 0.0)
        n_polys = 0
        for poly in rec["polys"]:
            kept_any = False
            for k, ring in enumerate(poly):
                pts = [fit(p) for p in ring]
                if pts and pts[0] != pts[-1]:
                    pass
                # simplify as a closed ring: split at the farthest vertex so both ends are anchored
                far = max(
                    range(len(pts)), key=lambda i: math.hypot(pts[i][0] - pts[0][0], pts[i][1] - pts[0][1])
                )
                a_part = _dp(pts[: far + 1], eps_px)
                b_part = _dp(pts[far:] + [pts[0]], eps_px)
                simp = a_part[:-1] + b_part[:-1]
                if len(simp) < 3 or abs(_area(simp)) < 1.0:  # < 1 px^2: speck
                    if k == 0:
                        break  # exterior ring too small -> drop the polygon (and its holes)
                    continue
                if k == 0:
                    kept_any = True
                    n_polys += 1
                    a = abs(_area(simp))
                    if a > best_area:
                        best_area, label = a, _centroid(simp)
                d.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in simp) + "Z")
            _ = kept_any
        out[code] = {
            "code": code,
            "name_en": rec["name_en"],
            "name_fa": rec["name_fa"],
            "path": "".join(d),
            "label": [round(label[0], 1), round(label[1], 1)],
            "n_polygons": n_polys,
        }
    return out


def provinces_json() -> dict:
    # Pick the smallest tolerance that keeps the file under the size budget.
    for eps in (0.25, 0.4, 0.6, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5, 3.0):
        prov = build_provinces(eps)
        doc = {
            "viewBox": [0, 0, *VIEWBOX],
            "projection": f"equirectangular, x scaled by cos({LAT0:g} deg), fitted to the viewBox",
            "fill_rule": "evenodd",
            "simplification_px": eps,
            "attribution": "geoBoundaries IRN ADM1 (ODbL 1.0), (c) OpenStreetMap contributors",
            "provinces": [prov[k] for k in sorted(prov, key=lambda c: prov[c]["name_en"])],
            "historic_units": [
                {
                    "code": "KHO",
                    "name_en": "Khorasan (undivided, until 1382)",
                    "name_fa": "خراسان",
                    "paint_on": ["KHR", "KHS", "KHJ"],
                }
            ],
        }
        if len(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode()) < MAX_PROVINCES_BYTES:
            return doc
    raise RuntimeError("could not simplify provinces under the size budget")


# ------------------------------------------------------------------ helpers
def _num(v):
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except TypeError:
        return None
    f = float(v)
    return int(f) if f == int(f) else round(f, 2)


def _ratio(num, den):
    if num is None or den is None or den == 0:
        return None
    return round(num / den, 2)


def _clean(d):
    """Drop None-only leaves recursively; empty dicts vanish."""
    if isinstance(d, dict):
        out = {k: _clean(v) for k, v in d.items()}
        return {k: v for k, v in out.items() if v not in (None, {})}
    return d


def _ranges(years: list[int]) -> str:
    ys = sorted(set(years))
    if not ys:
        return ""
    parts, start, prev = [], ys[0], ys[0]
    for y in ys[1:]:
        if y != prev + 1:
            parts.append(f"{start}-{prev}" if start != prev else str(start))
            start = y
        prev = y
    parts.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(parts)


# ------------------------------------------------------------------ K-12
def k12_json(con) -> tuple[dict, dict]:
    prov_names = {r[0] for r in con.execute("select code from provinces").fetchall()}
    gy = dict(con.execute("select distinct year_sh, year_gregorian from k12_stats").fetchall())

    data: dict[int, dict] = {}
    tdef: dict[int, dict] = {}

    def slot(year, prov, level):
        return data.setdefault(year, {}).setdefault(prov, {}).setdefault(level, {})

    # students by gender (regular programme), all levels incl. the printed all-levels row
    rows = con.execute(
        """select year_sh, province_code, level, gender, value from v_k12_best
           where programme='regular' and metric='students'
             and level in ('primary','lower_secondary','upper_secondary','all_levels')"""
    ).fetchall()
    for y, p, lv, g, v in rows:
        slot(y, p, lv).setdefault(g, {})["students"] = _num(v)

    # teachers: totals only (the yearbooks give no teacher counts by gender)
    for y, p, lv, st, t, es, _d in con.execute(
        """select year_sh, province_code, level, students, teachers, educational_staff, teacher_definition
           from v_k12_students_per_teacher where level in ('primary','lower_secondary','upper_secondary')"""
    ).fetchall():
        use = t if t is not None else es
        tot = slot(y, p, lv).setdefault("total", {})
        tot["teachers"] = _num(use)
        tot["students_per_teacher"] = _ratio(st, use)
        if use is not None:
            tdef.setdefault(y, {})[lv] = "teachers" if t is not None else "educational_staff_proxy"
    # the printed all-levels row (regular programme)
    for y, p, st, t, es in con.execute(
        """select s.year_sh, s.province_code, s.value,
                  max(case when k.metric='teachers' then k.value end),
                  max(case when k.metric='educational_staff' then k.value end)
           from v_k12_best s join v_k12_best k
             on k.year_sh=s.year_sh and k.province_code=s.province_code and k.level='all_levels'
            and k.programme='regular' and k.gender='total'
           where s.level='all_levels' and s.programme='regular' and s.metric='students' and s.gender='total'
           group by s.year_sh, s.province_code, s.value"""
    ).fetchall():
        use = t if t is not None else es
        tot = slot(y, p, "all_levels").setdefault("total", {})
        tot["teachers"] = _num(use)
        tot["students_per_teacher"] = _ratio(st, use)
        if use is not None:
            tdef.setdefault(y, {})["all_levels"] = "teachers" if t is not None else "educational_staff_proxy"

    # core three levels combined (existing view); gender students = sum of the three levels
    for y, p, st, tu, _spt, _n, proxy in con.execute(
        """select year_sh, province_code, students, teachers_used, students_per_teacher, n_levels, uses_proxy
           from v_k12_core_students_per_teacher"""
    ).fetchall():
        tot = slot(y, p, "core_three").setdefault("total", {})
        tot.update(students=_num(st), teachers=_num(tu), students_per_teacher=_ratio(st, tu))
        tdef.setdefault(y, {})["core_three"] = "educational_staff_proxy" if proxy else "teachers"
        for g in ("male", "female"):
            parts = [data[y][p].get(lv, {}).get(g, {}).get("students") for lv in K12_LEVELS]
            if all(x is not None for x in parts):
                slot(y, p, "core_three").setdefault(g, {})["students"] = sum(parts)

    # year metadata and flags (data driven where possible)
    years = []
    for y in sorted(data):
        provs = set(data[y]) - {"IRN"}
        flags = []
        if "KHO" in provs:
            flags.append("khorasan_undivided")
        if provs and "ALB" not in provs:
            flags.append("alborz_in_tehran")
        if 1391 <= y <= 1393:
            flags.append("school_reform_1391_93")
        proxy_levels = [lv for lv, d in tdef.get(y, {}).items() if d == "educational_staff_proxy"]
        if proxy_levels:
            flags.append("teacher_proxy_educational_staff")
        years.append(
            {
                "year_sh": y,
                "year_gregorian": int(gy.get(y, y + 621)),
                "n_provinces": len(provs & prov_names),
                "flags": flags,
                "teacher_definition": tdef.get(y, {}),
            }
        )

    data_out = {str(y): {p: _clean(v) for p, v in d.items()} for y, d in sorted(data.items())}
    data_out = {y: {p: v for p, v in d.items() if v} for y, d in data_out.items()}

    prov = {}
    for y, f, t in con.execute(
        """select distinct year_sh, source_file, source_table from v_k12_best
           where programme='regular' and metric in ('students','teachers','educational_staff')
             and level in ('primary','lower_secondary','upper_secondary','all_levels')"""
    ).fetchall():
        prov.setdefault(y, set()).add(f"{f} :: {t}")

    doc = {
        "levels": K12_LEVELS + K12_ALL,
        "genders": GENDERS,
        "fields": ["students", "teachers", "students_per_teacher"],
        "years": years,
        "data": data_out,
    }
    return doc, prov


# ------------------------------------------------------------------ higher education
def he_json(con) -> tuple[dict, dict]:
    gy = dict(con.execute("select distinct year_sh, year_gregorian from higher_ed_stats").fetchall())
    data: dict[int, dict] = {}
    emp: dict[int, dict] = {}

    def slot(y, p, ut, dl, g):
        return (
            data.setdefault(y, {}).setdefault(p, {}).setdefault(ut, {}).setdefault(dl, {}).setdefault(g, {})
        )

    for y, p, ut, dl, g, v in con.execute(
        """select year_sh, province_code, university_type, degree_level, gender, max(value)
           from v_he_best where metric='students' and field_group='all' and rank='all'
           group by all"""
    ).fetchall():
        slot(y, p, ut, dl, g)["students"] = _num(v)

    best_emp: dict[tuple, tuple] = {}
    for y, p, ut, g, e, v in con.execute(
        """select year_sh, province_code, university_type, gender, employment, max(value)
           from v_he_best where metric='academic_staff' and field_group='all' and rank='all'
             and degree_level='all' group by all"""
    ).fetchall():
        k = (y, p, ut, g)
        pref = HE_STAFF_PREFERENCE.get(e, 9)
        if k not in best_emp or pref < best_emp[k][0]:
            best_emp[k] = (pref, e, v)
    for (y, p, ut, g), (_, e, v) in best_emp.items():
        slot(y, p, ut, "all", g)["academic_staff"] = _num(v)
        emp.setdefault(y, {})[ut] = e

    for d in data.values():
        for types in d.values():
            for degs in types.values():
                tot = degs.get("all", {}).get("total")
                if tot is not None:
                    tot["students_per_staff"] = _ratio(tot.get("students"), tot.get("academic_staff"))

    # province quarantine: documented years where provincial tables are missing -> null + flag
    prov_codes = [
        r[0] for r in con.execute("select code from provinces where code not in ('IRN','KHO')").fetchall()
    ]
    years = []
    for y in sorted(data):
        provs = set(data[y]) - {"IRN"}
        flags = []
        quarantined = []
        if y in HE_QUARANTINE_YEARS:
            for field in ("students", "academic_staff"):
                have = {
                    p
                    for p, ts in data[y].items()
                    if p != "IRN"
                    and any(
                        field in gs.get(g, {}) for dl in ts.values() for gs in dl.values() for g in ("total",)
                    )
                }
                if len(have) < 10:
                    quarantined.append(field)
            if quarantined:
                flags.append("province_tables_quarantined")
                # explicit nulls: every province is present with null values, never zero
                for p in prov_codes:
                    data[y].setdefault(p, None)
        if y <= 1392:
            flags.append("coverage_excl_azad_vs_azad_separate")
        else:
            flags.append("coverage_incl_azad_fulltime_staff")
        if any(p == "KHO" for p in provs):
            flags.append("khorasan_undivided")
        if provs and "ALB" not in provs:
            flags.append("alborz_in_tehran")
        years.append(
            {
                "year_sh": y,
                "year_gregorian": int(gy.get(y, y + 621)),
                "n_provinces": len(provs),
                "flags": flags,
                "quarantined_province_fields": quarantined,
                "staff_basis": emp.get(y, {}),
            }
        )

    data_out = {
        str(y): {p: (_clean(v) if v is not None else None) for p, v in d.items()}
        for y, d in sorted(data.items())
    }
    types = sorted({ut for d in data.values() for ts in d.values() if ts for ut in ts})
    degs = sorted({dl for d in data.values() for ts in d.values() if ts for t in ts.values() for dl in t})

    prov = {}
    for y, f, t in con.execute(
        """select distinct year_sh, source_file, source_table from v_he_best
           where metric in ('students','academic_staff') and field_group='all' and rank='all'"""
    ).fetchall():
        prov.setdefault(y, set()).add(f"{f} :: {t}")

    doc = {
        "university_types": types,
        "degree_levels": degs,
        "genders": GENDERS,
        "fields": ["students", "academic_staff", "students_per_staff"],
        "years": years,
        "data": data_out,
    }
    return doc, prov


# ------------------------------------------------------------------ coverage / meta
def _coverage(k12: dict, he: dict) -> dict:
    cov: dict = {"k12": {}, "he": {}}
    for lv in k12["levels"]:
        for g in ("male", "female"):
            ys, counts = [], []
            for y, d in k12["data"].items():
                n = sum(
                    1
                    for p, v in d.items()
                    if p != "IRN" and v.get(lv, {}).get(g, {}).get("students") is not None
                )
                nat = d.get("IRN", {}).get(lv, {}).get(g, {}).get("students") is not None
                if n or nat:
                    ys.append(int(y))
                    counts.append(n)
            cov["k12"].setdefault(lv, {})[g] = {
                "students_years": _ranges(ys),
                "max_provinces": max(counts) if counts else 0,
                "years_with_province_split": _ranges([y for y, c in zip(ys, counts, strict=True) if c]),
            }
    cov["k12_teachers_by_gender"] = "not published in the yearbook tables; teachers are totals only"
    for dl in he["degree_levels"]:
        for g in ("male", "female"):
            ys, counts = [], []
            for y, d in he["data"].items():
                n = sum(
                    1
                    for p, ts in d.items()
                    if p != "IRN" and ts
                    for t in ts.values()
                    if t.get(dl, {}).get(g, {}).get("students") is not None
                )
                nat = any(
                    t.get(dl, {}).get(g, {}).get("students") is not None
                    for t in (d.get("IRN") or {}).values()
                )
                if n or nat:
                    ys.append(int(y))
                    counts.append(n)
            cov["he"].setdefault(dl, {})[g] = {
                "students_years": _ranges(ys),
                "years_with_province_split": _ranges([y for y, c in zip(ys, counts, strict=True) if c]),
            }
    cov["he_academic_staff_by_gender"] = (
        "male/female staff exist for azad, excl_azad (<=1392) and all_reported (1393-1401) at province level; "
        "never by degree level or by university type after 1392"
    )
    return cov


FLAG_DEFINITIONS = {
    "teacher_proxy_educational_staff": (
        "K-12: before 1394 the yearbooks print 'educational staff' (karkonan amoozeshi: teachers plus "
        "principals/assistants) instead of 'teachers' (moallem). It is used as the teacher count, so "
        "students-per-teacher is probably slightly low; the series has a definition break at 1394. "
        "years[].teacher_definition says which one applies per level."
    ),
    "khorasan_undivided": (
        "Up to 1382 Khorasan is one province (code KHO). Paint it on Razavi, North and South Khorasan; "
        "its figure is not the sum of the three."
    ),
    "alborz_in_tehran": (
        "Before Alborz became its own province (first data year 1390) its students and staff are counted "
        "in Tehran; ALB has no data and Tehran is overstated relative to later years."
    ),
    "school_reform_1391_93": (
        "School-system reform 1391-93 (5-3-4 became 6-3-3): whole grades move between primary, lower and "
        "upper secondary, so level series break (lower secondary enrolment -35% in 1391, +49% in 1394). "
        "Compare levels within one system only, or use core_three."
    ),
    "province_tables_quarantined": (
        "Higher education: the province tables of 1399, 1400 and 1402 (PDF yearbooks) failed validation "
        "(province-share shifts) and were excluded. The listed fields are null for provinces, never zero."
    ),
    "coverage_excl_azad_vs_azad_separate": (
        "Higher education up to 1392: yearbooks print non-Azad institutions (university_type excl_azad, "
        "full-time AND hourly staff) and Islamic Azad University (azad) separately. Not comparable with "
        "1393+."
    ),
    "coverage_incl_azad_fulltime_staff": (
        "Higher education from 1393: all_reported includes Islamic Azad University and counts full-time "
        "academic staff only. Break in series at 1393."
    ),
}


def meta_json(k12, he, generated_at) -> dict:
    k_years = [y["year_sh"] for y in k12["years"]]
    h_years = [y["year_sh"] for y in he["years"]]
    k_prov = [y["year_sh"] for y in k12["years"] if y["n_provinces"] >= 20]
    h_prov = [y["year_sh"] for y in he["years"] if y["n_provinces"] >= 20]
    return {
        "generated_at": generated_at,
        "source": "Statistical Centre of Iran, Salname Amari Keshvar (statistical yearbook), parsed by "
        "education-stats ETL; every number traces to provenance.json",
        "year_convention": "year_sh is the start year of the academic year (1402 = 1402-03 = 2023-24); "
        "year_gregorian = year_sh + 621",
        "k12": {
            "year_range": [min(k_years), max(k_years)],
            "province_level_range": [min(k_prov), max(k_prov)] if k_prov else None,
            "province_level_years": _ranges(k_prov),
            "national_only_years": _ranges([y for y in k_years if y not in set(k_prov)]),
            "levels": {
                "primary": "primary school (daboostan)",
                "lower_secondary": "lower secondary (rahnamaei until 1390, motevasete aval after)",
                "upper_secondary": "upper secondary (motevasete / motevasete dovom)",
                "all_levels": "the printed all-levels row (includes preschool and pre-university), regular programme",
                "core_three": "primary + lower + upper secondary summed (v_k12_core_students_per_teacher); "
                "gender students = sum of the three levels",
            },
            "scope": "regular programme only (adult, special-needs excluded); area, branch and sector all = total",
            "students_per_teacher": "students / teachers (or educational staff before 1394); null if either missing",
        },
        "higher_education": {
            "year_range": [min(h_years), max(h_years)],
            "province_level_range": [min(h_prov), max(h_prov)] if h_prov else None,
            "province_level_years": _ranges(h_prov),
            "quarantined_years": sorted(HE_QUARANTINE_YEARS),
            "university_types": {
                "all_reported": "all institutions reported, incl. Islamic Azad University (1393+); national "
                "series also exists for older years from a few tables",
                "azad": "Islamic Azad University",
                "excl_azad": "all institutions except Islamic Azad (<=1392)",
                "payame_noor": "Payame Noor University",
                "public_msrt": "public universities under the Ministry of Science (MSRT)",
                "public_mohme": "medical universities under the Ministry of Health (MOHME)",
                "public_other": "other public institutions",
                "applied_science": "University of Applied Science and Technology (UAST)",
                "technical_vocational_univ": "technical and vocational university",
                "farhangian_teacher_training": "Farhangian (teacher training) University",
                "private_nonprofit": "private non-profit institutions",
            },
            "degree_levels": {
                "all": "all degree levels",
                "associate": "associate (kardani)",
                "bachelor": "bachelor (karshenasi)",
                "master": "master (karshenasi arshad)",
                "professional_doctorate": "professional doctorate",
                "phd": "PhD",
            },
            "availability": (
                "Province level exists only for university_type all_reported (1393+), azad and excl_azad "
                "(<=1392), mostly degree_level all. Per-type and per-degree figures are national (IRN) only. "
                "Academic staff exist only for degree_level all and for all_reported/azad/excl_azad; "
                "students_per_staff by university type or degree level is therefore not available."
            ),
            "students_per_staff": "students / academic staff (full-time from 1393; see years[].staff_basis); "
            "total gender only (male/female ratios would mix different populations)",
        },
        "gender_coverage": _coverage(k12, he),
        "flag_definitions": FLAG_DEFINITIONS,
        "caveats": [
            "Gender splits are only those printed in the yearbooks: students by male/female; teachers and "
            "academic staff mostly totals. No split is estimated.",
            "Ratios are crude: HE province ratios mislead where students attend Azad/Payame Noor branches "
            "staffed from other provinces (e.g. Mazandaran, Gilan).",
            "Yearbooks 1345-1369 are not used; 1370-1379 are not parsed. Years before 1380 appear only as "
            "national historic rows reprinted in later yearbooks.",
            "Map geometry: geoBoundaries 2017 ADM1, simplified; province borders approximate.",
        ],
        "files": {
            "provinces.json": "SVG paths + labels",
            "k12.json": "data[year][province][level][gender] = {students, teachers, students_per_teacher}",
            "he.json": "data[year][province|null][university_type][degree_level][gender] = "
            "{students, academic_staff, students_per_staff}; province null = quarantined",
            "provenance.json": "datasets[k12|he][year] = list of 'source_file :: source_table'",
        },
    }


# ------------------------------------------------------------------ main
def _dump(path: Path, doc) -> int:
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n")
    return path.stat().st_size


def export(db: Path, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db), read_only=True)
    k12, k_prov = k12_json(con)
    he, h_prov = he_json(con)
    con.close()
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    provenance = {
        "format": "source_file :: source_table, relative to the yearbook folder (Keshvari)",
        "datasets": {
            "k12": {str(y): sorted(v) for y, v in sorted(k_prov.items())},
            "he": {str(y): sorted(v) for y, v in sorted(h_prov.items())},
        },
    }
    sizes = {}
    for name, doc in [
        ("provinces.json", provinces_json()),
        ("k12.json", k12),
        ("he.json", he),
        ("provenance.json", provenance),
        ("meta.json", meta_json(k12, he, now)),
    ]:
        sizes[name] = _dump(out / name, doc)
    return sizes


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "out" / "edu.duckdb")
    ap.add_argument("--out", type=Path, default=ROOT / "exports" / "site")
    a = ap.parse_args()
    sizes = export(a.db, a.out)
    for k, v in sizes.items():
        print(f"{k:18s}{v / 1024:9.1f} KB")
    print(f"{'total':18s}{sum(sizes.values()) / 1024:9.1f} KB -> {a.out}")


if __name__ == "__main__":
    main()
