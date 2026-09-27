"""The explicit, documented mapping from source wording to normalised dimensions.

HARD RULE: K-12 and higher education are never mixed. Every rule is scoped to a
domain (`k12`, `he` or `any`), and a table's domain is decided once, from its title,
by `classify_domain`. The source wording is always kept alongside (level_source,
row_label, col_header); the normalised value only comes from a rule in `RULES`.

Rules are matched against `norm()`-ed text (Arabic/Persian letter variants unified,
ZWNJ -> space). `exact` rules must equal a whole header part or label; `contains`
rules match a substring. Within one dimension the first matching rule wins, so more
specific wording is listed first (e.g. "کارشناسی ارشد" before "کارشناسی").

`docs/mappings.md` is generated from this table (`uv run python -m etl.run mappings`).
"""

from __future__ import annotations

from dataclasses import dataclass

from etl.normalize import norm, parse_academic_year
from etl.provinces import match_province


@dataclass(frozen=True)
class Rule:
    dim: str
    value: str
    pattern: str
    how: str = "contains"  # contains | exact | startswith
    domain: str = "any"  # k12 | he | any
    note: str = ""

    @property
    def key(self) -> str:
        return norm(self.pattern)


R = Rule
RULES: list[Rule] = [
    # ---------------- gender (exact whole-part matches only: "زن" is inside "زنجان")
    R("gender", "total", "جمع", "exact"), R("gender", "total", "مرد و زن", "exact"),
    R("gender", "total", "دختر و پسر", "exact"), R("gender", "total", "پسر و دختر", "exact"),
    R("gender", "total", "کل", "exact"), R("gender", "total", "جمع کل", "exact"),
    R("gender", "male", "مرد", "exact"), R("gender", "male", "پسر", "exact"),
    R("gender", "male", "مردان", "exact"), R("gender", "male", "پسران", "exact"),
    R("gender", "female", "زن", "exact"), R("gender", "female", "دختر", "exact"),
    R("gender", "female", "زنان", "exact"), R("gender", "female", "دختران", "exact"),
    # ---------------- area
    R("area", "urban", "نقاط شهری", "exact"), R("area", "urban", "شهری", "exact"),
    R("area", "rural", "نقاط روستایی", "exact"), R("area", "rural", "روستایی", "exact"),
    R("area", "nomadic", "عشایری", "exact"),
    # ---------------- sector (public vs non-public schools)
    R("sector", "public", "دولتی", "exact", "k12"),
    R("sector", "nonpublic", "غیر دولتی", "exact", "k12"), R("sector", "nonpublic", "غیردولتی", "exact", "k12"),
    R("sector", "nonpublic", "غیر انتفاعی", "exact", "k12"), R("sector", "nonpublic", "غیرانتفاعی", "exact", "k12"),
    # ---------------- K-12 level (stage). Source wording is kept in level_source.
    R("level", "pre_university", "پیش دانشگاهی", domain="k12"),
    R("level", "preschool", "پیش دبستانی", domain="k12"), R("level", "preschool", "آمادگی", domain="k12"),
    R("level", "preschool", "کودکستان", domain="k12"),
    R("level", "lower_secondary", "دوره اول متوسطه", domain="k12", note="new 6-3-3 system (from 1391-92): grades 7-9"),
    R("level", "lower_secondary", "متوسطه اول", domain="k12", note="new 6-3-3 system: grades 7-9"),
    R("level", "upper_secondary", "دوره دوم متوسطه", domain="k12", note="new system: grades 10-12"),
    R("level", "lower_secondary", "متوسطه دوره اول", domain="k12", note="1393-94 yearbooks' word order"),
    R("level", "upper_secondary", "متوسطه دوره دوم", domain="k12", note="1393-94 yearbooks' word order"),
    R("level", "upper_secondary", "متوسطه دوم", domain="k12", note="new system: grades 10-12"),
    R("level", "lower_secondary", "راهنمایی", domain="k12", note="old 5-3-4 system: guidance school, grades 6-8"),
    R("level", "lower_secondary", "عمومی شبانه", domain="k12", note="evening guidance (1370s)"),
    R("level", "primary", "ابتدایی", domain="k12", note="5 grades until 1390-91, 6 grades from 1391-92"),
    R("level", "primary", "دبستان", domain="k12"),
    R("level", "upper_secondary", "متوسطه", domain="k12", note="old system high school (3 grades + pre-university)"),
    R("level", "upper_secondary", "دبیرستان", domain="k12"), R("level", "upper_secondary", "هنرستان", domain="k12"),
    R("level", "upper_secondary", "کاردانش", domain="k12"),
    R("level", "upper_secondary", "آموزش فنی", domain="k12"), R("level", "upper_secondary", "آموزش حرفه ای", domain="k12"),
    R("level", "upper_secondary", "تکمیلی شبانه", domain="k12"),
    R("level", "all_levels", "کلیه دوره", domain="k12"), R("level", "all_levels", "دوره های تحصیلی", domain="k12"),
    R("level", "all_levels", "دوره های مختلف", domain="k12"),
    # programme: regular day school vs adult/special (kept apart from level on purpose)
    R("programme", "special_needs", "استثنایی", domain="k12"),
    R("programme", "adult", "بزرگسال", domain="k12"), R("programme", "adult", "شبانه", domain="k12"),
    R("programme", "adult", "متفرقه", domain="k12"),
    # branch of upper secondary
    R("branch", "theoretical", "نظری", domain="k12"), R("branch", "theoretical", "متوسطه عمومی", domain="k12"),
    R("branch", "technical_vocational", "فنی و حرفه ای", domain="k12"), R("branch", "technical", "آموزش فنی", domain="k12"),
    R("branch", "vocational", "آموزش حرفه ای", domain="k12"), R("branch", "kardanesh", "کاردانش", domain="k12"), R("branch", "kardanesh", "کار و دانش", domain="k12"),
    # ---------------- K-12 metrics (header parts are matched bottom-up; first hit wins)
    R("metric", "teachers", "معلم", "exact", "k12"), R("metric", "teachers", "معلمان", "exact", "k12"),
    R("metric", "teachers", "گروه معلم", "exact", "k12"),
    R("metric", "mgmt_quality_staff", "مدیریت و کیفیت بخشی", domain="k12", note="from 1394: non-teacher educational staff"),
    R("metric", "clerical_admin_staff", "دفتری و اداری", "exact", "k12"),
    R("metric", "educational_staff", "آموزشی", "exact", "k12", note="before 1394: 'educational staff' (teachers + principals etc.)"),
    R("metric", "staff_permanent_contract", "رسمی و پیمانی", domain="k12", note="1370s: educational+clerical staff, permanent/contract"),
    R("metric", "staff_hourly", "حق التدریسی", domain="k12", note="1370s: hourly-paid/contract"),
    R("metric", "educational_staff", "کارکنان آموزشی", "exact", "k12"),
    R("metric", "students", "دانش آموز", domain="k12"), R("metric", "students", "نوآموز", domain="k12"),
    R("metric", "students", "کودکان", domain="k12"),
    R("metric", "schools", "آموزشگاه", domain="k12"), R("metric", "schools", "مدرسه", domain="k12"),
    R("metric", "schools", "مدارس", "exact", "k12"),
    R("metric", "classes", "کلاس", domain="k12"),
    R("metric", "graduates", "فارغ التحصیل", domain="k12"), R("metric", "passed", "قبول شد", domain="k12"),
    # K-12 upper-secondary streams (graduates / students by branch tables)
    R("branch", "math_physics", "ریاضی فیزیک", domain="k12"), R("branch", "experimental_sciences", "علوم تجربی", domain="k12"),
    R("branch", "humanities", "علوم انسانی", domain="k12"), R("branch", "islamic_studies", "معارف اسلامی", domain="k12"),
    R("branch", "kardanesh", "کار دانش", domain="k12"),
    # umbrella header cells ("staff", "facilities") carry no dimension of their own
    R("staffgroup", "staff", "کارکنان", domain="any"), R("staffgroup", "facilities", "امکانات", domain="any"),
    R("staffgroup", "faculty_group", "هیات علمی", "exact", "he"),
    # ---------------- higher-ed employment type of academic staff
    R("employment", "fulltime_and_hourly", "تمام وقت و حق التدریس", domain="he"),
    R("employment", "fulltime_and_hourly", "تمام وقت و پاره وقت", domain="he"),
    R("employment", "fulltime", "تمام وقت", domain="he"), R("employment", "hourly", "حق التدریس", domain="he"),
    R("employment", "hourly", "پاره وقت", domain="he"),
    # ---------------- higher-education degree level (specific before generic!)
    R("degree_level", "master", "کارشناسی ارشد", domain="he"), R("degree_level", "master", "فوق لیسانس", domain="he"),
    R("degree_level", "professional_doctorate", "دکترای حرفه ای", domain="he"),
    R("degree_level", "professional_doctorate", "دکتری حرفه ای", domain="he"),
    R("degree_level", "professional_doctorate", "دکترای عمومی", domain="he"),
    R("degree_level", "phd", "دکترای تخصصی", domain="he"), R("degree_level", "phd", "دکتری تخصصی", domain="he"),
    R("degree_level", "phd", "ph.d", domain="he"),
    R("degree_level", "associate", "کاردانی", domain="he"), R("degree_level", "associate", "فوق دیپلم", domain="he"),
    R("degree_level", "bachelor", "کارشناسی", domain="he"), R("degree_level", "bachelor", "لیسانس", domain="he"),
    R("degree_level", "doctorate_unspecified", "دکترا", domain="he", note="older yearbooks do not split professional/PhD"),
    R("degree_level", "doctorate_unspecified", "دکتری", domain="he"),
    # ---------------- university / institution type
    R("university_type", "payame_noor", "پیام نور", domain="he"),
    R("university_type", "azad", "آزاد اسلامی", domain="he"), R("university_type", "azad", "دانشگاه آزاد", domain="he"),
    R("university_type", "applied_science", "علمی کاربردی", domain="he"),
    R("university_type", "applied_science", "علمی و کاربردی", domain="he"),
    R("university_type", "technical_vocational_univ", "فنی و حرفه ای", domain="he"),
    R("university_type", "farhangian_teacher_training", "فرهنگیان", domain="he"),
    R("university_type", "farhangian_teacher_training", "تربیت معلم", domain="he"),
    R("university_type", "public_mohme", "وزارت بهداشت", domain="he", note="medical universities"),
    R("university_type", "public_msrt", "وزارت علوم", domain="he"),
    R("university_type", "public_msrt", "وزارت فرهنگ و آموزش عالی", domain="he"),
    R("university_type", "public_other", "سایر دستگاه", domain="he"),
    R("university_type", "private_nonprofit", "غیر انتفاعی", domain="he"),
    R("university_type", "private_nonprofit", "غیرانتفاعی", domain="he"),
    R("university_type", "public_all", "دولتی", "exact", "he"),
    # ---------------- major field group
    R("field_group", "medical", "پزشکی", "exact", "he"), R("field_group", "medical", "علوم پزشکی", "exact", "he"),
    R("field_group", "humanities", "علوم انسانی", "exact", "he"),
    R("field_group", "basic_sciences", "علوم پایه", "exact", "he"),
    R("field_group", "engineering", "فنی و مهندسی", "exact", "he"), R("field_group", "engineering", "فنی مهندسی", "exact", "he"),
    R("field_group", "agri_vet", "کشاورزی و دامپزشکی", "exact", "he"),
    R("field_group", "agriculture", "کشاورزی", "exact", "he"), R("field_group", "veterinary", "دامپزشکی", "exact", "he"),
    R("field_group", "art", "هنر", "exact", "he"),
    # ---------------- academic rank
    R("rank", "instructor_assistant", "مربی آموزشیار", "exact", "he"),
    R("rank", "professor", "استاد", "exact", "he"), R("rank", "associate_professor", "دانشیار", "exact", "he"),
    R("rank", "assistant_professor", "استادیار", "exact", "he"), R("rank", "instructor", "مربی", "exact", "he"),
    R("rank", "non_faculty", "غیر هیات علمی", domain="he", note="full-time instructors who are not faculty members"),
    # ---------------- higher-ed metric (mostly from the title)
    R("metric", "new_entrants", "ثبت نام شدگان جدید", domain="he"), R("metric", "new_entrants", "پذیرفته شد", domain="he"),
    R("metric", "new_entrants", "پذیرفه شد", domain="he", note="typo in 1353 source"),
    R("metric", "graduates", "دانش آموخت", domain="he"), R("metric", "graduates", "فارغ التحصیل", domain="he"),
    R("metric", "academic_staff", "آموزشگران", domain="he", note="academic staff (faculty + non-faculty instructors); see employment dim"),
    R("metric", "academic_staff", "هیات علمی", domain="he"), R("metric", "academic_staff", "استادان", domain="he"),
    R("metric", "academic_staff", "کادر آموزشی", domain="he"), R("metric", "academic_staff", "کارکنان آموزشی", domain="he"),
    R("metric", "students", "دانشجو", domain="he"),
    R("metric", "institutions", "تعداد دانشگاه", domain="he"), R("metric", "institutions", "مراکز آموزش عالی", "exact", "he"),
]

