# Iran Statistical Yearbooks (سالنامه آماری) — scraper + education statistics

Two parts of one pipeline over the Statistical Centre of Iran yearbooks (amar.org.ir):

| Part | What | Where |
|---|---|---|
| **Scraper** (2025-11) | Download and organise the national/provincial yearbooks, province-name matching (Persian ↔ English, Wikipedia), URL availability per year/province | root: `amar_file_organizer.py`, `*.csv` |
| **Education statistics** (2026-09) | ETL of the education chapters 1345–1402 into Postgres (docker) with provenance to file + table; **K-12 and higher education kept separate** (degree levels and university types too); students-per-teacher / students-per-faculty views; validation; Streamlit province-map prototype | [`education-stats/`](education-stats/README.md) |

Research context: MSc thesis on AI in education (IUST) — the teacher/faculty shortage figures
motivate the thesis. Findings with provenance: [`education-stats/docs/findings.md`](education-stats/docs/findings.md).
