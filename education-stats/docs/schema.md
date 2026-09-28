# Schema

DDL: `sql/schema.sql`; views: `sql/views.sql`. Portable between PostgreSQL 16 and DuckDB.

* `k12_stats` - one row per printed K-12 number: `year_sh, year_gregorian, yearbook_sh,
  province_code, level (+ level_source), school_system, programme, branch, sector, area, gender,
  metric, value` + provenance `source_file, source_table, table_title, row_label, col_header,
  header_source` + `row_category/col_category` (non-NULL = wording not understood -> excluded).
* `higher_ed_stats` - same idea for HE: `university_type (+ source), degree_level (+ source),
  field_group, rank, employment, coverage` (footnote flags: incl_azad, excl_azad, excl_uast, ...).
* `raw_cells` - every number of every education table, uninterpreted (404,590 cells).
* `source_files`, `source_tables` (title, footnotes, geography, check_status), `provinces`,
  `province_aliases`, `metrics` (dictionary with comparability notes), `term_map` (the explicit
  wording -> dimension mapping, see `docs/mappings.md`), `validation_issues`.

`year_sh` is the academic year's start (1398 = 1398-99); `year_gregorian = year_sh + 621`.

Views: `v_k12_clean`, `v_k12_best` (one value per key), `v_k12_level_panel`,
`v_k12_students_per_teacher`, `v_k12_core_students_per_teacher`, `v_k12_growth`,
`v_k12_province_inequality`, `v_he_clean`, `v_he_best`, `v_he_students`, `v_he_staff`,
`v_he_students_per_staff`, `v_he_degree_mix`, `v_he_growth`.
