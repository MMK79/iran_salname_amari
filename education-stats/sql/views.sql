-- Derived metrics. Portable SQL (PostgreSQL 16 / DuckDB).
-- All views read only "understood" facts: row_category and col_category NULL.

-- ---------------------------------------------------------------- K-12
-- Yearbooks before 1380 are extracted (k12_stats / higher_ed_stats keep them) but their
-- table layouts are not yet verified, so the analytic views use yearbooks >= 1380 only.
-- Years before 1380 still enter through the historic rows printed in later yearbooks.
CREATE OR REPLACE VIEW v_k12_clean AS
SELECT f.* FROM k12_stats f
JOIN source_tables t ON t.source_file = f.source_file AND t.source_table = f.source_table
WHERE f.row_category IS NULL AND f.col_category IS NULL AND f.yearbook_sh >= 1380 AND t.check_status <> 'failed' 
  AND area = 'total' AND branch = 'all' AND sector = 'all';

-- One value per key: prefer the yearbook of that same year (first release, the one with
-- province detail); else the value most later yearbooks agree on; else the closest one.
CREATE OR REPLACE VIEW v_k12_best AS
SELECT * FROM (
  SELECT c.*,
         ROW_NUMBER() OVER (
           PARTITION BY year_sh, province_code, level, programme, gender, metric
           ORDER BY CASE WHEN yearbook_sh = year_sh THEN 0 ELSE 1 END,
                    n_agree DESC,
                    ABS(yearbook_sh - year_sh),
                    CASE WHEN header_source = 'document' THEN 0 ELSE 1 END,
                    source_table) AS rn
  FROM (SELECT x.*, COUNT(*) OVER (PARTITION BY year_sh, province_code, level, programme, gender, metric, value)
               AS n_agree FROM v_k12_clean x) c
  WHERE yearbook_sh >= year_sh
) t WHERE rn = 1;

-- Students, teachers (teacher proxy before 1394), classes and schools per province x level x year.
CREATE OR REPLACE VIEW v_k12_level_panel AS
SELECT year_sh, MIN(year_gregorian) AS year_gregorian, province_code, level,
       MAX(CASE WHEN metric = 'students' AND gender = 'total' THEN value END) AS students,
       MAX(CASE WHEN metric = 'students' AND gender = 'female' THEN value END) AS students_female,
       MAX(CASE WHEN metric = 'teachers' AND gender = 'total' THEN value END) AS teachers,
       MAX(CASE WHEN metric = 'educational_staff' AND gender = 'total' THEN value END) AS educational_staff,
       MAX(CASE WHEN metric = 'classes' AND gender = 'total' THEN value END) AS classes,
       MAX(CASE WHEN metric = 'schools' AND gender = 'total' THEN value END) AS schools,
       MIN(yearbook_sh) AS yearbook_sh,
       MIN(source_file || ' :: ' || source_table) AS provenance
FROM v_k12_best
WHERE programme = 'regular' AND level IN ('preschool', 'primary', 'lower_secondary', 'upper_secondary', 'pre_university')
GROUP BY year_sh, province_code, level;

CREATE OR REPLACE VIEW v_k12_students_per_teacher AS
SELECT p.*,
       COALESCE(teachers, educational_staff) AS teachers_used,
       CASE WHEN teachers IS NOT NULL THEN 'teachers (معلم)'
            WHEN educational_staff IS NOT NULL THEN 'educational staff (کارکنان آموزشی) - proxy' END AS teacher_definition,
       students / NULLIF(COALESCE(teachers, educational_staff), 0) AS students_per_teacher,
       students / NULLIF(classes, 0) AS students_per_class,
       students_female / NULLIF(students, 0) AS female_share
FROM v_k12_level_panel p;

-- The three core school levels summed (primary + lower + upper secondary; pre-university
-- is folded into upper secondary staff in the old system, so it is left out of both sides).
CREATE OR REPLACE VIEW v_k12_core_students_per_teacher AS
SELECT year_sh, MIN(year_gregorian) AS year_gregorian, province_code,
       SUM(students) AS students, SUM(COALESCE(teachers, educational_staff)) AS teachers_used,
       SUM(students) / NULLIF(SUM(COALESCE(teachers, educational_staff)), 0) AS students_per_teacher,
       COUNT(*) AS n_levels,
       MAX(CASE WHEN teachers IS NULL THEN 1 ELSE 0 END) AS uses_proxy
FROM v_k12_level_panel
WHERE level IN ('primary', 'lower_secondary', 'upper_secondary') AND students IS NOT NULL
  AND COALESCE(teachers, educational_staff) IS NOT NULL
GROUP BY year_sh, province_code
HAVING COUNT(*) = 3;

-- ---------------------------------------------------------------- Higher education
CREATE OR REPLACE VIEW v_he_clean AS
SELECT f.* FROM higher_ed_stats f
JOIN source_tables t ON t.source_file = f.source_file AND t.source_table = f.source_table
WHERE f.row_category IS NULL AND f.col_category IS NULL AND f.area = 'total' AND f.yearbook_sh >= 1380
  AND t.check_status <> 'failed';

