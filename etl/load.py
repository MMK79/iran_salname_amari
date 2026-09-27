"""Load the parquet outputs into PostgreSQL (default) or DuckDB (fallback, no server needed).

    uv run python -m etl.run load --pg postgresql://edu:edu@localhost:5432/edu
    uv run python -m etl.run load --duckdb data/out/edu.duckdb
If neither is given, $DATABASE_URL is used, else DuckDB.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd

from etl.metrics import METRICS
from etl.provinces import ALIASES, ALL
from etl.terms import RULES

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "out"
SQL = ROOT / "sql"

COLS = {
    "k12_stats": ["year_sh", "year_gregorian", "yearbook_sh", "province_code", "province_label", "level",
                  "level_source", "school_system", "programme", "branch", "sector", "area", "gender", "metric",
                  "value", "source_file", "source_format", "source_table", "table_title", "row_label",
                  "col_header", "row_category", "col_category", "header_source", "domain"],
    "higher_ed_stats": ["year_sh", "year_gregorian", "yearbook_sh", "province_code", "province_label",
                        "university_type", "university_type_source", "degree_level", "degree_level_source",
                        "field_group", "rank", "employment", "coverage", "area", "gender", "metric", "value", "source_file",
                        "source_format", "source_table", "table_title", "row_label", "col_header", "row_category",
                        "col_category", "header_source", "domain"],
    "raw_cells": ["yearbook_sh", "source_file", "source_table", "row_index", "col_index", "row_label",
                  "col_header", "value"],
    "source_tables": ["yearbook_sh", "source_file", "source_table", "table_no", "part", "title", "domain",
                      "table_year_sh", "geo", "n_rows", "n_cols", "n_provinces", "row_years", "col_headers",
                      "notes", "header_source", "n_k12_facts", "n_he_facts"],
}


def frames() -> dict[str, pd.DataFrame]:
    f: dict[str, pd.DataFrame] = {}
    f["k12_stats"] = pd.read_parquet(OUT / "k12.parquet")[COLS["k12_stats"]]
    f["higher_ed_stats"] = pd.read_parquet(OUT / "he.parquet")[COLS["higher_ed_stats"]]
    f["raw_cells"] = pd.read_parquet(OUT / "raw_cells.parquet")[COLS["raw_cells"]]
    st = pd.read_parquet(OUT / "tables.parquet")
    st = st.drop_duplicates(["source_file", "source_table"])
    ts = OUT / "table_status.parquet"
    if ts.exists():
        st = st.merge(pd.read_parquet(ts)[["source_file", "source_table", "check_status", "pass_rate"]],
                      on=["source_file", "source_table"], how="left")
    else:
        st["check_status"], st["pass_rate"] = None, None
    st["check_status"] = st["check_status"].fillna("unchecked")
    f["source_tables"] = st[COLS["source_tables"] + ["check_status", "pass_rate"]]
    units = pd.read_parquet(OUT / "units.parquet")
    sf = st.groupby(["source_file", "yearbook_sh"]).size().rename("n_tables").reset_index()
    kind = units.set_index("yearbook_sh")["kind"].to_dict()
    sf["unit_kind"] = sf.yearbook_sh.map(kind)
    f["source_files"] = sf[["source_file", "yearbook_sh", "unit_kind", "n_tables"]]
    f["provinces"] = pd.DataFrame([
        {"code": p.code, "name_fa": p.name_fa, "name_en": p.name_en, "iso_3166_2": p.iso,
         "harmonised_group": p.group, "established_sh": p.established_sh, "parent_code": p.parent,
         "is_historic": p.historic, "successors": ",".join(p.successors) or None}
        for p in ALL.values()
    ] + [{"code": "IRN", "name_fa": "کل کشور", "name_en": "Iran (national total)", "iso_3166_2": "IR",
          "harmonised_group": "IRN", "established_sh": None, "parent_code": None, "is_historic": False,
          "successors": None}])
    f["province_aliases"] = pd.DataFrame(sorted(ALIASES.items()), columns=["alias_norm", "code"])
    f["metrics"] = pd.DataFrame(METRICS, columns=["domain", "metric", "name_en", "name_fa", "unit", "definition",
                                                  "comparability"])
    f["term_map"] = pd.DataFrame([
        {"rule_order": i, "dim": r.dim, "value": r.value, "pattern": r.pattern, "how": r.how, "domain": r.domain,
         "note": r.note} for i, r in enumerate(RULES)
    ])
    vi = OUT / "validation.parquet"
    if vi.exists():
        f["validation_issues"] = pd.read_parquet(vi)
    return f


INT_COLS = {"year_sh", "year_gregorian", "yearbook_sh", "established_sh", "n_tables", "part", "table_year_sh",
            "n_rows", "n_cols", "n_provinces", "n_k12_facts", "n_he_facts", "row_index", "col_index", "rule_order"}

ORDER = ["provinces", "province_aliases", "metrics", "term_map", "source_files", "source_tables", "raw_cells",
         "k12_stats", "higher_ed_stats", "validation_issues"]


def _split_sql(text: str) -> list[str]:
    text = re.sub(r"--[^\n]*", "", text)
    return [s.strip() for s in text.split(";") if s.strip()]


def load_pg(url: str) -> None:
    import psycopg

    fr = frames()
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for stmt in _split_sql((SQL / "schema.sql").read_text()):
            cur.execute(stmt)
        for name in ORDER:
            if name not in fr:
                continue
            df = fr[name].copy()
            for c in df.columns:
                if c in INT_COLS:
                    df[c] = df[c].astype("Int64")
            df = df.astype(object).where(pd.notna(df), None)
            cols = list(df.columns)
            with cur.copy(f"COPY {name} ({', '.join(cols)}) FROM STDIN") as cp:
                for row in df.itertuples(index=False, name=None):
                    cp.write_row(row)
            print(f"  {name}: {len(df)} rows")
        for stmt in _split_sql((SQL / "views.sql").read_text()):
            cur.execute(stmt)
        conn.commit()
    print(f"loaded into {url.split('@')[-1]}")


def load_duckdb(path: str) -> None:
    import duckdb

    p = Path(path)
    if p.exists():
        p.unlink()
    fr = frames()
    con = duckdb.connect(str(p))
    for stmt in _split_sql((SQL / "schema.sql").read_text()):
        if stmt.upper().startswith("DROP"):
            continue
        con.execute(stmt)
    for name in ORDER:
        if name not in fr:
            continue
        df = fr[name]  # noqa: F841  (referenced by name inside the SQL)
        con.execute(f"INSERT INTO {name} ({', '.join(fr[name].columns)}) SELECT * FROM df")
        print(f"  {name}: {len(fr[name])} rows")
    for stmt in _split_sql((SQL / "views.sql").read_text()):
        con.execute(stmt)
    con.close()
    print(f"loaded into {p}")


def load(pg: str | None = None, duck: str | None = None) -> None:
    url = pg or (None if duck else os.environ.get("DATABASE_URL"))
    if url:
        load_pg(url)
    else:
        load_duckdb(duck or str(OUT / "edu.duckdb"))
