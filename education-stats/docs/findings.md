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

## 5. Outcomes next to the resource ratios (2026-10-01)

Views `v_k12_pass_rate`, `v_k12_class_size`, `v_k12_completion`, `v_he_graduation_ratio`; exports
`outcomes.json`, `relations.json`; analysis and plain-language reading in `analysis/README.md`.
**Association only; no causal claim.**

* **Pass rate** (promoted / enrolled, regular programme, adults excluded from both): national primary
  0.955 (1380) -> 0.965 (1385) -> 0.980 (1390) -> 0.969 (1394) -> 0.990 (1398) -> 0.926 (1399, COVID) -> 0.976
  (1401); lower secondary 0.876 (1380) -> 0.967 (1390) -> 0.945 (1394) -> 0.955 (1401). Province sums equal
  the national rows. *measured*
* **Usable years.** Province pass rates (27-31 units): 1380-85, 1389-90, 1392-99, 1401 (primary also 1391
  minus one row; 1385 primary minus one row; lower secondary 1391 withheld). Withheld: 1386 and 1387 (source
  columns misaligned, rates of 0.07 to 6.2), 1391 lower secondary (4 provinces > 1, reform year). Not
  available at province level: 1388 and 1400 (national only), 1370-1379. Completion proxy: provinces 1390,
  1392-95, 1397, 1399 (1396 prints 53,544 national graduates, withheld). HE graduation ratio: provinces
  1380-84, 1387, 1390-97, 1401. *measured*
* **Source defect found and repaired:** the 1399 PDF table 17-17#1 is the 1398 table (province rows sum to the
  national 1398 value, 8,213,495 primary passes) but was labelled 1399 and masked the 1399 values printed
  in the 1400 yearbook. Relabelled in `v_k12_passed_best`; this adds 1398 province pass rates. *measured*
* **Cross-province correlation of students per teacher with pass rate** (years with >= 25 provinces):
  1380-85 clearly negative (primary r -0.29 to -0.65, lower secondary -0.24 to -0.62), 1392+ near zero or
  mildly negative (1401: -0.13 primary, -0.20 lower secondary), sign flip in 1390. Class size: no consistent
  relation. *measured; ecological*
* **Within-province (province + year fixed effects, SE clustered by province):** pass rate falls by 0.13 pp
  (primary, SE 0.04) and 0.17 pp (lower secondary, SE 0.06) per +1 student per teacher over 1380-1401, but
  from 1394 on only: -0.03 pp (SE 0.045) and +0.04 pp (SE 0.10), not distinguishable from zero. So there is
  no reliable evidence in the post-1394 data that the rise in students per teacher went with lower pass
  rates, and the pooled estimate is dominated by the proxy/catch-up period. *(uncertain; association)*
* **Doubtful:** primary pass rates are near-ceiling (descriptive evaluation); pass rate is promotion, not
  learning; completion and HE graduation ratios are throughput proxies (three/four-year cohorts, shrinking and
  growing intakes, series break at 1393) and are not completion rates; HE ratios 1385-86, 1388-89 fail
  plausibility and are withheld.

## 6. TIMSS 2023 microdata: class size vs achievement (2026-10-01)

Reproduce: `uv run --group analysis python analysis/timss2023_class_size.py` (reads the public-use TIMSS 2023
Iran files from `$TIMSS_IRAN_DIR`, default `/Volumes/MigMig/Personal/Research/Iran Achievement Data/`; the
microdata is not in the repo). Writes `analysis/figures/timss2023_class_size_*.png` and
`exports/site/timss_class_size.json`; test `tests/test_timss_class_size.py`.

**Question:** do Iranian students in larger classes score lower in maths and science? **Association only.**

### What is measured
* **Class size:** teacher-reported "number of students in the class": `ATBG10A` (grade 4, teacher file ATG;
  999 = omitted, dropped) and `BTBG10` (grade 8; `BTM` file for maths, `BTS` for science). Linked to students
  through the student-teacher link files AST/BST (`IDTEACH`, `IDLINK`).
