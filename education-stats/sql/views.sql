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
