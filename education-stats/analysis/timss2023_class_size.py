#!/usr/bin/env python
"""TIMSS 2023 Iran: do students in larger classes score lower in maths and science?

    uv run --group analysis python analysis/timss2023_class_size.py

Microdata (NOT in the repo) is read from $TIMSS_IRAN_DIR, default
"/Volumes/MigMig/Personal/Research/Iran Achievement Data/". Writes analysis/figures/timss2023_*.png and
exports/site/timss_class_size.json. Association only; see analysis/README.md for caveats.

Method (TIMSS 2023 User Guide, IEA IDB Analyzer conventions):
* 5 plausible values (PV); estimate per PV, point = mean over PVs, variance = mean sampling variance +
  (1 + 1/5) * between-PV variance (Rubin).
* Sampling variance: jackknife repeated replication (JRR). For zone z, units with JKREP == 1 get weight x2,
  JKREP == 0 get weight x0, all other units unchanged; var = sum_z (theta_z - theta)^2. The Iran files carry
  JKZONE values up to 112 (not the 75 zones of older cycles), so ALL zones present in the data are used.
* Weight: the teacher-linked weight of the subject (MATWGT for maths, SCIWGT for science) taken from the
  student-teacher link file (AST/BST), as the User Guide prescribes for analyses with teacher-level variables.
* Class size = teacher-reported "number of students in the class": ATBG10A (G4, ATG file), BTBG10 (G8,
  BTM file for maths, BTS file for science). 999 = omitted -> missing.
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyreadr

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "analysis" / "figures"
OUT = ROOT / "exports" / "site" / "timss_class_size.json"
DATA = Path(os.environ.get("TIMSS_IRAN_DIR", "/Volumes/MigMig/Personal/Research/Iran Achievement Data/"))

BANDS = [("<=20", 0, 20), ("21-25", 21, 25), ("26-30", 26, 30), ("31-35", 31, 35), (">35", 36, 10**6)]
CFG = {
    "g4": dict(grade=4, p="a", home="ASBGHRL", teacher={"math": "atg", "science": "atg"}, cs="ATBG10A", sch="acg",
               loc="ACBG05B", eas="ACBGEAS", res={"math": "ACBGMRS", "science": "ACBGSRS"}, ses="ACDGSBC",
               pv={"math": "ASMMAT0", "science": "ASSSCI0"}),
    "g8": dict(grade=8, p="b", home="BSBGHER", teacher={"math": "btm", "science": "bts"}, cs="BTBG10", sch="bcg",
               loc="BCBG05B", eas="BCBGEAS", res={"math": "BCBGMRS", "science": "BCBGSRS"}, ses="BCDGSBC",
               pv={"math": "BSMMAT0", "science": "BSSSCI0"}),
}
LOC_LABEL = {1: "urban", 2: "suburban", 3: "medium city", 4: "small town/village", 5: "remote rural"}


def load(g: str, stem: str) -> pd.DataFrame:
    hits = glob.glob(str(DATA / f"timss2023_iran_{g}" / "R Data" / f"{stem}irnm8.rdata"))
    return list(pyreadr.read_r(hits[0]).values())[0]


def build(g: str, subj: str) -> pd.DataFrame:
    c = CFG[g]
    p = c["p"]
    link = load(g, p + "st")
    link = link[link["IDSUBJ"] == (1 if subj == "math" else 2) if g == "g8" else slice(None)]
    wcol = "MATWGT" if subj == "math" else "SCIWGT"
    link = link[["IDSCHOOL", "IDCLASS", "IDSTUD", "IDTEACH", "IDLINK", wcol, "JKZONE", "JKREP"]].rename(columns={wcol: "W"})
    t = load(g, c["teacher"][subj])[["IDTEACH", "IDLINK", c["cs"]]].rename(columns={c["cs"]: "CS"})
    st = load(g, p + "sg")[["IDSTUD", "ITSEX", c["home"]] + [f"{c['pv'][subj]}{i}" for i in range(1, 6)]]
    sc = load(g, c["sch"])[["IDSCHOOL", c["loc"], c["eas"], c["res"][subj], c["ses"]]]
    d = link.merge(t, on=["IDTEACH", "IDLINK"], how="left").merge(st, on="IDSTUD", how="left").merge(sc, on="IDSCHOOL", how="left")
    d = d.rename(columns={f"{c['pv'][subj]}{i}": f"PV{i}" for i in range(1, 6)})
    d["CS"] = d["CS"].where(d["CS"] < 900)
    d["HOME"] = d[c["home"]].where(d[c["home"]] < 900000)  # 999999 = omitted
    d["BOY"] = (d["ITSEX"] == 2).astype(float)
    d["LOC"] = d[c["loc"]].where(d[c["loc"]].isin([1, 2, 3, 4, 5]))  # 9 = omitted
    d["EAS"] = d[c["eas"]]
    d["RES"] = d[c["res"][subj]]
    d["SBC"] = d[c["ses"]].where(d[c["ses"]].isin([1, 2, 3]))
    return d


def jrr(fn, d: pd.DataFrame, w: np.ndarray):
    """fn(d, w, pv) -> vector. Returns (est, se) per element with Rubin + JRR."""
    zone = d["JKZONE"].to_numpy()
    rep = d["JKREP"].to_numpy()
    zones = np.unique(zone)
    ests, svars = [], []
    for k in range(1, 6):
        th = np.asarray(fn(d, w, f"PV{k}"), float)
        v = np.zeros_like(th)
        for z in zones:
            wz = w.copy()
            m = zone == z
            wz[m] = w[m] * np.where(rep[m] == 1, 2.0, 0.0)
            v += (np.asarray(fn(d, wz, f"PV{k}"), float) - th) ** 2
        ests.append(th)
        svars.append(v)
    ests = np.array(ests)
    est = ests.mean(0)
    var = np.mean(svars, 0) + (1 + 1 / 5) * ests.var(0, ddof=1)
    return est, np.sqrt(var)


def wmean(y, w):
    return np.array([np.sum(w * y) / np.sum(w)])


def design(d: pd.DataFrame, controls: bool) -> np.ndarray:
    x = [np.ones(len(d)), d["CS"].to_numpy() / 5.0]
    if controls:
        x += [d["HOME"].to_numpy(), d["BOY"].to_numpy(), d["EAS"].to_numpy(), d["RES"].to_numpy()]
        for k in (2, 3, 4, 5):
            x.append((d["LOC"] == k).astype(float).to_numpy())
        for k in (2, 3):
            x.append((d["SBC"] == k).astype(float).to_numpy())
    return np.column_stack(x)


def wls(d, w, pv, controls):
    X = design(d, controls)
    y = d[pv].to_numpy()
    sw = np.sqrt(w)
    b = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
    return b


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    res: dict = {"bands": [], "regression": [], "descriptives": []}
    for g, c in CFG.items():
        for subj in ("math", "science"):
            d0 = build(g, subj)
            d = d0.dropna(subset=["W", "CS", "PV1", "JKZONE"]).reset_index(drop=True)
            need = ["HOME", "BOY", "EAS", "RES", "LOC", "SBC"]
            dc = d.dropna(subset=need).reset_index(drop=True)
            w = d["W"].to_numpy()
            wc = dc["W"].to_numpy()
            n_tot = len(d0)
            print(f"{g} {subj}: link rows {n_tot}, with class size {len(d)}, complete controls {len(dc)}; "
                  f"classes {d['IDCLASS'].nunique()} / {dc['IDCLASS'].nunique()}; zones {d['JKZONE'].nunique()}")
            wm = np.sum(w * d["CS"]) / np.sum(w)
            res["descriptives"].append(dict(grade=c["grade"], subject=subj, n_students_linked=int(n_tot),
                n_students_with_class_size=int(len(d)), n_students_complete_controls=int(len(dc)),
                n_classes=int(d["IDCLASS"].nunique()), n_schools=int(d["IDSCHOOL"].nunique()),
                class_size_weighted_mean=round(float(wm), 2), class_size_min=float(d["CS"].min()),
                class_size_max=float(d["CS"].max()), jackknife_zones=int(d["JKZONE"].nunique())))
            for lab, lo, hi in BANDS:
                m = ((d["CS"] >= lo) & (d["CS"] <= hi)).to_numpy()
                sub = d[m].reset_index(drop=True)
                if len(sub) < 30:
                    res["bands"].append(dict(grade=c["grade"], subject=subj, band=lab, n=int(m.sum()), mean=None, se=None))
                    continue
                # share of students in the band: keep the full sample so the JRR sees all zones
                est, se = jrr(lambda dd, ww, pv, m=m: wmean(dd[pv].to_numpy()[m], ww[m]), d, w)
                share, shse = jrr(lambda dd, ww, pv, m=m: np.array([np.sum(ww[m]) / np.sum(ww)]), d, w)
                res["bands"].append(dict(grade=c["grade"], subject=subj, band=lab, n=int(m.sum()),
                    n_classes=int(sub["IDCLASS"].nunique()), mean=round(float(est[0]), 1), se=round(float(se[0]), 1),
                    share_of_students=round(float(share[0]), 3),
                    share_urban_or_suburban=round(float(np.average((sub["LOC"] <= 2)[sub["LOC"].notna()], weights=sub["W"][sub["LOC"].notna()])), 2),
                    mean_home_resources=round(float(np.average(sub["HOME"].dropna(), weights=sub["W"][sub["HOME"].notna()])), 2)))
            r = {}
            for name, dd, ww, ctrl in (("unadjusted_full_sample", d, w, False),
                                      ("unadjusted_controls_sample", dc, wc, False),
                                      ("with_controls", dc, wc, True)):
                est, se = jrr(lambda a, b, pv, ctrl=ctrl: wls(a, b, pv, ctrl), dd, ww)
                r[name] = (float(est[1]), float(se[1]))
            b0, b1 = r["unadjusted_controls_sample"][0], r["with_controls"][0]
            res["regression"].append(dict(grade=c["grade"], subject=subj,
                n_unadjusted=int(len(d)), n_controls=int(len(dc)),
                per_5_students_unadjusted=round(r["unadjusted_full_sample"][0], 2), se_unadjusted=round(r["unadjusted_full_sample"][1], 2),
                per_5_students_unadjusted_controls_sample=round(b0, 2), se_unadjusted_controls_sample=round(r["unadjusted_controls_sample"][1], 2),
                per_5_students_with_controls=round(b1, 2), se_with_controls=round(r["with_controls"][1], 2),
                change_with_controls=round(b1 - b0, 2)))
            print("  ", res["regression"][-1])
    res["variables"] = {
        "class_size": {"grade4": "ATBG10A (teacher questionnaire, ATG; 'number of students in the class', 999 = omitted)",
                       "grade8": "BTBG10 (BTM file for maths, BTS file for science)"},
        "achievement": "plausible values ASMMAT01-05 / ASSSCI01-05 (G4), BSMMAT01-05 / BSSSCI01-05 (G8)",
        "weight": "MATWGT (maths) / SCIWGT (science) from the student-teacher link files AST/BST",
        "jackknife": "JKZONE, JKREP (all zones present in the Iran files; up to 112)",
        "controls": {"home_resources": "ASBGHRL (G4 Home Resources for Learning) / BSBGHER (G8 Home Educational Resources), scale score",
                     "gender": "ITSEX", "location": "ACBG05B / BCBG05B (immediate area of school: 1 urban ... 5 remote rural), dummies",
                     "school_emphasis_on_academic_success": "ACBGEAS / BCBGEAS (principal scale)",
                     "resource_shortage": "ACBGMRS|ACBGSRS / BCBGMRS|BCBGSRS (instruction affected by resource shortage, scale)",
                     "school_ses_composition": "ACDGSBC / BCDGSBC (more affluent / neither / more disadvantaged; dummies)"},
        "students_per_teacher": "not derivable: the Iran school and teacher files carry no school enrolment or teacher count",
    }
    res["caveats"] = [
        "Association, not effect: larger classes are mostly in urban and richer schools and Iranian students are not randomly assigned to class sizes.",
        "Class size is teacher-reported (one number per teacher), not measured; some teachers report 999 (omitted) and are dropped.",
        "About 224 schools / classes per grade: the effective sample is the number of classes, not the number of students; standard errors use the jackknife on 112 zones.",
        "TIMSS 2023 is nationally representative of Iran, not of provinces; no province identifier exists in the microdata.",
        "Controls can absorb part of the real effect (home resources, school SES partly result from where large classes are).",
        "Bands are a coarse rendering of a continuous variable; the regression is linear in class size.",
    ]
    res["source"] = "TIMSS 2023 International Database, Iran (IEA), public-use files; analysis by analysis/timss2023_class_size.py"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print("wrote", OUT)
    figures(res)


def figures(res: dict) -> None:
    plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False, "font.size": 9, "axes.grid": True, "grid.alpha": 0.25})
    lab = [b[0] for b in BANDS]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=False)
    for ax, grade in zip(axes, (4, 8)):
        for subj, col in (("math", "#1f5fa8"), ("science", "#d1691f")):
            rows = {b["band"]: b for b in res["bands"] if b["grade"] == grade and b["subject"] == subj}
            xs = [i for i, bl in enumerate(lab) if rows.get(bl, {}).get("mean") is not None]
            ax.errorbar([x + (0.08 if subj == "science" else -0.08) for x in xs], [rows[lab[i]]["mean"] for i in xs],
                        yerr=[1.96 * rows[lab[i]]["se"] for i in xs], marker="o", capsize=3, color=col, label=subj)
        ax.set_xticks(range(len(lab)), lab)
        ax.set_title(f"Grade {grade}")
        ax.set_xlabel("students in class (teacher-reported)")
        ax.set_ylabel("mean TIMSS 2023 score (95% CI)")
        ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "timss2023_class_size_bands.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 3.6))
    for i, r in enumerate(res["regression"]):
        for j, (k, sek, col, nm) in enumerate((("per_5_students_unadjusted_controls_sample", "se_unadjusted_controls_sample", "#888", "no controls"),
                                              ("per_5_students_with_controls", "se_with_controls", "#1f5fa8", "with controls"))):
            ax.errorbar(i + (j - 0.5) * 0.25, r[k], yerr=1.96 * r[sek], marker="o", capsize=3, color=col, label=nm if i == 0 else None)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(range(len(res["regression"])), [f"G{r['grade']} {r['subject']}" for r in res["regression"]])
    ax.set_ylabel("score points per +5 students (95% CI)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "timss2023_class_size_coefficients.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