CREATE OR REPLACE VIEW v_he_best AS
SELECT * FROM (
  SELECT c.*,
         ROW_NUMBER() OVER (
           PARTITION BY year_sh, province_code, university_type, degree_level, field_group, rank, employment, gender, metric
           ORDER BY CASE WHEN yearbook_sh = year_sh THEN 0 ELSE 1 END,
                    n_agree DESC,
                    ABS(yearbook_sh - year_sh),
                    CASE WHEN header_source = 'document' THEN 0 ELSE 1 END,
                    source_table) AS rn
  FROM (SELECT x.*, COUNT(*) OVER (PARTITION BY year_sh, province_code, university_type, degree_level, field_group,
                                     rank, employment, gender, metric, value) AS n_agree FROM v_he_clean x) c
  WHERE yearbook_sh >= year_sh
) t WHERE rn = 1;

-- Students by degree level, university type, province (never mixed with K-12).
CREATE OR REPLACE VIEW v_he_students AS
SELECT year_sh, year_gregorian, province_code, university_type, degree_level, field_group,
       MAX(CASE WHEN gender = 'total' THEN value END) AS students,
       MAX(CASE WHEN gender = 'female' THEN value END) AS students_female,
       MAX(CASE WHEN gender = 'female' THEN value END) / NULLIF(MAX(CASE WHEN gender = 'total' THEN value END), 0) AS female_share,
       MIN(source_file || ' :: ' || source_table) AS provenance
FROM v_he_best WHERE metric = 'students'
GROUP BY year_sh, year_gregorian, province_code, university_type, degree_level, field_group;

-- Academic staff: all instructors and faculty members (= all minus non-faculty instructors).
CREATE OR REPLACE VIEW v_he_staff AS
SELECT year_sh, province_code, university_type, employment,
       MAX(CASE WHEN rank = 'all' AND gender = 'total' THEN value END) AS academic_staff,
       MAX(CASE WHEN rank = 'non_faculty' AND gender = 'total' THEN value END) AS non_faculty,
       MAX(CASE WHEN rank = 'all' AND gender = 'female' THEN value END) AS academic_staff_female,
       MAX(CASE WHEN rank = 'professor' AND gender = 'total' THEN value END) AS professors,
       MAX(CASE WHEN rank = 'associate_professor' AND gender = 'total' THEN value END) AS associate_professors,
       MAX(CASE WHEN rank = 'assistant_professor' AND gender = 'total' THEN value END) AS assistant_professors,
       MAX(CASE WHEN rank = 'instructor' AND gender = 'total' THEN value END) AS instructors,
       MIN(source_file || ' :: ' || source_table) AS provenance
FROM v_he_best WHERE metric = 'academic_staff' AND degree_level = 'all' AND field_group = 'all'
GROUP BY year_sh, province_code, university_type, employment;

-- Students per academic staff member by province and university type.
-- university_type: all_reported (1393+, incl. Azad) | excl_azad (<=1392) | azad (<=1392 separate tables)
CREATE OR REPLACE VIEW v_he_students_per_staff AS
SELECT s.year_sh, s.year_gregorian, s.province_code, s.university_type, st.employment,
       s.students, st.academic_staff,
       st.academic_staff - COALESCE(st.non_faculty, 0) AS faculty_members,
       s.students / NULLIF(st.academic_staff, 0) AS students_per_staff,
       s.students / NULLIF(st.academic_staff - COALESCE(st.non_faculty, 0), 0) AS students_per_faculty_member,
       s.provenance AS students_provenance, st.provenance AS staff_provenance
FROM v_he_students s
JOIN v_he_staff st ON st.year_sh = s.year_sh AND st.province_code = s.province_code
                  AND st.university_type = s.university_type
WHERE s.degree_level = 'all' AND s.field_group = 'all';

-- Degree-level mix (share of each degree in total enrolment).
CREATE OR REPLACE VIEW v_he_degree_mix AS
SELECT a.year_sh, a.province_code, a.university_type, a.degree_level, a.students,
       a.students / NULLIF(t.students, 0) AS share_of_total, a.female_share
FROM v_he_students a
JOIN v_he_students t ON t.year_sh = a.year_sh AND t.province_code = a.province_code
                    AND t.university_type = a.university_type AND t.degree_level = 'all'
                    AND t.field_group = 'all'
WHERE a.field_group = 'all' AND a.degree_level <> 'all';

-- ---------------------------------------------------------------- growth rates / time series
CREATE OR REPLACE VIEW v_k12_growth AS
SELECT *, students / NULLIF(LAG(students) OVER w, 0) - 1 AS students_growth,
       teachers_used / NULLIF(LAG(teachers_used) OVER w, 0) - 1 AS teachers_growth,
       year_sh - LAG(year_sh) OVER w AS gap_years
FROM v_k12_students_per_teacher
WINDOW w AS (PARTITION BY province_code, level ORDER BY year_sh);

CREATE OR REPLACE VIEW v_he_growth AS
SELECT *, students / NULLIF(LAG(students) OVER w, 0) - 1 AS students_growth,
       year_sh - LAG(year_sh) OVER w AS gap_years
FROM v_he_students
WHERE field_group = 'all'
WINDOW w AS (PARTITION BY province_code, university_type, degree_level ORDER BY year_sh);

