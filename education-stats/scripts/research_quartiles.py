"""AI-in-education publications: Iran vs the world, by journal quality (SCImago SJR quartile).

    uv run python scripts/research_quartiles.py sjr      # check/load external/research/scimago/scimagojr_<year>.csv (manual download)
    uv run python scripts/research_quartiles.py fetch    # OpenAlex group_by source x year, cached, resumable
    uv run python scripts/research_quartiles.py build    # CSVs in external/research/ + exports/site/research_quartiles.json
    uv run python scripts/research_quartiles.py all
    uv run python scripts/research_quartiles.py --test   # self-check on a tiny fixture (no network)

OPENALEX_API_KEY comes from the environment (never printed or written). Every HTTP response is cached under
external/research/cache/ (gitignored); re-running only fetches what is missing.

Design (see analysis/README.md, section "Journal quality"):
* Buckets (OpenAlex `title_and_abstract.search`, keyword based, stemmed), 2015-2026 (2026 = to AS_OF):
  ai  = AI/ML/deep learning AND education words   (the vault note's "AI/ML + education" filter)
  llm = ChatGPT/LLM/generative AI AND education words
  its = intelligent tutoring / knowledge tracing / educational knowledge graph
* Scope iran = `authorships.institutions.country_code:IR` (>= 1 Iranian affiliation; co-authored works count);
  scope world = no country filter (Iran is a subset of world).
* OpenAlex `group_by` returns at most 200 groups and cannot paginate, so the date range is split recursively
  (year -> halves -> ... -> single days) until a window returns < 200 groups; the leaf windows are exact.
* Source -> SJR by ISSN (print/electronic/ISSN-L, hyphens stripped). Quartile = BEST across the journal's SJR
  subject categories (a journal is Q1 if Q1 in any category). One SJR edition is applied to every publication year.
* Classes: Q1..Q4, not_ranked (OpenAlex journal / book series with no SJR match or SJR quartile "-"),
  conference, repository, other (ebook platform, metadata, other), unknown (no primary source).
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "external" / "research"
CACHE = RES / "cache"
QCACHE = CACHE / "quartiles"
SITE = ROOT / "exports" / "site"
API = "https://api.openalex.org"
AS_OF = date(2026, 10, 2)
Y0, Y1 = 2015, 2026
YEARS = list(range(Y0, Y1 + 1))
SJR_YEAR = 2025
# SCImago blocks scripted downloads (Cloudflare 403), so the full SJR export is downloaded by hand in a browser
# (scimagojr.com/journalrank.php -> "Download data", per year) and saved here; the folder is gitignored.
SJR_DIR = RES / "scimago"

EDU = '(education OR student OR students OR teaching OR "e-learning")'
BUCKETS = {
    "ai": {
        "label": "AI/ML + education (broad, noisy)",
        "search": f'("artificial intelligence" OR "machine learning" OR "deep learning") AND {EDU}',
    },
    "llm": {
        "label": "LLM / ChatGPT / generative AI + education",
        "search": '(ChatGPT OR "large language model" OR "large language models" OR "generative AI" OR '
        '"generative artificial intelligence" OR LLM OR LLMs) AND (education OR student OR students OR '
        "teacher OR teachers OR teaching)",
    },
    "its": {
        "label": "Intelligent tutoring / knowledge tracing / educational knowledge graph",
        "search": '("intelligent tutoring" OR "intelligent tutor" OR "knowledge tracing" OR '
        '("knowledge graph" AND (education OR learners OR course OR curriculum)))',
    },
}
SCOPES = {"iran": ",authorships.institutions.country_code:IR", "world": ""}
CLASSES = ["Q1", "Q2", "Q3", "Q4", "not_ranked", "conference", "repository", "other", "unknown"]
QRANK = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}


# ------------------------------------------------------------------ HTTP + cache
def api_key() -> str:
    return re.sub(r"\s+", "", os.environ.get("OPENALEX_API_KEY", ""))


def http_json(url: str, tries: int = 6):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "education-stats-research/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                rem = r.headers.get("x-ratelimit-remaining")
                body = json.loads(r.read())
                if url.startswith(API) and rem is not None and rem.isdigit() and int(rem) < 50:
                    raise SystemExit("OpenAlex credits nearly spent (remaining < 50); re-run after the reset (resumable).")
                return body
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise SystemExit("OpenAlex HTTP 429 (budget spent); re-run after the reset (resumable).") from e
            if e.code >= 500 and i < tries - 1:
                time.sleep(2**i)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
            time.sleep(2**i)


def cached(url_nokey: str, fetch):
    """Cache keyed by the key-less URL; `fetch` is called only on a miss."""
    p = QCACHE / (hashlib.sha1(url_nokey.encode()).hexdigest()[:20] + ".json")
    if p.exists():
        return json.loads(p.read_text())
    out = fetch()
    QCACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out))
    return out


def group_window(bucket: str, scope: str, d0: date, d1: date, extra: str = ""):
    """group_by primary source for works in [d0, d1]; returns [[source_id|'unknown', n]], total count."""
    flt = (
        f"title_and_abstract.search:{BUCKETS[bucket]['search']}"
        f",from_publication_date:{d0.isoformat()},to_publication_date:{d1.isoformat()}{SCOPES[scope]}{extra}"
    )
    params = {"filter": flt, "group_by": "primary_location.source.id:include_unknown"}
    nokey = f"{API}/works?" + urllib.parse.urlencode(params)

    def fetch():
        k = api_key()
        d = http_json(nokey + (f"&api_key={k}" if k else ""))
        time.sleep(0.05)
        return {
            "count": d["meta"]["count"],
            "groups": [[g["key"].rsplit("/", 1)[-1], g["count"]] for g in d["group_by"]],
        }

    r = cached(nokey, fetch)
    return r["groups"], r["count"]


# A single day can still hold >= 200 distinct sources (many works are dated Jan 1 / the 1st of a month); such a
# day is split by further filter pairs that partition the works, recursively, until no group_by is truncated.
PARTITIONS = [
    ("type:article", "type:!article"),
    ("open_access.is_oa:true", "open_access.is_oa:false"),
    ("language:en", "language:!en"),
    ("has_doi:true", "has_doi:false"),
    ("is_paratext:true", "is_paratext:false"),
]


def partitioned(bucket, scope, d0, getter, log, extras=(), depth=0, parent_count=None):
    """Exact source counts for one day with extra filters, splitting by PARTITIONS while truncated."""
    extra = "".join("," + e for e in extras)
    groups, count = getter(bucket, scope, d0, d0, extra)
    if len(groups) < 200 or depth >= len(PARTITIONS):
        if len(groups) >= 200 and log is not None:
            log.append((bucket, scope, d0.isoformat(), f"still truncated after partitions {extra}"))
        return [groups], count
    out, tot = [], 0
    for e in PARTITIONS[depth]:
        g, c = partitioned(bucket, scope, d0, getter, log, (*extras, e), depth + 1)
        out += g
        tot += c
    if tot != count and log is not None:
        log.append((bucket, scope, d0.isoformat(), f"partition sum {tot} != count {count} ({extra})"))
    return out, count


def windows(bucket, scope, d0, d1, getter=group_window, log=None):
    """Recursively split [d0, d1] until the group_by is not truncated (< 200 groups); yield (d0, d1, groups)."""
    groups, count = getter(bucket, scope, d0, d1)
    if len(groups) < 200:
        yield d0, d1, groups
        return
    if d0 == d1:
        parts, _ = partitioned(bucket, scope, d0, getter, log)
        merged: dict[str, int] = defaultdict(int)
        for g in parts:
            for sid, n in g:
                merged[sid] += n
        groups = [[k, v] for k, v in merged.items()]
        if log is not None and sum(n for _, n in groups) != count:
            log.append((bucket, scope, d0.isoformat(), f"day sum {sum(n for _, n in groups)} != count {count}"))
        yield d0, d1, groups
        return
    mid = d0 + (d1 - d0) // 2
    yield from windows(bucket, scope, d0, mid, getter, log)
    yield from windows(bucket, scope, mid + timedelta(days=1), d1, getter, log)


def collect(getter=group_window, years=YEARS, log=None):
    """agg[bucket][scope][source_id][year] = n works."""
    agg = {b: {s: defaultdict(lambda: defaultdict(int)) for s in SCOPES} for b in BUCKETS}
    for b in BUCKETS:
        for s in SCOPES:
            for y in years:
                end = min(date(y, 12, 31), AS_OF)
                for _, _, groups in windows(b, s, date(y, 1, 1), end, getter, log):
                    for sid, n in groups:
                        agg[b][s][sid][y] += n
            print(f"  {b}/{s}: {sum(sum(v.values()) for v in agg[b][s].values())} works, {len(agg[b][s])} sources", flush=True)
    return agg


# ------------------------------------------------------------------ OpenAlex source metadata
def fetch_sources(ids: list[str]) -> dict[str, dict]:
    path = QCACHE / "_sources.json"
    meta = json.loads(path.read_text()) if path.exists() else {}
    todo = [i for i in ids if i != "unknown" and i not in meta]
    for i in range(0, len(todo), 100):
        batch = todo[i : i + 100]
        params = {
            "filter": "openalex:" + "|".join(batch),
            "select": "id,display_name,type,issn,issn_l",
            "per_page": 100,
        }
        k = api_key()
        d = http_json(f"{API}/sources?" + urllib.parse.urlencode(params) + (f"&api_key={k}" if k else ""))
        got = {}
        for s in d["results"]:
            got[s["id"].rsplit("/", 1)[-1]] = {
                "name": s.get("display_name"),
                "type": s.get("type"),
                "issn": list(s.get("issn") or []) + ([s["issn_l"]] if s.get("issn_l") else []),
            }
        for sid in batch:
            meta[sid] = got.get(sid, {"name": None, "type": None, "issn": []})
        path.write_text(json.dumps(meta))
        time.sleep(0.05)
    return meta


# ------------------------------------------------------------------ SJR
def norm_issn(x: str) -> str:
    return re.sub(r"[^0-9X]", "", (x or "").upper())


def best_quartile(categories: str, fallback: str = "") -> str:
    qs = re.findall(r"\((Q[1-4])\)", categories or "")
    if not qs and fallback in QRANK:
        qs = [fallback]
    return min(qs, key=QRANK.get) if qs else ""


def parse_sjr_rows(text: str) -> dict[str, dict]:
    out = {}
    rd = csv.DictReader(text.splitlines(), delimiter=";")
    for r in rd:
        qcol = next((c for c in r if c and c.startswith("SJR") and "Quartile" in c), None)
        try:
            sjr = float((r.get("SJR") or "").replace(",", ".") or "nan")
        except ValueError:
            sjr = float("nan")
        out[r["Sourceid"]] = {
            "title": r["Title"],
            "type": r.get("Type"),
            "issns": [norm_issn(x) for x in (r.get("Issn") or "").split(",") if norm_issn(x)],
            "sjr": sjr,
            "quartile": best_quartile(r.get("Categories", ""), r.get(qcol, "") if qcol else ""),
            "h_index": int(r["H index"]) if (r.get("H index") or "").isdigit() else None,
            "categories": r.get("Categories", ""),
        }
    return out


def fetch_sjr(year: int = SJR_YEAR) -> dict[str, dict]:
    """Load the manually downloaded SCImago export for `year` (see SJR_DIR)."""
    f = SJR_DIR / f"scimagojr_{year}.csv"
    if not f.exists():
        raise SystemExit(f"missing {f}: download the SJR {year} CSV from scimagojr.com/journalrank.php (Download data)")
    rows = parse_sjr_rows(f.read_text(encoding="utf-8-sig"))
    print(f"SJR {year}: {len(rows)} titles from {f.name}")
    return rows


def sjr_index(rows: dict[str, dict]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for rec in rows.values():
        for i in rec["issns"]:
            old = idx.get(i)
            if old is None or QRANK.get(rec["quartile"], 9) < QRANK.get(old["quartile"], 9):
                idx[i] = rec
    return idx


def classify(src: dict | None, idx: dict[str, dict]):
    """-> (class, sjr_record|None)."""
    if src is None:
        return "unknown", None
    t = src.get("type")
    if t == "repository":
        return "repository", None
    if t == "conference":
        return "conference", None
    if t not in ("journal", "book series"):
        return "other", None
    hit = None
    for i in src.get("issn", []):
        rec = idx.get(norm_issn(i))
        if rec and (hit is None or QRANK.get(rec["quartile"], 9) < QRANK.get(hit["quartile"], 9)):
            hit = rec
    if hit and hit["quartile"] in QRANK:
        return hit["quartile"], hit
    return "not_ranked", hit


# ------------------------------------------------------------------ build
CAVEATS = [
    "OpenAlex under-indexes Persian-language journals (and does not index IranDoc theses): Iranian counts are a lower bound for the Persian-language record and cover mostly English-language output.",
    "Topic matching is keyword based (title_and_abstract.search, stemmed): the broad AI/ML bucket includes medical education, EFL and non-education ML; counts are upper bounds of genuine AI-in-education work.",
    "Iran = works with at least one author affiliation in Iran (co-authored works count); Iran is a subset of world.",
    "SJR quartile is defined per subject category; the best quartile across a journal's categories is used (a journal is Q1 if it is Q1 in any category), which inflates Q1 relative to a single-category ranking.",
    "A single SJR edition is applied to all publication years; journal quartiles change over time and journals discontinued or renamed before the edition may show as not_ranked.",
    "Match to SJR is by ISSN only; journals without ISSN or not in Scopus/SJR are not_ranked (not a judgement of quality). Clarivate JCR is paywalled and not used; Iran's ISC ranking is not included.",
    "2026 is a partial year (to the as_of date) and the newest works are not yet fully indexed.",
    "SJR file = the scimagojr.com 'Download data' export saved by hand (the site blocks scripted downloads); SCImago's data, gitignored, not redistributed here.",
]


def build_tables(agg, meta, idx):
    """-> per (bucket, scope): class -> year -> n, and per-journal rows."""
    byyear, journals = {}, {}
    for b in agg:
        for s in agg[b]:
            cy = {c: defaultdict(int) for c in CLASSES}
            jr = {}
            for sid, ys in agg[b][s].items():
                src = None if sid == "unknown" else meta.get(sid)
                cls, rec = classify(src, idx)
                for y, n in ys.items():
                    cy[cls][y] += n
                jr[sid] = {
                    "source_id": sid,
                    "name": (src or {}).get("name") or ("(no primary source)" if sid == "unknown" else sid),
                    "type": (src or {}).get("type"),
                    "class": cls,
                    "sjr": None if not rec or rec["sjr"] != rec["sjr"] else round(rec["sjr"], 3),
                    "h_index": rec["h_index"] if rec else None,
                    "issn": next(iter((src or {}).get("issn") or []), None),
                    "works": sum(ys.values()),
                    "by_year": {str(y): ys[y] for y in sorted(ys)},
                }
            byyear[(b, s)] = cy
            journals[(b, s)] = jr
    return byyear, journals


def top_journals(jr: dict, k: int = 15):
    rows = [r for r in jr.values() if r["source_id"] != "unknown" and r["type"] in ("journal", "book series", "conference")]
    rows.sort(key=lambda r: (-r["works"], r["name"]))
    return rows[:k]


def build(agg, meta, sjr_rows, years=YEARS, out_dir=RES, site_dir=SITE, as_of=AS_OF, write=True):
    idx = sjr_index(sjr_rows)
    byyear, journals = build_tables(agg, meta, idx)
    out = {
        "meta": {
            "as_of": as_of.isoformat(),
            "years": [years[0], years[-1]],
            "partial_year": f"{years[-1]} to {as_of.isoformat()}",
            "sources": {
                "works": "OpenAlex /works group_by primary_location.source.id (title_and_abstract.search; leaf date windows, exact)",
                "journal_rank": f"SCImago SJR {SJR_YEAR} (scimagojr_{SJR_YEAR}.csv, manual download from scimagojr.com; best quartile across subject categories; one edition applied to all publication years)",
                "not_used": "Clarivate JCR (paywalled); Iran ISC journal ranking (not included)",
            },
            "classes": CLASSES,
            "class_notes": {
                "not_ranked": "OpenAlex journal/book series with no SJR match (by ISSN)",
                "conference": "OpenAlex source type conference",
                "repository": "OpenAlex source type repository (arXiv, SSRN, ResearchGate, Zenodo ...)",
                "other": "ebook platform, metadata, other",
                "unknown": "work without a primary source",
            },
            "queries": {b: v["search"] for b, v in BUCKETS.items()},
            "scopes": {
                "iran": "authorships.institutions.country_code:IR (>= 1 Iranian affiliation)",
                "world": "no country filter (includes Iran)",
            },
            "caveats": CAVEATS,
        },
        "buckets": {},
    }
    rows_year, rows_j = [], []
    for b in BUCKETS:
        d = {"label": BUCKETS[b]["label"], "years": years}
        for s in ("iran", "world"):
            cy = byyear[(b, s)]
            d[s] = {c: [cy[c].get(y, 0) for y in years] for c in CLASSES}
            d[s]["total"] = [sum(cy[c].get(y, 0) for c in CLASSES) for y in years]
            for c in CLASSES:
                for y in years:
                    rows_year.append([b, s, y, c, cy[c].get(y, 0)])
        d["iran_share_pct"] = {
            c: [round(100 * i / w, 2) if w else None for i, w in zip(d["iran"][c], d["world"][c], strict=True)]
            for c in CLASSES + ["total"]
        }
        d["totals"] = {s: {c: sum(d[s][c]) for c in CLASSES + ["total"]} for s in ("iran", "world")}
        d["totals"]["iran_share_pct"] = {
            c: round(100 * d["totals"]["iran"][c] / d["totals"]["world"][c], 2) if d["totals"]["world"][c] else None
            for c in CLASSES + ["total"]
        }
        for s in ("iran", "world"):
            d[f"top_journals_{s}"] = top_journals(journals[(b, s)])
            for r in journals[(b, s)].values():
                rows_j.append([b, s, r["source_id"], r["name"], r["type"], r["class"], r["sjr"], r["h_index"], r["issn"], r["works"]])
        out["buckets"][b] = d
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        site_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "quartiles_by_year.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["bucket", "scope", "year", "class", "works"])
            w.writerows(rows_year)
        rows_j.sort(key=lambda r: (r[0], r[1], -r[9]))
        with (out_dir / "quartiles_journals.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["bucket", "scope", "source_id", "name", "type", "class", "sjr", "h_index", "issn", "works"])
            w.writerows(rows_j)
        (site_dir / "research_quartiles.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


# ------------------------------------------------------------------ self-test
def selftest(tmp: Path | None = None) -> None:
    txt = (
        "Rank;Sourceid;Title;Type;Issn;SJR;SJR Quartile;H index;Categories\n"
        '1;1;"Good Journal";journal;"15424863, 0007-9235";1,5;Q3;50;"A (Q3); B (Q1)"\n'
        '2;2;"No Quartile";journal;"11112222";0,1;-;3;"A (-)"\n'
    )
    rows = parse_sjr_rows(txt)
    assert rows["1"]["quartile"] == "Q1" and rows["1"]["sjr"] == 1.5 and "00079235" in rows["1"]["issns"]
    assert rows["2"]["quartile"] == ""
    idx = sjr_index(rows)
    assert classify({"type": "journal", "issn": ["1542-4863"]}, idx)[0] == "Q1"
    assert classify({"type": "journal", "issn": ["1111-2222"]}, idx)[0] == "not_ranked"
    assert classify({"type": "journal", "issn": ["9999-9999"]}, idx)[0] == "not_ranked"
    assert classify({"type": "repository", "issn": []}, idx)[0] == "repository"
    assert classify({"type": "conference", "issn": []}, idx)[0] == "conference"
    assert classify({"type": "ebook platform", "issn": []}, idx)[0] == "other"
    assert classify(None, idx)[0] == "unknown"

    # window splitting: fake getter that truncates (200 groups) whenever the window spans > 40 days
    def fake(bucket, scope, d0, d1, extra=""):
        days = (d1 - d0).days + 1
        if days > 40:
            return [[f"S{i}", 1] for i in range(200)], 999
        return [["S1", days], ["unknown", 1]], days + 1

    log: list = []
    got = list(windows("ai", "world", date(2024, 1, 1), date(2024, 12, 31), fake, log))
    assert got[0][0] == date(2024, 1, 1) and got[-1][1] == date(2024, 12, 31)
    for (_, b, _), (c, _, _) in zip(got, got[1:], strict=False):
        assert c == b + timedelta(days=1)  # contiguous, no gaps, no overlaps
    assert sum(g[2][0][1] for g in got) == 366 and not log

    # a truncated single day is partitioned by filter pairs (here: type:article vs type:!article)
    def fake_day(bucket, scope, d0, d1, extra=""):
        if not extra:
            return [[f"S{i}", 1] for i in range(200)], 300
        n = 100 if "type:article" in extra else 200
        return [[f"{'A' if 'type:article' in extra else 'B'}{i}", 1] for i in range(n - 1)], n

    log2: list = []
    (w,) = list(windows("ai", "world", date(2024, 1, 1), date(2024, 1, 1), fake_day, log2))
    assert len(w[2]) == 99 + 199

    # end-to-end build on a tiny fixture
    agg = {b: {s: defaultdict(lambda: defaultdict(int)) for s in SCOPES} for b in BUCKETS}
    agg["ai"]["world"]["S1"][2024] = 8
    agg["ai"]["world"]["S2"][2024] = 4
    agg["ai"]["world"]["unknown"][2024] = 2
    agg["ai"]["iran"]["S1"][2024] = 2
    agg["ai"]["iran"]["S2"][2024] = 1
    meta = {
        "S1": {"name": "Good Journal", "type": "journal", "issn": ["1542-4863"]},
        "S2": {"name": "arXiv", "type": "repository", "issn": []},
    }
    import tempfile

    tmp = tmp or Path(tempfile.mkdtemp())
    out = build(agg, meta, rows, years=[2024], out_dir=tmp, site_dir=tmp, write=True)
    a = out["buckets"]["ai"]
    assert a["world"]["Q1"] == [8] and a["iran"]["Q1"] == [2] and a["iran_share_pct"]["Q1"] == [25.0]
    assert a["world"]["repository"] == [4] and a["world"]["unknown"] == [2] and a["world"]["total"] == [14]
    assert a["top_journals_iran"][0]["name"] == "Good Journal" and a["top_journals_iran"][0]["sjr"] == 1.5
    assert json.loads((tmp / "research_quartiles.json").read_text())["meta"]["caveats"]
    print("selftest ok")


def main(argv: list[str]) -> None:
    if "--test" in argv:
        selftest()
        return
    cmd = argv[0] if argv else "all"
    if cmd in ("sjr", "all"):
        fetch_sjr()
    if cmd in ("fetch", "all"):
        if not api_key():
            print("note: OPENALEX_API_KEY not set; using the public pool (small budget)")
        log: list = []
        agg = collect(log=log)
        ids = sorted({sid for b in agg for s in agg[b] for sid in agg[b][s]})
        fetch_sources(ids)
        (QCACHE / "_agg.json").write_text(json.dumps({b: {s: agg[b][s] for s in agg[b]} for b in agg}))
        for x in log:
            print("WARN", *x)
    if cmd in ("build", "all"):
        raw = json.loads((QCACHE / "_agg.json").read_text())
        agg = {b: {s: {sid: {int(y): n for y, n in ys.items()} for sid, ys in raw[b][s].items()} for s in raw[b]} for b in raw}
        meta = json.loads((QCACHE / "_sources.json").read_text())
        out = build(agg, meta, fetch_sjr())
        for b, d in out["buckets"].items():
            t = d["totals"]
            print(b, "iran", t["iran"]["total"], "world", t["world"]["total"], "Q1 iran", t["iran"]["Q1"],
                  "world", t["world"]["Q1"], "share", t["iran_share_pct"]["Q1"])


if __name__ == "__main__":
    main(sys.argv[1:])
