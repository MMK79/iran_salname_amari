# external/achievement — outcome data to relate to the yearbook ratios

Retrieved 2026-10-01 by a research subagent. All CSVs are UTF-8 and carry `source_url`, `retrieved` and `verified`.
`verified=true` means the number was read directly from the primary publisher's file or API in this session.
`verified=false` means a press or secondary source that was not matched to an official original. Never treat `false` rows as measured.
Narrative and the claims-vs-evidence table: vault note `Notes/Iran - Student Achievement Data.md`.

| file | content | geography | verified |
|---|---|---|---|
| `timss_iran.csv` | Iran TIMSS grade 4 and 8, maths and science, 1995-2023, average scale score and SE, from the TIMSS 2023 International Results trend exhibits (1-1-10, 1-2-10, 2-1-10, 2-2-10) | national | true |
| `pirls_iran.csv` | Iran PIRLS grade 4 reading 2001-2021 (Exhibit 2.2 trend table) | national | true |
| `unesco_uis_iran.csv` | UNESCO UIS API (`api.uis.unesco.org`, version 20260507-91260335) and World Bank API for Iran: out-of-school (counts, rates), teachers with minimum qualifications, GER, school-age population, public education spend, adult literacy, plus World Bank pupil-teacher ratio (primary, secondary) and primary completion | national | true (as published by the APIs) |
| `final_exam_by_province.csv` | Grade-12 final-exam means (0-20) per province, long format: one row per outlet/value. Sessions: Khordad 1402 (Namnak table; Shargh infographic re-read; Ministry colour bands), academic year 1398-99 (Farhikhtegan chart, 31 provinces), Khordad 1403 (official Ministry change-vs-1402 per province, derived levels, Chaharmahal 10.27 and Tehran-city 12.51 official), Fars 1401/1402 (official), rank-only claims for Yazd 1404 and Kerman, and the Centre's denial of circulated 1405 rankings. See column notes below | province | mixed: official rows true, press tables false |
| `final_exam_national.csv` | National grade-12 means by field and year: 1398-1402 (Centre slide), 1403 by field, gender, school type, grades 10 and 11; 1404 by field and overall; plus caveat rows (all-field vs three-field definitions, provincial means mistaken for national). | national | mixed |
| `konkur_candidates_by_province_1404_round2.csv` | Konkur 1404, second round: candidates per province by exam group (sums reconcile to 822,953 total incl. 191 abroad) | province | false (press copy of a Sanjesh announcement) |

Province codes match `etl/provinces.py` / the yearbook tables (e.g. `YZD`, `SBL`).
Join key for a province x year analysis: `province_code` + the school year that ends in the exam year (Khordad 1402 exam = school year 1401-02; check which `year_sh` convention the yearbook table uses before joining).

Not in the repo: raw TIMSS 2023 microdata and the Iran extracts are in `/Volumes/MigMig/Personal/Research/Iran Achievement Data/`.

Known gaps: no official province-level final-exam table was found; no Konkur per-province admissions/top-rank table was retrieved; no IRPHE per-province graduation or drop-out table was retrieved; UIS has no completion-rate (`CR.*`) or NER series for Iran and no direct pupil-teacher ratio indicator after 2017.

## Final-exam file columns (updated 2026-10-01)

`final_exam_by_province.csv` keeps the original 12 columns and adds:
- `n_sources` - number of outlets that print the same figure (reposts of one graphic are counted once, so 1398-99 = 1).
- `sources` - the outlets.
- `value_type` - `mean`, `derived_mean` (= 1402 press value + official delta, arithmetic only), `delta_vs_prev_year`, `band:a-b` (Ministry map colour band, no number), `rank_only`, `upper_bound:x`, `denial`.
- `rank` - provincial rank where published (rank 1 = highest mean).
- `status` - `current` or `superseded`. The 24 rows of the original Shargh block are `superseded`: they were a text misread of an infographic (kept for the audit trail; do not use). The infographic was re-read from the image into 31 provinces.

`verified=true` here means an official Ministry / Centre / provincial-education source (including the Ministry map bands and the Centre's per-province change slide). It is NOT true for any press table of means: Namnak and Shargh agree exactly for 19 of 31 provinces (28 within 0.10; largest gap 0.36, Yazd 12.40 vs 12.04) but have a common ancestry and cannot be called independent; they are therefore `verified=false` even where they agree. Province-by-gender and province-by-field means were not found for any session. Dey-session means by province were not found. 1405 means do not exist officially (denial 2026-09-12).

`final_exam_national.csv` adds `grade`, `breakdown` (all, female, male, state schools, non-state schools), `n_sources`, `sources`.

Reading caveats: values from images (1398-99 bars, Shargh map, Ministry delta map) were read by eye at 2-decimal labels; Kermanshah and Bushehr deltas were illegible and left out.
