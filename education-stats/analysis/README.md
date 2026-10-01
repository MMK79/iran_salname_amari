# Resource ratios vs outcomes (students per teacher / per class vs pass rate)

Reproduce: `uv sync --all-groups && uv run python analysis/ratio_vs_outcomes.py` (writes
`analysis/figures/*.png`, prints the numbers below; console output saved in
`analysis/ratio_vs_outcomes.out.txt`). The same estimates are in `exports/site/relations.json`
(`make export-site`). Computed 2026-10-01 from `data/out/edu.duckdb`.

**Everything here is association, not effect.** Nothing in this dataset can say that more teachers
*cause* better results.

## What is measured (from printed counts)

* **Pass rate** = pupils promoted at the end of the year (قبول شدگان, table 17-17 / 24-15) divided by
  pupils enrolled (`students`), same level, gender, province, year; regular programme, adults excluded
  from both (footnote 1). `v_k12_pass_rate`. Levels: primary, lower secondary. National rates are 0.84-0.99;
  province sums equal the national row (checked, every year with province data).
* **Students per teacher** (`v_k12_students_per_teacher`; educational staff before 1394, see findings) and
  **students per class** (`v_k12_class_size`).
* Also exported (outcomes.json) but too sparse for the regressions: upper-secondary graduates / students
  (a throughput **proxy**, years 1390, 1392-95, 1397, 1399 at province level; 1396 prints a broken value and
  is withheld) and higher-education graduates / students (a throughput **proxy**, all degrees; usable at
  province level 1380-84, 1387, 1390-97, 1401; 1385-86, 1388-89 fail the 0.05-0.6 plausibility rule).

## Findings in plain language

1. **Nationally, pass rates did not fall while students per teacher rose.** Primary students per teacher went
   from 21.8 (1385) to 27.2 (1394) to 38.0 (1399) and 33.7 (1401); the primary pass rate went 0.965 -> 0.969
   -> 0.926 (1399, COVID) -> 0.976. Lower-secondary pass rate rose strongly from 0.876 (1380) to 0.967 (1390)
   and has been 0.94-0.97 since. Class size is nearly flat from 1385 (21-26). Figure `a_national_trends.png`.
2. **Across provinces, a weak negative association in recent years.** In the latest year (1401, 31
   provinces) the correlation between students per teacher and pass rate is r = -0.13 (primary) and
   r = -0.20 (lower secondary); slopes -0.03 and -0.06 percentage points per extra student per teacher
   (`b_scatter_latest_year.png`). The two lowest pass rates are Sistan and Baluchestan (mid-range ratio) and,
   in lower secondary, West Azerbaijan, so the pattern is driven by a few provinces, not by ratio.
3. **The cross-province correlation is not stable.** For 1380-85 it is clearly negative (primary mean r =
   -0.47, lower secondary -0.46, up to -0.65), for 1392+ near zero or mildly negative (-0.09 / -0.17), and
   it flips sign in 1390 (lower secondary r = +0.41). Swings between neighbouring years suggest
   year-specific data problems or composition effects, not a stable relation (`c_correlation_by_year.png`). Class size
   shows no consistent relation (|r| < 0.2 in 16 of 18 primary and 12 of 17 lower-secondary years; the exceptions 1389, 1390, 1399, 1401 flip sign).
4. **Within provinces over time (province + year fixed effects, cluster-robust SE by province):**
   primary -0.13 pp of pass rate per +1 student/teacher (SE 0.04, p = 0.002, 540 province-years, 1380-1401);
   lower secondary -0.17 pp (SE 0.06, p = 0.011). Dropping the 1391-93 reform years changes nothing
   (-0.12 / -0.17). **But from 1394 on only** (one school system, same teacher definition, 7 years): -0.03 pp
   (SE 0.045, p = 0.47) and +0.04 pp (SE 0.10, p = 0.66), i.e. no detectable association. The pooled
   negative estimate therefore comes mostly from 1380-1390, where the teacher count is the "educational
   staff" proxy and province pass rates were still catching up. We do not claim an effect.
   (Hand-rolled CR1 estimator reproduces statsmodels exactly; test in `tests/test_export_site.py`.)

## Caveats (what limits every number above)

* **Primary is a weak outcome.** Primary evaluation has been descriptive since the 1380s; the pass rate is
  0.93-0.99 nationally; the province standard deviation is about 2 pp (mean 2.2 pp, driven by a few low
  provinces). Differences of a few tenths of a point are within noise of the definitions. Lower secondary
  moved much more over time (0.84 -> 0.97) and is the more informative level.
* **Ecological correlation.** Province aggregates; they do not say anything about individual pupils or schools.
* **Confounders not in the data:** urbanisation, household income, the share of deprived areas, school
  type (public/non-profit), teacher qualificationand distance/language in remote provinces. Provinces with many students per teacher (Tehran, Alborz, Isfahan, Razavi Khorasan)
  are the richer, urban ones (inference, not measured here).
* **Pass rate is promotion, not learning.** Policy (automatic promotion), exam rules and enforcement change
  it independent of teaching quality.
* **Definition changes:** teacher = educational staff before 1394; 5-3-4 -> 6-3-3 reform 1391-93 moves grades
  between levels (flagged, 1391 lower-secondary province set withheld); 1399 is a COVID year; Alborz splits
  from Tehran in 1390 and Khorasan splits in 1383 (KHO is one unit in 1380-82).
