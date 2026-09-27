# Provinces: codes, historic changes, harmonisation

Defined in `etl/provinces.py`, loaded into `provinces` and `province_aliases`.

| code | province | ISO 3166-2 (2020, unverified) | own unit from (SH) | split from | harmonised group |
|---|---|---|---|---|---|
| ARD | Ardabil | IR-24 | 1372 (1993) | East Azerbaijan | G_AZSHARGH |
| QOM | Qom | IR-25 | 1374 (1995) | Tehran | G_TEHRAN |
| QZV | Qazvin | IR-26 | 1375 (1996) | Zanjan (parts earlier under Tehran) (unverified) | G_ZANJAN |
| GLS | Golestan | IR-27 | 1376 (1997) | Mazandaran | G_MAZ |
| KHR / KHS / KHJ | Razavi / North / South Khorasan | IR-09 / IR-28 / IR-29 | 1383 (2004) | Khorasan (KHO, historic) | G_KHORASAN |
| ALB | Alborz | IR-30 | 1389 (2010) | Tehran | G_TEHRAN |

All other provinces map one-to-one. Rules:

* Rows are stored with the unit **as printed** (e.g. `KHO` for undivided Khorasan until 1382,
  Tehran including Alborz until 1389). Nothing is re-allocated.
* For constant-border series use `harmonised_group` (sum members): valid from 1376 for all groups,
  from 1383 for Khorasan without it.
* Kermanshah was printed as «باختران» in the late 1360s-1370s: alias to `KSH`.
* Before 1365 «مرکزی» included Tehran; pre-1365 province data are not used in the views.
* `IRN` = national total. Yearbooks' «کل کشور» may differ slightly from the sum of provinces
  (checked by `province_sum`, 94 % of K-12 tables within 1 %).
