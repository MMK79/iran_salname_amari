"""Structure and consistency checks for scripts/export_site.py (needs data/out/edu.duckdb)."""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "out" / "edu.duckdb"
sys.path.insert(0, str(ROOT / "scripts"))

pytestmark = pytest.mark.skipif(not DB.exists(), reason="data/out/edu.duckdb not built")


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    import export_site

    d = tmp_path_factory.mktemp("site")
    export_site.export(DB, d)
    return {p.stem: json.loads(p.read_text()) for p in d.glob("*.json")} | {"_dir": d}


def walk(o, path=()):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, (*path, k))
    else:
        yield path, o


def test_files_and_size(out):
    assert {"provinces", "k12", "he", "outcomes", "relations", "provenance", "meta"} <= set(out)
    total = sum(p.stat().st_size for p in out["_dir"].glob("*.json"))
    assert total < 5_000_000
    assert (out["_dir"] / "provinces.json").stat().st_size < 400_000


def test_provinces(out):
    ps = out["provinces"]["provinces"]
    assert len(ps) == 31 and len({p["code"] for p in ps}) == 31
    assert out["provinces"]["viewBox"] == [0, 0, 1000, 860]
    for p in ps:
        assert p["name_en"] and p["name_fa"]
        assert p["path"].startswith("M") and p["path"].endswith("Z")
        nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", p["path"])]
        assert all(-1 <= v <= 1001 for v in nums)
        assert p["path"].count("M") >= p["n_polygons"] >= 1
        lx, ly = p["label"]
        assert 0 <= lx <= 1000 and 0 <= ly <= 860
    assert next(p for p in ps if p["code"] == "MZN")["n_polygons"] == 2
    assert out["provinces"]["historic_units"][0]["code"] == "KHO"


def test_k12_structure_and_ratio(out):
    k = out["k12"]
    assert {"primary", "lower_secondary", "upper_secondary", "all_levels"} <= set(k["levels"])
    yrs = [y["year_sh"] for y in k["years"]]
    assert min(yrs) <= 1380 and max(yrs) == 1402
    n_ratio = 0
    for y, d in k["data"].items():
        for p, levels in d.items():
            for lv, gs in levels.items():
                assert set(gs) <= {"total", "male", "female"}
                for g, rec in gs.items():
                    if g != "total":
                        assert set(rec) == {"students"}  # no teachers/ratio by gender: not published
                t = gs.get("total", {})
                s, tc, r = t.get("students"), t.get("teachers"), t.get("students_per_teacher")
                if r is not None:
                    n_ratio += 1
                    assert s and tc and abs(r - s / tc) <= 0.005 + 1e-9
                else:
                    assert not (s and tc), (y, p, lv)  # ratio must exist when both exist
    assert n_ratio > 2000
    # province-level year: 31 provinces + IRN
    assert len(k["data"]["1402"]) == 32
    assert k["data"]["1402"]["IRN"]["primary"]["total"]["students_per_teacher"] == pytest.approx(
        33.66, abs=0.01
    )


def test_k12_flags(out):
    by = {y["year_sh"]: y for y in out["k12"]["years"]}
    assert "teacher_proxy_educational_staff" in by[1390]["flags"]
    assert "teacher_proxy_educational_staff" not in by[1395]["flags"]
    assert "khorasan_undivided" in by[1382]["flags"] and "khorasan_undivided" not in by[1383]["flags"]
    assert "alborz_in_tehran" in by[1385]["flags"] and "alborz_in_tehran" not in by[1392]["flags"]
    assert all("school_reform_1391_93" in by[y]["flags"] for y in (1391, 1392, 1393))
    assert "school_reform_1391_93" not in by[1390]["flags"]
    assert "KHO" in out["k12"]["data"]["1382"] and "KHO" not in out["k12"]["data"]["1383"]


def test_no_zero_values_in_k12_and_provinces(out):
    for _, v in walk(out["k12"]["data"]):
        assert v != 0
    for path, v in walk(out["he"]["data"]):
        if v == 0:  # only printed zeros of national university-type x degree cells
            assert path[1] == "IRN" and path[2] not in ("all_reported", "azad", "excl_azad")


