# external/labour: graduate unemployment

Retrieved 2026-10-01 by a research subagent. UTF-8 CSV with `source_url`, `retrieved`, `quality`, `verified`, `note`.
Narrative and claims-vs-evidence: vault note `Notes/Iran - Graduate Outcomes and Brain Drain.md`.

| file | content |
|---|---|
| `graduate_unemployment_national.csv` | Unemployment rate of higher-education graduates (and the graduate share of all unemployed), national, by sex where published. Annual 1395-1401 and 1403, quarterly 1401-Q2 to 1404-Q1. |

## Quality: everything here is press/secondary, `verified=false`
amar.org.ir (Statistical Centre of Iran) could not be reached from this machine (connection fails), so no row was read from the official PDF or Excel. Values are the Centre's Labour Force Survey figures as reproduced by Etemad, Shargh, Khabaronline/Mehr, Eghtesadonline, Eghtesaad24, Asr Iran/Tasnim, Fararu, Rokna and iranstatis.com. Raw captures are in `/Volumes/MigMig/Personal/Research/Iran Labour Data/`.
Cross-check that passed: the mean of the four 1403 quarters (11.6, 11.6, 11.1, 10.7 = 11.25) matches the annual 11.2 on iranstatis.com.

## Traps
- **Definition break.** 1395-1397 rows (about 18-20%) count "graduates **or students** of higher education". From 1399 the series is graduates only (about 14% falling to about 11%). Do not plot them as one line. The change between 1397 (18.3) and 1399 (14.2) is partly definitional. 1398 is missing.
- Rows marked DERIVED in `note` were computed from a stated year-on-year change in a press article (for example 1399, 1402 quarters). They inherit the rounding of the source.
- "Share of unemployed who are graduates" (about 39-44%) is a different quantity from the graduate unemployment rate.
- The 1403-Q3 sex split (7.4 / 19.0) comes from Rokna, which says "educated" (تحصیل‌کرده), assumed to mean higher-education graduates.

## Not found
- **By province:** no graduate-specific provincial series was reachable. Overall provincial rates exist (1403-Q2: Sistan-Baluchestan 14.0, Khuzestan 13.1, Markazi 4.3) but those are all-population, so no `graduate_unemployment_by_province.csv` was written.
- **Graduate labour-force participation:** not found in a retrievable form.
- 1398 and the whole of 1384-1394 (annual), and 1402 annual.

## To fetch by hand (from inside Iran or with a working amar.org.ir session)
1. Quarterly "چکیده نتایج طرح آمارگیری نیروی کار" PDFs, pattern `https://amar.org.ir/Portals/0/Articles/niroorey kar-<q>-<year>.pdf` (found for spring 1403). Tables: graduate unemployment rate, share of unemployed, by sex and urban/rural.
2. Excel "نرخ بیکاری و مشارکت به تفکیک استان و تحصیلات" and the annual Salnameh labour-force tables 1384+.
3. iranstatis.com datasets A02010049 (graduate participation), A02010051 (graduate unemployment 1391-1403 by sex/field/urban-rural), A02010036/37/38 (employed/unemployed/inactive by education and province): paid subscription.
