# external/migration: outbound students and brain-drain indicators

Retrieved 2026-10-01 by a research subagent. UTF-8 CSV with `source_url`, `retrieved`, `quality`, `verified`, `note`.
Narrative and claims-vs-evidence: vault note `Notes/Iran - Graduate Outcomes and Brain Drain.md`.

| file | content | quality |
|---|---|---|
| `outbound_students.csv` | UNESCO UIS API (version 20260507-91260335, Feb 2026 release) for Iran: outbound internationally mobile tertiary students, total, female, male; outbound mobility ratio; mobile outbound GER; by destination region (NA+W Europe, Central+E Europe, Arab States, South+W Asia, East Asia+Pacific). 1998-2023 | official-international, verified=true (read from the API) |
| `brain_drain_indicators.csv` | IMOBS-derived figures (as quoted by Factnameh and other press), NSF stay intention, return-scheme counts, UIS-derived ratios | mostly press/secondary, verified=false |

## Caveats
- UIS counts **students enrolled abroad**, not graduates and not permanent emigrants. Destinations that do not report to UIS are missing, so levels are a lower bound.
- UIS revises history. The 2020 value is 69,404 in the Feb 2026 vintage but 66,701 in IMOBS's earlier citation.
- Destination-region columns are UIS regions; "Central and Eastern Europe" rises from 8,160 (2016) to 27,872 (2023), but the UIS grouping hides which countries. Country detail is not in this file.
- 2024 and later are not yet published.
- The IMOBS site (imobs.ir) did not respond from this machine and the IMOBS Yearbooks (1399, 1400, 1401) were not read directly. Their numbers appear here only as quoted by Factnameh (a fact-checking outlet that cites page numbers). Read the Yearbook PDFs to upgrade them.

## Excluded as unverifiable
Sensational figures that circulate in English-language press and appeared in search results were **not** entered: a "141% rise in emigration to wealthy countries 2020-21 (48,000 to 115,000)", "$50-70 billion annual loss", "150-180 thousand scientists left 2007-2021". No primary source was found.

## To fetch by hand
1. **OECD DIOC** (Iran-born, tertiary, 2020/21 and 2010/11 rounds): OECD Data Explorer, "Database on Immigrants in OECD and non-OECD Countries". Not retrieved (the 2024 OECD PDF found was a 7-page brief without an Iran line).
2. IMOBS Migration Yearbooks (Sharif SPRI: spri.sharif.ir, "سالنامه مهاجرتی ایران") for graduate-level and "service-obligation (معافیت از خدمت) waiver" series.
3. UIS destination-country detail (UIS Data Browser, "Outbound internationally mobile students by host country").
