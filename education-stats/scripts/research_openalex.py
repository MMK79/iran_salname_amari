"""Research output of Iranian universities (OpenAlex), per institution, province and year, per academic staff.

Reproducible; all HTTP responses are cached under external/research/cache/ (gitignored).

    uv run python scripts/research_openalex.py fetch      # institutions + works (cached, resumable)
    uv run python scripts/research_openalex.py rankings   # ISC WUR (Iran, 2018-2025) -> rankings.csv
    uv run python scripts/research_openalex.py build      # CSVs + exports/site/he_research.json from the cache
    uv run python scripts/research_openalex.py all

API key: OPENALEX_API_KEY from the environment (never printed or written). Without it the public pool is used.

Design (see external/research/README.md):
* Unit = OpenAlex institutions with country_code IR and type education (medical universities are
  type education there; hospitals and research institutes are not included).
* One record per (institution, work): a light fetch (id, year, cited_by_count, countries_distinct_count)
  of every work with type article|review, published 2000-2025, credited to that institution
  (authorships.institutions.id; OpenAlex credits each work once per institution).
* Province totals are the UNION of work ids over the province's institutions, so a paper with two
  Tehran institutions counts once; national totals are the union over all institutions.
* AI/ML = any topic with subfield "Artificial Intelligence" (id 1702); Education = any topic with
  subfield "Education" (id 3304). Slices are fetched with the same filter plus the topic filter.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "external" / "research"
CACHE = RES / "cache"
SITE = ROOT / "exports" / "site"
API = "https://api.openalex.org"
Y0, Y1 = 2000, 2025
YEARS = list(range(Y0, Y1 + 1))
SLICES = {"all": "", "ai": ",topics.subfield.id:1702", "edu": ",topics.subfield.id:3304"}
TYPE_FILTER = "type:article%7Creview"

# ---------------------------------------------------------------- province mapping
CAPITALS = {  # province capital lat/lon, used only to cross-check the city dictionary
    "THR": (35.69, 51.42), "ALB": (35.84, 50.99), "ARD": (38.25, 48.30), "BSH": (28.92, 50.84),
    "CHB": (32.33, 50.86), "AZS": (38.08, 46.29), "FRS": (29.61, 52.54), "GIL": (37.28, 49.58),
    "GLS": (36.84, 54.43), "HMD": (34.80, 48.51), "HRM": (27.18, 56.27), "ILM": (33.64, 46.42),
    "ISF": (32.65, 51.67), "KRM": (30.28, 57.07), "KSH": (34.31, 47.07), "KHZ": (31.32, 48.67),
    "KBA": (30.67, 51.59), "KRD": (35.31, 47.00), "LRS": (33.49, 48.35), "MRK": (34.09, 49.69),
    "MZN": (36.56, 53.06), "KHS": (37.47, 57.33), "QZV": (36.27, 50.00), "QOM": (34.64, 50.88),
    "KHR": (36.30, 59.60), "SMN": (35.58, 53.39), "SBL": (29.50, 60.86), "KHJ": (32.87, 59.22),
    "AZG": (37.55, 45.08), "YZD": (31.90, 54.37), "ZNJ": (36.68, 48.50),
}

# city (diacritics stripped, lower case) -> province code; hand-curated, OpenAlex's own `region` is wrong for several
# cities (e.g. it puts Maragheh in Razavi Khorasan) and missing for 186 of 343 institutions.
CITY_PROVINCE = {
    "ahar": "AZS", "ahvaz": "KHZ", "aliabad-e katul": "GLS", "arak": "MRK", "ardabil": "ARD", "arsanjan": "FRS",
    "bam": "KRM", "bandar abbas": "HRM", "bandar bushehr": "BSH", "bandar-e anzali": "GIL",
    "bandar-e mahshahr": "KHZ", "behbahan": "KHZ", "behshahr": "MZN", "birjand": "KHJ", "bojnourd": "KHS",
    "bonab": "AZS", "borujerd": "LRS", "bostanabad": "AZS", "babol": "MZN", "babolsar": "MZN", "bukan": "AZG",
    "buin zahra": "QZV", "chabahar": "SBL", "chalus": "MZN", "damavand": "THR", "damghan": "SMN",
    "dehaqan": "ISF", "dezful": "KHZ", "dogonbadan": "KBA", "dowlatabad": "ISF", "esfarayen": "KHS",
    "eslamshahr": "THR", "estahban": "FRS", "falavarjan": "ISF", "farmahin": "MRK", "fasa": "FRS",
    "farsan": "CHB", "firuzkuh": "THR", "firuzabad": "FRS", "garmsar": "SMN", "gonbad-e kavus": "GLS",
    "gonabad": "KHR", "gorgan": "GLS", "hamadan": "HMD", "harand": "ISF", "iranshahr": "SBL", "isfahan": "ISF",
    "jahrom": "FRS", "jenah": "HRM", "jiroft": "KRM", "karaj": "ALB", "kerman": "KRM", "kermanshah": "KSH",
    "khalkhal": "ARD", "khorramabad": "LRS", "khorramdarreh": "ZNJ", "khorramshahr": "KHZ", "khowy": "AZG",
    "komijan": "MRK", "kashan": "ISF", "kazerun": "FRS", "langarud": "GIL", "lahijan": "GIL", "larestan": "FRS",
    "mahabad": "AZG", "mahriz": "YZD", "malard": "THR", "malayer": "HMD", "marand": "AZS", "marvdasht": "FRS",
    "maragheh": "AZS", "masjed soleyman": "KHZ", "meybod": "YZD", "mobarakeh": "ISF", "mashhad": "KHR",
    "najafabad": "ISF", "namin": "ARD", "neyshabur": "KHR", "nur": "MZN", "omidiyeh": "KHZ", "qazvin": "QZV",
    "qom": "QOM", "qaem shahr": "MZN", "qaen": "KHJ", "quchan": "KHR", "rafsanjan": "KRM", "ramsar": "MZN",
    "rasht": "GIL", "rey": "THR", "robat karim": "THR", "rudehen": "THR", "sabzawar": "KHR", "sanandaj": "KRD",
    "sanandij": "KRD", "saqqez": "KRD", "sar-e saveh": "MRK", "saravan": "SBL", "sari": "MZN", "semnan": "SMN",
    "shabestar": "AZS", "shahr-e babak": "KRM", "shahr-e kord": "CHB", "shahr-e qadim-e lar": "FRS",
    "shahrestan-e jolfa": "AZS", "shahrestan-e mahallat": "MRK", "shahrestan-e torbat-e jam": "KHR",
    "torbat-e jam": "KHR", "shahreza": "ISF", "shahrud": "SMN", "shiraz": "FRS", "shahin shahr": "ISF",
    "shirvan": "KHS", "shushtar": "KHZ", "soltanabad": "KHR", "saveh": "MRK", "sirjan": "KRM", "tabriz": "AZS",
    "tafresh": "MRK", "tehran": "THR", "tonekabon": "MZN", "torbat-e heydariyeh": "KHR", "urmia": "AZG",
    "varamin": "THR", "yasuj": "KBA", "yazd": "YZD", "zabol": "SBL", "zahedan": "SBL", "zanjan": "ZNJ",
    "abadan": "KHZ", "amol": "MZN", "ashtian": "MRK", "azadshahr": "GLS", "ilam": "ILM", "izeh": "KHZ",
}
# Overrides decided by hand after reading the name (method = manual_name). Key = OpenAlex id.
MANUAL: dict[str, str] = {
    "I4210157180": "MRK",  # Arak University of Technology: OpenAlex city says Tehran, coordinates and name say Arak
    "I4210118749": "FRS",  # Gerash University of Medical Sciences: geo city "Farsan" (Chaharmahal) is wrong; Gerash is in Fars
    "I4210155517": "FRS",  # Salman Farsi University of Kazerun: coordinates point at Iranshahr, the university is in Kazerun (Fars)
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("’", "").replace("'", "").replace("ḩ", "h").replace("z̄", "z").lower().strip()


def nearest_capital(lat, lon):
    if lat is None or lon is None:
        return None, None
    best = min(CAPITALS, key=lambda c: (CAPITALS[c][0] - lat) ** 2 + ((CAPITALS[c][1] - lon) * math.cos(math.radians(lat))) ** 2)
    d = math.hypot((CAPITALS[best][0] - lat) * 111, (CAPITALS[best][1] - lon) * 111 * math.cos(math.radians(lat)))
    return best, round(d)


def map_province(inst: dict) -> tuple[str | None, str, str | None, int | None]:
    g = inst.get("geo") or {}
    near, dist = nearest_capital(g.get("latitude"), g.get("longitude"))
    iid = inst["id"].rsplit("/", 1)[-1]
    if iid in MANUAL:
        return MANUAL[iid], "manual_name", near, dist
    c = CITY_PROVINCE.get(norm(g.get("city") or ""))
    if c:
        return c, "city_dictionary", near, dist
    if near:
        return near, "nearest_capital", near, dist
    return None, "unmapped", near, dist


def group_of(name: str) -> str:
    n = name.lower()
    if "islamic azad" in n:
        return "azad"
    if "payame noor" in n:
        return "payame_noor"
    if any(k in n for k in ("medical sciences", "health services", "university of social welfare")):
        return "medical"
    return "other_university"


# ---------------------------------------------------------------- HTTP + cache
_KEY = "".join((os.environ.get("OPENALEX_API_KEY") or "").split())


_KEY_STATE = {"use": True}


def get(path_query: str) -> dict:
    url = f"{API}/{path_query}" + (f"&api_key={_KEY}" if _KEY and _KEY_STATE["use"] else "")
    for attempt in range(12):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept-Encoding": "identity", "User-Agent": "education-stats/research"}), timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and _KEY and b"remaining" in e.read():
                # the key's daily budget is spent: fall back to the keyless public pool (slower, same data)
                _KEY_STATE["use"] = False
                url = f"{API}/{path_query}"
                continue
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(60, 2 ** attempt))
                continue
            raise RuntimeError(f"HTTP {e.code} for {path_query[:120]}") from None  # no URL: it carries the key
        except Exception:
            time.sleep(min(60, 2 ** attempt))
    raise RuntimeError(f"giving up on {path_query[:120]}")


def fetch_institutions() -> list[dict]:
    f = CACHE / "institutions.json"
    if f.exists():
        return json.loads(f.read_text())
    out, cur = [], "*"
    sel = "id,display_name,ror,type,geo,works_count,cited_by_count,lineage,display_name_alternatives"
    while cur:
        j = get(f"institutions?filter=country_code:IR,type:education&per-page=200&select={sel}&cursor={urllib.parse.quote(cur)}")
        out += j["results"]
        cur = j["meta"].get("next_cursor")
        if not j["results"]:
            break
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"retrieved": date.today().isoformat(), "results": out}))
    return json.loads(f.read_text())


def load_institutions() -> tuple[str, list[dict]]:
    j = fetch_institutions()
    if isinstance(j, list):
        return "", j
    return j["retrieved"], j["results"]


def fetch_rows(iid: str, sl: str) -> list[list[int]]:
    """[[work_id_int, year, cited_by_count, countries_distinct_count], ...] cached as gz json."""
    f = CACHE / "works" / f"{iid}_{sl}.json.gz"
    if f.exists():
        return json.load(gzip.open(f, "rt"))
    rows, cur = [], "*"
    base = f"works?filter=authorships.institutions.id:{iid},publication_year:{Y0}-{Y1},{TYPE_FILTER}{SLICES[sl]}&per-page=200&select=id,publication_year,cited_by_count,countries_distinct_count"
    while cur:
        j = get(base + f"&cursor={urllib.parse.quote(cur)}")
        for w in j["results"]:
            rows.append([int(w["id"].rsplit("W", 1)[-1]), w["publication_year"], w["cited_by_count"], w.get("countries_distinct_count") or 1])
        cur = j["meta"].get("next_cursor")
        if not j["results"]:
            break
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as fh:
        json.dump(rows, fh)
    tmp.rename(f)
    return rows


def fetch_national() -> dict:
    """All Iranian works (any institution type) by year, article|review: the denominator for coverage."""
    f = CACHE / "national_by_year.json"
    if f.exists():
        return json.loads(f.read_text())
    if not _KEY_STATE.get("allow_api", True):
        return {}
    j = get(f"works?filter=authorships.countries:IR,publication_year:{Y0}-{Y1},{TYPE_FILTER}&group_by=publication_year&per-page=200")
    out = {str(g["key"]): g["count"] for g in j["group_by"]}
    f.write_text(json.dumps(out))
    return out


def cmd_fetch(workers: int = 4) -> None:
    ret, insts = load_institutions()
    insts = sorted(insts, key=lambda r: -r["works_count"])
    print(f"{len(insts)} institutions (retrieved {ret})", flush=True)
    jobs = [(r["id"].rsplit("/", 1)[-1], sl) for r in insts for sl in SLICES]
    done = [0]

    def run(j):
        try:
            fetch_rows(*j)
        except Exception as e:  # keep going; a re-run picks the missing files up
            print("  FAILED", j, str(e)[:80], flush=True)
        done[0] += 1
        if done[0] % 50 == 0:
            print(f"  {done[0]}/{len(jobs)}", flush=True)

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(run, jobs))
    fetch_national()
    print("fetch done", flush=True)


# ---------------------------------------------------------------- rankings (ISC World University Rankings)
ISC_URL = "https://wur.isc.ac/Home/GetUnivTableScoresJson?year={y}&table_type=0&rank_type=1&subject_id=1"


def isc_iran(year: int) -> list[dict]:
    """Public JSON behind wur.isc.ac (DataTables server-side; the country filter is column 1 search '#null#104', 104 = Iran)."""
    f = CACHE / f"isc_wur_{year}.json"
    if f.exists():
        return json.loads(f.read_text())
    form = [("draw", "1"), ("start", "0"), ("length", "500"), ("search[value]", ""), ("search[regex]", "false"),
            ("order[0][column]", "0"), ("order[0][dir]", "asc")]
    for i, n in enumerate(["Total", "UnivPic", "UnivName", "Country", "Compare"]):
        form += [(f"columns[{i}][data]", n), (f"columns[{i}][name]", ""), (f"columns[{i}][searchable]", "true"),
                 (f"columns[{i}][orderable]", "true"), (f"columns[{i}][search][regex]", "false"),
                 (f"columns[{i}][search][value]", "#null#104" if i == 1 else "")]
    req = urllib.request.Request(ISC_URL.format(y=year), data=urllib.parse.urlencode(form).encode(),
                                 headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"})
    data = json.load(urllib.request.urlopen(req, timeout=90))["data"]
    import html as _h
    import re
    out = []
    for x in data:
        name = _h.unescape(re.sub(r"<[^>]+>", "", x["UnivName"].split("&#32;")[0])).strip()
        sc = {(a, b): c for a, b, c in re.findall(r'id="univ-\d+-(\w)-(score|rank)"[^>]*>([^<]*)', x["Compare"])}
        out.append(dict(university=name, rank=x["Total"], score=sc.get(("t", "score")), rank_research=sc.get(("a", "rank")),
                        rank_education=sc.get(("b", "rank")), rank_international=sc.get(("c", "rank")),
                        rank_innovation=sc.get(("d", "rank")), rank_societal=sc.get(("e", "rank"))))
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out))
    return out


def cmd_rankings() -> None:
    import difflib
    _, insts = load_institutions()
    names = {norm(r["display_name"]): r["id"].rsplit("/", 1)[-1] for r in insts}
    rows = []
    for y in range(2018, 2026):
        try:
            data = isc_iran(y)
        except Exception as e:  # year may not exist
            print("ISC", y, "failed:", type(e).__name__)
            continue
        for d in data:
            n = norm(d["university"])
            m = difflib.get_close_matches(n, list(names), 1, 0.82)
            rows.append(dict(source="ISC World University Rankings", year=y, **d,
                             openalex_id=names[m[0]] if m else "", match_method="fuzzy_name_0.82" if m else "unmatched",
                             indicator_note="rank_* columns a-e of the site assumed = Research, Education, International Activity, Innovation, Societal Impact (table order; unverified)"))
    rows.append(dict(source="SCImago Institutions Rankings", year="", university="(not collected)", rank="",
                     score="", openalex_id="", match_method="blocked",
                     indicator_note="scimagoir.com answers 403 (Cloudflare challenge) to non-browser clients; URL only: https://www.scimagoir.com/rankings.php?country=IRN&year=2025 (download is a browser export)"))
    cols = ["source", "year", "university", "rank", "score", "rank_research", "rank_education", "rank_international", "rank_innovation", "rank_societal", "openalex_id", "match_method", "indicator_note"]
    RES.mkdir(parents=True, exist_ok=True)
    with open(RES / "rankings.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(rows)
    print("rankings:", len(rows))


# ---------------------------------------------------------------- aggregation
def agg(rows_by_slice: dict[str, list]) -> dict[int, dict]:
    """rows_by_slice: slice -> iterable of rows (already de-duplicated by work id). -> year -> metrics"""
    out = {y: dict(works=0, citations=0, intl_works=0, ai_works=0, edu_works=0) for y in YEARS}
    for _, y, c, nc in rows_by_slice["all"]:
        if y in out:
            o = out[y]
            o["works"] += 1
            o["citations"] += c
            o["intl_works"] += nc > 1
    for sl, key in (("ai", "ai_works"), ("edu", "edu_works")):
        for _, y, _c, _n in rows_by_slice[sl]:
            if y in out:
                out[y][key] += 1
    return out


def union(lists: list[list]) -> list:
    seen = {}
    for rows in lists:
        for r in rows:
            seen[r[0]] = r
    return list(seen.values())


def load_staff() -> tuple[dict, dict]:
    """province -> gregorian year -> {staff, basis, nonazad}. Academic year t (SH) -> publication year t+621."""
    he = json.load(open(SITE / "he.json"))["data"]
    staff: dict[str, dict[int, dict]] = defaultdict(dict)
    nat: dict[int, dict] = {}
    for ysh, d in he.items():
        yg = int(ysh) + 621
        for p, v in d.items():
            if not isinstance(v, dict):
                continue

            def tot(k):
                return (((v.get(k) or {}).get("all") or {}).get("total") or {}).get("academic_staff")
            ar, ex, az = tot("all_reported"), tot("excl_azad"), tot("azad")
            if ar is not None:
                s, basis = ar, "all_reported_fulltime"
            elif ex is not None and az is not None:
                s, basis = ex + az, "excl_azad(fulltime+hourly)+azad(unspecified)"
            else:
                s, basis = None, None
            rec = dict(staff=s, basis=basis, nonazad=ex)
            if p == "IRN":
                nat[yg] = rec
            else:
                staff[p][yg] = rec
    return staff, nat


def merge_staff(staff: dict, yg: int, members: list[str]):
    tot, nz, basis = 0, 0, None
    for m in members:
        r = staff.get(m, {}).get(yg)
        if not r or r["staff"] is None:
            return None
        tot += r["staff"]
        nz += r["nonazad"] or 0
        basis = r["basis"]
    return dict(staff=tot, nonazad=nz or None, basis=basis)


def ratio(works, s, consistent: bool):
    """works per academic staff. consistent=True: only the full-time 'all_reported' basis (comparable 2014 on, and some earlier years);
    consistent=False: the sum excl_azad(full+hourly)+azad(unspecified) used before 1393 SH, which breaks the series."""
    if not s or not s.get("staff"):
        return None
    is_cons = (s.get("basis") or "").startswith("all_reported")
    if is_cons != consistent:
        return None
    return round(works / s["staff"], 4)


def cmd_build() -> None:
    retrieved, insts = load_institutions()
    insts = sorted(insts, key=lambda r: -r["works_count"])
    prov = {p["code"]: p for p in json.load(open(SITE / "provinces.json"))["provinces"]}
    rows: dict[str, dict[str, list]] = {}
    meta = []
    for r in insts:
        iid = r["id"].rsplit("/", 1)[-1]
        have = all((CACHE / "works" / f"{iid}_{sl}.json.gz").exists() for sl in SLICES)
        if have:  # build never calls the API: institutions not yet fetched are listed but left out of the series
            rows[iid] = {sl: fetch_rows(iid, sl) for sl in SLICES}
        pc, method, near, dist = map_province(r)
        g = r.get("geo") or {}
        meta.append(dict(
            openalex_id=iid, ror=(r.get("ror") or "").replace("https://ror.org/", ""), name=r["display_name"],
            group=group_of(r["display_name"]), city=g.get("city"), openalex_region=g.get("region"),
            lat=g.get("latitude"), lon=g.get("longitude"), province_code=pc, method=method,
            nearest_capital=near, dist_km_to_nearest_capital=dist,
            agrees_with_nearest_capital=(pc == near), works_2000_2025=len(rows[iid]["all"]) if have else "", works_all_time=r["works_count"], fetched=have,
        ))
    meta_all = meta
    meta = [m for m in meta_all if m["fetched"]]
    coverage = dict(institutions_total=len(meta_all), institutions_fetched=len(meta),
                    share_of_all_time_works_fetched=round(sum(m["works_all_time"] for m in meta) / sum(m["works_all_time"] for m in meta_all), 4))
    RES.mkdir(parents=True, exist_ok=True)
    cols = list(meta[0])
    with open(RES / "institution_province.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(meta_all)
    # institutions.csv: same rows plus totals
    with open(RES / "institutions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols + ["citations_2000_2025", "intl_share", "ai_works", "edu_works"])
        w.writeheader()
        for m in meta:
            a = rows[m["openalex_id"]]["all"]
            w.writerow({**m, "citations_2000_2025": sum(x[2] for x in a),
                        "intl_share": round(sum(x[3] > 1 for x in a) / len(a), 4) if a else "",
                        "ai_works": len(rows[m["openalex_id"]]["ai"]), "edu_works": len(rows[m["openalex_id"]]["edu"])})

    # institution x year
    inst_year = {}
    with open(RES / "institution_year.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["openalex_id", "name", "province_code", "year", "works", "citations", "intl_works", "ai_works", "edu_works"])
        for m in meta:
            a = agg(rows[m["openalex_id"]])
            inst_year[m["openalex_id"]] = a
            for y in YEARS:
                v = a[y]
                if v["works"]:
                    w.writerow([m["openalex_id"], m["name"], m["province_code"], y, v["works"], v["citations"], v["intl_works"], v["ai_works"], v["edu_works"]])

    # province x year (union of work ids), groups, national
    by_prov = defaultdict(list)
    by_group = defaultdict(list)
    for m in meta:
        by_prov[m["province_code"]].append(m["openalex_id"])
        by_group[m["group"]].append(m["openalex_id"])

    def union_agg(ids):
        return agg({sl: union([rows[i][sl] for i in ids]) for sl in SLICES})

    grp = {m["openalex_id"]: m["group"] for m in meta}
    prov_agg = {p: union_agg(ids) for p, ids in by_prov.items()}
    thr_alb = by_prov["THR"] + by_prov["ALB"]
    thr_alb_agg = union_agg(thr_alb)
    thr_alb_nz = union_agg([i for i in thr_alb if grp[i] != "azad"])
    kh_ids = by_prov["KHR"] + by_prov["KHS"] + by_prov["KHJ"]
    kh_agg = union_agg(kh_ids)
    kh_nz = union_agg([i for i in kh_ids if grp[i] != "azad"])
    nonazad_agg = {p: union_agg([i for i in ids if grp[i] != "azad"]) for p, ids in by_prov.items()}
    group_agg = {g: union_agg(ids) for g, ids in by_group.items()}
    nat_agg = union_agg([m["openalex_id"] for m in meta])
    _KEY_STATE["allow_api"] = False
    nat_all = fetch_national()

    staff, nat_staff = load_staff()
    flags = {int(d["year_sh"]) + 621: d["flags"] for d in json.load(open(SITE / "he.json"))["years"]}

    def staff_for(p, yg):
        fl = flags.get(yg, [])
        if p == "THR" and "alborz_in_tehran" in fl:
            return merge_staff(staff, yg, ["THR"]), "THR includes Alborz in the staff table; works merged too"
        if p == "KHO":
            return merge_staff(staff, yg, ["KHO"]), ""
        return merge_staff(staff, yg, [p]), ""

    prov_rows = []
    series_prov = {}
    for p in sorted(CAPITALS):
        for yg in YEARS:
            a = prov_agg.get(p, {}).get(yg)
            za = nonazad_agg.get(p, {}).get(yg)
            if p in ("ALB", "THR") and "alborz_in_tehran" in flags.get(yg, []):
                # staff table has Alborz inside Tehran: merge the works of both so the ratio is consistent
                if p == "ALB":
                    continue
                a, za = thr_alb_agg[yg], thr_alb_nz[yg]
            if p in ("KHR", "KHS", "KHJ") and "khorasan_undivided" in flags.get(yg, []):
                continue
            s = merge_staff(staff, yg, [p])
            prow = dict(province_code=p, province=prov[p]["name_en"], year=yg, works=a["works"] if a else 0,
                        citations=a["citations"] if a else 0, intl_works=a["intl_works"] if a else 0,
                        ai_works=a["ai_works"] if a else 0, edu_works=a["edu_works"] if a else 0,
                        academic_staff=s["staff"] if s else None, staff_basis=s["basis"] if s else None,
                        works_per_staff=ratio(a["works"] if a else 0, s, True), works_per_staff_mixed_basis=ratio(a["works"] if a else 0, s, False),
                        nonazad_works=za["works"] if za else 0,
                        nonazad_works_per_staff_excl_azad=round(za["works"] / s["nonazad"], 4) if s and s.get("nonazad") and za else None,
                        merged_with=("ALB" if (p == "THR" and "alborz_in_tehran" in flags.get(yg, [])) else ""))
            prov_rows.append(prow)
        # Khorasan (undivided before 1383 SH): add a harmonised KHO row for the early years
    for yg in YEARS:
        if "khorasan_undivided" in flags.get(yg, []):
            a, za = kh_agg[yg], kh_nz[yg]
            s = merge_staff(staff, yg, ["KHO"])
            prov_rows.append(dict(province_code="KHO", province="Khorasan (undivided; KHR+KHS+KHJ)", year=yg, works=a["works"],
                                  citations=a["citations"], intl_works=a["intl_works"], ai_works=a["ai_works"], edu_works=a["edu_works"],
                                  academic_staff=s["staff"] if s else None, staff_basis=s["basis"] if s else None,
                                  works_per_staff=ratio(a["works"], s, True), works_per_staff_mixed_basis=ratio(a["works"], s, False),
                                  nonazad_works=za["works"], nonazad_works_per_staff_excl_azad=round(za["works"] / s["nonazad"], 4) if s and s.get("nonazad") else None,
                                  merged_with="KHR+KHS+KHJ"))
    with open(RES / "province_year.csv", "w", newline="") as f:
        w = csv.DictWriter(f, list(prov_rows[0]))
        w.writeheader()
        w.writerows(prov_rows)

    # ------------------------------------------------ rankings (read if collected)
    rank_rows = []
    rf = RES / "rankings.csv"
    if rf.exists():
        rank_rows = list(csv.DictReader(open(rf)))

    # ------------------------------------------------ site JSON
    def series(a):
        return {k: [a[y][k] for y in YEARS] for k in ("works", "citations", "intl_works", "ai_works", "edu_works")}

    top = []
    ranked = sorted(meta, key=lambda m: -m["works_2000_2025"])[:40]
    for m in ranked:
        s = series(inst_year[m["openalex_id"]])
        top.append(dict(openalex_id=m["openalex_id"], ror=m["ror"], name=m["name"], group=m["group"], city=m["city"],
                        province_code=m["province_code"], total_works=m["works_2000_2025"],
                        total_citations=sum(s["citations"]), intl_share=round(sum(s["intl_works"]) / max(1, sum(s["works"])), 4), **s))
    prov_series = {}
    for row in prov_rows:
        d = prov_series.setdefault(row["province_code"], dict(province=row["province"], years=[], works=[], citations=[], intl_works=[], ai_works=[], edu_works=[], academic_staff=[], works_per_staff=[], works_per_staff_mixed_basis=[], staff_basis=[], nonazad_works_per_staff_excl_azad=[]))
        d["years"].append(row["year"])
        for k in ("works", "citations", "intl_works", "ai_works", "edu_works", "academic_staff", "works_per_staff", "works_per_staff_mixed_basis", "staff_basis", "nonazad_works_per_staff_excl_azad"):
            d[k].append(row[k])
    nat = dict(years=YEARS, **series(nat_agg), all_iran_all_institution_types_works=[nat_all.get(str(y)) for y in YEARS],
               national_academic_staff=[(nat_staff.get(y) or {}).get("staff") for y in YEARS],
               national_staff_basis=[(nat_staff.get(y) or {}).get("basis") for y in YEARS])
    nat["works_per_staff"] = [round(w / s, 4) if s and (b or "").startswith("all_reported") else None for w, s, b in zip(nat["works"], nat["national_academic_staff"], nat["national_staff_basis"])]
    nat["works_per_staff_mixed_basis"] = [round(w / s, 4) if s and not (b or "").startswith("all_reported") else None for w, s, b in zip(nat["works"], nat["national_academic_staff"], nat["national_staff_basis"])]
    out = dict(
        meta=dict(source="OpenAlex (api.openalex.org)", retrieved=retrieved, years=[Y0, Y1], work_types=["article", "review"],
                  coverage=coverage, n_institutions=len(meta), unit="institutions with country_code IR and type education",
                  alignment="academic year t (SH) is matched to publication year t+621 (the year in which it starts)",
                  province_dedup="province and national totals are unions of work ids, so one paper is counted once per province"),
        national=nat,
        groups={g: dict(years=YEARS, **series(a)) for g, a in group_agg.items()},
        top_universities=top,
        provinces=prov_series,
        rankings=rank_rows,
        caveats=([f"INCOMPLETE FETCH: only {coverage['institutions_fetched']} of {coverage['institutions_total']} institutions are in the series ({coverage['share_of_all_time_works_fetched']:.0%} of their all-time works); the OpenAlex daily API budget ran out. Province totals, especially of small provinces, are lower bounds. Re-run `scripts/research_openalex.py all` to complete."] if coverage["institutions_fetched"] < coverage["institutions_total"] else []) + [
            "Citations are cited_by_count at the retrieval date: recent publication years have had less time to be cited (right-censoring), so citations by year are not comparable across years; use only for ranking within a year.",
            "Mega-authorship papers (hundreds of authors, e.g. physics collaborations) are counted in full for every credited institution and dominate citation sums of a few institutions.",
            "Conference papers are included only where OpenAlex types them as article; proceedings typed otherwise are excluded.",
            "An institution is credited by affiliation strings; branches of Islamic Azad University and Payame Noor are separate OpenAlex institutions, some papers carry only the parent name, so Tehran-based parent records are inflated relative to branches.",
            "Academic staff: all_reported (full-time) from 1393 SH; before that excl_azad (full-time + hourly) plus azad (basis unspecified) are summed; the break makes works per staff incomparable across 1392/1393; 2023 and 2024-25 have no staff (province tables quarantined / yearbook not yet parsed).",
            "Province = location of the institution's main site; branch campuses, hospitals and research institutes outside the education type are not attributed. Alborz is merged into Tehran (and Khorasan provinces into one) for years in which the staff table does so.",
            "works_per_staff is output per academic staff member of the same province (not per researcher) and is given only on the consistent full-time basis; works_per_staff_mixed_basis (before 1393 SH, and 2001-2003 for Khorasan) uses excl_azad(full+hourly)+azad(unspecified) staff and must not be compared with it.",
            "AI/ML slice = any OpenAlex topic in the subfield Artificial Intelligence; Education slice = any topic in subfield Education. Topic labels are model-assigned and change between OpenAlex releases.",
            "2025 is a partial year in OpenAlex at retrieval time (indexing lag).",
        ],
    )
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "he_research.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print("built", len(meta), "institutions;", len(prov_rows), "province-years")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("fetch", "all"):
        cmd_fetch()
    if cmd in ("rankings", "all"):
        cmd_rankings()
    if cmd in ("build", "all"):
        cmd_build()