-- Province inequality of K-12 students per teacher (coefficient of variation, min, max) per level-year.
CREATE OR REPLACE VIEW v_k12_province_inequality AS
SELECT year_sh, level, COUNT(*) AS n_provinces,
       AVG(students_per_teacher) AS mean_spt, MIN(students_per_teacher) AS min_spt,
       MAX(students_per_teacher) AS max_spt,
       STDDEV_SAMP(students_per_teacher) / NULLIF(AVG(students_per_teacher), 0) AS cv_spt
FROM v_k12_students_per_teacher
WHERE province_code <> 'IRN' AND students_per_teacher IS NOT NULL
GROUP BY year_sh, level;

-- ================================================================ Outcome measures (added 2026-10-01)
-- Association with the resource ratios, not causal effects. See docs/findings.md section 5.

-- 'passed' (قبول شدگان) with ONE known source defect repaired: the 1399 PDF table 17-17#1 has no printed
-- year labels, the ETL assigned it to 1399, but its 31 province rows sum to 8,213,495 primary passes =
-- the national value of 1398 (printed in the 1400 yearbook), and its lower-secondary rows sum to the
-- national 1398 value too. It is the 1398 table; it is relabelled here (the 1399 values come from the
-- 1400 yearbook, which labels its years). tests/test_export_site.py checks the sum.
CREATE OR REPLACE VIEW v_k12_passed_best AS
SELECT * FROM (
  SELECT c.*,
         ROW_NUMBER() OVER (
           PARTITION BY year_corr, province_code, level, programme, gender
           ORDER BY CASE WHEN yearbook_sh = year_corr THEN 0 ELSE 1 END,
                    n_agree DESC,
                    ABS(yearbook_sh - year_corr),
                    CASE WHEN header_source = 'document' THEN 0 ELSE 1 END,
                    source_table) AS rn
  FROM (SELECT x.*, COUNT(*) OVER (PARTITION BY year_corr, province_code, level, programme, gender, value) AS n_agree
        FROM (SELECT k.*, CASE WHEN k.source_file = '1399/1399.pdf' AND k.source_table = '17-17#1'
                               THEN k.year_sh - 1 ELSE k.year_sh END AS year_corr
              FROM v_k12_clean k WHERE k.metric = 'passed') x) c
  WHERE yearbook_sh >= year_corr
) t WHERE rn = 1;

-- Pass rate = passed / students, same level, gender, province and year, regular programme, adults
-- excluded from both tables (footnote 1 of the passed table; the students tables are regular only).
-- The passed table counts pupils promoted at the end of the year over ALL grades of the level, so the
-- numerator and denominator cover the same population in a stable school system. Checked: provinces sum to
-- the national row; national rates are 0.84-0.99. Weak spots:
--   * 1391-93 (5-3-4 -> 6-3-3 reform): grades move between levels in one table but not the other for some
--     provinces, 1391 lower secondary exceeds 1 in 4 provinces. Flagged 'school_reform_1391_93'.
--   * 1386, 1387 province rows contain values far outside 0..1 (column misalignment in the source table).
--   * Per row: a rate > 1 or < 0.5 is never published (pass_rate NULL, status 'implausible_rate').
--     If >= 2 provinces of a year x level are implausible (counted on gender = total), the whole province set of that year x level
--     is withheld (status 'year_unreliable'); the national row stays.
--   * Primary pass rate is ~0.95-0.99 with small variance (descriptive evaluation): a weak outcome.
CREATE OR REPLACE VIEW v_k12_pass_rate AS
WITH j AS (
  SELECT p.year_corr AS year_sh, p.province_code, p.level, p.gender,
         p.value AS passed, s.value AS students,
         p.source_file || ' :: ' || p.source_table AS passed_provenance
  FROM v_k12_passed_best p
  JOIN v_k12_best s ON s.year_sh = p.year_corr AND s.province_code = p.province_code AND s.level = p.level
                   AND s.gender = p.gender AND s.metric = 'students' AND s.programme = 'regular'
  WHERE p.programme = 'regular' AND p.level IN ('primary', 'lower_secondary')
),
r AS (
  SELECT j.*, passed / NULLIF(students, 0) AS raw_rate,
         CASE WHEN passed / NULLIF(students, 0) > 1 OR passed / NULLIF(students, 0) < 0.5 THEN 1 ELSE 0 END AS implausible
  FROM j
),
y AS (
  SELECT r.*, SUM(CASE WHEN province_code <> 'IRN' AND gender = 'total' THEN implausible ELSE 0 END)
              OVER (PARTITION BY year_sh, level) AS n_implausible_provinces
  FROM r
)
SELECT year_sh, province_code, level, gender, passed, students,
       CASE WHEN implausible = 1 OR (province_code <> 'IRN' AND n_implausible_provinces >= 2) THEN NULL
            ELSE raw_rate END AS pass_rate,
       raw_rate AS pass_rate_raw,
       CASE WHEN implausible = 1 THEN 'implausible_rate'
            WHEN province_code <> 'IRN' AND n_implausible_provinces >= 2 THEN 'year_unreliable'
            ELSE 'ok' END AS status,
       CASE WHEN year_sh BETWEEN 1391 AND 1393 THEN 1 ELSE 0 END AS school_reform_1391_93,
       passed_provenance