* **Data repairs.** (a) The 1399 yearbook PDF table 17-17#1 is the **1398** table (province rows sum to the
  national 1398 value); the parser labelled it 1399 and it overrode the right 1399 values. It is relabelled in
  `v_k12_passed_best`; 1398 province pass rates exist only because of this repair. (b) 1386 and 1387 province
  rows contain values far outside 0..1 (misaligned columns): withheld, as are single rows with rates > 1
  or < 0.5. (c) No province pass counts for 1388 and 1400 (national only), so those years have no correlation.
* **Missing years:** no cross-province correlation for 1386-88, 1391 (lower secondary), 1400, 1402; years with
  fewer than 25 provinces are never reported.
* **Multiple comparisons:** 12 fixed-effect estimates are listed; only the four pooled 1380-1401 students-per-teacher
  ones (two levels x two specs) are significant at 5 %, and they do not survive the 1394+ restriction.

## Proven vs inferred

* Proven (arithmetic on printed counts, checks in the tests): the pass and ratio values, the 1398/1399 repair,
  province sums = national rows, estimator = statsmodels.
* Inferred: that early-period negative association reflects the proxy/catch-up period rather than a causal
  link; the explanation for the 1390 sign flip (not investigated).

## TIMSS 2023 microdata: class size vs achievement (2026-10-01)

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

## Drop-out / progression: apparent cohort survival (2026-10-01)

No yearbook table gives drop-out, out-of-school or coverage-rate data (search in docs/findings.md section 6), so the
outcome is derived: **cohort survival = upper-secondary students in t+3 / lower-secondary students in t**
(regular programme, province x gender; `v_k12_cohort_survival`). The same three cohorts are counted twice, so it
needs no cohort-size correction; it is *not* a drop-out rate (repeaters, migration between provinces and moves to
adult programmes enter it). Publishable: provinces t = 1394-1399 (6 years x 31), national also 1377-1387 (old
system); t = 1388-1393 (reform windows) and 1387 provinces are withheld with a status. National: 0.865 (1394) ->
0.869 (1397) -> 0.835 (1399), male 0.858 -> 0.799, female 0.873 -> 0.874.

Against students per teacher (`relations.json -> cohort_survival_*`, same estimator as the pass-rate relation,
`_cluster_fe`): cross-province r by year is within -0.20..+0.07 for lower-secondary students/teacher at t and
-0.11..-0.17 for upper-secondary at t+3; province + year FE: -0.19 pp (SE 0.13) and +0.26 pp (SE 0.18) per extra
student/teacher, both p > 0.1 and of opposite sign. **No detectable association; association only.** Reproduce:
`uv run python -m etl.run views && uv run python scripts/export_site.py`; checks in `tests/test_export_site.py`
(`test_cohort_survival_*`).


## Higher education: cohort completion, rank mix, degree mix (2026-10-01)

Full account with numbers: docs/findings.md section 7. **Measured** = printed counts; **inferred** = nominal programme
length d (regulation, not in the yearbooks) and every reading of a ratio as "completion".

* `completion_ratio` = graduates in t / entrants in t-d, by degree, gender, province, all_reported basis (entry year
  >= 1393, i.e. national t = 1395-1401, provinces t = 1397, 1400, 1401). Before 1393 only a mixed all-degree series
  (Azad + non-Azad, d = 4 by convention). Withheld outside 0.2-1.3 and where province tables do not sum to the national
  row (1399; 1398 has no province table). National bachelor 0.587 (1397) -> 0.577 (1401).
* Caveats: stock-flow mismatch, programme-length variation (d+1 variant published), transfers and associate-to-bachelor
  continuation, Azad intake collapse 1396-98, COVID window flag, students studying outside the province of entry, the
  1393 Azad/full-time-staff break, the 1399 province tables.
* Association (`relations.json -> he_completion_vs_students_per_staff`, same `_cluster_fe` as above): bachelor completion
  vs students per staff at entry year, province + year FE: -0.42 pp per +1 student/staff (SE 0.17, p = 0.019, n = 93,
  3 years); cross-province r -0.47 / -0.25 / -0.21. Weakly identified; association only.
* Rank mix: senior share of full-time faculty 17.0 % (1393) -> 23.7 % (1398); students per senior 370 -> 154; ranks only
  for gender total, province 1393-1398 (all_reported) and 1380-1392 (Azad / non-Azad, not comparable). Degree mix: master
  share 3.9 % (1380) -> 18.8 % (1395) -> 14.9 % (1402), PhD 0.84 % (1385) -> 4.4 % (1402); Azad's pre-1393 doctorate figure
  bundles PhD and professional doctorate.
Reproduce: `uv run python -m etl.run views && uv run python scripts/export_site.py`; tests `tests/test_export_site.py`.

## Research output per academic staff (OpenAlex, 2026-10-01)

Not an analysis script of its own: `scripts/research_openalex.py` builds `external/research/*` and `exports/site/he_research.json`;
the findings are in `docs/findings.md` section 7 (growth 2.7 k works in 2000 to 115 k in 2020; Tehran about 52 % of works; works per
full-time academic staff 1.15 nationally in 2018, Tehran 2.38 against Hormozgan 0.29). The join with `he.json` aligns academic year t SH to
publication year t+621. Association only, and **partial data** (108 of 343 institutions fetched, 88 % of works) until the fetch is completed;
the pre-1393 staff basis differs and is kept in a separate field. Could be paired with `ratio_vs_outcomes.py` (staff ratios) as a
second outcome; not done.

