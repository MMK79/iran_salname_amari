# Research output of Iranian universities (OpenAlex), by institution, province and year

Built by `scripts/research_openalex.py` (stdlib only; `uv run python scripts/research_openalex.py all`).
Raw responses are cached in `cache/` (gitignored); the CSVs and `exports/site/he_research.json` are rebuilt from the cache.
OpenAlex retrieval date: 2026-10-01. Key read from `OPENALEX_API_KEY` in the environment, never stored.

## STATUS: fetch is incomplete (proven, see below)

108 of the 343 institutions are fetched (the 108 largest by works, 88 % of all-time institution works). The OpenAlex
daily budget ran out (HTTP 429 "$0 remaining", resets 00:00 UTC; the keyless pool was spent too). Province totals,
especially for small provinces, and any figure that depends on small institutions (many Azad branches, small medical
universities) are **lower bounds**. `institution_province.csv` lists all 343 with `fetched=False` for the missing ones.
Completing it needs no code change: `uv run python scripts/research_openalex.py all` (resumable, cached per file).
A delayed job was started to do this after the reset; if `exports/site/he_research.json` has `meta.coverage.institutions_fetched == 343` it ran.
The same re-run will also fill `all_iran_all_institution_types_works` (national group_by, not yet cached).

## Files

| file | content |
|---|---|
| `institution_province.csv` | all 343 OpenAlex institutions (country IR, type education) with ROR, city, lat/lon, `province_code`, `method`, nearest-capital cross-check |
| `institutions.csv` | fetched institutions with totals 2000-2025 (works, citations, international share, AI, education) |
| `institution_year.csv` | institution x publication year: works, citations, intl_works, ai_works, edu_works |
| `province_year.csv` | province x year (de-duplicated): the same plus academic staff and works per staff |
| `rankings.csv` | ISC World University Rankings (Iran, 2018-2025) + SCImago record (see below) |

## Method and choices

* **Population**: OpenAlex institutions with `country_code=IR` and `type=education` (medical universities are `education` in OpenAlex). Hospitals, research institutes (type healthcare/facility/government) are not included. Islamic Azad branches (120) and Payame Noor are separate OpenAlex institutions; `group` = azad / payame_noor / medical / other_university (by name).
* **Works**: type `article` or `review`, publication year 2000-2025, credited to the institution by `authorships.institutions.id`. OpenAlex has no separate conference-paper type: proceedings papers are included only where typed `article`. One record per (institution, work): `cited_by_count` and `countries_distinct_count` (international = more than one country on the work).
* **Citations**: sum of `cited_by_count` on the retrieval date. **Right-censored**: recent years have had less time to be cited (mean citations per paper falls from about 14 for 2015-2020 to 3.2 for 2025), so compare citations only within one publication year.
* **Topic slices**: AI/ML = any topic with OpenAlex subfield "Artificial Intelligence" (id 1702); Education = any topic in subfield "Education" (3304). Model-assigned labels, they change between releases; "Machine Learning" has no subfield of its own.
* **Multi-institution papers**: counted once per institution (OpenAlex default). For **province and national totals the union of work ids is taken**, so a paper with two Tehran institutions counts once in Tehran. (Chosen over summing institution counts, which over-counts collaborations within a province; fetching work ids per institution made the union cheap.) A paper with authors in two provinces counts once in each.
* **Province mapping**: hand-made city -> province dictionary on the OpenAlex `geo.city` (OpenAlex's own `region` is empty for 186 of 343 institutions and wrong for some cities, e.g. Maragheh). Cross-check: distance to the nearest province capital (`agrees_with_nearest_capital`; 42 disagreements, all checked by hand: border-town institutions that are genuinely closer to a neighbouring capital, e.g. Shahrud, Kashan, Garmsar). Three institutions whose OpenAlex geo is wrong were overridden by hand (`method=manual_name`): Arak University of Technology (geo says Tehran) -> MRK, Gerash University of Medical Sciences (geo Farsan/Chaharmahal) -> FRS, Salman Farsi University of Kazerun (coordinates Iranshahr) -> FRS. The big ones were read by hand: University of Tehran, Sharif, Amirkabir, IUST, Tarbiat Modares, Shahid Beheshti, Tehran/Shahid Beheshti/Iran medical, Payame Noor (head office Tehran: all its branches' works carry the parent record) -> THR; Shiraz -> FRS; Isfahan x2 -> ISF; Ferdowsi -> KHR; Tabriz -> AZS. Province = the institution's main site; branch campuses elsewhere are not split.
* **Academic staff and the year alignment**: academic year t SH (e.g. 1401 = Mehr 1401 to Shahrivar 1402) is matched to publication year **t + 621** (the Gregorian year in which it starts, `year_gregorian` in `he.json`). Publications of a year are made during the academic year that starts that year and the one before, so this is a convention, not an exact match. Staff = `all_reported` / all degrees / total from `exports/site/he.json`. Before 1393 SH the province tables have no `all_reported`, so staff = `excl_azad` (full-time + hourly) + `azad` (basis unspecified): this is the `mixed_basis` series and its ratio is **not comparable** with the full-time `works_per_staff` (provided only on the all_reported basis; 2014 onwards for provinces, some earlier years nationally). Where `he.json` has Alborz inside Tehran (to 1389 SH) or Khorasan undivided (to 1382 SH) the works are merged the same way (Alborz rows are absent, Tehran carries `merged_with=ALB`; a `KHO` row is added). 2020 (SH 1399) province tables and 2023 staff are quarantined in `he.json`; 2024-25 have no staff.
* **Not corrected**: field mix (medical vs engineering vs humanities), mega-authorship (a few huge physics collaborations give single institutions very high citation sums), duplicated records, affiliation-string errors.

## Rankings (task #5)

* **ISC World University Rankings** (Islamic World Science and Technology Monitoring and Citation Institute): the table at https://wur.isc.ac is loaded from a public JSON endpoint without login (`GetUnivTableScoresJson`, filtered to Iran). 2018-2025 collected (24 to 76 Iranian universities per year; rank bands for most, e.g. "451-500"). Names matched to OpenAlex by fuzzy name (cutoff 0.82; spot-checked, not all verified). The meaning of the five `rank_*` indicator columns (assumed Research, Education, International Activity, Innovation, Societal Impact) is **inferred from the order in the site's script, unverified**.
* **SCImago Institutions Rankings**: https://www.scimagoir.com/rankings.php?country=IRN&year=2025 answers 403 (Cloudflare challenge) to non-browser clients; only the URL is recorded (`rankings.csv`, last row). Not collected.
