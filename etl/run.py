"""ETL entry point.

    uv run python -m etl.run extract [--years 1388-1402]   # parse -> data/out/*.parquet
    uv run python -m etl.run load    [--pg URL | --duckdb]  # parquet -> Postgres (or DuckDB fallback)
    uv run python -m etl.run validate                       # checks -> data/out/validation.parquet
    uv run python -m etl.run mappings                       # regenerate docs/mappings.md
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from etl.discover import Unit, all_years, education_chapter, units_for_year
from etl.extract import docx_tables, html_tables
from etl.facts import table_to_records
from etl.tables import RawTable, blocks_to_rawtables, table_year
from etl.terms import classify_domain

OUT = Path(__file__).resolve().parent.parent / "data" / "out"


def parse_years(spec: str | None) -> list[int]:
    ys = all_years()
    if not spec:
        return ys
    sel: set[int] = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            sel |= set(range(int(a), int(b) + 1))
        else:
            sel.add(int(part))
    return [y for y in ys if y in sel]


def rawtables_for_unit(u: Unit) -> list[RawTable]:
    rts: list[RawTable] = []
    if u.kind in ("docx_chapter", "doc_converted_chapter", "doc_converted_book"):
        blocks = docx_tables.read_blocks(u.paths[0])
        fmt = "docx" if u.kind == "docx_chapter" else "doc"
        rts = blocks_to_rawtables(blocks, yearbook_sh=u.year, source_file=u.rel(u.source_paths[0]), source_format=fmt)
        if u.kind == "doc_converted_book":
            ch = education_chapter([rt.title for rt in rts])
            if ch:
                rts = [rt for rt in rts if rt.table_no.endswith(f"-{ch}")]
            else:
                rts = education_segments(rts)
    elif u.kind == "html_grid":
        for p in u.paths:
            blocks = html_tables.read_blocks(p)
            rts += blocks_to_rawtables(blocks, yearbook_sh=u.year, source_file=u.rel(p), source_format="html",
                                       default_title=p.stem)
    elif u.kind in ("pdf_chapter", "pdf_book", "pdf_tables"):
        from etl.extract import pdf_text

        rts = pdf_text.rawtables(u)
    elif u.kind == "html_text":
        from etl.extract import plaintext

        rts = plaintext.rawtables(u)
    return rts


def education_segments(rts: list[RawTable]) -> list[RawTable]:
    """Old books number tables per chapter without the chapter ("7- ..."). Split the book
    where the numbering restarts and keep the segment(s) that are mostly K-12/HE tables."""
    segs: list[list[RawTable]] = []
    last_no = 10**6
    for rt in rts:
        try:
            no = int(rt.table_no.split("-")[0]) if rt.table_no else None
        except ValueError:
            no = None
        if no is not None and no < last_no and rt.part == 0 and (no <= 2 or last_no - no > 5):
            segs.append([])
        if not segs:
            segs.append([])
        segs[-1].append(rt)
        if no is not None:
            last_no = no
    keep: list[RawTable] = []
    for si, seg in enumerate(segs):
        titles = {rt.title for rt in seg}
        edu = sum(1 for t in titles if classify_domain(t) in ("k12", "he", "teacher_training"))
        if edu >= 3 and edu / max(len(titles), 1) >= 0.4:
            for rt in seg:
                rt.table_no = f"{rt.table_no}-s{si}"
            keep += seg
    return keep


def table_row(rt: RawTable, n_k12: int, n_he: int) -> dict:
    from etl.normalize import parse_academic_year
    from etl.provinces import match_province

    labels = [lbl for lbl, _ in rt.rows]
    years = sorted({y for y in (parse_academic_year(x) for x in labels) if y})
    provs = {p for p in (match_province(x) for x in labels) if p and p != "IRN"}
    geo = "province" if len(provs) >= 10 else ("national" if years or not provs else "some-provinces")
    return {
        "yearbook_sh": rt.yearbook_sh,
        "source_file": rt.source_file,
        "source_format": rt.source_format,
        "source_table": rt.source_table,
        "table_no": rt.table_no,
        "part": rt.part,
        "title": rt.title,
        "domain": classify_domain(rt.title),
        "table_year_sh": table_year(rt),
        "n_rows": len(rt.rows),
        "n_cols": len(rt.col_headers),
        "col_headers": " || ".join(rt.col_headers),
        "row_years": ",".join(map(str, years)),
        "n_provinces": len(provs),
        "geo": geo,
        "notes": " ¶ ".join(rt.notes),
        "header_source": rt.header_source,
        "n_k12_facts": n_k12,
        "n_he_facts": n_he,
    }


def cmd_extract(args) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    years = parse_years(args.years)
    R, K, H, T, U = [], [], [], [], []
    for y in years:
        for u in units_for_year(y):
            t0 = time.time()
            try:
                rts = rawtables_for_unit(u)
            except Exception as e:  # keep going; record the failure in the unit log
                U.append({"yearbook_sh": y, "kind": u.kind, "n_files": len(u.paths), "n_tables": 0, "error": repr(e)})
                print(f"{y} {u.kind}: ERROR {e!r}", file=sys.stderr)
                continue
            nk = nh = 0
            seen_ids: dict[tuple[str, str], int] = {}
            for rt in rts:
                # keep (source_file, source_table) unique: chart captions / repeated numbers in PDFs
                k = (rt.source_file, rt.source_table)
                if k in seen_ids:
                    seen_ids[k] += 1
                    rt.table_no = f"{rt.table_no}.dup{seen_ids[k]}"
                else:
                    seen_ids[k] = 0
                r, k, h = table_to_records(rt)
                R += r
                K += k
                H += h
                nk += len(k)
                nh += len(h)
                T.append(table_row(rt, len(k), len(h)))
            U.append({"yearbook_sh": y, "kind": u.kind, "n_files": len(u.paths), "n_tables": len(rts), "error": None,
                      "n_k12": nk, "n_he": nh,
                      "source": ";".join(sorted({u.rel(p) for p in u.source_paths}))[:2000]})
            print(f"{y} {u.kind:22s} tables={len(rts):4d} k12={nk:6d} he={nh:6d} ({time.time() - t0:.1f}s)")
    suffix = f"_{args.tag}" if args.tag else ""
    pd.DataFrame(R).to_parquet(OUT / f"raw_cells{suffix}.parquet", index=False)
    pd.DataFrame(K).to_parquet(OUT / f"k12{suffix}.parquet", index=False)
    pd.DataFrame(H).to_parquet(OUT / f"he{suffix}.parquet", index=False)
    pd.DataFrame(T).to_parquet(OUT / f"tables{suffix}.parquet", index=False)
    pd.DataFrame(U).to_parquet(OUT / f"units{suffix}.parquet", index=False)
    print(f"raw={len(R)} k12={len(K)} he={len(H)} tables={len(T)} -> {OUT}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="etl")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--years")
    e.add_argument("--tag", default="")
    lo = sub.add_parser("load")
    lo.add_argument("--pg", default=None)
    lo.add_argument("--duckdb", default=None)
    sub.add_parser("validate")
    sub.add_parser("mappings")
    args = ap.parse_args(argv)
    if args.cmd == "extract":
        cmd_extract(args)
    elif args.cmd == "load":
        from etl.load import load

        load(pg=args.pg, duck=args.duckdb)
    elif args.cmd == "validate":
        from etl.validate import run

        run()
    elif args.cmd == "mappings":
        from etl.docs import write_mappings

        write_mappings()


if __name__ == "__main__":
    main()
