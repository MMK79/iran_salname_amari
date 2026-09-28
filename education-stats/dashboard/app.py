"""Streamlit prototype: Iran education ratios by province, animated over years.

    make dashboard            # or: uv run streamlit run dashboard/app.py
Reads DuckDB (data/out/edu.duckdb) by default, or Postgres when $DATABASE_URL is set.
K-12 and higher education are separate views and are never combined in one chart.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
GEO = json.loads((ROOT / "dashboard" / "data" / "provinces.geojson").read_text())

# reference palette (dataviz skill): sequential blue for the map, categorical slots 1-3 for lines
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
CAT = ["#2a78d6", "#eb6834", "#1baf7a"]
LEVELS = {"primary": "Primary (ابتدایی)", "lower_secondary": "Lower secondary (راهنمایی / متوسطه اول)",
          "upper_secondary": "Upper secondary (متوسطه / متوسطه دوم)"}


@st.cache_data
def query(sql: str) -> pd.DataFrame:
    url = os.environ.get("DATABASE_URL")
    if url:
        import psycopg

        with psycopg.connect(url) as c:
            return pd.read_sql(sql, c)
    import duckdb

    with duckdb.connect(str(ROOT / "data" / "out" / "edu.duckdb"), read_only=True) as c:
        return c.sql(sql).df()


st.set_page_config(page_title="Iran education ratios", layout="wide")
st.title("Students per teacher and per academic staff member, by province")
st.caption("Source: Statistical Centre of Iran, statistical yearbooks (education chapter). "
           "Years are academic years starting in Mehr of the Solar Hijri year shown. "
           "Map: geoBoundaries IRN ADM1 (ODbL 1.0, © OpenStreetMap contributors).")

prov = query("select code, name_en, name_fa from provinces where not is_historic and code <> 'IRN'")
domain = st.radio("Level of education", ["K-12 (آموزش و پرورش)", "Higher education (آموزش عالی)"],
                  horizontal=True)

if domain.startswith("K-12"):
    level = st.selectbox("School level", list(LEVELS), format_func=LEVELS.get)
    df = query("""select year_sh, year_gregorian, province_code, level, students, teachers_used,
                         students_per_teacher, teacher_definition, provenance
                  from v_k12_students_per_teacher where year_sh >= 1380""")
    m = df[(df.level == level) & (df.province_code != "IRN")].dropna(subset=["students_per_teacher"])
    value, label = "students_per_teacher", "Students per teacher"
    st.info("Teachers = «معلم» from 1394-95; before that the yearbooks report «کارکنان آموزشی» "
            "(educational staff), used here as a proxy - there is a definitional break at 1394.")
else:
    df = query("""select year_sh, year_gregorian, province_code, university_type, students, academic_staff,
                         students_per_staff, students_provenance as provenance
                  from v_he_students_per_staff where university_type = 'all_reported' and year_sh >= 1393""")
    m = df[df.province_code != "IRN"].dropna(subset=["students_per_staff"])
    value, label = "students_per_staff", "Students per full-time academic staff member"
    st.info("From 1393-94 the tables include Islamic Azad University and count full-time academic staff "
            "only. Years whose province table failed validation (1399, 1400, 1402 staff) are left blank.")

# undivided Khorasan (until 1382): paint its ratio on all three of today's Khorasan provinces
kho = m[m.province_code == "KHO"]
m = pd.concat([m[m.province_code != "KHO"]] + [kho.assign(province_code=c) for c in ("KHR", "KHS", "KHJ")])
m = m.merge(prov, left_on="province_code", right_on="code").sort_values("year_sh")
m.loc[m.year_sh.isin(kho.year_sh) & m.province_code.isin(["KHR", "KHS", "KHJ"]), "name_en"] = "Khorasan (undivided)"
if m.empty:
    st.warning("No data for this selection.")
    st.stop()
lo, hi = float(m[value].quantile(0.02)), float(m[value].quantile(0.98))
fig = px.choropleth(
    m, geojson=GEO, locations="province_code", featureidkey="properties.code", color=value,
    animation_frame="year_sh", hover_name="name_en",
    hover_data={"name_fa": True, value: ":.1f", "students": ":,.0f", "province_code": False, "year_sh": False},
    color_continuous_scale=SEQ_BLUE, range_color=(lo, hi), labels={value: label, "year_sh": "Year (SH)"},
)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(height=560, margin=dict(l=0, r=0, t=10, b=0), coloraxis_colorbar=dict(title=label))
sel = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="map")

clicked = None
try:
    pts = sel["selection"]["points"] if sel else []
    clicked = pts[0].get("location") if pts else None
except (KeyError, TypeError, IndexError):
    clicked = None
codes = prov.sort_values("name_en")
default = list(codes.code).index(clicked) if clicked in list(codes.code) else list(codes.code).index("THR")
pc = st.selectbox("Province (or click the map)", list(codes.code), index=default,
                  format_func=lambda c: f"{codes.set_index('code').loc[c, 'name_en']} - "
                                        f"{codes.set_index('code').loc[c, 'name_fa']}")

c1, c2 = st.columns(2)
k = query("""select year_sh, province_code, level, students_per_teacher, teacher_definition, provenance
             from v_k12_students_per_teacher
             where level in ('primary','lower_secondary','upper_secondary') and year_sh >= 1380""")
k = k[k.province_code.isin([pc, "IRN"])].dropna(subset=["students_per_teacher"])
k["series"] = k.level.map(LEVELS) + k.province_code.map(lambda c: "" if c == pc else " - national")
f1 = px.line(k[k.province_code == pc], x="year_sh", y="students_per_teacher", color="level", markers=True,
             color_discrete_sequence=CAT, category_orders={"level": list(LEVELS)},
             labels={"students_per_teacher": "Students per teacher", "year_sh": "Year (SH)", "level": "Level"},
             hover_data={"teacher_definition": True, "provenance": True})
f1.update_traces(line=dict(width=2), marker=dict(size=8))
f1.update_layout(title="K-12: students per teacher", hovermode="x unified", height=420)
c1.plotly_chart(f1, use_container_width=True)

h = query("""select year_sh, province_code, university_type, students_per_staff, students, academic_staff,
                    students_provenance as provenance
             from v_he_students_per_staff where university_type = 'all_reported' and year_sh >= 1393""")
h = h[h.province_code.isin([pc, "IRN"])].copy()
h["where"] = h.province_code.map(lambda c: "Selected province" if c == pc else "Iran (national)")
f2 = px.line(h, x="year_sh", y="students_per_staff", color="where", markers=True, color_discrete_sequence=CAT[:2],
             labels={"students_per_staff": "Students per academic staff", "year_sh": "Year (SH)", "where": ""},
             hover_data={"students": ":,.0f", "academic_staff": ":,.0f", "provenance": True})
f2.update_traces(line=dict(width=2), marker=dict(size=8))
f2.update_layout(title="Higher education: students per full-time academic staff (incl. Azad)",
                 hovermode="x unified", height=420)
c2.plotly_chart(f2, use_container_width=True)

with st.expander("Data table and provenance"):
    st.dataframe(pd.concat([k.assign(domain="k12"), h.assign(domain="he")], ignore_index=True),
                 use_container_width=True)