def test_he_ratio_and_quarantine(out):
    he = out["he"]
    for d in he["data"].values():
        for types in d.values():
            for degs in (types or {}).values():
                for dl, gs in degs.items():
                    for g, rec in gs.items():
                        r = rec.get("students_per_staff")
                        if r is not None:
                            assert g == "total" and dl == "all"
                            assert abs(r - rec["students"] / rec["academic_staff"]) <= 0.005 + 1e-9
    by = {y["year_sh"]: y for y in he["years"]}
    for y in (1399, 1400, 1402):
        assert "province_tables_quarantined" in by[y]["flags"]
        assert by[y]["quarantined_province_fields"]
    # 1399: all provinces explicit null, national still present
    d99 = he["data"]["1399"]
    assert d99["IRN"] and sum(1 for p, v in d99.items() if p != "IRN" and v is None) == 31
    # 1402: students exist, academic staff missing -> no staff, no ratio, no zero
    for _p, types in he["data"]["1402"].items():
        for degs in (types or {}).values():
            assert "academic_staff" not in degs.get("all", {}).get("total", {})
            assert "students_per_staff" not in degs.get("all", {}).get("total", {})
    # ratio exists in a healthy year
    assert he["data"]["1395"]["THR"]["all_reported"]["all"]["total"]["students_per_staff"] > 10
    assert "azad" in he["university_types"] and "payame_noor" in he["university_types"]


def test_provenance_and_meta(out):
    pv = out["provenance"]["datasets"]
    assert pv["k12"]["1398"] and pv["he"]["1395"]
    assert all(" :: " in s for v in pv["k12"].values() for s in v)
    # every exported year has provenance
    for y in out["k12"]["data"]:
        assert y in pv["k12"]
    m = out["meta"]
    assert m["generated_at"].endswith("Z")
    assert m["k12"]["year_range"][1] == 1402
    assert set(m["flag_definitions"]) >= {f for y in out["k12"]["years"] for f in y["flags"]}
    assert set(m["flag_definitions"]) >= {f for y in out["he"]["years"] for f in y["flags"]}
    assert m["gender_coverage"]["k12"]["primary"]["male"]["years_with_province_split"]


# ------------------------------------------------------------------ outcomes / relations
def test_outcomes_structure_and_bounds(out):
    oc = out["outcomes"]
    assert oc["levels_pass_rate"] == ["primary", "lower_secondary"]
    n_pub = 0
    for y, d in oc["data"].items():
        for p, rec in d.items():
            for lv, gs in rec.get("pass_rate", {}).items():
                assert lv in ("primary", "lower_secondary")
                for g, v in gs.items():
                    assert g in ("total", "male", "female")
                    if v.get("pass_rate") is not None:
                        n_pub += 1
                        assert 0 <= v["pass_rate"] <= 1, (y, p, lv, g, v)
                        assert v["passed"] <= v["students"]
                        assert abs(v["pass_rate"] - v["passed"] / v["students"]) <= 5e-5 + 1e-9
                        assert v["status"] == "ok"
                    else:
                        assert v["status"] in ("implausible_rate", "year_unreliable")
            for v in rec.get("class_size", {}).values():
                if v.get("students_per_class") is not None:
                    assert 5 <= v["students_per_class"] <= 60
            for v in rec.get("completion_proxy", {}).values():
                if v.get("completion_proxy") is not None:
                    assert 0.1 <= v["completion_proxy"] <= 0.5
            for v in rec.get("he_graduation_ratio", {}).values():
                if v.get("graduation_ratio") is not None:
                    assert 0.05 <= v["graduation_ratio"] <= 0.6
    assert n_pub > 1500
    # the PDF-1399 table is the 1398 table: 1398 province rows exist and sum to the national value
    d98 = oc["data"]["1398"]
    for lv in ("primary", "lower_secondary"):
        tot = d98["IRN"]["pass_rate"][lv]["total"]["passed"]
        assert sum(v["pass_rate"][lv]["total"]["passed"] for p, v in d98.items() if p != "IRN") == tot
    # known-bad province tables are withheld, not published
    assert all(
        v.get("pass_rate") is None
        for p, rec in oc["data"]["1386"].items()
        if p != "IRN"
        for v in rec["pass_rate"]["primary"].values()
    )
    by = {y["year_sh"]: y for y in oc["years"]}
    assert "pass_rate_provinces_withheld" in by[1386]["flags"] and "pandemic_1399" in by[1399]["flags"]
    assert "school_reform_1391_93" in by[1392]["flags"]
    assert set(out["meta"]["flag_definitions"]) >= {f for y in oc["years"] for f in y["flags"]}