* **Score:** TIMSS scale scores, 5 plausible values (`ASMMAT01-05`, `ASSSCI01-05`, `BSMMAT01-05`, `BSSSCI01-05`),
  combined with Rubin's rules. **Weight:** `MATWGT` / `SCIWGT` (teacher-linked analyses, User Guide).
  **SE:** jackknife repeated replication with `JKZONE`/`JKREP`; the Iran files have 112 zones (not 75), so all
  zones are used (the Technical Report chapter 13 is not in the downloaded material, so the 2x/0x JRR2 convention
  is the standard IDB Analyzer variant, applied by us, not checked against the Analyzer).
* **Controls:** home resources (`ASBGHRL` G4 / `BSBGHER` G8 scale), gender (`ITSEX`), school location
  (`ACBG05B`/`BCBG05B`, 5 categories), principal-reported emphasis on academic success (`ACBGEAS`/`BCBGEAS`),
  instruction affected by resource shortage (`ACBGMRS`|`ACBGSRS` / `BCBGMRS`|`BCBGSRS`), school SES composition
  (`ACDGSBC`/`BCDGSBC`). Omitted codes (999999 in home resources, 9 in location) set to missing.
* **Students per teacher: not derivable.** The Iran school/teacher files carry no school enrolment or teacher count.
* About 214-221 classes (and as many schools) per grade, 5.9-6.2 thousand students.

### Results (mean score, SE in brackets)

| Grade / subject | <=20 | 21-25 | 26-30 | 31-35 | >35 |
|---|---|---|---|---|---|
| G4 maths | 410 (10) | 441 (11) | 429 (8) | 414 (7) | 410 (10) |
| G4 science | 417 (11) | 454 (12) | 443 (8) | 427 (9) | 422 (11) |
| G8 maths | 405 (8) | 426 (14) | 438 (8) | 427 (7) | 414 (7) |
| G8 science | 391 (12) | 418 (12) | 430 (9) | 422 (6) | 423 (8) |

| Slope, points per +5 students (SE) | n students (all / complete controls) | no controls | no controls, controls sample | with controls |
|---|---|---|---|---|
| G4 math | 5855 / 5372 | -2.3 (2.5) | -1.8 (2.5) | -2.8 (2.9) |
| G4 science | 5855 / 5372 | -1.8 (2.7) | -1.4 (2.6) | -2.8 (3.1) |
| G8 math | 6158 / 5935 | +0.7 (1.5) | +0.5 (1.5) | -0.2 (1.5) |
| G8 science | 6091 / 5896 | +2.2 (3.0) | +2.1 (3.0) | +1.0 (2.0) |

### In plain language
1. **There is no detectable penalty from larger classes.** The regression slopes are small and all within
   about one standard error of zero (G4: -2 points per +5 students, SE 2.5-3; G8: between -0.2 and +2). *measured*
2. **The band means are not monotonic.** The smallest classes (<=20) have the *lowest* or near-lowest scores in
   grades 4 and 8; the best scores are in 21-25 (G4) and 26-30 (G8) students. In G4 means then fall by roughly
   20 points from 21-25 to >35 (maths 441 -> 410), but with SEs of 7-11 per band this is borderline. *measured; weak*
3. **Controls change little.** Adding home resources, gender, location, school emphasis, resource shortage and
   school SES moves the slopes by roughly one point (G4 maths -1.8 -> -2.8; G8 maths +0.5 -> -0.2); none become
   significant. The change is not a clean "shrinkage" because the unadjusted slopes are already near zero. *measured*
4. **Larger classes are urban:** the weighted share of students in urban/suburban schools rises from 19% (<=20)
   to 73% (>35) in grade 4 and 40% to 70% in grade 8 (`share_urban_or_suburban` in the JSON); small classes are
   mostly rural and low-scoring. This is the selection that makes the raw band pattern hard to read. *measured*

### Caveats
* Association, not effect: no variable assigns class size independently of school type, place or enrolment.
* Class size is one teacher-reported number per teacher; reporting error and rounding (30, 35) are likely.
* Effective sample is about 220 classes per grade, so the SEs are large; "no effect" is not shown, only that
  effects larger than roughly 5-6 points per +5 students are unlikely at 95%. *(inferred from the SEs)*
* TIMSS is nationally representative, not province-representative; no province identifier exists.
* Controls may be partly on the causal path (rich urban schools have larger classes); adjusting for them is not
  guaranteed to remove bias.
* Class size here is the grade-4 class or the grade-8 maths/science class, not the school-level pupil-teacher ratio
  in the yearbook; the two are not interchangeable.

## 6. Drop-out / out-of-school: no direct measure; apparent cohort survival instead (2026-10-01)

