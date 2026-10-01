# Dashboard spec

Status 2026-09-27: **prototype built** (`dashboard/app.py`, Streamlit + Plotly, `make dashboard`),
checked in a headless browser (map renders, animation slider, province charts). The target
stack below is the next step.

## Purpose

Show, for the thesis motivation chapter, where Iran lacks teachers and academic staff relative to
students, and how that changed over time. Two separate views, never mixed:
**K-12 students per teacher** and **higher-education students per academic staff member**.

## Views

1. **Province map** (31 provinces), colour = ratio for the selected year; sequential single-hue
   blue ramp (light = low ratio). Year slider with a play button animates 1380-1402.
   * K-12: level selector (primary / lower secondary / upper secondary). Before 1394 the teacher
     count is the «کارکنان آموزشی» proxy - banner + tooltip say so.
   * HE: students per full-time academic staff (incl. Azad), 1393-1402; years with quarantined
     province tables (1399, 1400, 1402) are blank, not zero.
   * Undivided Khorasan (<= 1382) is painted on all three of today's Khorasan provinces and named
     "Khorasan (undivided)" in the tooltip. Alborz is blank before 1389 (counted in Tehran).
2. **Province drill-down** (click the map or pick from the list): K-12 ratio over time, one line per
   level (3 categorical colours, legend + hover); HE ratio for the province vs the national line.
3. **Table + provenance** expander: every point with `source_file :: source_table`.

## Data contract

Reads only the SQL views: `v_k12_students_per_teacher`, `v_he_students_per_staff`, `provinces`.
DuckDB file by default; Postgres when `DATABASE_URL` is set.

## Map geometry

geoBoundaries IRN ADM1, simplified (gbOpen, commit 9469f09), boundary year 2017, **licence Open
Data Commons ODbL 1.0**, source OpenStreetMap contributors (Wambacher). Attribution shown in the
app. 32 features (Mazandaran is two polygons), 31 provinces. Joined on English name -> project
code (`dashboard/data/provinces.geojson` adds `code`, `name_fa`). Its `shapeISO` values use the
pre-2020 ISO numbering, so they are not used for joins. Rings were rewound for d3/Plotly
(exterior clockwise); without this Plotly fills the whole globe.

## Target stack (phase 2)

FastAPI (`/api/k12?level=&year=`, `/api/he?year=`, `/api/province/{code}`) over Postgres views +
a single-page app with MapLibre GL (choropleth + year slider/play) and a small chart library
(e.g. Observable Plot). Same colour rules; hover tooltips with provenance; a table view; dark mode
with its own validated steps; Persian labels RTL.

## Open items

* Faculty per province *by university type* is not in the yearbooks after 1392 - not shown.
* Add a "definitions changed here" marker on the time axis (1391-93 school reform, 1394 teacher
  definition, 1393 HE coverage).

## Static-site export (2026-10-01)

`make export-site` (`scripts/export_site.py`, tested by `tests/test_export_site.py`) writes
`exports/site/{provinces,k12,he,provenance,meta}.json` from the same views the dashboard reads.
Flag and caveat definitions are in `meta.json`. Measured: gender splits are students only (teachers and
academic staff are totals); HE per-type and per-degree figures are national only; HE academic staff for
1402 are absent from the views (so no 1402 ratio, national or province). Per-university counts are not
in the yearbooks and are not exported.

## Outcomes and relations (2026-10-01)

Two more files in `exports/site/`: `outcomes.json` (per year x province incl. IRN: `pass_rate[level][gender]`
for primary and lower secondary, `class_size[level]`, `completion_proxy[gender]`,
`he_graduation_ratio[gender]`; withheld values are absent with a `status`; year `flags` are defined in
`meta.json`) and `relations.json` (per-year cross-province Pearson/Spearman and n for years with >= 25
provinces, pooled province + year fixed-effects estimates in three specs). Suggested UI: a second map layer
or small scatter "students per teacher vs pass rate" for the selected year (grey out years with no
correlation: 1386-88, 1391 lower secondary, 1400, 1402), the within-province estimates as a footnote, and
always the wording **association, not effect**. Show the flags `school_reform_1391_93`, `pandemic_1399`,
`pass_year_relabelled_1398`, `pass_rate_provinces_withheld`. Primary pass rates are near ceiling and
low-variance: lead with lower secondary. Completion proxy and HE graduation ratio are throughput proxies,
label them so.
