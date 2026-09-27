"""Validation checks on the extracted facts (parquet in, parquet out).

Checks
  gender_sum     total == male + female                         (per source row)
  degree_sum     HE: all degrees == sum of degree levels        (per source row)
  province_sum   national row == sum of the provinces            (per source table)
  yoy_jump       |year-on-year change| > 30 % in the best series (warn)
  revision       same number printed differently by two yearbooks (info)
A source table whose arithmetic checks fail for more than 20 % of its rows is marked
`failed` in data/out/table_status.parquet; the analytic SQL views exclude such tables.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from etl.provinces import CURRENT

OUT = Path(__file__).resolve().parent.parent / "data" / "out"
CUR = {p.code for p in CURRENT} | {"KHO"}

K12_KEY = ["yearbook_sh", "source_file", "source_table", "row_label", "year_sh", "province_code", "level",
           "programme", "branch", "sector", "area", "metric"]
HE_KEY = ["yearbook_sh", "source_file", "source_table", "row_label", "year_sh", "province_code", "university_type",
          "degree_level", "field_group", "rank", "employment", "area", "metric"]


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    return df[df.row_category.isna() & df.col_category.isna()]


def _tol(x: float) -> float:
    return max(2.0, abs(x) * 0.005)


def gender_sum(df: pd.DataFrame, key: list[str], domain: str) -> list[dict]:
    p = df.pivot_table(index=key, columns="gender", values="value", aggfunc="first")
    if not {"total", "male", "female"} <= set(p.columns):
        return []
    p = p.dropna(subset=["total", "male", "female"]).reset_index()
    out = []
    for r in p.itertuples(index=False):
        d = r._asdict()
        exp = d["male"] + d["female"]
        ok = abs(d["total"] - exp) <= _tol(d["total"])
        out.append({"check_name": "gender_sum", "severity": "info" if ok else "error", "domain": domain,
                    "yearbook_sh": d["yearbook_sh"], "year_sh": d["year_sh"], "source_file": d["source_file"],
                    "source_table": d["source_table"], "detail": f"{d['metric']} {d['province_code']} {d['row_label']}",
                    "expected": exp, "actual": d["total"], "ok": ok})
    return out


def degree_sum(he: pd.DataFrame) -> list[dict]:
    key = [k for k in HE_KEY if k != "degree_level"] + ["gender"]
    x = he[he.metric.isin(["students", "new_entrants", "graduates"])].copy()
    x["source_table"] = x.source_table.str.split("#").str[0]  # degree levels span continuation parts
    parts = x[x.degree_level.isin(["associate", "bachelor", "master", "professional_doctorate", "phd"])]
    tot = x[x.degree_level == "all"]
    s = parts.groupby(key, dropna=False).value.agg(["sum", "count"]).reset_index()
    m = tot.merge(s, on=key)
    m = m[m["count"] >= 4]
    out = []
    for r in m.itertuples(index=False):
        ok = abs(r.value - r.sum) <= _tol(r.value)
        out.append({"check_name": "degree_sum", "severity": "info" if ok else "error", "domain": "he",
                    "yearbook_sh": r.yearbook_sh, "year_sh": r.year_sh, "source_file": r.source_file,
                    "source_table": r.source_table, "detail": f"{r.metric} {r.province_code} {r.gender}",
                    "expected": r.sum, "actual": r.value, "ok": ok})
    return out


def province_sum(df: pd.DataFrame, key: list[str], domain: str) -> list[dict]:
    k = [c for c in key if c not in ("row_label", "province_code")] + ["gender"]
    prov = df[df.province_code.isin(CUR)]
    nat = df[df.province_code == "IRN"]
    s = prov.groupby(k, dropna=False).value.agg(["sum", "count"]).reset_index()
    s = s[s["count"] >= 20]
    m = nat.merge(s, on=k)
    out = []
    for r in m.itertuples(index=False):
        ok = abs(r.value - r.sum) <= max(5.0, abs(r.value) * 0.01)
        out.append({"check_name": "province_sum", "severity": "info" if ok else "warn", "domain": domain,
                    "yearbook_sh": r.yearbook_sh, "year_sh": r.year_sh, "source_file": r.source_file,
                    "source_table": r.source_table, "detail": f"{r.metric} {r.gender} n={r.count}",
                    "expected": r.sum, "actual": r.value, "ok": ok})
    return out


def cross_publication(df: pd.DataFrame, key: list[str], domain: str) -> list[dict]:
    """The contemporaneous national figure vs the same figure reprinted by the next yearbook(s).

    Catches a correct-looking table read with the wrong column template (1399 PDF)."""
    k = [c for c in key if c not in ("yearbook_sh", "source_file", "source_table", "row_label")] + ["gender"]
    nat = df[df.province_code == "IRN"]
    first = nat[nat.yearbook_sh == nat.year_sh]
    later = nat[(nat.yearbook_sh > nat.year_sh) & (nat.yearbook_sh <= nat.year_sh + 3)]
    later = later.groupby(k, dropna=False).value.median().rename("later").reset_index()
    m = first.merge(later, on=k)
    out = []
    for r in m.itertuples(index=False):
        ok = abs(r.value - r.later) <= max(5.0, abs(r.later) * 0.05)
        out.append({"check_name": "cross_publication", "severity": "info" if ok else "error", "domain": domain,
                    "yearbook_sh": r.yearbook_sh, "year_sh": r.year_sh, "source_file": r.source_file,
                    "source_table": r.source_table, "detail": f"{r.metric} {r.gender} vs later yearbooks",
                    "expected": r.later, "actual": r.value, "ok": ok})
    return out


def revisions(df: pd.DataFrame, key: list[str], domain: str) -> list[dict]:
    k = [c for c in key if c not in ("yearbook_sh", "source_file", "source_table", "row_label")] + ["gender"]
    g = df.groupby(k, dropna=False).value.agg(["min", "max", "count"]).reset_index()
    g = g[(g["count"] > 1) & ((g["max"] - g["min"]) > g["max"].abs() * 0.01 + 2)]
    return [{"check_name": "revision", "severity": "info", "domain": domain, "yearbook_sh": None,
             "year_sh": r.year_sh, "source_file": None, "source_table": None,
             "detail": f"{r.metric} {r.province_code} printed as {r.min:.0f}..{r.max:.0f} in {r.count} places",
             "expected": r.min, "actual": r.max, "ok": True} for r in g.itertuples(index=False)]


def run() -> None:
    k12 = _clean(pd.read_parquet(OUT / "k12.parquet"))
    he = _clean(pd.read_parquet(OUT / "he.parquet"))
    rows: list[dict] = []
    rows += gender_sum(k12, K12_KEY, "k12")
    rows += gender_sum(he, HE_KEY, "he")
    rows += degree_sum(he)
    rows += province_sum(k12, K12_KEY, "k12")
    rows += province_sum(he, HE_KEY, "he")
    rows += cross_publication(k12, K12_KEY, "k12")
    rows += cross_publication(he, HE_KEY, "he")
    v = pd.DataFrame(rows)
    # table status from the arithmetic checks + agreement with the next yearbook
    arith = v[v.check_name.isin(["gender_sum", "degree_sum", "cross_publication"])]
    st = arith.groupby(["source_file", "source_table"]).ok.agg(["mean", "count"]).reset_index()
    cp = v[v.check_name == "cross_publication"].groupby(["source_file", "source_table"]).ok.mean().rename("cross_ok")
    st = st.merge(cp.reset_index(), on=["source_file", "source_table"], how="left")
    # failed: arithmetic mostly wrong, or the national row disagrees with later yearbooks for most cells
    st["check_status"] = [
        "failed" if (m < 0.8 or (pd.notna(c) and c < 0.5)) else "passed" for m, c in zip(st["mean"], st["cross_ok"])
    ]
    st = st.rename(columns={"mean": "pass_rate", "count": "n_checks"})
    st.to_parquet(OUT / "table_status.parquet", index=False)
    rev = pd.DataFrame(revisions(k12, K12_KEY, "k12") + revisions(he, HE_KEY, "he"))
    yoy = yoy_jumps(k12, he, st)
    allv = pd.concat([v, rev, yoy], ignore_index=True)
    issues = allv[allv.severity != "info"].copy()
    issues = pd.concat([issues, allv[allv.check_name == "revision"]]).drop(columns=["ok"], errors="ignore")
    issues.to_parquet(OUT / "validation.parquet", index=False)
    summ = v.groupby(["check_name", "domain"]).ok.agg(["count", "mean"]).rename(columns={"mean": "pass_rate"})
    print(summ.to_string())
    print(f"tables failed: {(st.check_status == 'failed').sum()} / {len(st)} checked")
    print(f"yoy jumps flagged: {len(yoy)}; revisions: {len(rev)}")
    summ.reset_index().to_csv(OUT / "validation_summary.csv", index=False)


def yoy_jumps(k12: pd.DataFrame, he: pd.DataFrame, st: pd.DataFrame) -> pd.DataFrame:
    failed = set(map(tuple, st[st.check_status == "failed"][["source_file", "source_table"]].values))
    out = []
    for dom, df, dims in (("k12", k12, ["level", "programme"]), ("he", he, ["university_type", "degree_level"])):
        x = df[(df.gender == "total") & (df.metric.isin(["students", "teachers", "educational_staff", "academic_staff"]))]
        if dom == "k12":
            x = x[(x.branch == "all") & (x.sector == "all") & (x.area == "total")]
        else:
            x = x[(x.field_group == "all") & (x["rank"] == "all") & (x.area == "total")]
        x = x[[(a, b) not in failed for a, b in zip(x.source_file, x.source_table)]]
        x = x[x.yearbook_sh >= 1380]
        x = x.assign(same=(x.yearbook_sh == x.year_sh).astype(int)).sort_values("same", ascending=False)
        best = x.drop_duplicates(["year_sh", "province_code", "metric"] + dims)
        best = best.sort_values("year_sh")
        for key, g in best.groupby(["province_code", "metric"] + dims):
            g = g.sort_values("year_sh")
            prev = None
            for r in g.itertuples(index=False):
                if prev is not None and r.year_sh - prev.year_sh == 1 and prev.value > 0:
                    ch = r.value / prev.value - 1
                    if abs(ch) > 0.30:
                        out.append({"check_name": "yoy_jump", "severity": "warn", "domain": dom,
                                    "yearbook_sh": r.yearbook_sh, "year_sh": r.year_sh, "source_file": r.source_file,
                                    "source_table": r.source_table, "detail": f"{key} {ch:+.0%}",
                                    "expected": prev.value, "actual": r.value, "ok": False})
                prev = r
    return pd.DataFrame(out)