_BY_DIM: dict[str, list[Rule]] = {}
for _r in RULES:
    _BY_DIM.setdefault(_r.dim, []).append(_r)


def _hit(rule: Rule, text: str) -> bool:
    # compare with spaces removed: the sources split words inconsistently ("متو سطه", "آموزشي‌،دفتري")
    k = rule.key.replace(" ", "")
    text = text.replace(" ", "")
    if rule.how == "exact":
        return text == k
    if rule.how == "startswith":
        return text.startswith(k)
    return k in text


def match(dim: str, text: str, domain: str) -> Rule | None:
    t = norm(text)
    if not t:
        return None
    for r in _BY_DIM.get(dim, []):
        if r.domain in ("any", domain) and _hit(r, t):
            return r
    return None


# ---------------------------------------------------------------- domain of a table
_OTHER = [
    "باسواد", "سواد آموز", "سوادآموز", "نهضت", "سازمان آموزش فنی و حرفه", "مراکز ثابت", "مربیان", "آموزش های برگزار",
    "هزینه", "اعتبار", "درآمد", "خانوار", "خارج از کشور", "آموزشیار", "روستاهای تحت پوشش", "جمعیت", "بودجه",
    "آموزش دیدگان", "کارآموز", "کتابخانه",
]
_HE = ["دانشجو", "آموزش عالی", "دانشگاه", "دانش آموخت", "آموزشگران دانشگاهی", "هیات علمی", "انستیتو"]
_TT = ["تربیت معلم", "دانشسرا"]
_K12 = [
    "دانش آموز", "مدارس", "آموزشگاه", "دبستان", "دبیرستان", "هنرستان", "کودکستان", "معلم", "کلاس", "راهنمایی",
    "ابتدایی", "متوسطه", "PREUNIV", "پیش دبستانی", "استثنایی", "قبول شدگان", "فارغ التحصیلان", "کودکان",
]


