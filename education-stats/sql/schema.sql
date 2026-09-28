-- Iran education statistics (Statistical Centre of Iran yearbooks 1345-1402 SH)
-- Tidy long format. K-12 and higher education live in SEPARATE fact tables and are
-- never mixed. Every fact keeps provenance: source_file + source_table (+ title,
-- row label and column header exactly as printed).
-- Portable: runs on PostgreSQL 16 and (for the fallback mode) DuckDB.

DROP VIEW IF EXISTS v_he_students_per_staff CASCADE;
DROP TABLE IF EXISTS validation_issues, k12_stats, higher_ed_stats, raw_cells, source_tables, source_files,
    term_map, metrics, province_aliases, provinces CASCADE;

CREATE TABLE provinces (
    code             TEXT PRIMARY KEY,          -- project key, e.g. THR
    name_fa          TEXT NOT NULL,
    name_en          TEXT NOT NULL,
    iso_3166_2       TEXT,                      -- IR-00..IR-30 (NULL for historic units)
    harmonised_group TEXT NOT NULL,             -- constant-border unit for long series
    established_sh   INTEGER,                   -- first academic year as its own unit (NULL = before 1345)
    parent_code      TEXT,                      -- province it split from
    is_historic      BOOLEAN NOT NULL,          -- TRUE for units that no longer exist (e.g. undivided Khorasan)
    successors       TEXT                       -- comma-separated codes of today's provinces
);

CREATE TABLE province_aliases (
    alias_norm TEXT PRIMARY KEY,                -- normalised spelling as matched by the ETL
    code       TEXT NOT NULL
);

CREATE TABLE metrics (
    domain      TEXT NOT NULL,                  -- k12 | he
    metric      TEXT NOT NULL,
    name_en     TEXT NOT NULL,
    name_fa     TEXT NOT NULL,
    unit        TEXT NOT NULL,
    definition  TEXT NOT NULL,
    comparability TEXT,
    PRIMARY KEY (domain, metric)
);

CREATE TABLE term_map (                         -- the explicit source-wording -> dimension mapping
    rule_order INTEGER PRIMARY KEY,
    dim        TEXT NOT NULL,
    value      TEXT NOT NULL,
    pattern    TEXT NOT NULL,
    how        TEXT NOT NULL,                   -- exact | contains | startswith
    domain     TEXT NOT NULL,                   -- k12 | he | any
    note       TEXT
);

CREATE TABLE source_files (
    source_file  TEXT PRIMARY KEY,              -- path relative to the read-only source root
    yearbook_sh  INTEGER NOT NULL,
    unit_kind    TEXT NOT NULL,                 -- docx_chapter | doc_converted_book | pdf_book | ...
    n_tables     INTEGER
);

CREATE TABLE source_tables (
    yearbook_sh   INTEGER NOT NULL,
    source_file   TEXT NOT NULL,
    source_table  TEXT NOT NULL,                -- "<table>-<chapter>#<part>" as numbered in the yearbook
    table_no      TEXT,
    part          INTEGER,
    title         TEXT,
    domain        TEXT,                         -- k12 | he | teacher_training | other
    table_year_sh INTEGER,
    geo           TEXT,                         -- national | province | some-provinces
    n_rows        INTEGER,
    n_cols        INTEGER,
    n_provinces   INTEGER,
    row_years     TEXT,
    col_headers   TEXT,
    notes         TEXT,                         -- footnotes as printed (coverage caveats live here)
    header_source TEXT,                         -- document | template:<yearbook>/<table> (PDF years)
    n_k12_facts   INTEGER,
    n_he_facts    INTEGER,
    check_status  TEXT,                         -- passed | failed | unchecked (etl.validate); views drop failed
    pass_rate     DOUBLE PRECISION,
    PRIMARY KEY (source_file, source_table)
);

CREATE TABLE raw_cells (                        -- every number of every education table, uninterpreted
    yearbook_sh  INTEGER NOT NULL,
    source_file  TEXT NOT NULL,
    source_table TEXT NOT NULL,
    row_index    INTEGER NOT NULL,
    col_index    INTEGER NOT NULL,
    row_label    TEXT,
    col_header   TEXT,
    value        DOUBLE PRECISION
);