**Search (proven).** Every table title (3.3k tables) and every row/column label (405k cells) was searched,
after unifying Arabic/Persian letters, for «ترک تحصیل», «بازمانده(گان)», «بازمانده از تحصیل», «پوشش تحصیلی»,
«نرخ پوشش», «لازم‌التعلیم», «جمعیت لازم‌التعلیم», «مردود(ی)», «تکرار (پایه)», «افت تحصیلی», «نرخ ثبت‌نام (خالص/ناخالص)».
Result: **no K-12 table gives drop-out, out-of-school children, enrolment/coverage rates, repeaters or a
school-age population.** The only hits are not school measures: «پوشش» = villages/learners covered by the
literacy movement (نهضت سوادآموزی, 1363-1369 and 1380+ adult-literacy tables); «لازم‌التعلیم» = compulsory-age
learners in literacy-movement classes (1366-1369, 24 provinces, yearbooks outside the verified range, a count
of children *served by literacy classes*, not of children out of school); 1361 table 38 = planning *targets*
for «درصد پوشش آموزشی»; census literacy tables (rate of literate 6+, census years only, not attendance).
`tests/test_export_site.py::test_no_direct_dropout_table_in_the_database` pins this. Grade-level counts do
not exist either (tables give totals per level, except the upper-secondary first-grade column from 1392 and
graduates in 8 years), so the suggested "first grade of lower secondary in t+1 / final primary grade in t"
cannot be computed.

**Derived measure: apparent cohort survival, lower -> upper secondary** (`v_k12_cohort_survival`, exported as
`outcomes.json -> data[t][prov].cohort_survival[gender]`):

    survival(t) = upper-secondary students in year t+3 / lower-secondary students in year t

