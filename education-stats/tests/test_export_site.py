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
    assert {"provinces", "k12", "he", "provenance", "meta"} <= set(out)
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