FROM y;

-- Students per class (regular programme), province x level x year. Same population in numerator and
-- denominator (both from the level panel). Implausible values (< 5 or > 60) get status 'implausible'.
CREATE OR REPLACE VIEW v_k12_class_size AS
SELECT year_sh, province_code, level, students, classes,
       students / NULLIF(classes, 0) AS students_per_class,
       CASE WHEN students / NULLIF(classes, 0) BETWEEN 5 AND 60 THEN 'ok' ELSE 'implausible' END AS status,
       CASE WHEN year_sh BETWEEN 1391 AND 1393 THEN 1 ELSE 0 END AS school_reform_1391_93,
       provenance
FROM v_k12_level_panel
WHERE level IN ('primary', 'lower_secondary', 'upper_secondary') AND students IS NOT NULL AND classes IS NOT NULL;

-- Completion PROXY (not a completion rate): upper-secondary graduates in year t divided by upper-secondary
-- students in year t, regular programme. It is a throughput ratio: with three grades and a stable cohort
-- it would be ~0.33; cohort growth/shrinkage, repeaters and the 1391-93 reform move it. Graduates exist
-- only for a subset of years (see docs/findings.md); values outside 0.1..0.5 get status 'implausible'
-- (e.g. 1396 prints 53,544 national graduates against ~590,000 in neighbouring years).
CREATE OR REPLACE VIEW v_k12_completion AS
SELECT g.year_sh, g.province_code, g.gender, g.value AS graduates, s.value AS students,
       g.value / NULLIF(s.value, 0) AS completion_proxy,
       CASE WHEN g.value / NULLIF(s.value, 0) BETWEEN 0.1 AND 0.5 THEN 'ok' ELSE 'implausible' END AS status,
       CASE WHEN g.year_sh BETWEEN 1391 AND 1393 THEN 1 ELSE 0 END AS school_reform_1391_93
FROM v_k12_best g
JOIN v_k12_best s ON s.year_sh = g.year_sh AND s.province_code = g.province_code AND s.gender = g.gender
                 AND s.level = 'upper_secondary' AND s.metric = 'students' AND s.programme = 'regular'
WHERE g.metric = 'graduates' AND g.level = 'upper_secondary' AND g.programme = 'regular';

-- Higher-education graduates / students (throughput proxy, NOT a completion rate: graduates of all
-- degrees in a year over all enrolled in that year). Population: all_reported (incl. Azad) where printed,
-- else azad + excl_azad summed; 'basis' says which. Series break at 1393 (see v_he_students_per_staff).
-- degree_level 'all', field_group 'all'. Province tables of 1399, 1400, 1402 are quarantined upstream.
CREATE OR REPLACE VIEW v_he_graduation_ratio AS
WITH g AS (
  SELECT year_sh, province_code, gender, university_type, MAX(value) AS v
  FROM v_he_best WHERE metric = 'graduates' AND degree_level = 'all' AND field_group = 'all' AND rank = 'all'
    AND university_type IN ('all_reported', 'azad', 'excl_azad') GROUP BY year_sh, province_code, gender, university_type
),
s AS (
  SELECT year_sh, province_code, gender, university_type, MAX(value) AS v
  FROM v_he_best WHERE metric = 'students' AND degree_level = 'all' AND field_group = 'all' AND rank = 'all'
    AND university_type IN ('all_reported', 'azad', 'excl_azad') GROUP BY year_sh, province_code, gender, university_type
),
gu AS (
  SELECT k.year_sh, k.province_code, k.gender,
         COALESCE(MAX(CASE WHEN university_type = 'all_reported' THEN v END),
                  CASE WHEN COUNT(*) = 2 THEN SUM(v) END) AS graduates,
         MAX(CASE WHEN university_type = 'all_reported' THEN 1 ELSE 0 END) AS used_all
  FROM g k GROUP BY k.year_sh, k.province_code, k.gender
),
su AS (
  SELECT k.year_sh, k.province_code, k.gender,
         COALESCE(MAX(CASE WHEN university_type = 'all_reported' THEN v END),
                  CASE WHEN COUNT(*) = 2 THEN SUM(v) END) AS students,
         MAX(CASE WHEN university_type = 'all_reported' THEN 1 ELSE 0 END) AS used_all
  FROM s k GROUP BY k.year_sh, k.province_code, k.gender
)
SELECT gu.year_sh, gu.province_code, gu.gender, gu.graduates, su.students,
       gu.graduates / NULLIF(su.students, 0) AS graduation_ratio,
       CASE WHEN gu.used_all = 1 AND su.used_all = 1 THEN 'all_reported'
            WHEN gu.used_all = 0 AND su.used_all = 0 THEN 'azad_plus_excl_azad'
            ELSE 'mixed' END AS basis,
       CASE WHEN gu.graduates / NULLIF(su.students, 0) BETWEEN 0.05 AND 0.6 THEN 'ok' ELSE 'implausible' END AS status
FROM gu JOIN su ON su.year_sh = gu.year_sh AND su.province_code = gu.province_code AND su.gender = gu.gender;


