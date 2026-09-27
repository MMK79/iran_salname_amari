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