def classify_domain(title: str) -> str:
    """'k12' | 'he' | 'teacher_training' | 'other'. Decided from the title only."""
    t = norm(title).replace("پیش دانشگاهی", " PREUNIV ").replace("پیشدانشگاهی", " PREUNIV ")  # K-12, not HE
    t = t.replace(" ", "")  # PDFs drop the ZWNJ ("دانشآموزان"); compare without spaces
    if any(k.replace(" ", "") in t for k in _OTHER):
        return "other"
    if any(k.replace(" ", "") in t for k in _TT) and "دانشگاه" not in t:
        return "teacher_training"
    if any(k.replace(" ", "") in t for k in _HE):
        return "he"
    if any(k.replace(" ", "") in t for k in _K12):
        return "k12"
    return "other"


DIMS_K12 = ["metric", "gender", "level", "programme", "branch", "sector", "area", "staffgroup"]
DIMS_HE = ["metric", "gender", "degree_level", "university_type", "field_group", "rank", "employment", "area", "staffgroup"]


def dims_of_text(text: str, domain: str, dims: list[str]) -> dict[str, tuple[str, str]]:
    """Classify one label. Returns {dim: (normalised_value, matched_source_text)}."""
    out: dict[str, tuple[str, str]] = {}
    for d in dims:
        r = match(d, text, domain)
        if r:
            out[d] = (r.value, text)
    return out


