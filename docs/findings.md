# Findings for the thesis (motivation chapter and beyond)

Computed 2026-09-27 from the views in `sql/views.sql` (DuckDB `data/out/edu.duckdb`; identical in
Postgres). Every number carries its provenance: `yearbook/file :: table-chapter` as printed in the
Statistical Centre of Iran yearbook. Years are **academic years by start year (SH)**:
1402 = 1402-03 = 2023-24.

Status: **measured** = read or computed from printed counts, arithmetic checks passed;
**(uncertain)** = depends on a definition change, a footnote reading, or an inference.

## 1. Core claim: fewer teachers per student in K-12

### Primary school: students per teacher rose from 27.2 (1394) to 38.0 (1399), 33.7 in 1402

| year | students | teachers | students/teacher | provenance |
|---|---|---|---|---|
| 1390 | 5,701,521 | 235,193 | 24.2 | 1390/salname_keshvar_1390/15.docx :: 10-15 (teacher = «کارکنان آموزشی», proxy) |
| 1394 | 7,422,505 | 273,005 | 27.2 | 1394/1394_w/17-آموزش.docx :: 10-17 |
| 1398 | 8,293,617 | 229,226 | 36.2 | 1398/salname_keshvar_1398/فصل 17- آموزش.docx :: 10-17 |
| 1399 | 8,443,528 | 222,318 | 38.0 | 1399/1399.pdf :: 10-17 |
| 1402 | 9,209,724 | 273,604 | 33.7 | 1402/salname-kole-keshvar-1402/17. آموزش.pdf :: 10-17 |

* 1394 -> 1399 (same «معلم» definition): primary enrolment **+13.8 %**, primary teachers
  **-18.6 %** (273,005 -> 222,318); the ratio rose **+40 %**. *measured*
* The rebound in 1400 (+18 % teachers) looks like a hiring wave (e.g. Farhangian graduates).
  Interpretation only. *(uncertain)*
* Students per **class** stayed near 23-24 (22.0 in 1390, 23.6 in 1398, 24.2 in 1402): the
  pressure is on teachers, not classrooms. *measured*

### Lower secondary rose too; upper secondary stayed low

| level (students per teacher) | 1390 | 1394 | 1398 | 1402 |
|---|---|---|---|---|
| lower secondary (راهنمایی -> متوسطه اول) | 19.5 | 21.4 | 26.4 | 29.8 |
| upper secondary (متوسطه -> متوسطه دوم) | 15.6 | 14.5 | 17.8 | 19.4 |

The 1391-1393 reform (5-3-4 -> 6-3-3) moves whole grades between levels: compare levels within
one system only (up to 1390, or from 1394). Tables 11-* and 12-* of each yearbook.
**Core three levels combined** (`v_k12_core_students_per_teacher`): 20.1 (1390) -> 22.3 (1394)
-> 28.2 (1398) -> 29.5 (1399) -> 28.8 (1402). *measured*

**Definition break:** before 1394 the yearbooks report «کارکنان آموزشی» (educational staff:
teachers plus principals/assistants); from 1394 «معلم» and «مدیریت و کیفیت بخشی». The 1398
yearbook prints the 1380 value (309,260) under «معلم», the same number the 1386 yearbook printed
as «آموزشی», so SCI itself treats them as one series. We follow SCI and flag `teacher_definition`
on every row. Ratios before 1394 are probably slightly low. *(uncertain)*

### Province inequality (primary)

* 1402 highest: Tehran 46.9, Isfahan 44.0, Razavi Khorasan 43.7, Alborz 43.2, Qom 42.5.
  Lowest: Ilam 20.2, Kohgiluyeh and Boyer-Ahmad 20.7, Kermanshah 23.9, Lorestan 25.1,
  Kurdistan 25.2 (1402 PDF :: 10-17). *measured*
* Coefficient of variation across provinces: ~0.19 (1380-1390) -> 0.25 (1395-1396) -> 0.22
  (1402); the maximum province ratio went from 34.3 (1390) to 52.2 (1399).
  (`v_k12_province_inequality`) *measured*

## 2. Higher education: the ratio improved because enrolment fell

Students per full-time academic staff member, all institutions **including Islamic Azad
University** (definition used from the 1393 yearbook on), national (`v_he_students_per_staff`;
tables 21-* staff, 26-*/28-* students):

