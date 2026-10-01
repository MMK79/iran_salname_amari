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
| `final_exam_by_province.csv` | Grade-12 final-exam mean score (0-20) per province. Block 1: Khordad 1402 table (31 provinces, press, unofficial). Block 2: Shargh infographic (24 provinces, conflicts with block 1, unverified) | province | false |
| `final_exam_national.csv` | National grade-12 final-exam means by field, 1398, 1402, 1403, quoted in the press | national | false |
| `konkur_candidates_by_province_1404_round2.csv` | Konkur 1404, second round: candidates per province by exam group (sums reconcile to 822,953 total incl. 191 abroad) | province | false (press copy of a Sanjesh announcement) |

Province codes match `etl/provinces.py` / the yearbook tables (e.g. `YZD`, `SBL`).
Join key for a province x year analysis: `province_code` + the school year that ends in the exam year (Khordad 1402 exam = school year 1401-02; check which `year_sh` convention the yearbook table uses before joining).

Not in the repo: raw TIMSS 2023 microdata and the Iran extracts are in `/Volumes/MigMig/Personal/Research/Iran Achievement Data/`.

Known gaps: no official province-level final-exam table was found; no Konkur per-province admissions/top-rank table was retrieved; no IRPHE per-province graduation or drop-out table was retrieved; UIS has no completion-rate (`CR.*`) or NER series for Iran and no direct pupil-teacher ratio indicator after 2017.