def test_relations_only_for_years_with_25_provinces(out):
    rel = out["relations"]
    oc = out["outcomes"]["data"]
    assert rel["min_provinces_per_year"] == 25
    n_rows = 0
    for pair, levels in rel["cross_province_by_year"].items():
        for lv, rows in levels.items():
            assert rows, (pair, lv)
            for r in rows:
                n_rows += 1
                assert r["n"] >= 25
                assert -1 <= r["pearson"] <= 1 and -1 <= r["spearman"] <= 1
                assert str(r["year_sh"]) in oc
                # n cannot exceed the published pass rates of that year x level
                pub = sum(
                    1
                    for p, rec in oc[str(r["year_sh"])].items()
                    if p != "IRN" and rec.get("pass_rate", {}).get(lv, {}).get("total", {}).get("pass_rate") is not None
                )
                assert r["n"] <= pub
    assert n_rows > 50
    # years with the withheld province tables or no province split have no correlation
    for lv, rows in rel["cross_province_by_year"]["students_per_teacher_vs_pass_rate"].items():
        years = {r["year_sh"] for r in rows}
        assert not years & {1386, 1387, 1388, 1400, 1402}, lv


def test_fixed_effects_structure(out):
    res = out["relations"]["within_province_fixed_effects"]["results"]["students_per_teacher_vs_pass_rate"]
    for lv in ("primary", "lower_secondary"):
        for e in res[lv].values():
            assert e["n"] > 100 and e["n_provinces"] >= 25 and e["se_cluster"] > 0
            assert e["years"][0] <= e["years"][1]
        assert res[lv]["from_1394"]["years"][0] >= 1394
        yrs = res[lv]["excl_reform_1391_93"]
        assert yrs["n"] < res[lv]["all_valid_years"]["n"]


def test_fixed_effects_match_statsmodels():
    smf = pytest.importorskip("statsmodels.formula.api")
    import duckdb
    import export_site

    con = duckdb.connect(str(DB), read_only=True)
    df = con.execute(
        """select t.year_sh, t.province_code, t.students_per_teacher, p.pass_rate
           from v_k12_students_per_teacher t join v_k12_pass_rate p on p.year_sh=t.year_sh
             and p.province_code=t.province_code and p.level=t.level and p.gender='total'
           where t.level='primary' and t.province_code <> 'IRN'"""
    ).df()
    con.close()
    d = df.dropna()
    ours = export_site._cluster_fe(d, "students_per_teacher", "pass_rate")
    import pandas as pd

    d = d[d.groupby("province_code").year_sh.transform("count") >= 2]
    m = smf.ols("pass_rate ~ students_per_teacher + C(province_code) + C(year_sh)", d).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d.province_code)[0]}
    )
    assert ours["coef"] == pytest.approx(m.params["students_per_teacher"], abs=1e-6)
    assert ours["se_cluster"] == pytest.approx(m.bse["students_per_teacher"], abs=1e-6)


