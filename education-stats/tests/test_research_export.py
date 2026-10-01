"""Structure check of exports/site/he_research.json (built by scripts/research_openalex.py from the cached OpenAlex responses)."""

import json
from pathlib import Path

import pytest

OUT = Path(__file__).resolve().parents[1] / "exports" / "site" / "he_research.json"

pytestmark = pytest.mark.skipif(not OUT.exists(), reason="he_research.json not built")

YEARS = list(range(2000, 2026))
KEYS = ("works", "citations", "intl_works", "ai_works", "edu_works")


def load():
    return json.loads(OUT.read_text())


def test_top_level():
    j = load()
    assert {"meta", "national", "groups", "top_universities", "provinces", "rankings", "caveats"} <= set(j)
    assert j["meta"]["years"] == [2000, 2025] and j["caveats"]


def test_national_series():
    n = load()["national"]
    assert n["years"] == YEARS
    for k in KEYS:
        assert len(n[k]) == len(YEARS)
    # growth: far more output in 2024 than in 2000
    assert n["works"][24] > 10 * n["works"][0] > 0
    # international and topical slices never exceed all works
    assert all(i <= w for i, w in zip(n["intl_works"], n["works"]))
    assert all(a <= w and e <= w for a, e, w in zip(n["ai_works"], n["edu_works"], n["works"]))


def test_top_universities():
    t = load()["top_universities"]
    assert len(t) == 40
    assert [u["total_works"] for u in t] == sorted((u["total_works"] for u in t), reverse=True)
    for u in t:
        assert u["openalex_id"].startswith("I") and len(u["works"]) == len(YEARS)
        assert sum(u["works"]) == u["total_works"]
        assert 0 <= u["intl_share"] <= 1
    names = " ".join(u["name"] for u in t)
    assert "University of Tehran" in names and "Sharif" in names


def test_province_series():
    j = load()
    p = j["provinces"]
    assert "THR" in p and "ISF" in p and len(p) >= 30
    for code, d in p.items():
        n = len(d["years"])
        assert n and all(len(d[k]) == n for k in KEYS + ("academic_staff", "works_per_staff"))
    thr = p["THR"]
    # province totals are a union: never above the national union; Tehran dominates
    nat = dict(zip(j["national"]["years"], j["national"]["works"]))
    for y, w in zip(thr["years"], thr["works"]):
        assert w <= nat[y]
    assert sum(thr["works"]) > 0.25 * sum(j["national"]["works"])
    # works per staff only where staff is known and positive
    for d in p.values():
        for s, r in zip(d["academic_staff"], d["works_per_staff"]):
            assert r is None or (s and r >= 0)
