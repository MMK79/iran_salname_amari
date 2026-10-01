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