_FILLER = {norm(x).replace(" ", "") for x in ["تعداد", "نفر", "سال تحصیلی", "شرح", "عنوان", "رقم", "درصد"]}


def dims_of_header(header_path: str, domain: str, dims: list[str]) -> dict[str, tuple[str, str]]:
    """Header path 'A > B > C': for each dim the most specific (bottom) part wins.

    Parts that no rule recognises are returned under the pseudo-dim "unmatched" so that
    a column like "پایه دهم > نظری" (grade x branch) is never silently read as a total.
    """
    parts = [p for p in header_path.split(" > ") if p.strip()]
    out: dict[str, tuple[str, str]] = {}
    unmatched: list[str] = []
    for p in reversed(parts):
        y = parse_academic_year(p)
        if y:
            out.setdefault("year", (str(y), p))
            continue
        got = dims_of_text(p, domain, dims)
        if not got and norm(p).replace(" ", "") not in _FILLER:
            unmatched.append(norm(p))
        for d, v in got.items():
            out.setdefault(d, v)
    if unmatched:
        out["unmatched"] = (" | ".join(reversed(unmatched)), header_path)
    return out


def dims_of_row_label(label: str, domain: str, dims: list[str]) -> dict[str, tuple[str, str]]:
    y = parse_academic_year(label)
    if y:
        return {"year": (str(y), label), "province": ("IRN", label)}
    p = match_province(label)
    if p:
        return {"province": (p, label)}
    return dims_of_text(label, domain, dims)
