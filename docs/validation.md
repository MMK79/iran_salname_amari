# Validation

`uv run python -m etl.run validate` (after `extract`). Results: `data/out/validation.parquet`
(loaded as `validation_issues`), `validation_summary.csv`, `table_status.parquet`
(-> `source_tables.check_status`). The analytic views **drop tables marked `failed`**.

| check | what | pass rate (2026-09-27 run) |
|---|---|---|
| gender_sum | total = male + female, per row | K-12 98.6 % (14,131) · HE 98.6 % (20,671) |
| degree_sum | HE all degrees = sum of the five levels | 95.6 % (7,385) |
| province_sum | national row = sum of provinces (1 %) | K-12 94.2 % · HE 99.0 % |
| cross_publication | first-release national value vs the next 1-3 yearbooks (5 %) | K-12 84.4 % · HE 76.0 % |
| province_shift | PDF tables: >= 3 provinces' share moves > 1.6x vs previous year -> misaligned | K-12 88.6 % · HE 37.5 % |
| yoy_jump | > 30 % year-on-year change in the best series (warn only) | 1,130 flags |
| revision | same figure printed differently by different yearbooks (info) | 5,637 |

220 of 1,289 checked tables are marked failed (most are pre-1380 or PDF 1399-1402). Cross-
publication failures are partly genuine SCI revisions, not parse errors; a failed table is
excluded, and the year is then served from later yearbooks' historic rows ("most yearbooks agree"
rule in `v_*_best`).

Known genuine discontinuities that `yoy_jump` flags and that are **not** errors: the 1391-93
school reform (lower-secondary enrolment -35 % in 1391, +49 % in 1394), HE coverage change 1393
(Azad included), teacher definition 1394.