-- ================================================================ Drop-out / progression (added 2026-10-01)
-- The yearbooks print NO drop-out, out-of-school, coverage-rate, repetition or compulsory-age-population
-- table for K-12 (searched titles and every row/column label; see docs/findings.md section 6). The only
-- derivable progression measure is an APPARENT COHORT SURVIVAL between two three-grade levels:
--   survival(t) = upper-secondary students in year t+3 / lower-secondary students in year t
-- (regular programme, same province and gender). The lower-secondary stock of year t is exactly three
-- cohorts (grades 7-9 in the 6-3-3 system, 6-8 in the old 5-3-4 system); three years later the same three
-- cohorts sit in the upper-secondary grades 10-12 (9-11), so no cohort-size correction is needed. It is
-- 1 - (drop-out + net out-migration + move to adult/non-regular programmes + deaths) + repeaters and
-- re-entrants; it is NOT a drop-out rate and not a cohort tracking.
-- year_sh = t (the lower-secondary year, so it lines up with students_per_teacher of that year);
-- survival_year_sh = t+3. Upper-secondary province data exist from 1390, so provinces start at t = 1387.
--   * reform_window: [t, t+3] touches 1391-93 (5-3-4 -> 6-3-3). In these windows the national ratio is
--     0.99-1.09 against 0.83-0.88 on both sides of the reform, i.e. the two stocks do not cover the same
--     grades. Withheld for every row (status 'reform_window').
--   * boundary_change: province units that were split during the window (Tehran/Alborz at 1390 in the
--     data, Khorasan at 1383); the two stocks do not cover the same territory. Withheld.
--   * a ratio > 1.05 or < 0.5 is never published (status 'implausible_rate'); if >= 2 provinces of a year
--     are implausible (counted on gender = total) the whole province set of that year is withheld
--     (status 'year_unreliable'), as in v_k12_pass_rate. The national row stays unless it is itself bad.
CREATE OR REPLACE VIEW v_k12_cohort_survival AS
WITH lo AS (
  SELECT year_sh, province_code, gender, value AS lower_students, source_file || ' :: ' || source_table AS lower_provenance
  FROM v_k12_best WHERE metric = 'students' AND programme = 'regular' AND level = 'lower_secondary'
),
up AS (
  SELECT year_sh, province_code, gender, value AS upper_students, source_file || ' :: ' || source_table AS upper_provenance
  FROM v_k12_best WHERE metric = 'students' AND programme = 'regular' AND level = 'upper_secondary'
),
j AS (
  SELECT lo.year_sh, up.year_sh AS survival_year_sh, lo.province_code, lo.gender, lo.lower_students, up.upper_students,
         up.upper_students / NULLIF(lo.lower_students, 0) AS raw_ratio,
         CASE WHEN lo.year_sh <= 1393 AND up.year_sh >= 1391 THEN 1 ELSE 0 END AS reform_window,
         CASE WHEN (lo.province_code IN ('TEH', 'ALB') AND lo.year_sh < 1390 AND up.year_sh >= 1390)
                OR (lo.province_code IN ('KHO', 'KHR', 'KHS', 'KHJ') AND lo.year_sh < 1383 AND up.year_sh >= 1383)
              THEN 1 ELSE 0 END AS boundary_change,
         lo.lower_provenance || ' -> ' || up.upper_provenance AS provenance
  FROM lo JOIN up ON up.year_sh = lo.year_sh + 3 AND up.province_code = lo.province_code AND up.gender = lo.gender
),
r AS (
  SELECT j.*, CASE WHEN raw_ratio > 1.05 OR raw_ratio < 0.5 THEN 1 ELSE 0 END AS implausible FROM j
),
y AS (
  SELECT r.*, SUM(CASE WHEN province_code <> 'IRN' AND gender = 'total' AND reform_window = 0 THEN implausible ELSE 0 END)
              OVER (PARTITION BY year_sh) AS n_implausible_provinces
  FROM r
)
SELECT year_sh, survival_year_sh, province_code, gender, lower_students, upper_students,
       CASE WHEN reform_window = 1 OR boundary_change = 1 OR implausible = 1
              OR (province_code <> 'IRN' AND n_implausible_provinces >= 2) THEN NULL
            ELSE raw_ratio END AS cohort_survival,
       raw_ratio AS cohort_survival_raw,
       CASE WHEN reform_window = 1 THEN 'reform_window'
            WHEN boundary_change = 1 THEN 'boundary_change'
            WHEN implausible = 1 THEN 'implausible_rate'
            WHEN province_code <> 'IRN' AND n_implausible_provinces >= 2 THEN 'year_unreliable'
            ELSE 'ok' END AS status,
       reform_window AS school_reform_1391_93,
       CASE WHEN year_sh BETWEEN 1396 AND 1400 THEN 1 ELSE 0 END AS pandemic_in_window,
       provenance
FROM y;


-- ================================================================ Higher-education quality indicators (added 2026-10-01)
-- Cohort completion, faculty rank mix and degree mix. Association/descriptive measures built only from
-- printed counts; see docs/findings.md section 7 for what is measured and what is inferred.

