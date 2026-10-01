#!/usr/bin/env python
"""Do resource ratios (students per teacher, students per class) go together with pass rates?

    uv run python analysis/ratio_vs_outcomes.py [--db data/out/edu.duckdb]

Reads the SQL views (v_k12_students_per_teacher, v_k12_class_size, v_k12_pass_rate) and the
relations computed by scripts/export_site.py. Writes analysis/figures/*.png and prints the numbers quoted
in analysis/README.md. Descriptive association only; see the README for the caveats.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import export_site  # noqa: E402

FIG = ROOT / "analysis" / "figures"
LEVELS = {"primary": "Primary", "lower_secondary": "Lower secondary"}
COL = {"primary": "#1f5fa8", "lower_secondary": "#d1691f"}
plt.rcParams.update(
    {"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False, "font.size": 9, "axes.grid": True,
     "grid.alpha": 0.25}
)


def panel(con) -> pd.DataFrame:
    return con.execute(
        """select t.year_sh, t.province_code, t.level, t.students_per_teacher, t.students_per_class,
                  p.pass_rate, p.status
           from v_k12_students_per_teacher t
           left join v_k12_pass_rate p on p.year_sh=t.year_sh and p.province_code=t.province_code
                and p.level=t.level and p.gender='total'
           where t.level in ('primary','lower_secondary')"""
    ).df()


def shade(ax):
    ax.axvspan(1390.5, 1393.5, color="#999", alpha=0.15, lw=0)  # school reform 1391-93
    ax.axvline(1393.5, color="#555", ls=":", lw=1)  # teacher definition: staff -> teachers from 1394
    ax.axvline(1399, color="#a33", ls=":", lw=1)  # COVID


def fig_trends(df: pd.DataFrame):
    nat = df[df.province_code == "IRN"]
    fig, axs = plt.subplots(3, 1, figsize=(7.5, 8), sharex=True)
    for ax, col, title, ylab in [
        (axs[0], "students_per_teacher", "Students per teacher (before 1394: educational staff)", "students / teacher"),
        (axs[1], "students_per_class", "Students per class", "students / class"),
        (axs[2], "pass_rate", "Pass rate (passed / students, regular programme)", "share promoted"),
    ]:
        for lv, lab in LEVELS.items():
            d = nat[nat.level == lv].sort_values("year_sh")
            ax.plot(d.year_sh, d[col], marker="o", ms=3, color=COL[lv], label=lab)
        shade(ax)
        ax.set_title(title, loc="left", fontsize=9)
        ax.set_ylabel(ylab)
    axs[0].legend(frameon=False, ncol=2)
    axs[2].set_xlabel("academic year start (SH)   |   grey band: 1391-93 school reform; dotted: 1394 teacher definition, 1399 COVID")
    fig.suptitle("Iran, national: resource ratios and pass rate on one time axis", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(FIG / "a_national_trends.png")
    plt.close(fig)


def latest_good_year(df: pd.DataFrame, level: str, n_min: int = 25) -> int:
    d = df[(df.level == level) & (df.province_code != "IRN")].dropna(subset=["students_per_teacher", "pass_rate"])
    n = d.groupby("year_sh").size()
    return int(n[n >= n_min].index.max())


def fig_scatter(df: pd.DataFrame, con) -> dict:
    names = dict(con.execute("select code, name_en from provinces").fetchall())
    out = {}
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 4.4))
    for ax, (lv, lab) in zip(axs, LEVELS.items(), strict=True):
        y = latest_good_year(df, lv)
        d = df[(df.level == lv) & (df.year_sh == y) & (df.province_code != "IRN")].dropna(
            subset=["students_per_teacher", "pass_rate"]
        )
        x, z = d.students_per_teacher.to_numpy(), d.pass_rate.to_numpy()
        b, a = np.polyfit(x, z, 1)
        r = float(np.corrcoef(x, z)[0, 1])
        ax.scatter(x, z, color=COL[lv], s=22, alpha=0.85)
        xs = np.linspace(x.min(), x.max(), 20)
        ax.plot(xs, a + b * xs, color="#222", lw=1.2)
        for _, row in d.iterrows():
            if abs(row.pass_rate - (a + b * row.students_per_teacher)) > 1.6 * np.std(z - (a + b * x)):
                ax.annotate(names.get(row.province_code, row.province_code), (row.students_per_teacher, row.pass_rate),
                            fontsize=7, xytext=(3, 3), textcoords="offset points")
        ax.set_title(f"{lab}, {y} (n = {len(d)})\nr = {r:.2f}; slope = {b * 100:.2f} pp per +1 student/teacher",
                     loc="left", fontsize=8)
        ax.set_xlabel("students per teacher")
        ax.set_ylabel("pass rate")
        out[lv] = {"year": y, "n": len(d), "r": r, "slope_pp": b * 100}
    fig.suptitle("Province cross-section, latest year with >= 25 provinces (association only)", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(FIG / "b_scatter_latest_year.png")
    plt.close(fig)
    return out


def fig_corr(rel: dict):
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.8), sharey=True)
    for ax, key, title in [
        (axs[0], "students_per_teacher_vs_pass_rate", "students per teacher vs pass rate"),
        (axs[1], "class_size_vs_pass_rate", "students per class vs pass rate"),
    ]:
        for lv, lab in LEVELS.items():
            by = {r["year_sh"]: r for r in rel["cross_province_by_year"][key][lv]}
            yrs = list(range(min(by), max(by) + 1))  # NaN for missing years: no line across gaps
            ax.plot(yrs, [by[y]["pearson"] if y in by else np.nan for y in yrs], marker="o", ms=3, color=COL[lv],
                    label=f"{lab} Pearson")
            ax.plot(yrs, [by[y]["spearman"] if y in by else np.nan for y in yrs], marker="x", ms=3, ls="--",
                    color=COL[lv], alpha=0.7, label=f"{lab} Spearman")
        ax.axhline(0, color="#444", lw=0.8)
        ax.axvspan(1390.5, 1393.5, color="#999", alpha=0.15, lw=0)
        ax.set_title(title, loc="left", fontsize=9)
        ax.set_xlabel("year (SH); only years with >= 25 provinces and published pass rates")
    axs[0].set_ylabel("cross-province correlation")
    axs[0].legend(frameon=False, fontsize=7, ncol=1)
    fig.tight_layout()
    fig.savefig(FIG / "c_correlation_by_year.png")
    plt.close(fig)


def crosscheck_fe(df: pd.DataFrame, rel: dict):
    """Our hand-rolled clustered FE must equal statsmodels (same CR1 small-sample correction)."""
    import statsmodels.formula.api as smf

    print("\ncluster-FE cross-check vs statsmodels (students_per_teacher -> pass_rate, all_valid_years):")
    for lv in LEVELS:
        d = df[(df.level == lv) & (df.province_code != "IRN")].dropna(subset=["students_per_teacher", "pass_rate"]).copy()
        d = d[d.groupby("province_code").year_sh.transform("count") >= 2]
        m = smf.ols("pass_rate ~ students_per_teacher + C(province_code) + C(year_sh)", d).fit(
            cov_type="cluster", cov_kwds={"groups": pd.factorize(d.province_code)[0]}
        )
        ours = rel["within_province_fixed_effects"]["results"]["students_per_teacher_vs_pass_rate"][lv]["all_valid_years"]
        print(f"  {lv:16s} ours coef {ours['coef']:+.6f} se {ours['se_cluster']:.6f} | statsmodels coef "
              f"{m.params['students_per_teacher']:+.6f} se {m.bse['students_per_teacher']:.6f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "out" / "edu.duckdb")
    a = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(a.db), read_only=True)
    df = panel(con)
    rel = export_site.relations_json(con)

    nat = df[df.province_code == "IRN"].set_index(["level", "year_sh"])
    print("National (primary): students/teacher, students/class, pass rate")
    for lv in LEVELS:
        print(" ", lv)
        for y in (1380, 1385, 1390, 1394, 1398, 1399, 1401):
            if (lv, y) in nat.index:
                r = nat.loc[(lv, y)]
                print(f"    {y}: spt {r.students_per_teacher:.1f}  class {r.students_per_class:.1f}  pass {r.pass_rate:.3f}")
    fig_trends(df)
    sc = fig_scatter(df, con)
    print("\nScatter latest good year:", sc)
    fig_corr(rel)
    crosscheck_fe(df, rel)

    print("\nCross-province Pearson: mean over years by level (spt vs pass rate)")
    for lv in LEVELS:
        rows = rel["cross_province_by_year"]["students_per_teacher_vs_pass_rate"][lv]
        print(f"  {lv}: n_years={len(rows)}, mean r={np.mean([r['pearson'] for r in rows]):+.2f}, "
              f"1380-85 mean {np.mean([r['pearson'] for r in rows if r['year_sh'] <= 1385]):+.2f}, "
              f"1392+ mean {np.mean([r['pearson'] for r in rows if r['year_sh'] >= 1392]):+.2f}")
    print("\nWithin-province FE (pass rate on students per teacher; coef in percentage points per +1 student/teacher)")
    for lv in LEVELS:
        for spec, e in rel["within_province_fixed_effects"]["results"]["students_per_teacher_vs_pass_rate"][lv].items():
            if e:
                print(f"  {lv:16s} {spec:20s} {e['coef'] * 100:+.3f} pp (se {e['se_cluster'] * 100:.3f}, p={e['p_value']}), "
                      f"n={e['n']}, provinces={e['n_provinces']}, years {e['years']}")


if __name__ == "__main__":
    main()
