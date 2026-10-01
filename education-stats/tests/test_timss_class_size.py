"""Structure check of exports/site/timss_class_size.json; skipped when the TIMSS microdata is absent."""

import json
import os
from pathlib import Path

import pytest

DATA = Path(os.environ.get("TIMSS_IRAN_DIR", "/Volumes/MigMig/Personal/Research/Iran Achievement Data/"))
OUT = Path(__file__).resolve().parents[1] / "exports" / "site" / "timss_class_size.json"

pytestmark = pytest.mark.skipif(not DATA.exists(), reason="TIMSS 2023 microdata not available")


def test_json_structure():
    j = json.loads(OUT.read_text())
    assert {"bands", "regression", "descriptives", "variables", "caveats"} <= set(j)
    assert len(j["bands"]) == 20  # 2 grades x 2 subjects x 5 bands
    for b in j["bands"]:
        assert b["band"] in {"<=20", "21-25", "26-30", "31-35", ">35"}
        assert b["mean"] is None or 200 < b["mean"] < 700
        assert b["se"] is None or 0 < b["se"] < 50
    assert len(j["regression"]) == 4
    for r in j["regression"]:
        assert r["n_controls"] <= r["n_unadjusted"] <= 7000
        assert r["se_unadjusted"] > 0 and r["se_with_controls"] > 0
        assert abs(r["per_5_students_unadjusted"]) < 30
