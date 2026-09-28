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