regular programme, same province and gender, `year_sh` = t. The lower-secondary stock of year t is three
cohorts (grades 7-9 / old 6-8); three years later those cohorts are in upper-secondary grades 10-12 / 9-11, so
the stocks cover the same pupils and no cohort-size correction is needed (a ratio like "first-grade intake /
passes" would need one). It is arithmetic on printed counts (*measured*); what it *means* is inferred (below).

* **Coverage.** Provinces (31, gender male/female/total): t = 1394-1399 (survivors counted 1397-1402).
  National: t = 1377-1387 (sparse upper-secondary years; old 5-3-4 system) and 1394-1399. Province
  upper-secondary data exist only from 1390, so no province value before t = 1387.
* **Withheld, with status.** t = 1388-1393 (`reform_window`): the window touches the 1391-93 reform; the
  national ratio there is 0.99-1.09 against 0.83-0.88 on both sides, i.e. the two stocks do not cover the same
  grades. t = 1387 provinces (`year_unreliable`, 30 of 32 rows implausible or misaligned in the source; the
  national row stays). `boundary_change` (Tehran/Alborz around 1390, Khorasan around 1383) is coded but no
  published window crosses either split. Single ratios > 1.05 or < 0.5 are never published.
* **National trend (total).** Old system 0.753 (1377) -> 0.762 (1380) -> 0.847 (1384) -> 0.819 (1386) ->
  0.850 (1387); new system 0.865 (1394) -> 0.869 (1397) -> 0.848 (1398) -> 0.835 (1399). The old and new
  levels are *not* strictly comparable (different grades/definitions, 4-year technical tracks in the old
  upper secondary). Within 1394-1399 the fall since 1397 is entirely male: male 0.858 (1394) -> 0.848 (1397) ->
  0.799 (1399); female 0.873 -> 0.891 -> 0.874. In 1399 the median province gap (female minus male) is 7.4
  pp (was 0.3 pp in 1394); lowest male values 1399: Sistan and Baluchestan 0.669, West Azerbaijan 0.714,
  North Khorasan 0.732. Lowest total 1399: Sistan and Baluchestan 0.693; highest: Ilam 0.922. *measured*
* **Association with students per teacher (t = 1394-1399, 31 provinces, total gender).** Cross-province
  Pearson r with lower-secondary students per teacher in t: +0.07, +0.05, -0.06, -0.16, -0.16, -0.20 (1394 ->
  1399); with upper-secondary students per teacher in t+3: -0.11 ... -0.17 in every year. Province + year
  fixed effects, SE clustered by province: -0.19 pp of survival per +1 lower-secondary student/teacher at t
  (SE 0.13, p = 0.14, n = 186) and +0.26 pp per +1 upper-secondary student/teacher at t+3 (SE 0.18, p = 0.17).
  Dropping t = 1399: -0.16 pp (p = 0.38) and +0.22 pp (p = 0.21). **Neither is distinguishable from zero and
  the two have opposite signs: no evidence of an association; association only, never an effect.**
  *(uncertain)*
* **What is doubtful.** (1) It is a stock ratio, not a tracking: repeaters, re-entrants and anyone entering the
  upper secondary from outside the regular lower-secondary stock inflate it; dropout, death, **migration
  between provinces** (large for Tehran, Alborz, Khorasan) and **moves to adult/evening/non-formal schools**
  (excluded here, programme = regular) deflate it. (2) Private/non-profit schools are inside the stock
  (sector = all) but home-schooling and unregistered pupils are not in any yearbook count. (3) Definition
  changes: reform 1391-93 (withheld), a 4th upper-secondary grade in old technical tracks, adult exclusions
  reworded between yearbooks. (4) The window 1396-1400 contains COVID years (flag
  `cohort_survival_pandemic_window`); the 1399 fall cannot be split into pandemic, dropout and migration.
  (5) Only 6 province-years per province, so fixed effects are weakly identified.

## 7. Higher education: cohort completion, faculty rank mix, degree mix (2026-10-01)

Views `v_he_cohort_completion`, `v_he_rank_mix`, `v_he_degree_mix_trend` (sql/views.sql); export `he_quality.json`
(`he.json` is unchanged); association in `relations.json -> he_completion_vs_students_per_staff`. Tests:
`tests/test_export_site.py::test_he_quality_*`, `test_he_completion_relations`.

### Cohort completion ratio = graduates in t / new entrants in t-d
* **Measured:** the two printed counts. **Inferred:** d. The yearbooks print no programme length; d is the regulated
  nominal length (associate 2, bachelor 4, master 2, PhD 4, professional doctorate 6), each also shown with d+1
  (`plus_1`; PhD 5 and professional doctorate 7 cover the 4-5 / 6-7 ranges). Not verified against the data (5 usable
  years are too few to estimate a lag).
* **Coverage.** Basis `all_reported` (incl. Azad, Payame Noor, UAST) needs entry year >= 1393 as well, because
  before 1393 the yearbooks print entrants by degree for the non-Azad set only (one 1385 table) and the national
  `all_reported` cells of 1375-1392 do not match Azad + non-Azad (graduates 1385 bachelor 2.49 M). Hence national
  t = 1395-1401 (associate, master), 1397-1401 (bachelor, PhD), 1399-1401 (professional doctorate). Provinces: only
  t = 1397, 1400, 1401 (entrants have province tables 1393-98; graduates 1392-97 and 1399-1401; **1398 has none,
  1399 fails the province-sum check**: province sums 3-1500 % of the national row, so every province is withheld,
  `province_sum_mismatch`). Gender exists for all three publishable years; ratios outside 0.2-1.3 are withheld
  (`implausible_rate`; a handful of tiny-province PhD / professional-doctorate cells).
  Before 1393: degree level `all` only (`azad_plus_excl_azad`, d = 4 by convention, mixes 2- and 6-year
  programmes, national 1374-1388, provinces 1384-1388; 1387 is withheld nationally because the non-Azad graduate
  cell 567,415 is not credible). Treat as a continuity series, not a rate.
* **National, nominal d (total):** bachelor 0.587 (1397) -> 0.667 (1398) -> 0.607 -> 0.585 -> 0.577 (1401); associate 0.548 (1395) ... 0.830 (1399, entrants collapsed to 105 k in 1397) -> 0.558
  (1401); master 0.639 (1395) ... 0.763 (1398), 0.495 (1399), 0.447 (1401); PhD 0.483 (1397) -> 0.670 -> 0.401 ->
  0.595 -> 0.523 (1401); professional doctorate 0.890 (1399) -> 0.795 -> 0.859 (1401); all degrees (d = 4) 0.541
  (1397) -> 0.485 (1399) -> 0.606 (1401). Bachelor 1401 by province: 0.50 (Tehran) to 0.81 (South Khorasan).
* **Not a completion rate.** Stock-flow mismatch (two different groups of people); programmes shorter or longer
  than d (the `plus_1` bachelor ratio is 0.54 in 1401 against 0.58); transfers between degree levels and
  institutions, associate -> bachelor continuation (entrants include them), guest students, dropouts and late
  finishers, Azad's shrinking intake (master entrants 254 k in 1395 -> 184 k in 1396, which makes 1398 look high
  and 1399 low), and COVID (`completion_pandemic_window`, any window touching 1399-1400). Province: students
  graduate in another province than they entered (Azad / Payame Noor branches).