-- Entrants and graduates, one value per key (field_group 'all', rank 'all'), with the footnote flags of the
-- source table. The max() only collapses duplicate cells of the SAME key; v_he_best already has one row per key.
CREATE OR REPLACE VIEW v_he_flow AS
SELECT year_sh, province_code, university_type, degree_level, gender, metric,
       MAX(value) AS value,
       STRING_AGG(DISTINCT NULLIF(coverage, ''), '|') AS coverage_flags,
       MIN(source_file || ' :: ' || source_table) AS provenance
FROM v_he_best
WHERE metric IN ('new_entrants', 'graduates') AND field_group = 'all' AND rank = 'all'
  AND university_type IN ('all_reported', 'azad', 'excl_azad')
GROUP BY year_sh, province_code, university_type, degree_level, gender, metric;

-- Province rows are only used when they add up to the printed national row of the same table family
-- (0.97..1.03). The 1399 province graduate tables fail this (province sums 3-1500% of the national value:
-- the parser reads a different table), 1398 has no province graduate table at all.
CREATE OR REPLACE VIEW v_he_flow_checked AS
SELECT f.*,
       MAX(CASE WHEN province_code = 'IRN' THEN value END)
         OVER (PARTITION BY year_sh, university_type, degree_level, gender, metric) AS national_value,
       SUM(CASE WHEN province_code <> 'IRN' THEN value END)
         OVER (PARTITION BY year_sh, university_type, degree_level, gender, metric) AS province_sum,
       CASE WHEN province_code = 'IRN' THEN 1
            WHEN SUM(CASE WHEN province_code <> 'IRN' THEN value END)
                   OVER (PARTITION BY year_sh, university_type, degree_level, gender, metric)
                 / NULLIF(MAX(CASE WHEN province_code = 'IRN' THEN value END)
                   OVER (PARTITION BY year_sh, university_type, degree_level, gender, metric), 0)
                 BETWEEN 0.97 AND 1.03 THEN 1
            ELSE 0 END AS checks_ok
FROM v_he_flow f;

-- Nominal entry lag d (years between entry and graduation) by degree level. These are the regulated
-- programme lengths (inferred from MSRT/MOHME regulations, NOT printed in the yearbooks):
-- associate 2, bachelor 4, master 2, PhD 4 (3-5 in practice), professional doctorate 6 (medicine 7).
-- 'plus_1' is a sensitivity variant for programmes that run longer. 'all' mixes the lengths and is only a
-- continuity series across the 1393 break (d = 4 is then a convention, not a programme length).
CREATE OR REPLACE VIEW v_he_programme_length AS
SELECT * FROM (VALUES
  ('associate', 2, 'nominal'), ('associate', 3, 'plus_1'),
  ('bachelor', 4, 'nominal'), ('bachelor', 5, 'plus_1'),
  ('master', 2, 'nominal'), ('master', 3, 'plus_1'),
  ('phd', 4, 'nominal'), ('phd', 5, 'plus_1'),
  ('professional_doctorate', 6, 'nominal'), ('professional_doctorate', 7, 'plus_1'),
  ('all', 4, 'mixed_convention')
) AS t(degree_level, entry_lag, length_basis);

-- Cohort completion RATIO = graduates in year t / new entrants in year t - d (same degree level, gender,
-- province and population basis). NOT a completion rate and not a cohort tracking: the numerator and
-- denominator are two different stocks of different people (transfers between degrees and institutions,
-- guest students, repeaters, programmes longer or shorter than d, dropouts and late finishers all move
-- it). Bases: 'all_reported' (1393+ both sides; incl. Azad, Payame Noor, UAST ...);
-- 'azad_plus_excl_azad' (degree 'all' only, entry and graduation years before 1393: the yearbooks print no
-- entrants by degree for those years; Azad + non-Azad summed where both exist). A ratio outside
-- 0.2..1.3 is never published (status 'implausible_rate'); a province row whose side does not add up to
-- the national row is withheld (status 'province_sum_mismatch'); raw value kept in completion_ratio_raw.
CREATE OR REPLACE VIEW v_he_cohort_completion AS
WITH comb AS (
  SELECT year_sh, province_code, 'azad_plus_excl_azad' AS university_type, degree_level, gender, metric,
         SUM(value) AS value, MIN(checks_ok) AS checks_ok,
         STRING_AGG(DISTINCT coverage_flags, '|') AS coverage_flags, MIN(provenance) AS provenance
  FROM v_he_flow_checked
  WHERE university_type IN ('azad', 'excl_azad') AND degree_level = 'all'
  GROUP BY year_sh, province_code, degree_level, gender, metric
  HAVING COUNT(DISTINCT university_type) = 2
),
fc AS (
  SELECT year_sh, province_code, university_type, degree_level, gender, metric, value, checks_ok, coverage_flags, provenance
  FROM v_he_flow_checked WHERE university_type = 'all_reported'
  UNION ALL
  SELECT year_sh, province_code, university_type, degree_level, gender, metric, value, checks_ok, coverage_flags, provenance
  FROM comb
),
j AS (
  SELECT g.year_sh, g.year_sh - l.entry_lag AS entry_year_sh, g.province_code, g.university_type, g.degree_level,
         g.gender, l.entry_lag AS nominal_years, l.length_basis,
         g.value AS graduates, e.value AS entrants,
         g.value / NULLIF(e.value, 0) AS raw_ratio,
         g.checks_ok * e.checks_ok AS sides_ok,
         g.coverage_flags AS coverage_graduates, e.coverage_flags AS coverage_entrants,
         g.provenance || ' <- ' || e.provenance AS provenance
  FROM fc g
  JOIN v_he_programme_length l ON l.degree_level = g.degree_level
  JOIN fc e ON e.year_sh = g.year_sh - l.entry_lag AND e.province_code = g.province_code
           AND e.university_type = g.university_type AND e.degree_level = g.degree_level AND e.gender = g.gender
  WHERE g.metric = 'graduates' AND e.metric = 'new_entrants'
    AND (g.university_type <> 'all_reported' OR e.year_sh >= 1393)  -- the Azad break: both sides must be 1393+
)
SELECT year_sh, entry_year_sh, province_code, university_type, degree_level, gender, nominal_years, length_basis,
       graduates, entrants,
       CASE WHEN sides_ok = 0 OR raw_ratio > 1.3 OR raw_ratio < 0.2 THEN NULL ELSE raw_ratio END AS completion_ratio,
       raw_ratio AS completion_ratio_raw,
       CASE WHEN sides_ok = 0 THEN 'province_sum_mismatch'
            WHEN raw_ratio > 1.3 OR raw_ratio < 0.2 THEN 'implausible_rate'
            ELSE 'ok' END AS status,
       CASE WHEN entry_year_sh <= 1400 AND year_sh >= 1399 THEN 1 ELSE 0 END AS pandemic_in_window,
       CASE WHEN university_type = 'azad_plus_excl_azad' THEN 1 ELSE 0 END AS mixed_degree_lengths_pre_1393,
       coverage_entrants, coverage_graduates, provenance
