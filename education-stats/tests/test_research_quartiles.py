"""Self-check of scripts/research_quartiles.py on a tiny fixture (no network)."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "research_quartiles.py"


def test_selftest(tmp_path):
    spec = importlib.util.spec_from_file_location("research_quartiles", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.selftest(tmp_path)