* **Association with students per academic staff member (bachelor, all_reported, provinces, total):** cross-
  province Pearson r with staff ratio *at entry year*: -0.47 (t = 1397), -0.25 (1400), -0.21 (1401); with the
  graduation-year ratio: -0.07 (1397), +0.12 (1401). Province + year FE (3 years x 31, SE clustered by province),
  exposure at entry year: -0.42 pp completion per +1 student per staff (SE 0.17, p = 0.019); degree `all`: -0.34
  pp (p = 0.011). The graduation-year exposure has fewer than three usable years, so no FE estimate is published.
  **Association only, weakly identified (3 years, one slow-moving regressor, composition effects of Azad / Payame
  Noor, entry-year ratios fall everywhere); do not read as an effect.** *(uncertain)*

### Faculty rank mix (`v_he_rank_mix`)
* Ranks are printed for gender total only (no gender, no degree, no university-type split after 1392). Province
  level: all_reported 1393-1398 (full-time staff); azad and excl_azad 1380-1392 (excl_azad includes hourly staff, so
  pre-1393 shares are **not** comparable with 1393+). No rank table exists for 1399-1402. No `term_map` change was
  needed: no academic-staff cell of 1380+ is unmapped. Instructors = morabbi + morabbi amoozeshyar; non-faculty
  staff is left out of the faculty denominator. Rows whose ranks do not add up to all-staff minus non-faculty
  (2 %) are withheld (4 Azad provinces 1387; Azad 1375).
* **National senior share (professor + associate) of faculty members:** 17.0 % (1393) -> 18.0 -> 20.1 -> 21.8 ->
  22.4 -> 23.7 % (1398); professors 4,018 -> 6,856, instructors 28.9 k -> 22.2 k. Students per senior faculty member
  370 (1393) -> 154 (1398) (students fell 4.80 M -> 3.18 M while seniors rose 12,967 -> 20,711). Province 1398: senior
  share 5.8 % (South Khorasan) to 31.7 % (Tehran); students per senior 493 (South Khorasan) to 103 (Tehran).
  Azad (separate table, pre-1393): senior share 3-6 %, 700-1,000 students per senior. *measured*; the Azad
  count is unspecified full/part-time, so it is not comparable with full-time government figures.

### Degree mix (`v_he_degree_mix_trend`)
* All-reported national: master share 3.9 % (1380) -> 7.1 % (1389) -> 15.0 % (1393) -> 18.8 % (1395) -> 14.9 % (1402);
  PhD share 0.84 % (1385) -> 1.96 % (1393) -> 4.83 % (1399) -> 4.36 % (1402); master + doctoral ("postgraduate") 6.4 %
  (1385) -> 18.5 % (1393) -> 25.0 % (1397) -> 22.4 % (1402); bachelor 70 % (1380) -> 59 % (1393) -> 64 % (1402);
  associate 26 % (1385) -> 12.6 % (1401). Province 1397: master share 9.8 % (South Khorasan) to 24.1 % (Tehran).
* The rise is a share of a shrinking base after 1393 (total enrolment 4.80 M -> 3.37 M in 1399 -> 3.35 M in 1402);
  headcount of master students peaked in 1394 (775 k) and fell to 499 k in 1402, PhD headcount ~150 k since 1397.
* Before 1393 Azad's doctorate cell bundles PhD and professional doctorate, so `share_phd` is null for `azad` and
  `azad_plus_excl_azad`; `share_doctoral` (PhD + professional) is the comparable column. All-reported 1375 and 1392
  national cells do not match Azad + non-Azad (`population_mismatch`) and are withheld; the combined basis fills
  1375-1392. Non-Azad totals jump in 1386 and 1388 (definition changes, UAST footnotes), which moves pre-1393 shares.
  Province degree tables exist for all_reported 1393-1398 and 1401-1402 only.
