import zipfile
from pathlib import Path

import pytest

from etl.extract.docx_tables import read_blocks
from etl.extract.pdf_text import _parse_line
from etl.tables import Table, blocks_to_rawtables

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _cell(t, span=1, vm=None):
    pr = (f'<w:gridSpan w:val="{span}"/>' if span > 1 else "") + (f'<w:vMerge w:val="{vm}"/>' if vm else "")
    return f"<w:tc><w:tcPr>{pr}</w:tcPr><w:p><w:r><w:t>{t}</w:t></w:r></w:p></w:tc>"


def test_docx_grid_sliver_columns(tmp_path: Path):
    """Header and body disagree on gridSpan around a 22-twip sliver column (1395 yearbook case)."""
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in (3000, 1000, 1000, 1000, 22, 1000))
    hdr1 = _cell("استان", vm="restart") + _cell("دانش آموز", 3) + _cell("معلم", 2, "restart")
    hdr2 = _cell("", vm="continue") + _cell("جمع") + _cell("پسر") + _cell("دختر", 2) + _cell("", vm="continue")
    body = _cell("تهران") + _cell("10") + _cell("6") + _cell("4") + _cell("1", 2)
    xml = (f'<w:document {W}><w:body><w:p><w:r><w:t>10-17- دانش آموزان دوره ابتدايي</w:t></w:r></w:p>'
           f"<w:tbl><w:tblGrid>{grid}</w:tblGrid><w:tr>{hdr1}</w:tr><w:tr>{hdr2}</w:tr><w:tr>{body}</w:tr></w:tbl>"
           "</w:body></w:document>")
    p = tmp_path / "t.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("word/document.xml", xml)
    blocks = read_blocks(p)
    tbl = [b for b in blocks if isinstance(b, Table)][0]
    assert tbl.rows[-1] == ["تهران", "10", "6", "4", "1"]
    rt = blocks_to_rawtables(blocks, yearbook_sh=1398, source_file="t", source_format="docx")[0]
    assert rt.col_headers == ["دانش آموز > جمع", "دانش آموز > پسر", "دانش آموز > دختر", "معلم"]
    assert rt.rows == [("تهران", [10.0, 6.0, 4.0, 1.0])]


def test_pdf_line_visual_order():
    line = "   278335   64646   65315  267516  2818290  3009561  5827851 ...................... 1385-1386"
    label, vals = _parse_line(line)
    assert label == "1385-1386"
    assert vals == [5827851, 3009561, 2818290, 267516, 65315, 64646, 278335]  # back to logical order


def test_pdf_line_footnote_marker():
    label, vals = _parse_line("  1094049   816905  1910954 ............ )1(1385-1386")
    assert label.startswith("1385-1386") and vals == [1910954, 816905, 1094049]


SRC = Path("/Volumes/MigMig/Programming/Datasets/Statistical Yearbook/Keshvari/1398/salname_keshvar_1398")


@pytest.mark.skipif(not SRC.exists(), reason="source yearbooks not mounted")
def test_1398_primary_real_file():
    from etl.facts import table_to_records

    f = next(SRC.glob("*17*.docx"))
    rts = blocks_to_rawtables(read_blocks(f), yearbook_sh=1398, source_file="x", source_format="docx")
    rt = next(r for r in rts if r.table_no == "10-17")
    _, k12, he = table_to_records(rt)
    assert not he
    thr = {r["metric"]: r["value"] for r in k12 if r["province_code"] == "THR" and r["gender"] == "total"}
    assert thr["students"] == 1163731 and thr["teachers"] == 23381  # as printed in table 10-17