FROM j;

-- Degree mix: share of each degree level in total enrolment (gender total), per population basis.
--   all_reported         1393+ (province level 1393-98, 1401-02; 1399, 1400 national) and the national
--                        years before that which add up to Azad + non-Azad (1375 does not: status
--                        'population_mismatch', it equals the non-Azad figure)
--   azad_plus_excl_azad  <= 1392, Azad + non-Azad summed where both exist
--   azad / excl_azad     as printed
-- Azad's doctorate cells before 1393 bundle PhD and professional doctorate (they equal the Azad part of the
-- later split), so PhD alone is NULL for azad and azad_plus_excl_azad before 1393 and `doctoral`
-- (PhD + professional doctorate) is the comparable column. postgraduate = master + doctoral.
CREATE OR REPLACE VIEW v_he_degree_mix_trend AS
WITH p AS (
  SELECT year_sh, province_code, university_type,
         MAX(CASE WHEN degree_level = 'all' THEN students END) AS total,
         MAX(CASE WHEN degree_level = 'associate' THEN students END) AS associate,
         MAX(CASE WHEN degree_level = 'bachelor' THEN students END) AS bachelor,
         MAX(CASE WHEN degree_level = 'master' THEN students END) AS master,
         MAX(CASE WHEN degree_level = 'phd' THEN students END) AS phd,
         MAX(CASE WHEN degree_level = 'professional_doctorate' THEN students END) AS professional_doctorate,
         MIN(provenance) AS provenance
  FROM v_he_students
  WHERE field_group = 'all' AND university_type IN ('all_reported', 'azad', 'excl_azad')
  GROUP BY year_sh, province_code, university_type
),
d AS (
  SELECT p.*, CASE WHEN phd IS NOT NULL THEN phd + COALESCE(professional_doctorate, 0)
                   ELSE professional_doctorate END AS doctoral
  FROM p
),
comb AS (
  SELECT year_sh, province_code, 'azad_plus_excl_azad' AS university_type,
         SUM(total) AS total, SUM(associate) AS associate, SUM(bachelor) AS bachelor, SUM(master) AS master,
         CASE WHEN COUNT(phd) = 2 THEN SUM(phd) END AS phd,
         CASE WHEN COUNT(professional_doctorate) = 2 AND COUNT(phd) = 2 THEN SUM(professional_doctorate) END
           AS professional_doctorate,
         SUM(doctoral) AS doctoral, MIN(provenance) AS provenance
  FROM d WHERE university_type IN ('azad', 'excl_azad')
  GROUP BY year_sh, province_code HAVING COUNT(*) = 2 AND COUNT(total) = 2 AND COUNT(doctoral) = 2
),
u AS (
  SELECT year_sh, province_code, university_type, total, associate, bachelor, master, phd, professional_doctorate,
         doctoral, provenance FROM d
  UNION ALL
  SELECT year_sh, province_code, university_type, total, associate, bachelor, master, phd, professional_doctorate,
         doctoral, provenance FROM comb
),
x AS (
  SELECT u.*, cb.total AS combined_total
  FROM u LEFT JOIN comb cb ON cb.year_sh = u.year_sh AND cb.province_code = u.province_code
                          AND u.university_type = 'all_reported'
)
SELECT year_sh, province_code, university_type, total AS students, associate, bachelor, master, phd,
       professional_doctorate, doctoral,
       associate / NULLIF(total, 0) AS share_associate, bachelor / NULLIF(total, 0) AS share_bachelor,
       master / NULLIF(total, 0) AS share_master,
       CASE WHEN phd IS NOT NULL THEN phd / NULLIF(total, 0) END AS share_phd,
       doctoral / NULLIF(total, 0) AS share_doctoral,
       (master + doctoral) / NULLIF(total, 0) AS share_postgraduate,
       CASE WHEN total IS NULL OR master IS NULL OR doctoral IS NULL OR associate IS NULL OR bachelor IS NULL
              THEN 'degree_missing'
            WHEN (associate + bachelor + master + doctoral) / NULLIF(total, 0) NOT BETWEEN 0.97 AND 1.03
              THEN 'degree_sum_mismatch'
            WHEN university_type = 'all_reported' AND year_sh <= 1392 AND combined_total IS NOT NULL
                 AND ABS(total / combined_total - 1) > 0.02 THEN 'population_mismatch'
            WHEN university_type = 'all_reported' AND year_sh <= 1392 AND combined_total IS NULL
              THEN 'population_unverified'
            ELSE 'ok' END AS status,
       provenance