CREATE TABLE k12_stats (
    year_sh        INTEGER NOT NULL,            -- academic year start (SH), e.g. 1398 = 1398-99
    year_gregorian INTEGER NOT NULL,            -- calendar year the academic year starts (Mehr ~ Sept/Oct)
    yearbook_sh    INTEGER NOT NULL,            -- which yearbook printed the number
    province_code  TEXT NOT NULL,               -- IRN = national
    province_label TEXT,                        -- as printed
    level          TEXT NOT NULL,               -- normalised via term_map (primary, lower_secondary, ...)
    level_source   TEXT NOT NULL,               -- the wording the level came from
    school_system  TEXT NOT NULL,               -- old_5-3-4 (<=1390) | new_6-3-3 (>=1391)
    programme      TEXT NOT NULL,               -- regular | adult | special_needs
    branch         TEXT NOT NULL,               -- all | theoretical | technical_vocational | kardanesh | ...
    sector         TEXT NOT NULL,               -- all | public | nonpublic
    area           TEXT NOT NULL,               -- total | urban | rural | nomadic
    gender         TEXT NOT NULL,               -- total | male | female
    metric         TEXT NOT NULL,               -- see metrics
    value          DOUBLE PRECISION NOT NULL,
    source_file    TEXT NOT NULL,
    source_format  TEXT NOT NULL,
    source_table   TEXT NOT NULL,
    table_title    TEXT,
    row_label      TEXT,
    col_header     TEXT,
    row_category   TEXT,                        -- non-NULL = row label not understood by term_map (excluded from views)
    col_category   TEXT,                        -- non-NULL = column part not understood (e.g. grade x stream)
    header_source  TEXT,
    domain         TEXT
);

CREATE TABLE higher_ed_stats (
    year_sh               INTEGER NOT NULL,
    year_gregorian        INTEGER NOT NULL,
    yearbook_sh           INTEGER NOT NULL,
    province_code         TEXT NOT NULL,
    province_label        TEXT,
    university_type       TEXT NOT NULL,        -- all_reported | excl_azad | azad | payame_noor | applied_science | ...
    university_type_source TEXT,
    degree_level          TEXT NOT NULL,        -- all | associate | bachelor | master | professional_doctorate | phd | doctorate_unspecified
    degree_level_source   TEXT,
    field_group           TEXT NOT NULL,        -- all | medical | humanities | basic_sciences | engineering | agri_vet | art | ...
    rank                  TEXT NOT NULL,        -- academic staff only: all | professor | ... | non_faculty
    employment            TEXT NOT NULL,        -- academic staff only: fulltime | hourly | fulltime_and_hourly | unspecified
    coverage              TEXT,                 -- flags from the footnotes that apply to this cell: incl_azad;excl_azad;excl_uast;excl_pnu;...
    area                  TEXT NOT NULL,
    gender                TEXT NOT NULL,
    metric                TEXT NOT NULL,
    value                 DOUBLE PRECISION NOT NULL,
    source_file           TEXT NOT NULL,
    source_format         TEXT NOT NULL,
    source_table          TEXT NOT NULL,
    table_title           TEXT,
    row_label             TEXT,
    col_header            TEXT,
    row_category          TEXT,
    col_category          TEXT,
    header_source         TEXT,
    domain                TEXT
);

CREATE TABLE validation_issues (
    check_name   TEXT NOT NULL,
    severity     TEXT NOT NULL,                 -- error | warn | info
    domain       TEXT,
    yearbook_sh  INTEGER,
    year_sh      INTEGER,
    source_file  TEXT,
    source_table TEXT,
    detail       TEXT,
    expected     DOUBLE PRECISION,
    actual       DOUBLE PRECISION
);

CREATE INDEX ix_k12_main ON k12_stats (metric, level, year_sh, province_code);
CREATE INDEX ix_he_main ON higher_ed_stats (metric, year_sh, province_code, university_type);
