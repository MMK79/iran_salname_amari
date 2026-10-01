#!/usr/bin/env python
"""Export the education statistics as static JSON for a website's interactive Iran map.

    uv run python scripts/export_site.py [--db data/out/edu.duckdb] [--out exports/site]

Writes provinces.json, k12.json, he.json, he_quality.json, outcomes.json, relations.json, provenance.json,
meta.json.
Everything is read from the SQL views (v_k12_best, v_k12_students_per_teacher,
v_k12_core_students_per_teacher, v_he_best, v_he_students_per_staff, v_k12_pass_rate, v_k12_class_size,
v_k12_completion, v_he_graduation_ratio, v_he_cohort_completion, v_he_rank_mix, v_he_degree_mix_trend);
no cleaning is redone here.

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
import numpy as np
import pandas as pd

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



# ------------------------------------------------------------------ higher-education quality
COMPLETION_DEGREES = ["associate", "bachelor", "master", "phd", "professional_doctorate", "all"]
DEGREE_MIX_BASES = ["all_reported", "azad_plus_excl_azad", "azad", "excl_azad"]


def _flags_he_quality(y: int, section: str, withheld: bool = False, pandemic: bool = False, mixed: bool = False):
    f = []
    if section == "completion":
        if mixed:
            f.append("completion_mixed_degree_lengths")
        if pandemic:
            f.append("completion_pandemic_window")
        if withheld:
            f.append("completion_provinces_withheld")
        f.append("coverage_excl_azad_vs_azad_separate" if y <= 1392 else "coverage_incl_azad_fulltime_staff")
    elif section == "rank_mix":
        f.append("coverage_excl_azad_vs_azad_separate" if y <= 1392 else "coverage_incl_azad_fulltime_staff")
        f.append("rank_not_split_by_gender")
    elif section == "degree_mix":
        f.append("coverage_excl_azad_vs_azad_separate" if y <= 1392 else "coverage_incl_azad_fulltime_staff")
        if y <= 1392:
            f.append("azad_doctorate_bundled")
    return f


def he_quality_json(con) -> tuple[dict, dict]:
    """Cohort completion ratio, faculty rank mix and degree mix, all with a status per value."""
    prov: dict[int, set] = {}
    comp: dict[int, dict] = {}
    withheld_years: dict[int, set] = {}
    pandemic: dict[int, bool] = {}
    mixed_years: set[int] = set()
    for (y, ey, p, ut, dl, g, nom, lb, gr, en, cr, status, pw, mixed, prv) in con.execute(
        """select year_sh, entry_year_sh, province_code, university_type, degree_level, gender, nominal_years,
                  length_basis, graduates, entrants, completion_ratio, status, pandemic_in_window,
                  mixed_degree_lengths_pre_1393, provenance
           from v_he_cohort_completion"""
    ).fetchall():
        if lb == "plus_1" and g != "total":
            continue  # the sensitivity variant is published for gender total only
        slot = (
            comp.setdefault(y, {}).setdefault(p, {}).setdefault(ut, {}).setdefault(dl, {}).setdefault(lb, {})
        )
        slot["nominal_years"] = int(nom)
        slot["entry_year_sh"] = int(ey)
        if cr is None:
            slot[g] = {"completion_ratio": None, "status": status}
            if p != "IRN":
                withheld_years.setdefault(y, set()).add(status)
        else:
            slot[g] = {
                "graduates": _num(gr),
                "entrants": _num(en),
                "completion_ratio": _round(cr),
                "status": status,
            }
        pandemic[y] = pandemic.get(y, False) or bool(pw)
        if ut == "azad_plus_excl_azad":
            mixed_years.add(y)
        g_src, _, e_src = prv.partition(" <- ")
        prov.setdefault(y, set()).add(g_src)
        prov.setdefault(ey, set()).add(e_src)
    comp_years = []
    for y in sorted(comp):
        comp_years.append(
            {
                "year_sh": y,
                "n_provinces": len([p for p in comp[y] if p != "IRN"]),
                "flags": _flags_he_quality(
                    y, "completion", withheld=bool(withheld_years.get(y)), pandemic=pandemic.get(y, False),
                    mixed=y in mixed_years,
                ),
            }
        )

    # rank mix
    ranks: dict[int, dict] = {}
    best: dict[tuple, tuple] = {}
    for row in con.execute(
        """select year_sh, province_code, university_type, employment, professors, associate_professors,
                  assistant_professors, instructors, non_faculty, faculty_members, senior_share, students,
                  students_per_senior, students_per_faculty_member, status, provenance
           from v_he_rank_mix"""
    ).fetchall():
        k = (row[0], row[1], row[2])
        pref = HE_STAFF_PREFERENCE.get(row[3], 9)
        if k not in best or pref < best[k][0]:
            best[k] = (pref, row)
    for (y, p, ut), (_, r) in best.items():
        (_y, _p, _ut, emp, pr, ap, asp, ins, nf, fac, sh, stu, sps, spf, status, prv) = r
        if status != "ok":
            rec = {"employment": emp, "status": status}
        else:
            rec = {
                "employment": emp,
                "professors": _num(pr),
                "associate_professors": _num(ap),
                "assistant_professors": _num(asp),
                "instructors": _num(ins),
                "non_faculty": _num(nf),
                "faculty_members": _num(fac),
                "senior_share": _round(sh),
                "students": _num(stu),
                "students_per_senior": _round(sps, 2),
                "students_per_faculty_member": _round(spf, 2),
                "status": status,
            }
        ranks.setdefault(y, {}).setdefault(p, {})[ut] = rec
        prov.setdefault(y, set()).add(prv)
    rank_years = [
        {
            "year_sh": y,
            "n_provinces": len([p for p in ranks[y] if p != "IRN"]),
            "flags": _flags_he_quality(y, "rank_mix"),
        }
        for y in sorted(ranks)
    ]

    # degree mix
    mix: dict[int, dict] = {}
    for y, p, ut, tot, a, b, m, ph, pd_, dc, sa, sb, sm, sp, sd, spg, status, prv in con.execute(
        """select year_sh, province_code, university_type, students, associate, bachelor, master, phd,
                  professional_doctorate, doctoral, share_associate, share_bachelor, share_master, share_phd,
                  share_doctoral, share_postgraduate, status, provenance
           from v_he_degree_mix_trend where status <> 'degree_missing'"""
    ).fetchall():
        if status == "ok":
            rec = {
                "students": _num(tot),
                "students_by_degree": {
                    "associate": _num(a), "bachelor": _num(b), "master": _num(m), "phd": _num(ph),
                    "professional_doctorate": _num(pd_), "doctoral": _num(dc),
                },
                "share": {
                    "associate": _round(sa), "bachelor": _round(sb), "master": _round(sm), "phd": _round(sp),
                    "doctoral": _round(sd), "postgraduate": _round(spg),
                },
                "status": status,
            }
        else:
            rec = {"status": status}
        mix.setdefault(y, {}).setdefault(p, {})[ut] = rec
        prov.setdefault(y, set()).add(prv)
    mix_years = [
        {
            "year_sh": y,
            "n_provinces": len([p for p in mix[y] if p != "IRN"]),
            "flags": _flags_he_quality(y, "degree_mix"),
        }
        for y in sorted(mix)
    ]

    doc = {
        "measures": {
            "completion": "COHORT COMPLETION RATIO, not a completion rate: graduates in year t / new entrants in year "
            "t - d, same degree level, gender, province and population basis. d = nominal programme length "
            "(associate 2, bachelor 4, master 2, PhD 4, professional doctorate 6), plus_1 = d + 1 (sensitivity). "
            "The two are different stocks of different people (transfers, repeaters, longer or shorter "
            "programmes, dropouts, late finishers, guest students). null + status when withheld "
            "(implausible_rate: outside 0.2-1.3 | province_sum_mismatch: provinces do not add up to the national "
            "row). data[year=t][province][basis][degree][length_basis][gender]; length_basis nominal | plus_1 "
            "(gender total only) | mixed_convention (degree 'all', d = 4 by convention). basis all_reported = "
            "1393+ (entry year >= 1393 as well, i.e. t >= 1395 for associate/master, 1397 for bachelor/PhD, "
            "1399 for professional doctorate); azad_plus_excl_azad = degree 'all' only, years before 1393.",
            "rank_mix": "Full-time (1393+; excl_azad includes hourly staff, azad unspecified before) academic staff by "
            "rank; senior = professor + associate professor; senior_share = senior / faculty members "
            "(professor + associate + assistant + instructor + instructor assistant, non-faculty excluded); "
            "students_per_senior = all students of the same population / senior. data[year][province][university_type]. "
            "Ranks are printed for gender total only. instructors = morabbi + morabbi amoozeshyar.",
            "degree_mix": "Share of each degree level in total enrolment (gender total). share.doctoral = PhD + "
            "professional doctorate (comparable across the 1393 break: before 1393 Azad prints one doctorate "
            "figure bundling both, so share.phd is null for azad and azad_plus_excl_azad); share.postgraduate = "
            "master + doctoral. Province level exists for all_reported 1393-1398 and 1401-1402 only. "
            "data[year][province][basis]; basis all_reported | azad_plus_excl_azad | azad | excl_azad.",
        },
        "completion_degree_levels": COMPLETION_DEGREES,
        "degree_mix_bases": DEGREE_MIX_BASES,
        "genders": GENDERS,
        "completion": {
            "years": comp_years,
            "data": {str(y): {p: _clean(v) for p, v in d.items()} for y, d in sorted(comp.items())},
        },
        "rank_mix": {
            "years": rank_years,
            "data": {str(y): {p: _clean(v) for p, v in d.items()} for y, d in sorted(ranks.items())},
        },
        "degree_mix": {
            "years": mix_years,
            "data": {str(y): {p: _clean(v) for p, v in d.items()} for y, d in sorted(mix.items())},
        },
    }
    return doc, prov


# ------------------------------------------------------------------ outcomes + relations
PASS_LEVELS = ["primary", "lower_secondary"]
REL_MIN_PROVINCES = 25  # a cross-province correlation is only computed for years with >= this many units
# Specs for the pooled within-province (province + year fixed effects) regressions.
FE_SPECS = {
    "all_valid_years": "every year x level with a published pass rate",
    "excl_reform_1391_93": "drops 1391-1393 (5-3-4 -> 6-3-3 reform moves grades between levels)",
    "from_1394": "1394 onwards only: one school system and the same teacher definition (moallem)",
}
OUTCOME_FLAGS = ("school_reform_1391_93", "pandemic_1399", "pass_year_relabelled_1398")


def _opt(v):
    return _num(v)


def _round(v, nd=4):
    if v is None:
        return None
    try:
        if math.isnan(v) or math.isinf(v):
            return None
    except TypeError:
        return None
    return round(float(v), nd)


def outcomes_json(con) -> dict:
    data: dict[int, dict] = {}

    def prov(y, p):
        return data.setdefault(y, {}).setdefault(p, {})

    pass_withheld: dict[int, set] = {}
    for y, p, lv, g, passed, st, rate, status in con.execute(
        "select year_sh, province_code, level, gender, passed, students, pass_rate, status from v_k12_pass_rate"
    ).fetchall():
        slot = prov(y, p).setdefault("pass_rate", {}).setdefault(lv, {})
        if rate is None:
            slot[g] = {"pass_rate": None, "status": status}
            if status == "year_unreliable":
                pass_withheld.setdefault(y, set()).add(lv)
        else:
            slot[g] = {
                "passed": _num(passed),
                "students": _num(st),
                "pass_rate": _round(rate),
                "status": status,
            }
    for y, p, lv, st, cl, status in con.execute(
        "select year_sh, province_code, level, students, classes, status from v_k12_class_size"
    ).fetchall():
        rec = {"students": _num(st), "classes": _num(cl), "students_per_class": _ratio(st, cl)}
        if status != "ok":
            rec = {"students_per_class": None, "status": status}
        prov(y, p).setdefault("class_size", {})[lv] = rec
    for y, p, g, gr, st, rate, status in con.execute(
        "select year_sh, province_code, gender, graduates, students, completion_proxy, status from v_k12_completion"
    ).fetchall():
        rec = (
            {"graduates": _num(gr), "students": _num(st), "completion_proxy": _round(rate), "status": status}
            if status == "ok"
            else {"completion_proxy": None, "status": status}
        )
        prov(y, p).setdefault("completion_proxy", {})[g] = rec
    for y, p, g, gr, st, rate, basis, status in con.execute(
        "select year_sh, province_code, gender, graduates, students, graduation_ratio, basis, status "
        "from v_he_graduation_ratio"
    ).fetchall():
        rec = (
            {
                "graduates": _num(gr),
                "students": _num(st),
                "graduation_ratio": _round(rate),
                "basis": basis,
                "status": status,
            }
            if status == "ok"
            else {"graduation_ratio": None, "basis": basis, "status": status}
        )
        prov(y, p).setdefault("he_graduation_ratio", {})[g] = rec

    surv_withheld: dict[int, str] = {}
    for y, sy, p, g, lo, up, sv, status in con.execute(
        "select year_sh, survival_year_sh, province_code, gender, lower_students, upper_students, cohort_survival, "
        "status from v_k12_cohort_survival"
    ).fetchall():
        if sv is None:
            rec = {"cohort_survival": None, "status": status}
            if p != "IRN":
                surv_withheld.setdefault(y, set()).add(status)
        else:
            rec = {
                "lower_students": _num(lo),
                "upper_students": _num(up),
                "survival_year_sh": int(sy),
                "cohort_survival": _round(sv),
                "status": status,
            }
        prov(y, p).setdefault("cohort_survival", {})[g] = rec

    years = []
    for y in sorted(data):
        flags = []
        if 1388 <= y <= 1393:
            flags.append("cohort_survival_reform_window")
        if 1396 <= y <= 1400:
            flags.append("cohort_survival_pandemic_window")
        if surv_withheld.get(y) and y not in range(1388, 1394):
            flags.append("cohort_survival_provinces_withheld")
        if 1391 <= y <= 1393:
            flags.append("school_reform_1391_93")
        if y == 1399:
            flags.append("pandemic_1399")
        if y == 1398:
            flags.append("pass_year_relabelled_1398")
        if y <= 1393:
            flags.append("teacher_proxy_educational_staff")
        if y <= 1392:
            flags.append("coverage_excl_azad_vs_azad_separate")
        else:
            flags.append("coverage_incl_azad_fulltime_staff")
        if pass_withheld.get(y):
            flags.append("pass_rate_provinces_withheld")
        years.append(
            {
                "year_sh": y,
                "n_units": len([p for p in data[y] if p != "IRN"]),
                "flags": flags,
                "pass_rate_withheld_levels": sorted(pass_withheld.get(y, [])),
            }
        )
    return {
        "levels_pass_rate": PASS_LEVELS,
        "levels_class_size": K12_LEVELS,
        "genders": GENDERS,
        "measures": {
            "pass_rate": "passed / students, same level, gender, province, year; regular programme, adults "
            "excluded; null + status when withheld (status implausible_rate | year_unreliable). "
            "data[year][prov].pass_rate[level][gender]",
            "class_size": "students / classes (regular programme); data[year][prov].class_size[level]",
            "completion_proxy": "upper-secondary graduates / upper-secondary students (a throughput proxy, "
            "NOT a completion rate); data[year][prov].completion_proxy[gender]; only some years exist",
            "he_graduation_ratio": "higher-education graduates / students, all degrees (a throughput proxy, "
            "NOT a completion rate); basis = all_reported | azad_plus_excl_azad | mixed; "
            "data[year][prov].he_graduation_ratio[gender]",
            "cohort_survival": "APPARENT COHORT SURVIVAL lower -> upper secondary (the yearbooks print no drop-out "
            "or out-of-school table): upper-secondary students in year t+3 / lower-secondary students in year t, "
            "regular programme, same province and gender. data[year=t][prov].cohort_survival[gender] = "
            "{lower_students, upper_students, survival_year_sh, cohort_survival, status}. Not a drop-out rate: "
            "it also reflects repeaters, inter-province migration and moves to adult/non-regular programmes. "
            "null + status when withheld (reform_window | boundary_change | implausible_rate | year_unreliable). "
            "Usable: provinces t = 1394-1399; national t = 1377-1387 (old 5-3-4 system) and 1394-1399",
        },
        "years": years,
        "data": {
            str(y): {p: _clean(v) for p, v in d.items()} for y, d in sorted(data.items())
        },
    }


def _cluster_fe(df: pd.DataFrame, x: str, y: str) -> dict | None:
    """OLS of y on x with province and year dummies; CR1 standard errors clustered by province."""
    d = df[["province_code", "year_sh", x, y]].dropna()
    cnt = d.groupby("province_code")["year_sh"].transform("count")
    d = d[cnt >= 2]
    ys = d["year_sh"].nunique()
    g = d["province_code"].nunique()
    if len(d) < 30 or ys < 3 or g < 5:
        return None
    X = pd.concat(
        [
            d[[x]].reset_index(drop=True),
            pd.get_dummies(d["province_code"], drop_first=True, dtype=float).reset_index(drop=True),
            pd.get_dummies(d["year_sh"], drop_first=True, dtype=float).reset_index(drop=True),
        ],
        axis=1,
    )
    X.insert(0, "const", 1.0)
    Xm = X.to_numpy(float)
    yv = d[y].to_numpy(float)
    n, k = Xm.shape
    xtx_inv = np.linalg.pinv(Xm.T @ Xm)
    beta = xtx_inv @ Xm.T @ yv
    u = yv - Xm @ beta
    meat = np.zeros((k, k))
    for _, idx in d.reset_index(drop=True).groupby("province_code").indices.items():
        sg = Xm[idx].T @ u[idx]
        meat += np.outer(sg, sg)
    adj = (g / (g - 1)) * ((n - 1) / (n - k))
    V = adj * xtx_inv @ meat @ xtx_inv
    coef, se = float(beta[1]), float(math.sqrt(max(V[1, 1], 0.0)))
    out = {
        "coef": _round(coef, 6),
        "se_cluster": _round(se, 6),
        "t": _round(coef / se, 3) if se else None,
        "n": int(n),
        "n_provinces": int(g),
        "n_years": int(ys),
        "years": [int(d["year_sh"].min()), int(d["year_sh"].max())],
    }
    try:  # optional: t(g-1) interval; scipy ships with the analysis dependency group
        from scipy import stats

        crit = float(stats.t.ppf(0.975, g - 1))
        out["ci95"] = [_round(coef - crit * se, 6), _round(coef + crit * se, 6)]
        out["p_value"] = _round(float(2 * stats.t.sf(abs(coef / se), g - 1)), 4) if se else None
    except ImportError:
        out["ci95"] = None
        out["p_value"] = None
    return out


# Cohort survival (lower -> upper secondary, v_k12_cohort_survival) against students per teacher.
# Year t = the lower-secondary year; the exposure is read either at the cohort's baseline (lower-secondary
# students per teacher in t) or where the survivors are counted (upper-secondary students per teacher in t+3).
SURV_EXPOSURES = {
    "lower_secondary_at_t": "students per teacher of lower secondary in year t (the cohort's baseline year)",
    "upper_secondary_at_t_plus_3": "students per teacher of upper secondary in year t+3 (where survivors are counted)",
}
SURV_FE_SPECS = {
    "all_valid_years": "every publishable window: t = 1394-1399 (the 1388-93 windows touch the reform; 1387 misaligned)",
    "excl_cohort_1399": "drops t = 1399 (window 1399-1402, the last year, includes COVID years)",
}


def _survival_relations(con) -> tuple[dict, dict]:
    df = con.execute(
        """select s.year_sh, s.province_code, s.cohort_survival,
                  lo.students_per_teacher as spt_lower_at_t, up.students_per_teacher as spt_upper_at_t3
           from v_k12_cohort_survival s
           left join v_k12_students_per_teacher lo on lo.year_sh=s.year_sh and lo.province_code=s.province_code
                and lo.level='lower_secondary'
           left join v_k12_students_per_teacher up on up.year_sh=s.survival_year_sh
                and up.province_code=s.province_code and up.level='upper_secondary'
           where s.gender='total' and s.province_code <> 'IRN' and s.cohort_survival is not null"""
    ).df()
    xs = {"lower_secondary_at_t": "spt_lower_at_t", "upper_secondary_at_t_plus_3": "spt_upper_at_t3"}
    cross: dict = {}
    fe: dict = {}
    for name, x in xs.items():
        rows = []
        for yr, g in df.groupby("year_sh"):
            d = g[[x, "cohort_survival"]].dropna()
            if len(d) < REL_MIN_PROVINCES:
                continue
            rows.append(
                {
                    "year_sh": int(yr),
                    "n": int(len(d)),
                    "pearson": _round(d[x].corr(d["cohort_survival"], method="pearson")),
                    "spearman": _round(d[x].corr(d["cohort_survival"], method="spearman")),
                    "flags": [f for f, ok in (("cohort_survival_pandemic_window", 1396 <= yr <= 1400),) if ok],
                }
            )
        cross[name] = rows
        for spec in SURV_FE_SPECS:
            d = df if spec == "all_valid_years" else df[df.year_sh <= 1398]
            fe.setdefault(name, {})[spec] = _cluster_fe(d, x, "cohort_survival")
    return cross, {
        "model": "cohort_survival_it = a_province + b_year + beta * x_it + e_it (t = lower-secondary year), OLS "
        "with dummies, standard errors CR1-clustered by province; coef = change in survival (a fraction; x100 "
        "for percentage points) per +1 student per teacher",
        "exposures": SURV_EXPOSURES,
        "specs": SURV_FE_SPECS,
        "results": fe,
    }


# HE cohort completion (v_he_cohort_completion, all_reported, gender total, province level) against students per
# academic staff member (v_he_students_per_staff). Year t = graduation year; the exposure is read where the
# cohort ENTERED (t - d) or where it graduated (t).
HE_EXPOSURES = {
    "at_entry_year": "students per academic staff member of all_reported in year t - d (the cohort's entry year)",
    "at_graduation_year": "students per academic staff member of all_reported in year t (graduation year)",
}
HE_FE_SPECS = {"all_valid_years": "every province x year with a published completion ratio and staff ratio"}
HE_COMPLETION_DEGREES = ["bachelor", "all"]


def _he_completion_relations(con) -> dict:
    out: dict = {}
    for dl in HE_COMPLETION_DEGREES:
        df = con.execute(
            f"""select c.year_sh, c.entry_year_sh, c.province_code, c.completion_ratio,
                       e.students_per_staff as sps_entry, g.students_per_staff as sps_grad
                from v_he_cohort_completion c
                left join v_he_students_per_staff e on e.year_sh=c.entry_year_sh and e.province_code=c.province_code
                     and e.university_type='all_reported'
                left join v_he_students_per_staff g on g.year_sh=c.year_sh and g.province_code=c.province_code
                     and g.university_type='all_reported'
                where c.university_type='all_reported' and c.degree_level='{dl}' and c.gender='total'
                  and c.length_basis in ('nominal', 'mixed_convention') and c.province_code <> 'IRN'
                  and c.completion_ratio is not null"""
        ).df()
        cross: dict = {}
        fe: dict = {}
        for name, x in (("at_entry_year", "sps_entry"), ("at_graduation_year", "sps_grad")):
            rows = []
            for yr, g in df.groupby("year_sh"):
                d = g[[x, "completion_ratio"]].dropna()
                if len(d) < REL_MIN_PROVINCES:
                    continue
                rows.append(
                    {
                        "year_sh": int(yr),
                        "entry_year_sh": int(g["entry_year_sh"].iloc[0]),
                        "n": int(len(d)),
                        "pearson": _round(d[x].corr(d["completion_ratio"], method="pearson")),
                        "spearman": _round(d[x].corr(d["completion_ratio"], method="spearman")),
                        "flags": [f for f, ok in (("completion_pandemic_window", yr >= 1399),) if ok],
                    }
                )
            cross[name] = rows
            for spec in HE_FE_SPECS:
                fe.setdefault(name, {})[spec] = _cluster_fe(df, x, "completion_ratio")
        out[dl] = {"cross_province_by_year": cross, "within_province_fixed_effects": fe}
    return {
        "interpretation": "ASSOCIATION, not effect. Province aggregates; students_per_staff is crude (students attend "
        "Azad / Payame Noor branches staffed from other provinces) and the completion ratio is a stock-flow ratio "
        "(see he_quality.json measures.completion). Only 3-4 graduation years exist at province level "
        "(t = 1397, 1400, 1401; 1398 has no province graduate table, 1399 fails the province-sum check).",
        "model": "completion_ratio_it = a_province + b_year + beta * x_it + e_it, OLS with dummies, standard errors "
        "CR1-clustered by province; coef = change in the completion ratio (a fraction; x100 for percentage "
        "points) per +1 student per academic staff member",
        "outcome": "graduates in t / entrants in t - d, university_type all_reported, gender total; bachelor d = 4, "
        "'all' = all degrees with d = 4 by convention",
        "exposures": HE_EXPOSURES,
        "specs": HE_FE_SPECS,
        "by_degree": out,
    }


def relations_json(con) -> dict:
    df = con.execute(
        """select t.year_sh, t.province_code, t.level, t.students_per_teacher, t.teacher_definition,
                  c.students_per_class, p.pass_rate
           from v_k12_students_per_teacher t
           left join v_k12_class_size c on c.year_sh=t.year_sh and c.province_code=t.province_code
                and c.level=t.level and c.status='ok'
           left join v_k12_pass_rate p on p.year_sh=t.year_sh and p.province_code=t.province_code
                and p.level=t.level and p.gender='total'
           where t.province_code <> 'IRN' and t.level in ('primary','lower_secondary')"""
    ).df()
    pairs = {
        "students_per_teacher_vs_pass_rate": ("students_per_teacher", "pass_rate"),
        "class_size_vs_pass_rate": ("students_per_class", "pass_rate"),
    }
    cross: dict = {}
    for lv in PASS_LEVELS:
        for name, (x, y) in pairs.items():
            rows = []
            for yr, g in df[df.level == lv].groupby("year_sh"):
                d = g[[x, y]].dropna()
                if len(d) < REL_MIN_PROVINCES:
                    continue
                rows.append(
                    {
                        "year_sh": int(yr),
                        "n": int(len(d)),
                        "pearson": _round(d[x].corr(d[y], method="pearson")),
                        "spearman": _round(d[x].corr(d[y], method="spearman")),
                        "flags": [f for f, ok in (("school_reform_1391_93", 1391 <= yr <= 1393),
                                                  ("pandemic_1399", yr == 1399),
                                                  ("teacher_proxy_educational_staff", yr <= 1393)) if ok],
                    }
                )
            cross.setdefault(name, {})[lv] = rows

    fe: dict = {}
    for lv in PASS_LEVELS:
        d_lv = df[df.level == lv]
        for name, (x, y) in pairs.items():
            for spec in FE_SPECS:
                d = d_lv
                if spec == "excl_reform_1391_93":
                    d = d[~d.year_sh.between(1391, 1393)]
                elif spec == "from_1394":
                    d = d[d.year_sh >= 1394]
                est = _cluster_fe(d, x, y)
                fe.setdefault(name, {}).setdefault(lv, {})[spec] = est
    surv_cross, surv_fe = _survival_relations(con)
    return {
        "interpretation": "ASSOCIATION, not effect. Correlations are ecological (province aggregates) and "
        "confounded by urbanisation, income, the teacher-definition break at 1394, composition of "
        "provinces, and data-definition changes. Primary pass rates are high and low-variance "
        "(descriptive evaluation), so primary is a weak outcome.",
        "min_provinces_per_year": REL_MIN_PROVINCES,
        "gender": "total",
        "cross_province_by_year": cross,
        "within_province_fixed_effects": {
            "model": "pass_rate_it = a_province + b_year + beta * x_it + e_it, OLS with dummies, standard "
            "errors CR1-clustered by province; coef = change in pass rate (a fraction; x100 for "
            "percentage points) per +1 unit of x",
            "specs": FE_SPECS,
            "results": fe,
        },
        "cohort_survival_cross_province_by_year": surv_cross,
        "cohort_survival_within_province_fixed_effects": surv_fe,
        "he_completion_vs_students_per_staff": _he_completion_relations(con),
    }


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
    "pandemic_1399": (
        "Academic year 1399-1400 (COVID-19 school closures): the national primary pass rate drops to 0.926 "
        "from 0.99 the year before. Read pass rates of this year as exceptional."
    ),
    "pass_year_relabelled_1398": (
        "The 1398 province pass counts come from the 1399 yearbook PDF table 17-17#1, which has no printed "
        "year labels and was labelled 1399 by the parser; its province rows sum to the national 1398 value "
        "printed in the 1400 yearbook, so it is relabelled to 1398 in v_k12_passed_best."
    ),
    "pass_rate_provinces_withheld": (
        "Province pass rates of the listed levels are not published for this year (>= 2 provinces with "
        "rates outside 0.5-1; source table misaligned). Individual implausible rows are also withheld."
    ),
    "cohort_survival_reform_window": (
        "Cohort survival (upper-secondary students in t+3 / lower-secondary students in t): windows t = 1388-1393 "
        "touch the 1391-93 reform. The national ratio there is 0.99-1.09 against 0.83-0.88 on both sides, so "
        "the two stocks do not cover the same grades; withheld (status reform_window)."
    ),
    "cohort_survival_provinces_withheld": (
        "Province cohort survival of this year is not published (>= 2 provinces outside 0.5-1.05, 1387: lower-"
        "secondary province rows misaligned in the source); the national row stays."
    ),
    "cohort_survival_pandemic_window": (
        "The cohort window t..t+3 contains the COVID-19 years 1399-1400; a part of the change in survival may "
        "be pandemic-related (not separable here)."
    ),
    "completion_mixed_degree_lengths": (
        "Higher education before 1393: the yearbooks print no entrants by degree level, so the completion ratio is "
        "computed for all degrees together (Azad + non-Azad summed, d = 4 by convention) although associate "
        "programmes last 2 years and professional doctorates 6-7. A crude continuity series only."
    ),
    "completion_pandemic_window": (
        "The cohort window (entry year .. graduation year) contains the COVID-19 years 1399-1400; part of the "
        "change in the completion ratio may be pandemic-related (not separable here)."
    ),
    "completion_provinces_withheld": (
        "Some province completion ratios of this graduation year are not published: the province tables of one "
        "side do not add up to the national row (status province_sum_mismatch, e.g. the 1399 graduate tables) or "
        "the ratio lies outside 0.2-1.3 (status implausible_rate)."
    ),
    "rank_not_split_by_gender": (
        "Academic staff by rank (professor ... instructor) is printed for gender total only; no split by gender "
        "or degree level exists."
    ),
    "azad_doctorate_bundled": (
        "Before 1393 Islamic Azad University prints one doctorate figure that bundles PhD and professional "
        "doctorate (it equals their sum in 1393). PhD alone is withheld for azad and azad_plus_excl_azad; "
        "use the doctoral share (PhD + professional doctorate)."
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
            "he_quality.json": "completion.data[year=t][province][basis][degree][length_basis][gender] = {graduates, "
            "entrants, completion_ratio, status} (graduates in t / entrants in t-d); rank_mix.data[year][province]"
            "[university_type] = {professors, associate_professors, assistant_professors, instructors, senior_share, "
            "students_per_senior, status}; degree_mix.data[year][province][basis] = {students, share.{associate, "
            "bachelor, master, phd, doctoral, postgraduate}, status}; withheld values are null with a status",
            "outcomes.json": "data[year][province].{pass_rate[level][gender], class_size[level], "
            "completion_proxy[gender], he_graduation_ratio[gender], cohort_survival[gender]}; withheld values are "
            "null with a status",
            "relations.json": "cross_province_by_year (Pearson/Spearman, n >= 25) and "
            "within_province_fixed_effects (province + year FE, cluster-robust); association only; "
            "cohort_survival_* keys hold the same two estimates for cohort survival; "
            "he_completion_vs_students_per_staff.by_degree[bachelor|all] the same for HE cohort completion",
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
    heq, q_prov = he_quality_json(con)
    outcomes = outcomes_json(con)
    relations = relations_json(con)
    con.close()
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    provenance = {
        "format": "source_file :: source_table, relative to the yearbook folder (Keshvari)",
        "datasets": {
            "k12": {str(y): sorted(v) for y, v in sorted(k_prov.items())},
            "he": {str(y): sorted(v) for y, v in sorted(h_prov.items())},
            "he_quality": {str(y): sorted(v) for y, v in sorted(q_prov.items())},
        },
    }
    sizes = {}
    for name, doc in [
        ("provinces.json", provinces_json()),
        ("k12.json", k12),
        ("he.json", he),
        ("he_quality.json", heq),
        ("outcomes.json", outcomes),
        ("relations.json", relations),
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