FROM x;

-- Academic staff by rank (full-time staff from 1393, see v_he_students_per_staff for the employment basis).
-- Ranks are printed for gender = total only. instructors = instructor (morabbi) + instructor assistant
-- (morabbi amoozeshyar); non_faculty is NOT counted as a faculty member (same convention as v_he_staff).
-- senior = professor + associate professor. status: 'rank_incomplete' (a rank missing),
-- 'rank_sum_mismatch' (faculty members differ from all-staff minus non-faculty by more than 2%), else 'ok'.
-- students_per_senior = all students (degree all) of the same population / senior faculty. For all_reported
-- before 1393 the students are only used when v_he_degree_mix_trend verifies that population (the national
-- 1375 and 1392 all_reported students do not add up to Azad + non-Azad); otherwise NULL.
CREATE OR REPLACE VIEW v_he_rank_mix AS
WITH r AS (
  SELECT year_sh, province_code, university_type, employment,
         MAX(CASE WHEN rank = 'professor' THEN value END) AS professors,
         MAX(CASE WHEN rank = 'associate_professor' THEN value END) AS associate_professors,
         MAX(CASE WHEN rank = 'assistant_professor' THEN value END) AS assistant_professors,
         MAX(CASE WHEN rank = 'instructor' THEN value END) AS instructors_main,
         MAX(CASE WHEN rank = 'instructor_assistant' THEN value END) AS instructor_assistants,
         MAX(CASE WHEN rank = 'non_faculty' THEN value END) AS non_faculty,
         MAX(CASE WHEN rank = 'all' THEN value END) AS academic_staff,
         MIN(source_file || ' :: ' || source_table) AS provenance
  FROM v_he_best
  WHERE metric = 'academic_staff' AND degree_level = 'all' AND field_group = 'all' AND gender = 'total'
    AND university_type IN ('all_reported', 'azad', 'excl_azad')
  GROUP BY year_sh, province_code, university_type, employment
),
c AS (
  SELECT r.*,
         COALESCE(instructors_main, 0) + COALESCE(instructor_assistants, 0) AS instructors,
         professors + associate_professors + assistant_professors
           + COALESCE(instructors_main, 0) + COALESCE(instructor_assistants, 0) AS faculty_members
  FROM r WHERE professors IS NOT NULL OR associate_professors IS NOT NULL OR assistant_professors IS NOT NULL
)
SELECT c.year_sh, c.province_code, c.university_type, c.employment,
       c.professors, c.associate_professors, c.assistant_professors, c.instructors, c.non_faculty,
       c.academic_staff, c.faculty_members,
       c.professors + c.associate_professors AS senior_faculty,
       (c.professors + c.associate_professors) / NULLIF(c.faculty_members, 0) AS senior_share,
       CASE WHEN s.students_ok = 1 THEN s.students END AS students,
       CASE WHEN s.students_ok = 1 THEN s.students / NULLIF(c.professors + c.associate_professors, 0) END
         AS students_per_senior,
       CASE WHEN s.students_ok = 1 THEN s.students / NULLIF(c.faculty_members, 0) END AS students_per_faculty_member,
       CASE WHEN c.professors IS NULL OR c.associate_professors IS NULL OR c.assistant_professors IS NULL
                 OR c.instructors_main IS NULL THEN 'rank_incomplete'
            WHEN c.academic_staff IS NOT NULL
                 AND c.faculty_members / NULLIF(c.academic_staff - COALESCE(c.non_faculty, 0), 0) NOT BETWEEN 0.98 AND 1.02
              THEN 'rank_sum_mismatch'
            ELSE 'ok' END AS status,
       c.provenance
FROM c
LEFT JOIN (SELECT st.*, CASE WHEN st.university_type = 'all_reported' AND st.year_sh <= 1392
                                  AND COALESCE(dm.status, 'x') <> 'ok' THEN 0 ELSE 1 END AS students_ok
           FROM v_he_students st
           LEFT JOIN v_he_degree_mix_trend dm ON dm.year_sh = st.year_sh AND dm.province_code = st.province_code
                                             AND dm.university_type = st.university_type
           WHERE st.degree_level = 'all' AND st.field_group = 'all') s
  ON s.year_sh = c.year_sh AND s.province_code = c.province_code AND s.university_type = c.university_type;