| year | students | full-time academic staff | students/staff | faculty members |
|---|---|---|---|---|
| 1393 | 4,802,721 | 77,924 | 61.6 | 76,129 |
| 1395 | 4,073,827 | 81,683 | 49.9 | 80,313 |
| 1398 | 3,182,989 | 88,255 | 36.1 | 87,275 |
| 1399 | 3,070,748 | 78,408 | 39.2 | 77,663 |
| 1402 | 3,351,877 | 78,841 | 42.5 | 78,518 |

* Enrolment **fell 36 %** from the 1393 peak (4.80 M) to 1399 (3.07 M) while staff grew 13 % to
  1398, so the ratio improved from 61.6 to 36.1. Since 1398 staff fell 10.7 % and the ratio is
  rising again (42.5 in 1402). *measured*
* 1399 values come from the 1400-1402 yearbooks (the 1399 PDF tables failed validation); the 1402
  yearbook notes Azad did not report academic staff for 1398-99. *(uncertain)*
* **Before 1393 the series is not comparable**: those yearbooks print non-Azad institutions
  («به استثنای دانشگاه آزاد اسلامی») with full-time *and* part-time staff, plus Azad in separate
  tables. Non-Azad: 13.8 students per staff member (1380) -> 16.4 (1392), but 21.5 -> 60.6 per
  *faculty member* (1380/1380.doc :: 30-15; 1392/1392_w/16-آموزش.docx :: 30-16). Azad alone:
  33.2 (1380) -> 17.6 (1392) (tables 32/33-15, 39-15). *measured; definitions differ*
* Rank mix (full-time, national, table 22-*): professors 5.2 % (1393) -> 10.1 % (1402) of academic
  staff; instructors («مربی») 28,344 -> 11,745; women 24.4 % -> 31.2 % of academic staff. *measured*

### Degree levels (each kept separate; never mixed with K-12)

| degree | 1393 | 1398 | 1402 | female share 1402 |
|---|---|---|---|---|
| associate (کاردانی) | 1,096,028 | 436,348 | 451,562 | 38.2 % |
| bachelor (کارشناسی) | 2,819,662 | 1,990,478 | 2,150,710 | 54.0 % |
| master (کارشناسی ارشد) | 720,806 | 513,342 | 498,861 | 49.7 % |
| professional doctorate (دکترای حرفه‌ای) | 71,914 | 95,412 | 104,517 | 48.1 % |
| PhD (دکترای تخصصی) | 94,311 | 147,409 | 146,227 | 46.5 % |

* PhD enrolment grew ~18x from 8,544 (1375) to its peak 152,006 (1397), then flat. Supervision
  capacity is the sharper shortage indicator; faculty are **not** reported by degree level taught,
  so a per-degree student/faculty ratio is **not available** from these tables. *measured*
* Women: 45.8 % of students (1393) -> 50.7 % (1402). *measured*

### University types (1402, table 27-17)

Azad 38.9 %, MSRT public 19.7 %, Payame Noor 10.4 % (15.6 % in 1394), private non-profit 7.7 %,
applied-science UAST 7.5 % (11.2 % in 1394), medical MoHME 6.4 %, technical-vocational university
5.9 %, Farhangian (teacher training) 2.9 % (1.6 % in 1394). After 1392 faculty are not split by
university type, so students-per-faculty by type exists only for 1380-1392 (Azad vs the rest).

### Flows

New entrants 1.18 M (1393) -> 0.82 M (1397) -> 1.09 M (1402); graduates 0.86 M (1393) -> 0.50 M
(1401); women's share of new entrants 43.5 % -> 49.7 % (tables 23-*, 29-*). *measured*

## 3. Other analyses the data support

1. Province panel of teacher shortage (31 provinces x 23 years, 1380-1402).
2. Gender: girls ~48.6 % of primary pupils (stable); women now the majority of HE students and
   31 % of academic staff; rank-by-gender tables exist (22-*).
3. University-type restructuring: decline of Payame Noor and UAST, growth of Farhangian (the K-12
   teacher pipeline, a direct thesis link).
4. Transition/dropout proxies: grade-passing (17-*), upper-secondary graduates by stream and
   province (18-*), HE new entrants vs diploma graduates.
5. Long national series 1365-1402 via the historic rows the yearbooks reprint.

## 4. Not yet reliable

* Province HE ratios for 1399, 1400, 1402: PDF tables failed the province-shift check; excluded.
* Yearbooks 1345-1369: extracted, not verified; excluded from the views.
* 1370-1379 province data: not parsed (plain-text HTML, legacy-font PDFs).
* Province HE ratios mislead where students study at Azad/Payame Noor branches staffed from
  elsewhere (e.g. Mazandaran, Gilan): read with university-type shares.
