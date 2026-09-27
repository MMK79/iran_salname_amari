"""RawTable -> tidy long records (raw cells + K-12 facts + higher-ed facts)."""

from __future__ import annotations

from etl.normalize import norm, sh_to_gregorian_start
from etl.tables import RawTable, table_year
from etl.terms import (
    DIMS_HE,
    DIMS_K12,
    classify_domain,
    dims_of_header,
    dims_of_row_label,
    dims_of_text,
)

# dims that a title may supply as a default
_TITLE_DIMS_K12 = ["metric", "level", "programme", "branch", "sector", "area"]
_TITLE_DIMS_HE = ["metric", "university_type", "degree_level", "area"]


def system_for(year_sh: int) -> str:
    """School system in force in that academic year (Mehr start)."""
    return "old_5-3-4" if year_sh <= 1390 else "new_6-3-3"


def table_to_records(rt: RawTable) -> tuple[list[dict], list[dict], list[dict]]:
    raw, k12, he = [], [], []
    domain = classify_domain(rt.title)
    ty = table_year(rt)
    dims = DIMS_K12 if domain in ("k12",) else DIMS_HE
    tdims = dims_of_text(rt.title, domain, _TITLE_DIMS_K12 if domain == "k12" else _TITLE_DIMS_HE)
    col_dims = [dims_of_header(h, domain, dims) for h in rt.col_headers]
    base = {
        "yearbook_sh": rt.yearbook_sh,
        "source_file": rt.source_file,
        "source_format": rt.source_format,
        "source_table": rt.source_table,
        "table_title": rt.title,
        "domain": domain,
        "header_source": rt.header_source,
    }
    for ri, (label, vals) in enumerate(rt.rows):
        rdims = dims_of_row_label(label, domain, dims) if label else {}
        for ci, v in enumerate(vals):
            if v is None:
                continue
            cdims = col_dims[ci] if ci < len(col_dims) else {}
            header = rt.col_headers[ci] if ci < len(rt.col_headers) else ""
            raw.append({**base, "row_index": ri, "row_label": label, "col_index": ci, "col_header": header, "value": v})
            if domain not in ("k12", "he"):
                continue
            d = {**tdims, **rdims, **{k: v for k, v in cdims.items() if k != "unmatched"}}
            if "metric" not in d:
                continue
            year = int(d["year"][0]) if "year" in d else ty
            prov = d.get("province", ("IRN", ""))[0]
            known_row = bool(rdims) or not label
            rec = {
                **base,
                "year_sh": year,
                "year_gregorian": sh_to_gregorian_start(year),
                "province_code": prov,
                "province_label": rdims.get("province", ("", ""))[1] if "province" in rdims and "year" not in rdims else "",
                "gender": d.get("gender", ("total", ""))[0],
                "area": d.get("area", ("total", ""))[0],
                "metric": d["metric"][0],
                "value": v,
                "row_label": label,
                "col_header": header,
                "row_category": None if known_row else norm(label),
                "col_category": cdims["unmatched"][0] if "unmatched" in cdims else None,
            }
            if domain == "k12":
                lvl = d.get("level")
                rec.update(
                    level=lvl[0] if lvl else "all_levels",
                    level_source=lvl[1] if lvl else "(none: all levels)",
                    school_system=system_for(year),
                    programme=d.get("programme", ("regular", ""))[0],
                    branch=d.get("branch", ("all", ""))[0],
                    sector=d.get("sector", ("all", ""))[0],
                )
                k12.append(rec)
            else:
                deg = d.get("degree_level")
                ut = d.get("university_type")
                rec.update(
                    degree_level=deg[0] if deg else "all",
                    degree_level_source=deg[1] if deg else "",
                    university_type=ut[0] if ut else "all_reported",
                    university_type_source=ut[1] if ut else "",
                    field_group=d.get("field_group", ("all", ""))[0],
                    rank=d.get("rank", ("all", ""))[0],
                )
                he.append(rec)
    return raw, k12, he