# ------------------------------------------------------------------ cohort survival (drop-out proxy)
def test_cohort_survival_published_values_are_plausible_and_consistent(out):
    oc = out["outcomes"]["data"]
    n_pub = 0
    for y, d in oc.items():
        for p, rec in d.items():
            for g, v in rec.get("cohort_survival", {}).items():
                assert g in ("total", "male", "female")
                if v.get("cohort_survival") is None:
                    assert v["status"] in ("reform_window", "boundary_change", "implausible_rate", "year_unreliable")
                    continue
                n_pub += 1
                assert v["status"] == "ok"
                assert 0.5 <= v["cohort_survival"] <= 1.05, (y, p, g, v)
                assert v["survival_year_sh"] == int(y) + 3
                assert abs(v["cohort_survival"] - v["upper_students"] / v["lower_students"]) <= 5e-5 + 1e-9
    assert n_pub > 500
    # reform windows (t = 1388-1393) are withheld everywhere, provinces and national
    for y in range(1388, 1394):
        for p, rec in oc[str(y)].items():
            assert all(v.get("cohort_survival") is None and v["status"] == "reform_window"
                       for v in rec.get("cohort_survival", {}).values()), (y, p)
    # 1387 province rows are misaligned in the source: provinces withheld, national row kept
    assert all(
        rec["cohort_survival"]["total"].get("cohort_survival") is None
        for p, rec in oc["1387"].items()
        if p != "IRN" and "cohort_survival" in rec
    )
    assert oc["1387"]["IRN"]["cohort_survival"]["total"].get("cohort_survival") is not None
    # province data from t = 1394: 31 provinces; national 1394 close to the arithmetic of the printed students
    prov_1394 = [p for p, r in oc["1394"].items() if p != "IRN" and r["cohort_survival"]["total"].get("cohort_survival") is not None]
    assert len(prov_1394) == 31
    by = {y["year_sh"]: y for y in out["outcomes"]["years"]}
    assert "cohort_survival_reform_window" in by[1391]["flags"] and "cohort_survival_provinces_withheld" in by[1387]["flags"]
    assert set(out["meta"]["flag_definitions"]) >= {f for y in out["outcomes"]["years"] for f in y["flags"]}


def test_cohort_survival_national_equals_stock_ratio():
    """The national row is the arithmetic ratio of two printed stocks, three years apart."""
    import duckdb

    con = duckdb.connect(str(DB), read_only=True)
    lo, up, sv = con.execute(
        """select s.lower_students, s.upper_students, s.cohort_survival from v_k12_cohort_survival s
           where s.province_code='IRN' and s.gender='total' and s.year_sh=1396"""
    ).fetchone()
    lo_ref = con.execute(
        "select value from v_k12_best where province_code='IRN' and gender='total' and metric='students' "
        "and programme='regular' and level='lower_secondary' and year_sh=1396"
    ).fetchone()[0]
    up_ref = con.execute(
        "select value from v_k12_best where province_code='IRN' and gender='total' and metric='students' "
        "and programme='regular' and level='upper_secondary' and year_sh=1399"
    ).fetchone()[0]
    con.close()
    assert (lo, up) == (lo_ref, up_ref) and sv == pytest.approx(up_ref / lo_ref)


def test_cohort_survival_relations(out):
    rel = out["relations"]
    cross = rel["cohort_survival_cross_province_by_year"]
    assert set(cross) == {"lower_secondary_at_t", "upper_secondary_at_t_plus_3"}
    for rows in cross.values():
        assert {r["year_sh"] for r in rows} == set(range(1394, 1400))  # only publishable years, never reform/1387
        for r in rows:
            assert r["n"] >= 25 and -1 <= r["pearson"] <= 1 and -1 <= r["spearman"] <= 1
    res = rel["cohort_survival_within_province_fixed_effects"]["results"]
    for x in cross:
        e = res[x]["all_valid_years"]
        assert e["n"] > 150 and e["n_provinces"] >= 30 and e["se_cluster"] > 0 and e["years"] == [1394, 1399]
        assert res[x]["excl_cohort_1399"]["years"] == [1394, 1398] and res[x]["excl_cohort_1399"]["n"] < e["n"]


def test_no_direct_dropout_table_in_the_database():
    """Documented negative result (docs/findings.md section 6): no drop-out / out-of-school / coverage table."""
    import duckdb

    from etl.normalize import norm

    con = duckdb.connect(str(DB), read_only=True)
    titles = [norm(t or "").replace(" ", "") for (t,) in con.execute(
        "select title from source_tables where yearbook_sh >= 1370").fetchall()]
    con.close()
    for kw in ("ترک تحصیل", "بازمانده", "نرخ پوشش", "پوشش تحصیلی", "مردود", "تکرار پایه"):
        k = norm(kw).replace(" ", "")
        assert not [t for t in titles if k in t], kw
