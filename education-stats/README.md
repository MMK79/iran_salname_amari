# Iran education statistics (Statistical Centre of Iran yearbooks, 1345-1402 SH)

A tidy, provenance-preserving dataset of Iran's education chapter (K-12 and higher education) from
the national statistical yearbooks (سالنامه آماری کشور), built for an MSc thesis on AI in
education (motivation: shortage of teachers and academic staff relative to students).

**Hard rule:** K-12 (آموزش و پرورش) and higher education (آموزش عالی) are separate fact tables
and are never mixed; within HE the degree levels (associate, bachelor, master, professional
doctorate, PhD) and university types stay separate. Source wording is kept next to every
normalised value; the mapping is explicit (`etl/terms.py`, `docs/mappings.md`).

## Status (2026-09-27)

* Parsed and loaded: yearbooks **1380-1402** (verified structure; province level every year
  1380-1402 for K-12) and **1345-1369** (extracted, not yet verified, excluded from the views).
  Not parsed: 1370-1379 (plain-text HTML / legacy-font PDFs); see `docs/inventory.md`.
* 138k K-12 facts, 98k HE facts, 405k raw cells, 3.3k source tables; validation in
  `docs/validation.md`; findings in `docs/findings.md`.

## Run

Requirements: `uv`, Docker (for Postgres), LibreOffice `soffice` and `pdftotext` (poppler) on the
host for `etl-local`. The source folder is only ever read (mounted `:ro` in Docker).

```bash
uv sync --all-groups
make up            # Postgres 16 on localhost:5433 (user/pass/db: edu), volume "pgdata"
make etl           # in Docker: convert .doc -> .cache, extract, validate, load Postgres
# or on the host:
make etl-local     # same; loads Postgres if it is up, else DuckDB data/out/edu.duckdb
make test          # pytest (28 tests)
make dashboard     # Streamlit prototype on http://localhost:8501
make export-site   # static JSON for a website map -> exports/site/ (scripts/export_site.py)
uv run python analysis/ratio_vs_outcomes.py   # students/teacher vs pass rate: figures + numbers (analysis/README.md)
```

Step by step: `scripts/convert_docs.sh 4` -> `uv run python -m etl.run extract [--years 1388-1402]`
-> `... validate` -> `... load --pg URL` or `--duckdb PATH` -> `... docs` (regenerates
inventory and mappings). `SOURCE_DIR` overrides the source path.

Without Docker: everything works with the DuckDB fallback (`data/out/edu.duckdb`), same schema
and views.

## Layout

```
etl/extract/   docx (fast lxml, x-position grid), html grid, PDF text (pdftotext + templates)
etl/           normalize (Persian digits/letters), provinces, terms (mapping), coverage (footnotes),
               facts, validate, load, docs, run (CLI)
sql/           schema.sql, views.sql (derived ratios, growth, inequality)
scripts/       convert_docs.sh, export_site.py (provinces/k12/he/outcomes/relations/provenance/meta JSON for the site)
dashboard/     app.py (Streamlit + Plotly), data/provinces.geojson (geoBoundaries, ODbL)
analysis/      ratio_vs_outcomes.py, figures/, README.md (resource ratios vs pass rates; association only)
docs/          inventory, schema, mappings, provinces, validation, findings, dashboard-spec
```

## Key caveats

* Teachers: «معلم» from 1394, «کارکنان آموزشی» (educational staff) before, used as proxy.
* HE: until 1392 tables exclude Islamic Azad University and count full + part-time staff; from
  1393 they include Azad and count full-time staff. Break in series.
* PDF years 1399-1402: headers come from matching Word-era tables and are validated; misread
  tables are quarantined (`source_tables.check_status = 'failed'`).
* School reform 1391-93 (5-3-4 -> 6-3-3) moves grades between levels.

Map data: geoBoundaries IRN ADM1 (ODbL 1.0, (c) OpenStreetMap contributors).
