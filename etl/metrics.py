"""Metric dictionary (loaded into the `metrics` table and rendered in docs/schema.md)."""

METRICS = [
    # domain, metric, name_en, name_fa, unit, definition, comparability
    ("k12", "students", "Students", "دانش‌آموز", "persons",
     "Enrolled pupils of the Ministry of Education (public + non-public schools unless the table says otherwise).",
     "Level boundaries change with the 1391-92 reform (primary 5->6 grades; guidance 3 grades -> lower secondary)."),
    ("k12", "teachers", "Teachers", "معلم", "persons",
     "Teacher group of educational staff (from 1394-95 classification: teacher / management & quality).",
     "From 1394 only. SCI back-fills earlier years in the same column with 'educational staff' (آموزشی)."),
    ("k12", "educational_staff", "Educational staff", "کارکنان آموزشی", "persons",
     "Educational staff (teachers plus principals/assistants) as opposed to clerical & administrative staff.",
     "Up to 1393. Used as the teacher proxy for years before 1394 (flagged teacher_definition)."),
    ("k12", "mgmt_quality_staff", "Management & quality staff", "مدیریت و کیفیت بخشی", "persons",
     "Non-teaching educational staff under the 1394 job classification.", "From 1394."),
    ("k12", "clerical_admin_staff", "Clerical & administrative staff", "کارکنان دفتری و اداری", "persons",
     "Office and administrative staff of schools.", "Up to 1393."),
    ("k12", "staff_permanent_contract", "Staff, permanent/contract", "رسمی و پیمانی", "persons",
     "1370s tables: educational + clerical staff with permanent or contract status.", "1370s only."),
    ("k12", "staff_hourly", "Staff, hourly-paid/contract", "حق‌التدریسی و قراردادی", "persons",
     "1370s tables: hourly-paid staff.", "1370s only."),
    ("k12", "schools", "Schools", "آموزشگاه / مدرسه", "units",
     "Schools (a building used by two levels/shifts is counted once per level).", ""),
    ("k12", "classes", "Classes", "کلاس", "units", "Class sections.", ""),
    ("k12", "graduates", "Graduates", "فارغ‌التحصیلان", "persons", "Upper-secondary graduates (diploma).", ""),
    ("k12", "passed", "Passed (promoted)", "قبول‌شدگان", "persons", "Pupils who passed the grade exams.", ""),
    ("he", "students", "Students enrolled", "دانشجو", "persons",
     "Students enrolled in higher-education institutions.",
     "Coverage differs by year: until 1392 the main tables EXCLUDE Islamic Azad University (separate tables); "
     "from 1393 they include Azad; applied-science university (UAST) excluded in some years (see footnotes)."),
    ("he", "new_entrants", "New entrants", "ثبت‌نام‌شدگان جدید / پذیرفته‌شدگان", "persons",
     "First-year registrations (older yearbooks: admitted applicants).", "Coverage as for students."),
    ("he", "graduates", "Graduates", "دانش‌آموختگان / فارغ‌التحصیلان", "persons",
     "Graduates of higher-education institutions in the academic year.", "Coverage as for students."),
    ("he", "academic_staff", "Academic staff", "آموزشگران / کارکنان آموزشی / اعضای هیئت علمی", "persons",
     "Academic teaching staff; `rank` splits faculty members (professor .. instructor-assistant) from non-faculty "
     "instructors; `employment` says full-time / hourly.",
     "1380s-1392: full-time + part-time/hourly, excluding Azad (and in some years Payame Noor & UAST). "
     "From 1393: full-time only, including Azad. Break in series at 1393."),
    ("he", "institutions", "Institutions", "تعداد دانشگاه / مراکز", "units", "Higher-education institutions.", ""),
]
